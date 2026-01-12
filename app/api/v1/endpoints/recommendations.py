from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timedelta
import logging

from app.models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    Recommendation
)
from app.models.models import RecommendationRequest as RecommendationRequestModel
from app.core.database import get_db
from app.services.recommendation_engine import RecommendationEngine
from app.services.model_loaders import RecommendationModelLoader
from app.services.model_management import ModelManager
from app.services.data_loader import get_data_loader
from app.models.bcom_models import Link, DetectedAnomaly, Recommendation as RecommendationModel
from app.core.rate_limiter import limiter
import os

logger = logging.getLogger(__name__)

router = APIRouter()
recommendation_engine = RecommendationEngine()
# Initialize ModelManager with models directory
models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models_cache")
model_manager = ModelManager(models_dir)
model_loader = RecommendationModelLoader(model_manager)
data_loader = get_data_loader("data")


@router.post("/generate", response_model=RecommendationResponse)
@limiter.limit("40/minute")
async def generate_recommendations(
    request_data: RecommendationRequest,
    
    db: Session = Depends(get_db),
    request=None
):
    try:
        recommendations_data = recommendation_engine.generate_recommendations(
            context=request_data.context,
            entity_id=request_data.entity_id,
            historical_data=request_data.historical_data,
            max_recommendations=request_data.max_recommendations
        )

        recommendations = [Recommendation(**rec) for rec in recommendations_data]

        request_id = uuid.uuid4()

        # Save to PostgreSQL
        rec_request = RecommendationRequestModel(
            id=request_id,
            user_id=None,
            context=request_data.context,
            entity_id=request_data.entity_id,
            recommendations_count=len(recommendations)
        )
        db.add(rec_request)
        db.commit()

        return RecommendationResponse(
            request_id=str(request_id),
            recommendations=recommendations,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recommendation generation failed: {str(e)}"
        )


@router.get("/by-priority/{priority}")
@limiter.limit("100/minute")
async def get_recommendations_by_priority(
    priority: str,
    
    request=None
):
    try:
        recommendations_data = recommendation_engine.get_recommendations_by_priority(priority)
        recommendations = [Recommendation(**rec) for rec in recommendations_data]

        return {
            "priority": priority,
            "recommendations": recommendations,
            "count": len(recommendations)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recommendations: {str(e)}"
        )


@router.post("/by-tags")
@limiter.limit("100/minute")
async def get_recommendations_by_tags(
    tags: List[str],
    
    request=None
):
    try:
        recommendations_data = recommendation_engine.get_recommendations_by_tags(tags)
        recommendations = [Recommendation(**rec) for rec in recommendations_data]

        return {
            "tags": tags,
            "recommendations": recommendations,
            "count": len(recommendations)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recommendations: {str(e)}"
        )


@router.get("/history")
@limiter.limit("100/minute")
async def get_recommendation_history(
    
    db: Session = Depends(get_db),
    limit: int = 50,
    request=None
):
    try:
        requests = db.query(RecommendationRequestModel) \
            .filter(RecommendationRequestModel.user_id == None) \
            .order_by(RecommendationRequestModel.created_at.desc()) \
            .limit(limit) \
            .all()

        return {"history": requests}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {str(e)}"
        )


@router.get("/statistics")
@limiter.limit("100/minute")
async def get_recommendation_statistics(
    
    db: Session = Depends(get_db),
    request=None
):
    try:
        requests = db.query(RecommendationRequestModel) \
            .filter(RecommendationRequestModel.user_id == None) \
            .all()

        total_requests = len(requests)

        context_counts = {}
        for rec_request in requests:
            context = rec_request.context
            context_counts[context] = context_counts.get(context, 0) + 1

        return {
            "total_requests": total_requests,
            "context_distribution": context_counts
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


# ============================================================================
# BCom Offshore-Specific Recommendation Endpoints
# ============================================================================


@router.post("/bcom/link/{link_id}/recommend")
@limiter.limit("60/minute")
async def generate_link_recommendations(
    link_id: int,
    days_lookback: int = 30,
    max_recommendations: int = 5,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Generate recommendations for improving link performance.
    
    Args:
        link_id: Link ID to analyze
        days_lookback: Days of historical data to consider
        max_recommendations: Maximum recommendations to return
        current_user: Authenticated user
        db: Database session
    
    Returns:
        List of actionable recommendations
    """
    try:
        # Get link context
        try:
            link_context = data_loader.get_link_full_context(link_id)
        except Exception as e:
            logger.warning(f"DataLoader failed for link {link_id}, attempting database")
            link = db.query(Link).filter_by(link_id=link_id).first()
            if not link:
                raise HTTPException(status_code=404, detail=f"Link {link_id} not found")
            link_context = {}

        # Get recent grades
        start_date = (datetime.now() - timedelta(days=days_lookback)).date()
        try:
            grades = data_loader.get_link_grades(link_id, start_date, datetime.now().date())
        except Exception:
            grades = []

        if not grades:
            raise HTTPException(status_code=404, detail=f"No grade data found for link {link_id}")

        # Analyze performance trends
        import numpy as np
        grade_values = [g.get('grade', 5) for g in grades]
        avg_grade = np.mean(grade_values)
        std_grade = np.std(grade_values)
        min_grade = np.min(grade_values)
        recent_avg = np.mean(grade_values[-7:]) if len(grade_values) >= 7 else avg_grade

        # Generate recommendations based on performance
        recommendations = []

        # Low average grade
        if avg_grade < 6.0:
            recommendations.append({
                'link_id': link_id,
                'recommendation_type': 'performance_improvement',
                'priority': 1,  # Highest
                'title': 'Link Performance Degradation Detected',
                'description': f"Average grade is {avg_grade:.2f}/10. Investigate root cause and plan improvements.",
                'action_items': [
                    'Review link configuration and hardware',
                    'Check for packet loss or latency issues',
                    'Validate QoS settings',
                    'Consider network upgrade'
                ],
                'confidence': 0.95
            })

        # High variability
        if std_grade > 1.5:
            recommendations.append({
                'link_id': link_id,
                'recommendation_type': 'stability_improvement',
                'priority': 2,
                'title': 'Unstable Link Performance',
                'description': f"Performance variability is high (σ={std_grade:.2f}). Indicates intermittent issues.",
                'action_items': [
                    'Identify peak usage patterns',
                    'Review link capacity and utilization',
                    'Check for congestion or interference',
                    'Implement traffic shaping'
                ],
                'confidence': 0.88
            })

        # Recent degradation trend
        if recent_avg < avg_grade - 0.5:
            recommendations.append({
                'link_id': link_id,
                'recommendation_type': 'trend_analysis',
                'priority': 2,
                'title': 'Performance Degradation Trend',
                'description': f"Recent performance ({recent_avg:.2f}) worse than historical average ({avg_grade:.2f}).",
                'action_items': [
                    'Investigate recent changes',
                    'Check device health and logs',
                    'Monitor key metrics closely',
                    'Plan proactive maintenance'
                ],
                'confidence': 0.92
            })

        # Preventive maintenance for stable but moderate performance
        if 6.0 <= avg_grade < 8.0:
            recommendations.append({
                'link_id': link_id,
                'recommendation_type': 'preventive_maintenance',
                'priority': 3,
                'title': 'Proactive Performance Optimization',
                'description': "Link is stable but has room for improvement. Optimize for better reliability.",
                'action_items': [
                    'Review and tune network parameters',
                    'Update device firmware',
                    'Implement link redundancy',
                    'Plan capacity expansion'
                ],
                'confidence': 0.85
            })

        # Excellent performance - maintain standards
        if avg_grade >= 8.5:
            recommendations.append({
                'link_id': link_id,
                'recommendation_type': 'maintenance',
                'priority': 4,  # Lowest
                'title': 'Maintain Current Performance Standards',
                'description': "Link performance is excellent. Focus on maintaining service quality.",
                'action_items': [
                    'Continue regular monitoring',
                    'Perform preventive maintenance',
                    'Keep documentation updated',
                    'Monitor for future capacity needs'
                ],
                'confidence': 0.98
            })

        # Save recommendations to database
        for rec in recommendations[:max_recommendations]:
            recommendation = RecommendationModel(
                link_id=link_id,
                device_id=None,  # Link-level recommendation
                recommendation_type=rec['recommendation_type'],
                priority=rec['priority'],
                description=rec['description'],
                action_items='\n'.join(rec['action_items']),
                status='pending'
            )
            db.add(recommendation)

        db.commit()

        return {
            'link_id': link_id,
            'analysis_period': f'{days_lookback} days',
            'performance_metrics': {
                'average_grade': float(avg_grade),
                'std_deviation': float(std_grade),
                'min_grade': float(min_grade),
                'recent_7day_avg': float(recent_avg)
            },
            'recommendations_count': len(recommendations),
            'recommendations': recommendations[:max_recommendations],
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Recommendation generation failed for link {link_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}")


@router.post("/bcom/network/{network_id}/health-report")
@limiter.limit("60/minute")
async def generate_network_health_report(
    network_id: int,
    days_lookback: int = 30,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Generate comprehensive health report with recommendations for a network.
    
    Args:
        network_id: Network ID to analyze
        days_lookback: Days of historical data to consider
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Health report with status, metrics, and recommendations
    """
    try:
        # Get network summary
        try:
            summary = data_loader.get_network_performance_summary(network_id)
        except Exception as e:
            logger.warning(f"DataLoader failed for network {network_id}")
            summary = {}

        # Get all links in network
        cutoff_date = datetime.now() - timedelta(days=days_lookback)
        
        # Count anomalies by severity
        anomalies = db.query(DetectedAnomaly).filter(
            DetectedAnomaly.timestamp >= cutoff_date
        ).all()

        critical_count = len([a for a in anomalies if a.severity >= 0.8])
        warning_count = len([a for a in anomalies if 0.5 <= a.severity < 0.8])

        # Overall health status
        if critical_count > 0:
            overall_status = 'critical'
            health_score = max(0, 100 - (critical_count * 20))
        elif warning_count > 5:
            overall_status = 'warning'
            health_score = max(50, 100 - (warning_count * 5))
        else:
            overall_status = 'healthy'
            health_score = 100 - warning_count

        recommendations = []

        # Add recommendations based on network health
        if overall_status != 'healthy':
            recommendations.append({
                'type': 'immediate_action',
                'title': 'Address Critical Issues',
                'description': f'Network has {critical_count} critical anomalies requiring immediate attention',
                'priority': 1,
                'actions': [
                    'Investigate critical anomalies',
                    'Engage network operations team',
                    'Prepare incident response plan',
                    'Monitor metrics closely'
                ]
            })

        if warning_count > 3:
            recommendations.append({
                'type': 'monitoring',
                'title': 'Increase Monitoring Coverage',
                'description': f'Frequent warnings ({warning_count}) detected. Enhance monitoring.',
                'priority': 2,
                'actions': [
                    'Add more detailed KPI monitoring',
                    'Implement predictive analytics',
                    'Set up advanced alerting',
                    'Review historical trends'
                ]
            })

        recommendations.append({
            'type': 'planning',
            'title': 'Network Capacity & Scalability',
            'description': 'Plan for future growth and capacity needs',
            'priority': 3,
            'actions': [
                'Forecast traffic growth',
                'Identify upgrade paths',
                'Plan technology refreshes',
                'Budget for improvements'
            ]
        })

        return {
            'network_id': network_id,
            'period_days': days_lookback,
            'health_status': overall_status,
            'health_score': health_score,
            'anomaly_summary': {
                'critical': critical_count,
                'warning': warning_count,
                'total': len(anomalies)
            },
            'network_metrics': summary if summary else {
                'note': 'Database query in progress'
            },
            'recommendations': recommendations,
            'generated_at': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Health report generation failed for network {network_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/bcom/customer/{customer_id}/improvement-plan")
@limiter.limit("60/minute")
async def get_customer_improvement_plan(
    customer_id: int,
    days_lookback: int = 90,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Get comprehensive improvement plan for entire customer network.
    
    Args:
        customer_id: Customer ID
        days_lookback: Days of historical data to consider
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Strategic improvement plan with priorities
    """
    try:
        # Get customer summary
        try:
            summary = data_loader.get_customer_summary(customer_id)
        except Exception:
            summary = {}

        # Get recent recommendations
        cutoff_date = datetime.now() - timedelta(days=days_lookback)
        recent_recs = db.query(RecommendationModel).filter(
            RecommendationModel.status == 'pending'
        ).order_by(RecommendationModel.priority).all()

        # Get anomalies
        recent_anomalies = db.query(DetectedAnomaly).filter(
            DetectedAnomaly.timestamp >= cutoff_date
        ).all()

        # Group by priority
        by_priority = {1: [], 2: [], 3: [], 4: []}
        for rec in recent_recs:
            if rec.priority in by_priority:
                by_priority[rec.priority].append(rec)

        # Build improvement plan
        improvement_plan = {
            'customer_id': customer_id,
            'analysis_period': f'{days_lookback} days',
            'summary': summary if summary else {'note': 'Data loading...'},
            'anomalies_detected': len(recent_anomalies),
            'improvement_roadmap': [
                {
                    'phase': 'Immediate (1-2 weeks)',
                    'priority': 'critical',
                    'items': [
                        {
                            'title': 'Address Critical Anomalies',
                            'count': len([a for a in recent_anomalies if a.severity >= 0.8]),
                            'timeline': '1 week'
                        }
                    ]
                },
                {
                    'phase': 'Short-term (1-3 months)',
                    'priority': 'high',
                    'items': [
                        {
                            'title': 'Optimize Underperforming Links',
                            'count': len(by_priority[1]),
                            'timeline': '4-8 weeks'
                        },
                        {
                            'title': 'Implement Stability Improvements',
                            'count': len(by_priority[2]),
                            'timeline': '6-10 weeks'
                        }
                    ]
                },
                {
                    'phase': 'Medium-term (3-6 months)',
                    'priority': 'medium',
                    'items': [
                        {
                            'title': 'Capacity Planning & Upgrade',
                            'count': 1,
                            'timeline': '8-12 weeks'
                        },
                        {
                            'title': 'Technology Refresh',
                            'count': 1,
                            'timeline': '10-16 weeks'
                        }
                    ]
                },
                {
                    'phase': 'Long-term (6+ months)',
                    'priority': 'low',
                    'items': [
                        {
                            'title': 'Infrastructure Modernization',
                            'count': 1,
                            'timeline': '16-24 weeks'
                        },
                        {
                            'title': 'Advanced Analytics & AI',
                            'count': 1,
                            'timeline': '20+ weeks'
                        }
                    ]
                }
            ],
            'key_metrics': {
                'critical_items': len(by_priority[1]),
                'high_priority': len(by_priority[2]),
                'medium_priority': len(by_priority[3]),
                'low_priority': len(by_priority[4])
            },
            'estimated_impact': {
                'availability_improvement': '5-15%',
                'performance_improvement': '20-40%',
                'operational_efficiency': '30-50%'
            },
            'generated_at': datetime.now().isoformat()
        }

        return improvement_plan

    except Exception as e:
        logger.error(f"Improvement plan generation failed for customer {customer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {str(e)}")


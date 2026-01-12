from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timedelta
import logging

from app.models.schemas import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    AnomalyResult,
    AnomalyType
)
from app.models.models import AnomalyDetection
from app.core.database import get_db
from app.services.anomaly_detector import AnomalyDetector
from app.services.model_cache import get_model_cache
from app.services.model_loaders import AnomalyDetectorModelLoader
from app.services.model_management import ModelManager
from app.services.data_loader import get_data_loader
from app.models.bcom_models import DetectedAnomaly, Link, Device
from app.core.rate_limiter import limiter
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# Use a single detector instance with caching enabled
anomaly_detector = AnomalyDetector(cache_enabled=True)
# Initialize ModelManager with models directory (create if doesn't exist)
models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models_cache")
model_manager = ModelManager(models_dir)
model_loader = AnomalyDetectorModelLoader(model_manager)
data_loader = get_data_loader("data")


@router.post("/detect", response_model=AnomalyDetectionResponse)
@limiter.limit("60/minute")
async def detect_anomalies(
    request_data: AnomalyDetectionRequest,
    
    db: Session = Depends(get_db),
    request=None
):
    try:
        if request_data.anomaly_type == AnomalyType.NETWORK:
            anomalies = anomaly_detector.detect_network_anomalies(
                request_data.data,
                request_data.sensitivity
            )
        elif request_data.anomaly_type == AnomalyType.SITE:
            anomalies = anomaly_detector.detect_site_anomalies(
                request_data.data,
                request_data.sensitivity
            )
        elif request_data.anomaly_type == AnomalyType.LINK:
            anomalies = anomaly_detector.detect_link_anomalies(
                request_data.data,
                request_data.sensitivity
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid anomaly type"
            )

        results = [AnomalyResult(**anomaly) for anomaly in anomalies]

        overall_status = "healthy"
        if any(r.severity in ["critical", "high"] for r in results):
            overall_status = "critical"
        elif any(r.severity == "medium" for r in results):
            overall_status = "warning"
        elif results:
            overall_status = "anomalies_detected"

        request_id = uuid.uuid4()

        # Save to PostgreSQL
        detection = AnomalyDetection(
            id=request_id,
            user_id=None,
            anomaly_type=request_data.anomaly_type.value,
            anomalies_count=len(results),
            overall_status=overall_status,
            sensitivity=request_data.sensitivity
        )
        db.add(detection)
        db.commit()

        return AnomalyDetectionResponse(
            request_id=str(request_id),
            anomaly_type=request_data.anomaly_type,
            results=results,
            overall_status=overall_status,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}"
        )


@router.post("/batch-detect", response_model=list[AnomalyDetectionResponse])
@limiter.limit("30/minute")
async def batch_detect_anomalies(
    requests: List[AnomalyDetectionRequest],
    
    db: Session = Depends(get_db),
    request=None
):
    results = []
    for req in requests:
        try:
            result = await detect_anomalies(req, current_user, db)
            results.append(result)
        except Exception as e:
            continue

    return results


@router.get("/history")
@limiter.limit("100/minute")
async def get_detection_history(
    
    db: Session = Depends(get_db),
    limit: int = 50,
    request=None
):
    try:
        detections = db.query(AnomalyDetection) \
            .filter(AnomalyDetection.user_id == None) \
            .order_by(AnomalyDetection.created_at.desc()) \
            .limit(limit) \
            .all()

        return {"history": detections}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {str(e)}"
        )


@router.get("/statistics")
@limiter.limit("100/minute")
async def get_detection_statistics(
    
    db: Session = Depends(get_db),
    request=None
):
    try:
        detections = db.query(AnomalyDetection) \
            .filter(AnomalyDetection.user_id == None) \
            .all()

        total_detections = len(detections)

        status_counts = {}
        type_counts = {}

        for detection in detections:
            status = detection.overall_status
            anomaly_type = detection.anomaly_type

            status_counts[status] = status_counts.get(status, 0) + 1
            type_counts[anomaly_type] = type_counts.get(anomaly_type, 0) + 1

        return {
            "total_detections": total_detections,
            "status_distribution": status_counts,
            "type_distribution": type_counts
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


# ============================================================================
# BCom Offshore-Specific Anomaly Detection Endpoints
# ============================================================================


@router.post("/bcom/device/{device_id}/detect")
@limiter.limit("60/minute")
async def detect_device_anomalies(
    device_id: int,
    hours_lookback: int = 24,
    sensitivity: float = 0.8,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Detect anomalies in device KPI data using ML model.
    
    Args:
        device_id: Device ID to analyze
        hours_lookback: Hours of historical data to analyze
        sensitivity: Detection sensitivity (0.5-1.0, higher = more sensitive)
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Anomaly detection results with severity scores
    """
    try:
        # Get device KPI data
        try:
            kpi_data = data_loader.get_device_kpis(device_id)
        except Exception as e:
            logger.warning(f"DataLoader failed for device {device_id}, attempting database query")
            device = db.query(Device).filter_by(device_id=device_id).first()
            if not device:
                raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
            kpi_data = []

        if not kpi_data:
            raise HTTPException(
                status_code=404,
                detail=f"No KPI data found for device {device_id}"
            )

        # Prepare features from KPI data
        features = []
        for kpi in kpi_data:
            features.append({
                'max_value': kpi.get('max', 0),
                'min_value': kpi.get('min', 0),
                'avg_value': kpi.get('avg', 0),
                'std_deviation': kpi.get('StandardDeviation', 0),
                'timestamp': kpi.get('timestamp', '')
            })

        if not features:
            raise HTTPException(status_code=400, detail="Insufficient KPI data for analysis")

        # Load pre-trained model
        try:
            model = model_loader.load_device_detector()
            if model is None:
                logger.warning("ML model not found, using statistical detection")
                model = anomaly_detector
        except Exception as e:
            logger.warning(f"Failed to load ML model: {str(e)}, using statistical detection")
            model = anomaly_detector

        # Extract feature columns
        feature_columns = ['max_value', 'min_value', 'avg_value', 'std_deviation']
        feature_values = [[f[col] for col in feature_columns] for f in features]

        # Predict anomalies
        import numpy as np
        X = np.array(feature_values)
        
        if hasattr(model, 'predict'):
            predictions = model.predict(X)
            anomaly_indices = np.where(predictions == -1)[0]
        else:
            anomaly_indices = []

        # Build response
        anomalies = []
        for idx in anomaly_indices:
            anomalies.append({
                'device_id': device_id,
                'timestamp': features[idx].get('timestamp', ''),
                'severity': min(1.0, (1 - sensitivity) * 1.5),  # Scale to 0-1
                'confidence': sensitivity,
                'anomaly_type': 'kpi_outlier',
                'description': f"Abnormal KPI patterns detected (avg: {features[idx]['avg_value']:.2f})"
            })

        # Save to database
        for anomaly in anomalies:
            detected = DetectedAnomaly(
                device_id=device_id,
                timestamp=datetime.now(datetime.timezone.utc),
                anomaly_type='kpi_outlier',
                severity=anomaly['severity'],
                confidence=anomaly['confidence'],
                description=anomaly['description'],
                model_version='1.0.0'
            )
            db.add(detected)

        db.commit()

        return {
            'device_id': device_id,
            'anomalies_detected': len(anomalies),
            'anomalies': anomalies,
            'timestamp': datetime.now(datetime.timezone.utc).isoformat()
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Anomaly detection failed for device {device_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Anomaly detection failed: {str(e)}"
        )


@router.post("/bcom/link/{link_id}/detect")
@limiter.limit("60/minute")
async def detect_link_anomalies(
    link_id: int,
    days_lookback: int = 7,
    sensitivity: float = 0.8,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Detect anomalies in link performance grades.
    
    Args:
        link_id: Link ID to analyze
        days_lookback: Days of historical grades to analyze
        sensitivity: Detection sensitivity (0.5-1.0)
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Anomalies in link performance
    """
    try:
        # Get link grade history
        try:
            start_date = (datetime.now() - timedelta(days=days_lookback)).date()
            grades = data_loader.get_link_grades(link_id, start_date, datetime.now().date())
        except Exception as e:
            logger.warning(f"DataLoader failed for link {link_id}, attempting database query")
            grades = []

        if not grades:
            raise HTTPException(status_code=404, detail=f"No grade data found for link {link_id}")

        # Prepare grade time-series
        grade_values = [g.get('grade', 5) for g in grades]
        import numpy as np
        grades_array = np.array(grade_values).reshape(-1, 1)

        # Detect grade anomalies (sudden drops)
        anomalies = []
        for i in range(1, len(grade_values)):
            current_grade = grade_values[i]
            previous_grade = grade_values[i-1]
            drop = previous_grade - current_grade

            # Flag significant degradation
            if drop > (2 * (1 - sensitivity)):  # Adjust threshold by sensitivity
                anomalies.append({
                    'link_id': link_id,
                    'timestamp': grades[i].get('timestamp', ''),
                    'grade': current_grade,
                    'previous_grade': previous_grade,
                    'severity': min(1.0, drop / 10.0),  # Normalize to 0-1
                    'confidence': sensitivity,
                    'anomaly_type': 'grade_degradation',
                    'description': f"Link grade dropped from {previous_grade:.2f} to {current_grade:.2f}"
                })

        # Save to database
        for anomaly in anomalies:
            devices = db.query(Device).filter_by(link_id=link_id).all()
            for device in devices:
                detected = DetectedAnomaly(
                    device_id=device.id,
                    timestamp=datetime.now(datetime.timezone.utc),
                    anomaly_type='grade_degradation',
                    severity=anomaly['severity'],
                    confidence=anomaly['confidence'],
                    description=anomaly['description'],
                    model_version='1.0.0'
                )
                db.add(detected)

        db.commit()

        return {
            'link_id': link_id,
            'anomalies_detected': len(anomalies),
            'anomalies': anomalies,
            'timestamp': datetime.now(datetime.timezone.utc).isoformat()
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Link anomaly detection failed for link {link_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get("/bcom/customer/{customer_id}/summary")
@limiter.limit("60/minute")
async def get_customer_anomaly_summary(
    customer_id: int,
    days_lookback: int = 7,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Get summary of all anomalies across a customer's network.
    
    Args:
        customer_id: Customer ID
        days_lookback: Days to look back for anomalies
        current_user: Authenticated user
        db: Database session
    
    Returns:
        Anomaly summary by severity and type
    """
    try:
        # Get anomalies from database
        cutoff_date = datetime.now(datetime.timezone.utc) - timedelta(days=days_lookback)
        anomalies = db.query(DetectedAnomaly).filter(
            DetectedAnomaly.timestamp >= cutoff_date
        ).all()

        # Group by severity
        critical = [a for a in anomalies if a.severity >= 0.8]
        warning = [a for a in anomalies if 0.5 <= a.severity < 0.8]
        info = [a for a in anomalies if a.severity < 0.5]

        # Group by type
        by_type = {}
        for a in anomalies:
            if a.anomaly_type not in by_type:
                by_type[a.anomaly_type] = []
            by_type[a.anomaly_type].append(a)

        return {
            'customer_id': customer_id,
            'period_days': days_lookback,
            'total_anomalies': len(anomalies),
            'summary': {
                'critical': len(critical),
                'warning': len(warning),
                'info': len(info)
            },
            'by_type': {k: len(v) for k, v in by_type.items()},
            'latest_anomalies': [
                {
                    'device_id': a.device_id,
                    'type': a.anomaly_type,
                    'severity': a.severity,
                    'timestamp': a.timestamp.isoformat()
                }
                for a in sorted(anomalies, key=lambda x: x.timestamp, reverse=True)[:10]
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get customer anomaly summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve summary: {str(e)}")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


# ==================== CORRELATION ANALYSIS ENDPOINTS ====================

from app.services.correlation_engine import CorrelationEngine


@router.post("/bcom/correlations/network/{network_id}/analyze")
@limiter.limit("60/minute")
async def analyze_network_correlation(
    network_id: int,
    hours_lookback: int = 24,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Analyze network-level degradation to identify equipment/hardware issues.
    
    Pattern: Multiple sites in same network degrading simultaneously
    Root Cause: Equipment failure affecting multiple sites, core network issues
    
    Args:
        network_id: Network ID to analyze
        hours_lookback: Hours of historical data to analyze (default: 24)
        
    Returns:
        Correlation analysis with detected patterns and recommendations
    """
    try:
        logger.info(f"Analyzing network correlation for network {network_id}")
        
        correlation_engine = CorrelationEngine()
        analysis = correlation_engine.analyze_network_degradation(
            db=db,
            network_id=network_id,
            hours_lookback=hours_lookback
        )
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No network found or unable to analyze network {network_id}"
            )
        
        return {
            'status': 'success',
            'analysis': analysis.to_dict(),
            'timestamp': datetime.utcnow().isoformat(),
            'analyzed_by': 'correlation_engine_v1.0.0'
        }
    
    except Exception as e:
        logger.error(f"Error analyzing network correlation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze network correlation: {str(e)}"
        )


@router.post("/bcom/correlations/hub-antenna/{site_id}/analyze")
@limiter.limit("60/minute")
async def analyze_hub_antenna_correlation(
    site_id: int,
    hours_lookback: int = 24,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Analyze hub antenna degradation to identify antenna alignment issues.
    
    Pattern: Multiple links from same hub antenna degrading together
    Root Cause: Antenna alignment issue, equipment failure at hub
    
    Args:
        site_id: Hub antenna site ID
        hours_lookback: Hours of historical data (default: 24)
        
    Returns:
        Correlation analysis with antenna-specific patterns and recommendations
    """
    try:
        logger.info(f"Analyzing hub antenna correlation for site {site_id}")
        
        correlation_engine = CorrelationEngine()
        analysis = correlation_engine.analyze_hub_antenna_degradation(
            db=db,
            site_id=site_id,
            hours_lookback=hours_lookback
        )
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Site {site_id} not found or is not a hub antenna"
            )
        
        return {
            'status': 'success',
            'analysis': analysis.to_dict(),
            'timestamp': datetime.utcnow().isoformat(),
            'analyzed_by': 'correlation_engine_v1.0.0'
        }
    
    except Exception as e:
        logger.error(f"Error analyzing hub antenna correlation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze hub antenna correlation: {str(e)}"
        )


@router.post("/bcom/correlations/satellite/{satellite_name}/analyze")
@limiter.limit("60/minute")
async def analyze_satellite_correlation(
    satellite_name: str,
    hours_lookback: int = 24,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Analyze satellite-level degradation to identify interference/underperformance.
    
    Pattern: Multiple satellite links degrading simultaneously
    Root Cause: Satellite interference, saturation, underperformance
    
    Args:
        satellite_name: Satellite name/identifier (e.g., 'INTELSAT', 'EUTELSAT')
        hours_lookback: Hours of historical data (default: 24)
        
    Returns:
        Correlation analysis with satellite-specific patterns and recommendations
    """
    try:
        logger.info(f"Analyzing satellite correlation for satellite {satellite_name}")
        
        correlation_engine = CorrelationEngine()
        analysis = correlation_engine.analyze_satellite_degradation(
            db=db,
            satellite_name=satellite_name,
            hours_lookback=hours_lookback
        )
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No satellite links found matching {satellite_name}"
            )
        
        return {
            'status': 'success',
            'analysis': analysis.to_dict(),
            'timestamp': datetime.utcnow().isoformat(),
            'analyzed_by': 'correlation_engine_v1.0.0'
        }
    
    except Exception as e:
        logger.error(f"Error analyzing satellite correlation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze satellite correlation: {str(e)}"
        )


@router.post("/bcom/correlations/link/{link_id}/bidirectional")
@limiter.limit("60/minute")
async def analyze_link_bidirectional_degradation(
    link_id: int,
    hours_lookback: int = 24,
    
    db: Session = Depends(get_db),
    request=None
):
    """
    Analyze link-level bidirectional degradation (IB & OB simultaneous).
    
    Pattern: Both inbound AND outbound degradation on same link at same time
    Root Cause: Antenna misalignment affecting both directions
    
    Args:
        link_id: Link ID to analyze
        hours_lookback: Hours of historical data (default: 24)
        
    Returns:
        Correlation analysis with bidirectional degradation patterns
    """
    try:
        logger.info(f"Analyzing bidirectional degradation for link {link_id}")
        
        correlation_engine = CorrelationEngine()
        analysis = correlation_engine.analyze_link_bidirectional_degradation(
            db=db,
            link_id=link_id,
            hours_lookback=hours_lookback
        )
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for link {link_id}"
            )
        
        return {
            'status': 'success',
            'analysis': analysis.to_dict(),
            'timestamp': datetime.utcnow().isoformat(),
            'analyzed_by': 'correlation_engine_v1.0.0'
        }
    
    except Exception as e:
        logger.error(f"Error analyzing bidirectional degradation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze bidirectional degradation: {str(e)}"
        )


"""
Correlation Engine for BCom Offshore Network Analysis

Identifies correlations in RF/traffic degradation patterns to detect root causes:
1. Network-level degradation -> Equipment/hardware issues
2. Hub antenna-level degradation -> Antenna alignment or equipment issues
3. Satellite-level degradation -> Interference or satellite underperformance
4. Link-level bidirectional degradation -> Antenna misalignment
"""

import logging
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from statistics import mean, stdev, StatisticsError
import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ==================== DATA CLASSES ====================

@dataclass
class DegradationPattern:
    """Represents a RF/traffic degradation pattern."""
    
    pattern_id: str
    pattern_type: str  # 'network', 'hub_antenna', 'satellite', 'link_bidirectional'
    severity: float  # 0-1
    confidence: float  # 0-1
    affected_items: List[int]  # device_ids, link_ids, site_ids
    root_cause: str
    supporting_metrics: Dict
    timestamp: datetime
    hours_duration: int
    devices_affected_count: int
    links_affected_count: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'pattern_id': self.pattern_id,
            'pattern_type': self.pattern_type,
            'severity': self.severity,
            'confidence': self.confidence,
            'affected_items': self.affected_items,
            'root_cause': self.root_cause,
            'supporting_metrics': self.supporting_metrics,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'hours_duration': self.hours_duration,
            'devices_affected_count': self.devices_affected_count,
            'links_affected_count': self.links_affected_count,
        }


@dataclass
class CorrelationAnalysis:
    """Complete correlation analysis result."""
    
    analysis_id: str
    scope: str  # 'network', 'hub_antenna', 'satellite', 'link', 'custom'
    scope_id: int  # network_id, site_id (hub antenna), or link_id
    timestamp: datetime
    hours_analyzed: int
    patterns_found: List[DegradationPattern]
    correlation_score: float  # 0-1, how strong the correlations are
    recommendations: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'analysis_id': self.analysis_id,
            'scope': self.scope,
            'scope_id': self.scope_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'hours_analyzed': self.hours_analyzed,
            'patterns_found': [p.to_dict() for p in self.patterns_found],
            'correlation_score': self.correlation_score,
            'recommendations': self.recommendations,
        }


# ==================== CORRELATION ENGINE ====================

class CorrelationEngine:
    """
    Analyzes RF/traffic degradation patterns to identify correlated issues.
    
    Supports multiple correlation analysis types:
    1. Network-level: Multiple sites degrading together -> equipment/hardware issue
    2. Hub antenna: Multiple links from same hub antenna -> antenna alignment issue
    3. Satellite: Multiple links using same satellite -> interference/underperformance
    4. Link-level: Both IB and OB degradation on same link -> antenna misalignment
    """
    
    def __init__(self):
        """Initialize correlation engine."""
        self.logger = logging.getLogger(__name__)
        
        # Degradation thresholds
        self.CRITICAL_GRADE_THRESHOLD = 6.0  # Grade < 6.0 is critical
        self.WARNING_GRADE_THRESHOLD = 7.0   # Grade < 7.0 is warning
        self.MIN_DEVICES_FOR_PATTERN = 2     # Minimum devices to form pattern
        
        # Degradation metrics thresholds
        self.IB_DEGRADATION_THRESHOLD = 0.2   # 20%+ inbound degradation
        self.OB_DEGRADATION_THRESHOLD = 0.2   # 20%+ outbound degradation
        self.INSTABILITY_THRESHOLD = 0.3      # 30%+ instability
        
    def analyze_network_degradation(
        self,
        db: Session,
        network_id: int,
        hours_lookback: int = 24,
        min_correlation: float = 0.7
    ) -> Optional[CorrelationAnalysis]:
        """
        Analyze network-level degradation to detect equipment issues.
        
        Pattern: Multiple sites/links in same network degrading together
        Root Cause: Equipment/hardware failure affecting multiple sites
        
        Args:
            db: Database session
            network_id: Network ID to analyze
            hours_lookback: Hours of historical data to analyze
            min_correlation: Minimum correlation threshold (0-1)
            
        Returns:
            CorrelationAnalysis with detected patterns
        """
        import uuid
        from app.models.bcom_models import Link, SiteGrade, Site
        
        analysis_id = f"NET_{network_id}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Get all links in network
            links = db.query(Link).filter(Link.network_id == network_id).all()
            if not links:
                self.logger.warning(f"No links found for network {network_id}")
                return None
            
            link_ids = [link.link_id for link in links]
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)
            
            # Get recent grades for all links
            link_grades = {}
            for link_id in link_ids:
                grades = db.query(SiteGrade).filter(
                    SiteGrade.link_id == link_id,
                    SiteGrade.timestamp >= cutoff_time,
                    SiteGrade.grade < self.WARNING_GRADE_THRESHOLD
                ).all()
                
                if grades:
                    link_grades[link_id] = grades
            
            if not link_grades:
                return CorrelationAnalysis(
                    analysis_id=analysis_id,
                    scope='network',
                    scope_id=network_id,
                    timestamp=datetime.utcnow(),
                    hours_analyzed=hours_lookback,
                    patterns_found=[],
                    correlation_score=0.0,
                    recommendations=['No degradation detected in this network']
                )
            
            # Analyze temporal correlation
            patterns = self._detect_temporal_correlation(
                link_grades, 
                network_id,
                pattern_type='network_equipment'
            )
            
            # Analyze which sites are affected
            affected_sites = set()
            for link_id, grades in link_grades.items():
                link = next((l for l in links if l.link_id == link_id), None)
                if link:
                    affected_sites.add(link.site_id)
            
            # Calculate correlation score
            correlation_score = self._calculate_correlation_score(link_grades, hours_lookback)
            
            # Generate recommendations
            recommendations = self._generate_network_recommendations(
                len(affected_sites),
                len(link_grades),
                correlation_score,
                patterns
            )
            
            return CorrelationAnalysis(
                analysis_id=analysis_id,
                scope='network',
                scope_id=network_id,
                timestamp=datetime.utcnow(),
                hours_analyzed=hours_lookback,
                patterns_found=patterns,
                correlation_score=correlation_score,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing network {network_id}: {e}")
            return None
    
    def analyze_hub_antenna_degradation(
        self,
        db: Session,
        site_id: int,
        hours_lookback: int = 24
    ) -> Optional[CorrelationAnalysis]:
        """
        Analyze hub antenna degradation to detect antenna alignment issues.
        
        Pattern: Multiple links from same hub antenna degrading together
        Root Cause: Antenna alignment issue or equipment failure at hub
        
        Args:
            db: Database session
            site_id: Hub antenna site ID
            hours_lookback: Hours of historical data
            
        Returns:
            CorrelationAnalysis with detected patterns
        """
        import uuid
        from app.models.bcom_models import Link, SiteGrade, Site
        
        analysis_id = f"HUB_{site_id}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Verify this is a hub antenna site
            site = db.query(Site).filter(Site.site_id == site_id).first()
            if not site or 'Hub' not in (site.site_type or ''):
                self.logger.warning(f"Site {site_id} is not a hub antenna")
                return None
            
            # Get all links from this hub antenna
            links = db.query(Link).filter(Link.site_id == site_id).all()
            if not links:
                return None
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)
            
            # Get grades showing degradation
            degraded_links = {}
            for link in links:
                grades = db.query(SiteGrade).filter(
                    SiteGrade.link_id == link.link_id,
                    SiteGrade.timestamp >= cutoff_time
                ).all()
                
                if grades:
                    # Check for antenna-specific metrics (IB/OB instability)
                    antenna_issues = [
                        g for g in grades 
                        if (g.ib_instability or 0) > self.INSTABILITY_THRESHOLD or
                           (g.ob_instability or 0) > self.INSTABILITY_THRESHOLD
                    ]
                    
                    if antenna_issues:
                        degraded_links[link.link_id] = grades
            
            if not degraded_links:
                return CorrelationAnalysis(
                    analysis_id=analysis_id,
                    scope='hub_antenna',
                    scope_id=site_id,
                    timestamp=datetime.utcnow(),
                    hours_analyzed=hours_lookback,
                    patterns_found=[],
                    correlation_score=0.0,
                    recommendations=['No antenna-level degradation detected']
                )
            
            # Detect antenna alignment patterns
            patterns = self._detect_antenna_alignment_patterns(
                degraded_links,
                site_id
            )
            
            # Calculate correlation
            correlation_score = self._calculate_correlation_score(degraded_links, hours_lookback)
            
            recommendations = self._generate_antenna_recommendations(
                len(degraded_links),
                len(links),
                correlation_score,
                patterns
            )
            
            return CorrelationAnalysis(
                analysis_id=analysis_id,
                scope='hub_antenna',
                scope_id=site_id,
                timestamp=datetime.utcnow(),
                hours_analyzed=hours_lookback,
                patterns_found=patterns,
                correlation_score=correlation_score,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing hub antenna {site_id}: {e}")
            return None
    
    def analyze_satellite_degradation(
        self,
        db: Session,
        satellite_name: str,
        hours_lookback: int = 24
    ) -> Optional[CorrelationAnalysis]:
        """
        Analyze satellite-level degradation to detect interference/underperformance.
        
        Pattern: Multiple links using same satellite degrading together
        Root Cause: Satellite interference, saturation, or underperformance
        
        Note: Requires satellite information in device metadata or link configuration
        
        Args:
            db: Database session
            satellite_name: Satellite name/identifier
            hours_lookback: Hours of historical data
            
        Returns:
            CorrelationAnalysis with detected patterns
        """
        import uuid
        from app.models.bcom_models import Link, SiteGrade, Device
        
        analysis_id = f"SAT_{satellite_name}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Note: This assumes satellite info is in device metadata or link_type
            # Adjust based on your actual data structure
            
            # For now, search in link_type if satellite info is available
            relevant_links = db.query(Link).filter(
                Link.link_type.ilike(f"%{satellite_name}%")
            ).all()
            
            if not relevant_links:
                self.logger.info(f"No links found for satellite {satellite_name}")
                return CorrelationAnalysis(
                    analysis_id=analysis_id,
                    scope='satellite',
                    scope_id=0,
                    timestamp=datetime.utcnow(),
                    hours_analyzed=hours_lookback,
                    patterns_found=[],
                    correlation_score=0.0,
                    recommendations=['No matching satellite links found']
                )
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)
            
            # Get degradation data
            degraded_links = {}
            for link in relevant_links:
                grades = db.query(SiteGrade).filter(
                    SiteGrade.link_id == link.link_id,
                    SiteGrade.timestamp >= cutoff_time,
                    SiteGrade.grade < self.WARNING_GRADE_THRESHOLD
                ).all()
                
                if grades:
                    degraded_links[link.link_id] = grades
            
            if not degraded_links:
                return CorrelationAnalysis(
                    analysis_id=analysis_id,
                    scope='satellite',
                    scope_id=0,
                    timestamp=datetime.utcnow(),
                    hours_analyzed=hours_lookback,
                    patterns_found=[],
                    correlation_score=0.0,
                    recommendations=['No degradation detected on this satellite']
                )
            
            # Detect satellite interference patterns
            patterns = self._detect_satellite_patterns(
                degraded_links,
                satellite_name
            )
            
            correlation_score = self._calculate_correlation_score(degraded_links, hours_lookback)
            
            recommendations = self._generate_satellite_recommendations(
                len(degraded_links),
                correlation_score,
                patterns
            )
            
            return CorrelationAnalysis(
                analysis_id=analysis_id,
                scope='satellite',
                scope_id=0,
                timestamp=datetime.utcnow(),
                hours_analyzed=hours_lookback,
                patterns_found=patterns,
                correlation_score=correlation_score,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing satellite {satellite_name}: {e}")
            return None
    
    def analyze_link_bidirectional_degradation(
        self,
        db: Session,
        link_id: int,
        hours_lookback: int = 24
    ) -> Optional[CorrelationAnalysis]:
        """
        Analyze link-level bidirectional degradation to detect antenna misalignment.
        
        Pattern: Both inbound AND outbound degradation on same link simultaneously
        Root Cause: Antenna misalignment affecting both directions
        
        Args:
            db: Database session
            link_id: Link ID to analyze
            hours_lookback: Hours of historical data
            
        Returns:
            CorrelationAnalysis with detected patterns
        """
        import uuid
        from app.models.bcom_models import SiteGrade
        
        analysis_id = f"LINK_{link_id}_{uuid.uuid4().hex[:8]}"
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_lookback)
            
            # Get all grades for this link
            grades = db.query(SiteGrade).filter(
                SiteGrade.link_id == link_id,
                SiteGrade.timestamp >= cutoff_time
            ).order_by(SiteGrade.timestamp).all()
            
            if not grades:
                return CorrelationAnalysis(
                    analysis_id=analysis_id,
                    scope='link',
                    scope_id=link_id,
                    timestamp=datetime.utcnow(),
                    hours_analyzed=hours_lookback,
                    patterns_found=[],
                    correlation_score=0.0,
                    recommendations=['Insufficient data for analysis']
                )
            
            # Detect bidirectional degradation patterns
            patterns = self._detect_bidirectional_degradation(
                grades,
                link_id
            )
            
            if not patterns:
                return CorrelationAnalysis(
                    analysis_id=analysis_id,
                    scope='link',
                    scope_id=link_id,
                    timestamp=datetime.utcnow(),
                    hours_analyzed=hours_lookback,
                    patterns_found=[],
                    correlation_score=0.0,
                    recommendations=['No bidirectional degradation detected']
                )
            
            correlation_score = self._calculate_bidirectional_score(grades)
            
            recommendations = self._generate_bidirectional_recommendations(
                patterns,
                correlation_score
            )
            
            return CorrelationAnalysis(
                analysis_id=analysis_id,
                scope='link',
                scope_id=link_id,
                timestamp=datetime.utcnow(),
                hours_analyzed=hours_lookback,
                patterns_found=patterns,
                correlation_score=correlation_score,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing link {link_id}: {e}")
            return None
    
    # ==================== PATTERN DETECTION METHODS ====================
    
    def _detect_temporal_correlation(
        self,
        link_grades: Dict[int, List],
        network_id: int,
        pattern_type: str
    ) -> List[DegradationPattern]:
        """Detect temporal correlation between multiple links."""
        patterns = []
        
        if not link_grades or len(link_grades) < self.MIN_DEVICES_FOR_PATTERN:
            return patterns
        
        try:
            # Group grades by hour
            hourly_buckets = {}
            for link_id, grades in link_grades.items():
                for grade in grades:
                    hour_key = grade.timestamp.replace(minute=0, second=0, microsecond=0)
                    if hour_key not in hourly_buckets:
                        hourly_buckets[hour_key] = []
                    hourly_buckets[hour_key].append((link_id, grade))
            
            # Find hours with simultaneous degradation
            for hour, entries in hourly_buckets.items():
                if len(entries) >= self.MIN_DEVICES_FOR_PATTERN:
                    affected_links = list(set([e[0] for e in entries]))
                    grades_list = [e[1].grade for e in entries]
                    
                    severity = 1.0 - (mean(grades_list) / 10.0)  # Normalized to 0-1
                    confidence = min(0.95, len(affected_links) / 10.0 * 2)
                    
                    pattern = DegradationPattern(
                        pattern_id=f"{network_id}_{hour.isoformat()}",
                        pattern_type='network_equipment_failure',
                        severity=severity,
                        confidence=confidence,
                        affected_items=affected_links,
                        root_cause='Possible equipment/hardware failure affecting multiple sites',
                        supporting_metrics={
                            'avg_grade': mean(grades_list),
                            'min_grade': min(grades_list),
                            'affected_links': len(affected_links),
                            'simultaneous_degradation_count': len(entries)
                        },
                        timestamp=hour,
                        hours_duration=1,
                        devices_affected_count=len(affected_links),
                        links_affected_count=len(affected_links)
                    )
                    patterns.append(pattern)
        
        except Exception as e:
            self.logger.error(f"Error in temporal correlation: {e}")
        
        return patterns
    
    def _detect_antenna_alignment_patterns(
        self,
        degraded_links: Dict[int, List],
        site_id: int
    ) -> List[DegradationPattern]:
        """Detect antenna alignment issues from instability patterns."""
        patterns = []
        
        try:
            for link_id, grades in degraded_links.items():
                # Look for high instability on both directions
                ib_instability_values = [g.ib_instability or 0 for g in grades]
                ob_instability_values = [g.ob_instability or 0 for g in grades]
                
                avg_ib_instability = mean(ib_instability_values) if ib_instability_values else 0
                avg_ob_instability = mean(ob_instability_values) if ob_instability_values else 0
                
                # Antenna alignment issue if both directions have high instability
                if avg_ib_instability > self.INSTABILITY_THRESHOLD and \
                   avg_ob_instability > self.INSTABILITY_THRESHOLD:
                    
                    severity = max(avg_ib_instability, avg_ob_instability)
                    confidence = 0.85
                    
                    pattern = DegradationPattern(
                        pattern_id=f"ANTENNA_{site_id}_{link_id}",
                        pattern_type='antenna_alignment',
                        severity=severity,
                        confidence=confidence,
                        affected_items=[link_id],
                        root_cause='Antenna alignment issue causing bidirectional instability',
                        supporting_metrics={
                            'avg_ib_instability': avg_ib_instability,
                            'avg_ob_instability': avg_ob_instability,
                            'grade_records_analyzed': len(grades)
                        },
                        timestamp=grades[0].timestamp if grades else datetime.utcnow(),
                        hours_duration=len(grades),
                        devices_affected_count=1,
                        links_affected_count=1
                    )
                    patterns.append(pattern)
        
        except Exception as e:
            self.logger.error(f"Error detecting antenna alignment: {e}")
        
        return patterns
    
    def _detect_satellite_patterns(
        self,
        degraded_links: Dict[int, List],
        satellite_name: str
    ) -> List[DegradationPattern]:
        """Detect satellite interference or underperformance patterns."""
        patterns = []
        
        try:
            if len(degraded_links) >= self.MIN_DEVICES_FOR_PATTERN:
                all_grades = []
                for grades in degraded_links.values():
                    all_grades.extend(grades)
                
                grades_values = [g.grade for g in all_grades]
                avg_grade = mean(grades_values) if grades_values else 0
                
                # High correlation across multiple links suggests satellite issue
                congestion_values = [g.congestion or 0 for g in all_grades]
                avg_congestion = mean(congestion_values) if congestion_values else 0
                
                severity = max(1.0 - (avg_grade / 10.0), avg_congestion)
                confidence = 0.88
                
                pattern = DegradationPattern(
                    pattern_id=f"SAT_{satellite_name}",
                    pattern_type='satellite_interference',
                    severity=severity,
                    confidence=confidence,
                    affected_items=list(degraded_links.keys()),
                    root_cause='Possible satellite interference or underperformance',
                    supporting_metrics={
                        'affected_links': len(degraded_links),
                        'avg_grade': avg_grade,
                        'avg_congestion': avg_congestion,
                        'total_measurements': len(all_grades)
                    },
                    timestamp=all_grades[0].timestamp if all_grades else datetime.utcnow(),
                    hours_duration=len(all_grades),
                    devices_affected_count=len(degraded_links),
                    links_affected_count=len(degraded_links)
                )
                patterns.append(pattern)
        
        except Exception as e:
            self.logger.error(f"Error detecting satellite patterns: {e}")
        
        return patterns
    
    def _detect_bidirectional_degradation(
        self,
        grades: List,
        link_id: int
    ) -> List[DegradationPattern]:
        """Detect simultaneous IB and OB degradation (antenna misalignment)."""
        patterns = []
        
        try:
            for grade in grades:
                # Check for simultaneous IB and OB degradation
                ib_deg = (grade.ib_degradation or 0)
                ob_deg = (grade.ob_degradation or 0)
                
                if ib_deg >= self.IB_DEGRADATION_THRESHOLD and \
                   ob_deg >= self.OB_DEGRADATION_THRESHOLD:
                    
                    severity = max(ib_deg, ob_deg)
                    confidence = 0.90  # High confidence for bidirectional pattern
                    
                    pattern = DegradationPattern(
                        pattern_id=f"BIDIR_{link_id}_{grade.timestamp.isoformat()}",
                        pattern_type='antenna_misalignment',
                        severity=severity,
                        confidence=confidence,
                        affected_items=[link_id],
                        root_cause='Antenna misalignment: simultaneous IB & OB degradation',
                        supporting_metrics={
                            'ib_degradation': ib_deg,
                            'ob_degradation': ob_deg,
                            'grade': grade.grade,
                            'timestamp': grade.timestamp.isoformat()
                        },
                        timestamp=grade.timestamp,
                        hours_duration=1,
                        devices_affected_count=1,
                        links_affected_count=1
                    )
                    patterns.append(pattern)
        
        except Exception as e:
            self.logger.error(f"Error detecting bidirectional degradation: {e}")
        
        return patterns
    
    # ==================== SCORING & RECOMMENDATION METHODS ====================
    
    def _calculate_correlation_score(
        self,
        degraded_items: Dict,
        hours_lookback: int
    ) -> float:
        """Calculate overall correlation strength (0-1)."""
        try:
            if not degraded_items:
                return 0.0
            
            # More items = stronger correlation
            item_count = len(degraded_items)
            item_score = min(item_count / 10.0, 1.0)
            
            # Consistency of degradation
            all_grades = []
            for grades in degraded_items.values():
                all_grades.extend([g.grade for g in grades])
            
            if all_grades:
                try:
                    grade_stdev = stdev(all_grades)
                    # Lower stdev = more consistent = stronger correlation
                    consistency_score = 1.0 - (grade_stdev / 10.0)
                    consistency_score = max(0, min(1.0, consistency_score))
                except StatisticsError:
                    consistency_score = 0.5
            else:
                consistency_score = 0.5
            
            # Average of both factors
            correlation_score = (item_score * 0.4) + (consistency_score * 0.6)
            return min(1.0, correlation_score)
        
        except Exception as e:
            self.logger.error(f"Error calculating correlation score: {e}")
            return 0.5
    
    def _calculate_bidirectional_score(self, grades: List) -> float:
        """Calculate correlation score for bidirectional degradation."""
        try:
            bidirectional_count = 0
            total_count = len(grades)
            
            for grade in grades:
                ib_deg = (grade.ib_degradation or 0)
                ob_deg = (grade.ob_degradation or 0)
                
                if ib_deg >= self.IB_DEGRADATION_THRESHOLD and \
                   ob_deg >= self.OB_DEGRADATION_THRESHOLD:
                    bidirectional_count += 1
            
            if total_count == 0:
                return 0.0
            
            return bidirectional_count / total_count
        
        except Exception as e:
            self.logger.error(f"Error calculating bidirectional score: {e}")
            return 0.0
    
    def _generate_network_recommendations(
        self,
        affected_sites: int,
        affected_links: int,
        correlation_score: float,
        patterns: List[DegradationPattern]
    ) -> List[str]:
        """Generate network-level recommendations."""
        recommendations = []
        
        if correlation_score > 0.8:
            recommendations.append(
                "🔴 CRITICAL: Strong correlation detected across network. "
                "Investigate potential equipment failure at central hub or core network equipment."
            )
        elif correlation_score > 0.6:
            recommendations.append(
                "🟠 HIGH: Moderate correlation detected across multiple sites. "
                "Check for common equipment, power infrastructure, or core network issues."
            )
        
        recommendations.append(
            f"• Affected Sites: {affected_sites}, Affected Links: {affected_links}"
        )
        recommendations.append(
            "• Check network equipment logs at affected sites for errors"
        )
        recommendations.append(
            "• Verify power stability and UPS status at affected locations"
        )
        recommendations.append(
            "• Review recent configuration changes affecting multiple sites"
        )
        
        if patterns:
            recommendations.append(
                f"• {len(patterns)} temporal correlation pattern(s) detected"
            )
        
        return recommendations
    
    def _generate_antenna_recommendations(
        self,
        affected_links: int,
        total_links: int,
        correlation_score: float,
        patterns: List[DegradationPattern]
    ) -> List[str]:
        """Generate hub antenna-level recommendations."""
        recommendations = []
        
        percentage = (affected_links / total_links * 100) if total_links > 0 else 0
        
        if correlation_score > 0.75:
            recommendations.append(
                "🔴 CRITICAL: Multiple links from this hub antenna showing instability. "
                "Likely antenna alignment or equipment issue at this hub."
            )
            recommendations.append(
                f"• {percentage:.1f}% of links affected ({affected_links}/{total_links})"
            )
            recommendations.append(
                "• Schedule immediate antenna alignment check"
            )
        else:
            recommendations.append(
                "🟠 WARNING: Hub antenna showing instability patterns."
            )
            recommendations.append(
                "• Verify antenna orientation and mechanical stability"
            )
        
        recommendations.append(
            "• Check hub equipment (modem, amplifier, frequency converter) status"
        )
        recommendations.append(
            "• Inspect cable connections and potential water ingress"
        )
        recommendations.append(
            "• Consider frequency retuning if recent weather events occurred"
        )
        
        return recommendations
    
    def _generate_satellite_recommendations(
        self,
        affected_links: int,
        correlation_score: float,
        patterns: List[DegradationPattern]
    ) -> List[str]:
        """Generate satellite-level recommendations."""
        recommendations = []
        
        if correlation_score > 0.7:
            recommendations.append(
                "🔴 CRITICAL: Multiple satellite links degrading simultaneously. "
                "Check for satellite interference, congestion, or degradation."
            )
        else:
            recommendations.append(
                "🟠 WARNING: Satellite link degradation detected."
            )
        
        recommendations.append(
            f"• Affected Links: {affected_links}"
        )
        recommendations.append(
            "• Check satellite operator status page for known issues"
        )
        recommendations.append(
            "• Monitor interference on satellite frequency band"
        )
        recommendations.append(
            "• Verify satellite uplink/downlink parameters"
        )
        recommendations.append(
            "• Consider frequency hopping to alternate satellite if available"
        )
        
        return recommendations
    
    def _generate_bidirectional_recommendations(
        self,
        patterns: List[DegradationPattern],
        correlation_score: float
    ) -> List[str]:
        """Generate bidirectional degradation recommendations."""
        recommendations = []
        
        if correlation_score > 0.6:
            recommendations.append(
                "🔴 CRITICAL: Bidirectional degradation detected (IB & OB). "
                "Strong indicator of antenna misalignment."
            )
            recommendations.append(
                "• IMMEDIATE ACTION: Schedule antenna re-alignment"
            )
        else:
            recommendations.append(
                "🟠 WARNING: Simultaneous IB & OB degradation patterns detected."
            )
        
        recommendations.append(
            "• Check antenna orientation using spectrum analyzer"
        )
        recommendations.append(
            "• Verify antenna cable connections and impedance matching"
        )
        recommendations.append(
            "• Review weather conditions during degradation period"
        )
        recommendations.append(
            "• Inspect for physical damage to antenna or mast"
        )
        
        return recommendations

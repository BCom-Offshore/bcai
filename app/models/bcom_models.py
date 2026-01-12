"""
SQLAlchemy ORM Models for BCom Offshore Data

Maps database tables to Python classes for type-safe data access.
Supports customer networks, sites, links, devices, performance metrics, and KPI data.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, BigInteger, 
    ForeignKey, Text, JSON, DECIMAL, Index, CheckConstraint, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


# ==================== CORE ENTITIES ====================

class Customer(Base):
    """Customer entity representing BCom Offshore client."""
    
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, unique=True, nullable=False, index=True)
    customer_name = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    networks = relationship("Network", back_populates="customer", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Customer(id={self.customer_id}, name='{self.customer_name}')>"


class Network(Base):
    """Network belonging to a customer."""
    
    __tablename__ = "networks"
    
    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False, index=True)
    network_name = Column(String(255), nullable=False, index=True)
    network_type = Column(String(50))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="networks")
    links = relationship("Link", back_populates="network", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_networks_customer_id", "customer_id"),
    )
    
    def __repr__(self):
        return f"<Network(id={self.network_id}, name='{self.network_name}', type='{self.network_type}')>"


class Site(Base):
    """Physical site/location in network.
    
    IMPORTANT: A site can belong to multiple networks through multiple links.
    The relationship is many-to-many, established via the Link table:
    - One Site → Many Links (with different networks)
    - One Network → Many Links (to different sites)
    """
    
    __tablename__ = "sites"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, unique=True, nullable=False, index=True)
    site_name = Column(String(255), nullable=False, index=True)
    site_type = Column(String(50))
    country = Column(String(100), index=True)
    city = Column(String(100), index=True)
    latitude = Column(DECIMAL(10, 6))
    longitude = Column(DECIMAL(10, 6))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    links = relationship("Link", back_populates="site", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_sites_location", "country", "city"),
    )
    
    def __repr__(self):
        return f"<Site(id={self.site_id}, name='{self.site_name}', location='{self.city}, {self.country}')>"


class Link(Base):
    """Network link connecting sites within networks.
    
    A link is the central entity that defines:
    - Which network a specific site is connected to
    - What devices (antennas/sensors) are deployed on this link
    - Daily performance metrics (SiteGrade) for monitoring
    
    Key point: A site can have multiple links to the same or different networks,
    creating the many-to-many relationship between Sites and Networks.
    """
    
    __tablename__ = "links"
    
    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, unique=True, nullable=False, index=True)
    site_id = Column(Integer, ForeignKey("sites.site_id"), nullable=False, index=True)
    network_id = Column(Integer, ForeignKey("networks.network_id"), nullable=False, index=True)
    link_name = Column(String(255), nullable=False, index=True)
    link_type = Column(String(100))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    site = relationship("Site", back_populates="links")
    network = relationship("Network", back_populates="links")
    devices = relationship("Device", back_populates="link", cascade="all, delete-orphan")
    site_grades = relationship("SiteGrade", back_populates="link", cascade="all, delete-orphan")
    anomalies = relationship("DetectedAnomaly", back_populates="link", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="link", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_links_site_id", "site_id"),
        Index("idx_links_network_id", "network_id"),
    )
    
    def __repr__(self):
        return f"<Link(id={self.link_id}, name='{self.link_name}', type='{self.link_type}')>"


class Device(Base):
    """Antenna/sensor device on a link."""
    
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, unique=True, nullable=False, index=True)
    link_id = Column(Integer, ForeignKey("links.link_id"), nullable=False, index=True)
    device_api = Column(String(50))
    device_api_id = Column(Integer)
    device_source = Column(String(100))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    link = relationship("Link", back_populates="devices")
    kpi_data = relationship("KPIData", back_populates="device", cascade="all, delete-orphan")
    anomalies = relationship("DetectedAnomaly", back_populates="device", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="device", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_devices_link_id", "link_id"),
        Index("idx_devices_api", "device_api"),
    )
    
    def __repr__(self):
        return f"<Device(id={self.device_id}, api='{self.device_api}', source='{self.device_source}')>"


# ==================== PERFORMANCE METRICS ====================

class SiteGrade(Base):
    """Daily link performance grade (1-10 scale)."""
    
    __tablename__ = "site_grades"
    
    id = Column(BigInteger, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("links.link_id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    availability = Column(Float)
    ib_degradation = Column(Float)
    ob_degradation = Column(Float)
    ib_instability = Column(Float)
    ob_instability = Column(Float)
    up_time = Column(Float)
    status = Column(Boolean)
    performance = Column(Float)
    congestion = Column(Float)
    latency = Column(Float)
    grade = Column(Float, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    link = relationship("Link", back_populates="site_grades")
    
    __table_args__ = (
        CheckConstraint("grade >= 1 AND grade <= 10", name="ck_grade_range"),
        CheckConstraint("availability >= 0 AND availability <= 100", name="ck_availability_range"),
        Index("idx_site_grades_timestamp", "timestamp"),
        Index("idx_site_grades_link_timestamp", "link_id", "timestamp"),
        Index("idx_site_grades_status", "status"),
    )
    
    def __repr__(self):
        return f"<SiteGrade(link_id={self.link_id}, timestamp='{self.timestamp}', grade={self.grade:.2f})>"


# ==================== KPI DATA ====================

class KPIData(Base):
    """Time-series KPI metrics from devices (sensors).
    
    KPI data has two data sources:
    1. Database records (this table) - for querying and analysis
    2. JSON files in data/kpis/ folder - named by link_id (e.g., 3156.json)
       Contains all KPI measurements for all devices on that link
    
    Relationship: Device → KPI Data (N:1)
    The device_id links to the Device that generated the metrics.
    The api_connection_channel_id identifies the specific measurement channel/port.
    """
    
    __tablename__ = "kpi_data"
    
    id = Column(BigInteger, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.device_id"), nullable=False, index=True)
    api_connection_channel_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    metric_type = Column(String(20), default="numeric", index=True)  # 'numeric' or 'categorical'
    max_value = Column(Float)
    min_value = Column(Float)
    avg_value = Column(Float)
    std_deviation = Column(Float)
    total_raw_entries = Column(Integer)
    metric_data = Column(JSONB)  # For categorical data (error counts, etc.)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    device = relationship("Device", back_populates="kpi_data")
    
    __table_args__ = (
        CheckConstraint("metric_type IN ('numeric', 'categorical')", name="ck_metric_type"),
        Index("idx_kpi_channel_id", "api_connection_channel_id"),
        Index("idx_kpi_timestamp", "timestamp"),
        Index("idx_kpi_device_timestamp", "device_id", "timestamp"),
    )
    
    def __repr__(self):
        return f"<KPIData(device_id={self.device_id}, timestamp='{self.timestamp}', avg={self.avg_value})>"


# ==================== ANOMALY DETECTION ====================

class DetectedAnomaly(Base):
    """Anomaly detected by ML model."""
    
    __tablename__ = "detected_anomalies"
    
    id = Column(BigInteger, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("links.link_id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.device_id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    anomaly_type = Column(String(100), index=True)
    severity = Column(Float)  # 0-1
    confidence = Column(Float)  # 0-1
    description = Column(Text)
    model_version = Column(String(50))
    raw_data = Column(JSONB)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(100))
    
    # Relationships
    link = relationship("Link", back_populates="anomalies")
    device = relationship("Device", back_populates="anomalies")
    
    __table_args__ = (
        CheckConstraint("severity >= 0 AND severity <= 1", name="ck_severity"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_confidence"),
        Index("idx_anomalies_device_id", "device_id"),
        Index("idx_anomalies_timestamp", "timestamp"),
        Index("idx_anomalies_severity", "severity"),
        Index("idx_anomalies_type", "anomaly_type"),
    )
    
    def __repr__(self):
        return f"<DetectedAnomaly(device_id={self.device_id}, type='{self.anomaly_type}', severity={self.severity:.2f})>"


# ==================== RECOMMENDATIONS ====================

class Recommendation(Base):
    """Recommendation generated by ML model."""
    
    __tablename__ = "recommendations"
    
    id = Column(BigInteger, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("links.link_id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.device_id"), index=True)
    recommendation_type = Column(String(100))
    priority = Column(Integer, default=3)  # 1=critical, 2=high, 3=medium, 4=low
    description = Column(Text, nullable=False)
    action_items = Column(Text)  # JSON array
    model_version = Column(String(50))
    status = Column(String(50), default="pending", index=True)  # pending, acknowledged, resolved, dismissed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100))
    
    # Relationships
    link = relationship("Link", back_populates="recommendations")
    device = relationship("Device", back_populates="recommendations")
    
    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 4", name="ck_priority"),
        CheckConstraint("status IN ('pending', 'acknowledged', 'resolved', 'dismissed')", name="ck_status"),
        Index("idx_recommendations_link_id", "link_id"),
        Index("idx_recommendations_device_id", "device_id"),
        Index("idx_recommendations_priority", "priority"),
        Index("idx_recommendations_status", "status"),
        Index("idx_recommendations_created", "created_at"),
    )
    
    def __repr__(self):
        return f"<Recommendation(link_id={self.link_id}, type='{self.recommendation_type}', priority={self.priority})>"


# ==================== MODEL METRICS ====================

class ModelMetrics(Base):
    """ML model training and performance metrics."""
    
    __tablename__ = "model_metrics"
    
    id = Column(BigInteger, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False, index=True)
    model_version = Column(String(50), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False)  # accuracy, precision, recall, f1, auc, etc.
    metric_value = Column(Float, nullable=False)
    training_date = Column(DateTime, index=True)
    test_set_size = Column(Integer)
    true_positives = Column(Integer)
    true_negatives = Column(Integer)
    false_positives = Column(Integer)
    false_negatives = Column(Integer)
    model_metadata = Column(JSONB)  # Renamed from 'metadata' to avoid SQLAlchemy reserved name
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("metric_value >= 0 AND metric_value <= 1", name="ck_metric_value"),
        Index("idx_model_metrics_name", "model_name", "model_version"),
        Index("idx_model_metrics_date", "training_date"),
    )
    
    def __repr__(self):
        return f"<ModelMetrics(model='{self.model_name}:{self.model_version}', {self.metric_name}={self.metric_value:.3f})>"


# ==================== SYSTEM TABLES ====================

class DataProcessingLog(Base):
    """Log of data processing operations."""
    
    __tablename__ = "data_processing_logs"
    
    id = Column(BigInteger, primary_key=True, index=True)
    process_type = Column(String(100), index=True)
    status = Column(String(50), index=True)  # success, error, warning
    record_count = Column(Integer)
    error_message = Column(Text)
    details = Column(JSONB)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index("idx_logs_process_type", "process_type"),
        Index("idx_logs_status", "status"),
        Index("idx_logs_created", "created_at"),
    )
    
    def __repr__(self):
        return f"<DataProcessingLog(type='{self.process_type}', status='{self.status}')>"

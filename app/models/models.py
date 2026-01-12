"""
SQLAlchemy database models for PostgreSQL backend
"""
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    """Users table - stores user account information"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    company = Column(String(255), default="BCom Offshore SAL")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    anomaly_detections = relationship("AnomalyDetection", back_populates="user", cascade="all, delete-orphan")
    recommendation_requests = relationship("RecommendationRequest", back_populates="user", cascade="all, delete-orphan")
    network_metrics = relationship("NetworkMetrics", back_populates="user", cascade="all, delete-orphan")
    site_metrics = relationship("SiteMetrics", back_populates="user", cascade="all, delete-orphan")
    link_metrics = relationship("LinkMetrics", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, full_name={self.full_name})>"


class AnomalyDetection(Base):
    """Anomaly Detections table - stores anomaly detection results"""
    __tablename__ = "anomaly_detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    anomaly_type = Column(String(100), nullable=False)
    anomalies_count = Column(Integer, default=0)
    overall_status = Column(String(50), nullable=False)
    sensitivity = Column(Float, default=0.95)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="anomaly_detections")

    def __repr__(self):
        return f"<AnomalyDetection(id={self.id}, user_id={self.user_id}, type={self.anomaly_type})>"


class RecommendationRequest(Base):
    """Recommendation Requests table - stores recommendation request history"""
    __tablename__ = "recommendations_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    context = Column(Text, nullable=False)
    entity_id = Column(String(255), nullable=False)
    recommendations_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="recommendation_requests")

    def __repr__(self):
        return f"<RecommendationRequest(id={self.id}, user_id={self.user_id}, entity_id={self.entity_id})>"


class NetworkMetrics(Base):
    """Network Metrics table - stores network performance metrics"""
    __tablename__ = "network_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    network_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    bandwidth_usage = Column(Float, nullable=False)
    packet_loss = Column(Float, nullable=False)
    latency = Column(Float, nullable=False)
    error_rate = Column(Float, nullable=False)
    connection_count = Column(Integer, nullable=False)
    additional_metrics = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="network_metrics")

    def __repr__(self):
        return f"<NetworkMetrics(id={self.id}, network_id={self.network_id}, timestamp={self.timestamp})>"


class SiteMetrics(Base):
    """Site Metrics table - stores site performance metrics"""
    __tablename__ = "site_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    response_time = Column(Float, nullable=False)
    uptime_percentage = Column(Float, nullable=False)
    request_count = Column(Integer, nullable=False)
    error_count = Column(Integer, nullable=False)
    cpu_usage = Column(Float, nullable=False)
    memory_usage = Column(Float, nullable=False)
    additional_metrics = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="site_metrics")

    def __repr__(self):
        return f"<SiteMetrics(id={self.id}, site_id={self.site_id}, timestamp={self.timestamp})>"


class LinkMetrics(Base):
    """Link Metrics table - stores link performance metrics"""
    __tablename__ = "link_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    link_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    throughput = Column(Float, nullable=False)
    utilization = Column(Float, nullable=False)
    errors = Column(Integer, nullable=False)
    discards = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    additional_metrics = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="link_metrics")

    def __repr__(self):
        return f"<LinkMetrics(id={self.id}, link_id={self.link_id}, timestamp={self.timestamp})>"

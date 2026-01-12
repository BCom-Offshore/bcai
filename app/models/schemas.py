from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AnomalyType(str, Enum):
    NETWORK = "network"
    SITE = "site"
    LINK = "link"


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company: str = "BCom Offshore SAL"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    company: str
    created_at: datetime


class NetworkMetrics(BaseModel):
    timestamp: datetime
    network_id: str
    bandwidth_usage: float
    packet_loss: float
    latency: float
    error_rate: float
    connection_count: int
    additional_metrics: Optional[Dict[str, Any]] = None


class SiteMetrics(BaseModel):
    timestamp: datetime
    site_id: str
    response_time: float
    uptime_percentage: float
    request_count: int
    error_count: int
    cpu_usage: float
    memory_usage: float
    additional_metrics: Optional[Dict[str, Any]] = None


class LinkMetrics(BaseModel):
    timestamp: datetime
    link_id: str
    throughput: float
    utilization: float
    errors: int
    discards: int
    status: str
    additional_metrics: Optional[Dict[str, Any]] = None


class AnomalyDetectionRequest(BaseModel):
    anomaly_type: AnomalyType
    data: List[Dict[str, Any]]
    sensitivity: float = Field(default=0.95, ge=0.0, le=1.0)
    lookback_window: int = Field(default=100, ge=10, le=1000)


class AnomalyResult(BaseModel):
    anomaly_detected: bool
    anomaly_score: float
    affected_metrics: List[str]
    severity: str
    timestamp: datetime
    recommendations: List[str]


class RecommendationRequest(BaseModel):
    context: str
    entity_id: str
    historical_data: Optional[List[Dict[str, Any]]] = None
    max_recommendations: int = Field(default=5, ge=1, le=20)


class Recommendation(BaseModel):
    id: str
    title: str
    description: str
    priority: str
    expected_impact: str
    implementation_steps: List[str]
    confidence_score: float


class AnomalyDetectionResponse(BaseModel):
    request_id: str
    anomaly_type: AnomalyType
    results: List[AnomalyResult]
    overall_status: str
    timestamp: datetime


class RecommendationResponse(BaseModel):
    request_id: str
    recommendations: List[Recommendation]
    timestamp: datetime

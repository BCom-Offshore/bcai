from fastapi import APIRouter
from app.api.v1.endpoints import auth, anomaly_detection, recommendations, monitoring

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(anomaly_detection.router, prefix="/anomaly-detection", tags=["Anomaly Detection"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["Monitoring"])

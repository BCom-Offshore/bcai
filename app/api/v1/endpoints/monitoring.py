from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict
from datetime import datetime, timedelta
import uuid

from app.models.schemas import NetworkMetrics, SiteMetrics, LinkMetrics
from app.models.models import NetworkMetrics as NetworkMetricsModel, SiteMetrics as SiteMetricsModel, LinkMetrics as LinkMetricsModel
from app.core.database import get_db
from app.core.rate_limiter import limiter

router = APIRouter()


@router.post("/network-metrics")
@limiter.limit("100/minute")
async def store_network_metrics(
    metrics: NetworkMetrics,
    
    db: Session = Depends(get_db),
    request=None
):
    try:
        network_metric = NetworkMetricsModel(
            id=uuid.uuid4(),
            user_id=None,
            network_id=metrics.network_id,
            timestamp=metrics.timestamp,
            bandwidth_usage=metrics.bandwidth_usage,
            packet_loss=metrics.packet_loss,
            latency=metrics.latency,
            error_rate=metrics.error_rate,
            connection_count=metrics.connection_count,
            additional_metrics=metrics.additional_metrics
        )

        db.add(network_metric)
        db.commit()
        db.refresh(network_metric)

        return {"message": "Network metrics stored successfully", "data": network_metric}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store network metrics: {str(e)}"
        )


@router.post("/site-metrics")
@limiter.limit("100/minute")
async def store_site_metrics(
    metrics: SiteMetrics,
    
    db: Session = Depends(get_db),
    request=None
):
    try:
        site_metric = SiteMetricsModel(
            id=uuid.uuid4(),
            user_id=None,
            site_id=metrics.site_id,
            timestamp=metrics.timestamp,
            response_time=metrics.response_time,
            uptime_percentage=metrics.uptime_percentage,
            request_count=metrics.request_count,
            error_count=metrics.error_count,
            cpu_usage=metrics.cpu_usage,
            memory_usage=metrics.memory_usage,
            additional_metrics=metrics.additional_metrics
        )

        db.add(site_metric)
        db.commit()
        db.refresh(site_metric)

        return {"message": "Site metrics stored successfully", "data": site_metric}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store site metrics: {str(e)}"
        )


@router.post("/link-metrics")
@limiter.limit("100/minute")
async def store_link_metrics(
    metrics: LinkMetrics,
    
    db: Session = Depends(get_db),
    request=None
):
    try:
        link_metric = LinkMetricsModel(
            id=uuid.uuid4(),
            user_id=None,
            link_id=metrics.link_id,
            timestamp=metrics.timestamp,
            throughput=metrics.throughput,
            utilization=metrics.utilization,
            errors=metrics.errors,
            discards=metrics.discards,
            status=metrics.status,
            additional_metrics=metrics.additional_metrics
        )

        db.add(link_metric)
        db.commit()
        db.refresh(link_metric)

        return {"message": "Link metrics stored successfully", "data": link_metric}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store link metrics: {str(e)}"
        )


@router.get("/network-metrics/{network_id}")
@limiter.limit("50/minute")
async def get_network_metrics(
    network_id: str,
    
    db: Session = Depends(get_db),
    hours: int = 24,
    request=None
):
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)

        metrics = db.query(NetworkMetricsModel) \
            .filter(
                NetworkMetricsModel.user_id == None,
                NetworkMetricsModel.network_id == network_id,
                NetworkMetricsModel.timestamp >= start_time
            ) \
            .order_by(NetworkMetricsModel.timestamp.desc()) \
            .all()

        return {"metrics": metrics, "count": len(metrics)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve network metrics: {str(e)}"
        )


@router.get("/site-metrics/{site_id}")
@limiter.limit("50/minute")
async def get_site_metrics(
    site_id: str,
    
    db: Session = Depends(get_db),
    hours: int = 24,
    request=None
):
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)

        metrics = db.query(SiteMetricsModel) \
            .filter(
                SiteMetricsModel.user_id == None,
                SiteMetricsModel.site_id == site_id,
                SiteMetricsModel.timestamp >= start_time
            ) \
            .order_by(SiteMetricsModel.timestamp.desc()) \
            .all()

        return {"metrics": metrics, "count": len(metrics)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve site metrics: {str(e)}"
        )


@router.get("/link-metrics/{link_id}")
@limiter.limit("50/minute")
async def get_link_metrics(
    link_id: str,
    
    db: Session = Depends(get_db),
    hours: int = 24,
    request=None
):
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)

        metrics = db.query(LinkMetricsModel) \
            .filter(
                LinkMetricsModel.user_id == None,
                LinkMetricsModel.link_id == link_id,
                LinkMetricsModel.timestamp >= start_time
            ) \
            .order_by(LinkMetricsModel.timestamp.desc()) \
            .all()

        return {"metrics": metrics, "count": len(metrics)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve link metrics: {str(e)}"
        )

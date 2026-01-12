"""
Rate limiting configuration for API endpoints.
Uses slowapi to prevent abuse and DoS attacks.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Global limiter instance
limiter = Limiter(key_func=get_remote_address)

# Rate limit policies
RATE_LIMITS = {
    # Authentication endpoints (more restrictive)
    "auth_register": "5/day",           # 5 registrations per day per IP
    "auth_login": "20/hour",            # 20 login attempts per hour per IP
    "auth_me": "100/minute",            # User profile queries

    # Anomaly detection endpoints
    "anomaly_detect": "60/minute",      # 60 detection requests per minute
    "anomaly_batch": "30/minute",       # 30 batch requests per minute
    "anomaly_history": "100/minute",    # History queries (read-only)
    "anomaly_statistics": "100/minute", # Stats queries (read-only)

    # Recommendation endpoints
    "recommendation_generate": "40/minute",      # 40 generation requests per minute
    "recommendation_by_priority": "100/minute",  # Read-only
    "recommendation_by_tags": "100/minute",      # Read-only

    # Monitoring/metrics endpoints
    "metrics_network": "100/minute",    # Metrics submissions (write-heavy)
    "metrics_site": "100/minute",
    "metrics_link": "100/minute",

    # Default for unlisted endpoints
    "default": "200/minute"
}


def get_rate_limit(endpoint_type: str) -> str:
    """
    Get rate limit string for an endpoint type.
    Returns default if endpoint_type not found.
    """
    return RATE_LIMITS.get(endpoint_type, RATE_LIMITS["default"])

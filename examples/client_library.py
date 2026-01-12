"""
BCom AI Services API - Python Client Library
A simple wrapper library for easy integration
"""

import requests
from typing import List, Dict, Any, Optional
from datetime import datetime


class BComAIException(Exception):
    """Base exception for BCom AI API"""
    pass


class BComAIAuthenticationError(BComAIException):
    """Authentication related errors"""
    pass


class BComAIValidationError(BComAIException):
    """Validation errors"""
    pass


class BComAI:
    """
    BCom AI Services API Client

    Usage:
        client = BComAI(base_url="http://localhost:8010/api/v1")
        client.login("user@bcom.com", "password")
        result = client.detect_anomalies("network", data)
    """

    def __init__(self, base_url: str = "http://localhost:8010/api/v1"):
        """
        Initialize the client

        Args:
            base_url: Base URL of the API
        """
        self.base_url = base_url.rstrip('/')
        self.token: Optional[str] = None
        self.session = requests.Session()

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        auth_required: bool = True
    ) -> Dict:
        """Make HTTP request to API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        headers = {"Content-Type": "application/json"}
        if auth_required:
            if not self.token:
                raise BComAIAuthenticationError("Not authenticated. Please login first.")
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise BComAIAuthenticationError("Authentication failed")
            elif e.response.status_code == 400:
                raise BComAIValidationError(f"Validation error: {e.response.text}")
            else:
                raise BComAIException(f"API error: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise BComAIException(f"Request failed: {str(e)}")

    def register(
        self,
        email: str,
        password: str,
        full_name: str,
        company: str = "BCom Offshore SAL"
    ) -> Dict:
        """
        Register a new user

        Args:
            email: User email
            password: User password
            full_name: Full name
            company: Company name

        Returns:
            User information
        """
        return self._make_request(
            "POST",
            "/auth/register",
            data={
                "email": email,
                "password": password,
                "full_name": full_name,
                "company": company
            },
            auth_required=False
        )

    def login(self, email: str, password: str) -> str:
        """
        Login and get access token

        Args:
            email: User email
            password: User password

        Returns:
            Access token
        """
        result = self._make_request(
            "POST",
            "/auth/login",
            data={"email": email, "password": password},
            auth_required=False
        )
        self.token = result["access_token"]
        return self.token

    def get_current_user(self) -> Dict:
        """Get current user information"""
        return self._make_request("GET", "/auth/me")

    def detect_anomalies(
        self,
        anomaly_type: str,
        data: List[Dict],
        sensitivity: float = 0.95,
        lookback_window: int = 100
    ) -> Dict:
        """
        Detect anomalies

        Args:
            anomaly_type: Type of anomaly (network, site, link)
            data: List of metrics data
            sensitivity: Detection sensitivity (0.0 - 1.0)
            lookback_window: Number of records to analyze (10 - 1000)

        Returns:
            Detection results
        """
        return self._make_request(
            "POST",
            "/anomaly-detection/detect",
            data={
                "anomaly_type": anomaly_type,
                "data": data,
                "sensitivity": sensitivity,
                "lookback_window": lookback_window
            }
        )

    def batch_detect_anomalies(self, requests: List[Dict]) -> List[Dict]:
        """Batch anomaly detection"""
        return self._make_request(
            "POST",
            "/anomaly-detection/batch-detect",
            data=requests
        )

    def get_detection_history(self, limit: int = 50) -> Dict:
        """Get anomaly detection history"""
        return self._make_request(
            "GET",
            "/anomaly-detection/history",
            params={"limit": limit}
        )

    def get_detection_statistics(self) -> Dict:
        """Get anomaly detection statistics"""
        return self._make_request("GET", "/anomaly-detection/statistics")

    def generate_recommendations(
        self,
        context: str,
        entity_id: str,
        historical_data: Optional[List[Dict]] = None,
        max_recommendations: int = 5
    ) -> Dict:
        """
        Generate recommendations

        Args:
            context: Context description
            entity_id: Entity identifier
            historical_data: Optional historical data
            max_recommendations: Maximum number of recommendations

        Returns:
            Recommendations
        """
        return self._make_request(
            "POST",
            "/recommendations/generate",
            data={
                "context": context,
                "entity_id": entity_id,
                "historical_data": historical_data,
                "max_recommendations": max_recommendations
            }
        )

    def get_recommendations_by_priority(self, priority: str) -> Dict:
        """Get recommendations by priority"""
        return self._make_request(
            "GET",
            f"/recommendations/by-priority/{priority}"
        )

    def get_recommendations_by_tags(self, tags: List[str]) -> Dict:
        """Get recommendations by tags"""
        return self._make_request(
            "POST",
            "/recommendations/by-tags",
            data=tags
        )

    def store_network_metrics(self, metrics: Dict) -> Dict:
        """Store network metrics"""
        return self._make_request(
            "POST",
            "/monitoring/network-metrics",
            data=metrics
        )

    def store_site_metrics(self, metrics: Dict) -> Dict:
        """Store site metrics"""
        return self._make_request(
            "POST",
            "/monitoring/site-metrics",
            data=metrics
        )

    def store_link_metrics(self, metrics: Dict) -> Dict:
        """Store link metrics"""
        return self._make_request(
            "POST",
            "/monitoring/link-metrics",
            data=metrics
        )

    def get_network_metrics(
        self,
        network_id: str,
        hours: int = 24
    ) -> Dict:
        """Get network metrics"""
        return self._make_request(
            "GET",
            f"/monitoring/network-metrics/{network_id}",
            params={"hours": hours}
        )

    def get_site_metrics(self, site_id: str, hours: int = 24) -> Dict:
        """Get site metrics"""
        return self._make_request(
            "GET",
            f"/monitoring/site-metrics/{site_id}",
            params={"hours": hours}
        )

    def get_link_metrics(self, link_id: str, hours: int = 24) -> Dict:
        """Get link metrics"""
        return self._make_request(
            "GET",
            f"/monitoring/link-metrics/{link_id}",
            params={"hours": hours}
        )

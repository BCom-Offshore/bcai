"""
Example usage of BCom AI Services API
This script demonstrates how to use the API for anomaly detection and recommendations.
"""

import requests
from datetime import datetime, timedelta
import json


class BComAIClient:
    def __init__(self, base_url="http://localhost:8010/api/v1"):
        self.base_url = base_url
        self.token = None

    def register(self, email, password, full_name, company="BCom Offshore SAL"):
        """Register a new user"""
        response = requests.post(
            f"{self.base_url}/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": full_name,
                "company": company
            }
        )
        response.raise_for_status()
        return response.json()

    def login(self, email, password):
        """Login and get access token"""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={
                "email": email,
                "password": password
            }
        )
        response.raise_for_status()
        self.token = response.json()["access_token"]
        return self.token

    def get_headers(self):
        """Get authorization headers"""
        if not self.token:
            raise Exception("Not authenticated. Please login first.")
        return {"Authorization": f"Bearer {self.token}"}

    def detect_network_anomalies(self, data, sensitivity=0.95):
        """Detect network anomalies"""
        response = requests.post(
            f"{self.base_url}/anomaly-detection/detect",
            headers=self.get_headers(),
            json={
                "anomaly_type": "network",
                "data": data,
                "sensitivity": sensitivity
            }
        )
        response.raise_for_status()
        return response.json()

    def detect_site_anomalies(self, data, sensitivity=0.95):
        """Detect site anomalies"""
        response = requests.post(
            f"{self.base_url}/anomaly-detection/detect",
            headers=self.get_headers(),
            json={
                "anomaly_type": "site",
                "data": data,
                "sensitivity": sensitivity
            }
        )
        response.raise_for_status()
        return response.json()

    def detect_link_anomalies(self, data, sensitivity=0.95):
        """Detect link anomalies"""
        response = requests.post(
            f"{self.base_url}/anomaly-detection/detect",
            headers=self.get_headers(),
            json={
                "anomaly_type": "link",
                "data": data,
                "sensitivity": sensitivity
            }
        )
        response.raise_for_status()
        return response.json()

    def generate_recommendations(self, context, entity_id, max_recommendations=5):
        """Generate recommendations"""
        response = requests.post(
            f"{self.base_url}/recommendations/generate",
            headers=self.get_headers(),
            json={
                "context": context,
                "entity_id": entity_id,
                "max_recommendations": max_recommendations
            }
        )
        response.raise_for_status()
        return response.json()

    def store_network_metrics(self, metrics):
        """Store network metrics"""
        response = requests.post(
            f"{self.base_url}/monitoring/network-metrics",
            headers=self.get_headers(),
            json=metrics
        )
        response.raise_for_status()
        return response.json()

    def get_network_metrics(self, network_id, hours=24):
        """Get network metrics"""
        response = requests.get(
            f"{self.base_url}/monitoring/network-metrics/{network_id}",
            headers=self.get_headers(),
            params={"hours": hours}
        )
        response.raise_for_status()
        return response.json()


def generate_sample_network_data(num_samples=50):
    """Generate sample network metrics data"""
    import random
    data = []
    base_time = datetime.utcnow() - timedelta(hours=1)

    for i in range(num_samples):
        timestamp = base_time + timedelta(minutes=i)

        is_anomaly = random.random() < 0.1

        if is_anomaly:
            bandwidth = random.uniform(90, 100)
            packet_loss = random.uniform(3, 10)
            latency = random.uniform(100, 300)
            error_rate = random.uniform(0.1, 0.5)
            connection_count = random.randint(200, 300)
        else:
            bandwidth = random.uniform(40, 80)
            packet_loss = random.uniform(0, 1)
            latency = random.uniform(20, 60)
            error_rate = random.uniform(0, 0.05)
            connection_count = random.randint(50, 150)

        data.append({
            "timestamp": timestamp.isoformat(),
            "network_id": "net_001",
            "bandwidth_usage": bandwidth,
            "packet_loss": packet_loss,
            "latency": latency,
            "error_rate": error_rate,
            "connection_count": connection_count
        })

    return data


def main():
    """Main example function"""

    client = BComAIClient()

    print("=" * 60)
    print("BCom AI Services API - Example Usage")
    print("=" * 60)

    print("\n1. User Registration and Login")
    print("-" * 60)

    email = "demo@bcom.com"
    password = "securepassword123"

    try:
        user = client.register(
            email=email,
            password=password,
            full_name="Demo User"
        )
        print(f"✓ User registered: {user['email']}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            print("ℹ User already exists, proceeding with login")
        else:
            raise

    token = client.login(email, password)
    print(f"✓ Login successful")
    print(f"  Token: {token[:20]}...")

    print("\n2. Network Anomaly Detection")
    print("-" * 60)

    network_data = generate_sample_network_data(num_samples=100)
    print(f"Generated {len(network_data)} network metrics samples")

    detection_result = client.detect_network_anomalies(
        data=network_data,
        sensitivity=0.95
    )

    print(f"\n✓ Anomaly Detection Results:")
    print(f"  Request ID: {detection_result['request_id']}")
    print(f"  Overall Status: {detection_result['overall_status']}")
    print(f"  Anomalies Found: {len(detection_result['results'])}")

    if detection_result['results']:
        print(f"\n  Anomaly Details:")
        for idx, anomaly in enumerate(detection_result['results'][:3], 1):
            print(f"\n  Anomaly #{idx}:")
            print(f"    Severity: {anomaly['severity']}")
            print(f"    Score: {anomaly['anomaly_score']:.2f}")
            print(f"    Affected Metrics: {', '.join(anomaly['affected_metrics'])}")
            print(f"    Recommendations:")
            for rec in anomaly['recommendations'][:2]:
                print(f"      - {rec}")

    print("\n3. Generate Recommendations")
    print("-" * 60)

    recommendations = client.generate_recommendations(
        context="network optimization",
        entity_id="net_001",
        max_recommendations=3
    )

    print(f"✓ Generated {len(recommendations['recommendations'])} recommendations:")

    for idx, rec in enumerate(recommendations['recommendations'], 1):
        print(f"\n  Recommendation #{idx}:")
        print(f"    Title: {rec['title']}")
        print(f"    Priority: {rec['priority']}")
        print(f"    Confidence: {rec['confidence_score']:.2f}")
        print(f"    Impact: {rec['expected_impact']}")
        print(f"    Steps:")
        for step in rec['implementation_steps'][:3]:
            print(f"      - {step}")

    print("\n4. Store Metrics")
    print("-" * 60)

    current_metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "network_id": "net_001",
        "bandwidth_usage": 75.5,
        "packet_loss": 0.3,
        "latency": 35.2,
        "error_rate": 0.02,
        "connection_count": 120
    }

    store_result = client.store_network_metrics(current_metrics)
    print(f"✓ Metrics stored successfully")
    print(f"  Metric ID: {store_result['data']['id']}")

    print("\n5. Retrieve Historical Metrics")
    print("-" * 60)

    historical = client.get_network_metrics("net_001", hours=24)
    print(f"✓ Retrieved {historical['count']} historical metrics")

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

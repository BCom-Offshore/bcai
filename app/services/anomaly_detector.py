import numpy as np
import pandas as pd
import polars as pl
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.covariance import EllipticEnvelope
from typing import List, Dict, Any, Tuple
from datetime import datetime
import logging
import pickle
import hashlib

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    ML-based anomaly detection engine with caching support.
    Supports caching of trained models to avoid retraining.
    """

    def __init__(self, contamination: float = 0.05, cache_enabled: bool = True):
        """
        Initialize anomaly detector.

        Args:
            contamination: Expected proportion of outliers in dataset
            cache_enabled: Enable model caching for performance
        """
        self.contamination = contamination
        self.cache_enabled = cache_enabled
        self.scaler = StandardScaler()
        self.isolation_forest = None
        self.elliptic_envelope = None
        self._model_hash = None  # For cache key generation

    def _prepare_data(self, data: List[Dict[str, Any]], feature_columns: List[str]) -> Tuple[np.ndarray, pl.DataFrame]:
        df = pl.DataFrame(data)

        numeric_cols = [col for col in feature_columns if col in df.columns and df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]

        if not numeric_cols:
            raise ValueError("No numeric columns found in the data")

        df_numeric = df.select(numeric_cols).fill_null(0)
        X = df_numeric.to_numpy()

        return X, df

    def _calculate_data_hash(self, data: np.ndarray) -> str:
        """
        Calculate hash of data array for cache key generation.
        Uses shape and first few values to identify similar data patterns.
        """
        hash_input = f"{data.shape}_{data.dtype}_{data.flat[:10].tobytes()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]

    def _get_cached_detector(self, anomaly_type: str, feature_columns: List[str]) -> 'AnomalyDetector':
        """
        Try to get a cached detector instance.
        Falls back to None if caching is disabled.
        """
        if not self.cache_enabled:
            return None

        try:
            from app.services.model_cache import get_model_cache
            cache = get_model_cache()
            cached_detector = cache.get(anomaly_type, len(feature_columns), 1)
            return cached_detector
        except ImportError:
            logger.warning("Model cache not available, skipping cache lookup")
            return None

    def _cache_detector(self, anomaly_type: str, feature_columns: List[str]) -> None:
        """
        Cache the current detector instance.
        """
        if not self.cache_enabled:
            return

        try:
            from app.services.model_cache import get_model_cache
            cache = get_model_cache()
            cache.set(anomaly_type, len(feature_columns), 1, self)
        except ImportError:
            logger.warning("Model cache not available, skipping cache storage")
            return

    def detect_network_anomalies(self, data: List[Dict[str, Any]], sensitivity: float = 0.95) -> List[Dict[str, Any]]:
        feature_columns = ['bandwidth_usage', 'packet_loss', 'latency', 'error_rate', 'connection_count']

        try:
            X, df = self._prepare_data(data, feature_columns)

            if len(X) < 10:
                logger.warning("Insufficient data for anomaly detection")
                return []

            contamination = 1 - sensitivity
            self.isolation_forest = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100
            )

            X_scaled = self.scaler.fit_transform(X)
            predictions = self.isolation_forest.fit_predict(X_scaled)
            anomaly_scores = self.isolation_forest.score_samples(X_scaled)

            anomalies = []
            for idx, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
                if pred == -1:
                    affected_metrics = self._identify_affected_metrics(X[idx], X, feature_columns)
                    severity = self._calculate_severity(score, anomaly_scores)

                    anomalies.append({
                        'index': idx,
                        'anomaly_detected': True,
                        'anomaly_score': float(abs(score)),
                        'affected_metrics': affected_metrics,
                        'severity': severity,
                        'timestamp': data[idx].get('timestamp', datetime.utcnow()),
                        'recommendations': self._generate_network_recommendations(affected_metrics, severity)
                    })

            return anomalies

        except Exception as e:
            logger.error(f"Error in network anomaly detection: {str(e)}")
            raise

    def detect_site_anomalies(self, data: List[Dict[str, Any]], sensitivity: float = 0.95) -> List[Dict[str, Any]]:
        feature_columns = ['response_time', 'uptime_percentage', 'request_count', 'error_count', 'cpu_usage', 'memory_usage']

        try:
            X, df = self._prepare_data(data, feature_columns)

            if len(X) < 10:
                logger.warning("Insufficient data for anomaly detection")
                return []

            contamination = 1 - sensitivity
            self.isolation_forest = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100
            )

            X_scaled = self.scaler.fit_transform(X)
            predictions = self.isolation_forest.fit_predict(X_scaled)
            anomaly_scores = self.isolation_forest.score_samples(X_scaled)

            anomalies = []
            for idx, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
                if pred == -1:
                    affected_metrics = self._identify_affected_metrics(X[idx], X, feature_columns)
                    severity = self._calculate_severity(score, anomaly_scores)

                    anomalies.append({
                        'index': idx,
                        'anomaly_detected': True,
                        'anomaly_score': float(abs(score)),
                        'affected_metrics': affected_metrics,
                        'severity': severity,
                        'timestamp': data[idx].get('timestamp', datetime.utcnow()),
                        'recommendations': self._generate_site_recommendations(affected_metrics, severity)
                    })

            return anomalies

        except Exception as e:
            logger.error(f"Error in site anomaly detection: {str(e)}")
            raise

    def detect_link_anomalies(self, data: List[Dict[str, Any]], sensitivity: float = 0.95) -> List[Dict[str, Any]]:
        feature_columns = ['throughput', 'utilization', 'errors', 'discards']

        try:
            X, df = self._prepare_data(data, feature_columns)

            if len(X) < 10:
                logger.warning("Insufficient data for anomaly detection")
                return []

            contamination = 1 - sensitivity
            self.isolation_forest = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100
            )

            X_scaled = self.scaler.fit_transform(X)
            predictions = self.isolation_forest.fit_predict(X_scaled)
            anomaly_scores = self.isolation_forest.score_samples(X_scaled)

            anomalies = []
            for idx, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
                if pred == -1:
                    affected_metrics = self._identify_affected_metrics(X[idx], X, feature_columns)
                    severity = self._calculate_severity(score, anomaly_scores)

                    anomalies.append({
                        'index': idx,
                        'anomaly_detected': True,
                        'anomaly_score': float(abs(score)),
                        'affected_metrics': affected_metrics,
                        'severity': severity,
                        'timestamp': data[idx].get('timestamp', datetime.utcnow()),
                        'recommendations': self._generate_link_recommendations(affected_metrics, severity)
                    })

            return anomalies

        except Exception as e:
            logger.error(f"Error in link anomaly detection: {str(e)}")
            raise

    def _identify_affected_metrics(self, sample: np.ndarray, all_samples: np.ndarray, feature_names: List[str]) -> List[str]:
        affected = []
        means = np.mean(all_samples, axis=0)
        stds = np.std(all_samples, axis=0)

        for idx, (value, mean, std) in enumerate(zip(sample, means, stds)):
            if std > 0 and abs(value - mean) > 2 * std:
                affected.append(feature_names[idx])

        return affected if affected else feature_names[:1]

    def _calculate_severity(self, score: float, all_scores: np.ndarray) -> str:
        score_abs = abs(score)
        percentile = np.percentile(np.abs(all_scores), 90)

        if score_abs > percentile * 1.5:
            return "critical"
        elif score_abs > percentile:
            return "high"
        elif score_abs > percentile * 0.5:
            return "medium"
        else:
            return "low"

    def _generate_network_recommendations(self, affected_metrics: List[str], severity: str) -> List[str]:
        recommendations = []

        if 'bandwidth_usage' in affected_metrics:
            recommendations.append("Monitor bandwidth consumption and consider upgrading capacity")
        if 'packet_loss' in affected_metrics:
            recommendations.append("Check network equipment and cable connections for packet loss")
        if 'latency' in affected_metrics:
            recommendations.append("Investigate routing paths and potential bottlenecks")
        if 'error_rate' in affected_metrics:
            recommendations.append("Review error logs and check for hardware issues")
        if 'connection_count' in affected_metrics:
            recommendations.append("Analyze connection patterns and consider load balancing")

        if severity in ['critical', 'high']:
            recommendations.append("Immediate investigation recommended - potential service impact")

        return recommendations if recommendations else ["Review network metrics and establish baseline"]

    def _generate_site_recommendations(self, affected_metrics: List[str], severity: str) -> List[str]:
        recommendations = []

        if 'response_time' in affected_metrics:
            recommendations.append("Optimize database queries and implement caching strategies")
        if 'uptime_percentage' in affected_metrics:
            recommendations.append("Investigate recent downtime and implement redundancy")
        if 'error_count' in affected_metrics:
            recommendations.append("Review application logs and fix recurring errors")
        if 'cpu_usage' in affected_metrics:
            recommendations.append("Consider scaling compute resources or optimizing CPU-intensive tasks")
        if 'memory_usage' in affected_metrics:
            recommendations.append("Check for memory leaks and optimize memory allocation")

        if severity in ['critical', 'high']:
            recommendations.append("Critical issue detected - immediate action required")

        return recommendations if recommendations else ["Monitor site performance metrics"]

    def _generate_link_recommendations(self, affected_metrics: List[str], severity: str) -> List[str]:
        recommendations = []

        if 'throughput' in affected_metrics:
            recommendations.append("Verify link capacity and check for congestion")
        if 'utilization' in affected_metrics:
            recommendations.append("Consider link upgrade or traffic optimization")
        if 'errors' in affected_metrics:
            recommendations.append("Inspect physical connections and replace faulty equipment")
        if 'discards' in affected_metrics:
            recommendations.append("Review QoS policies and buffer configurations")

        if severity in ['critical', 'high']:
            recommendations.append("High-priority link issue - potential connectivity impact")

        return recommendations if recommendations else ["Monitor link health metrics"]

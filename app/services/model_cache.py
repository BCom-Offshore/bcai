"""
ML Model caching module for efficient anomaly detection.
Caches trained models to avoid retraining on each request.
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import threading
from app.services.anomaly_detector import AnomalyDetector

logger = logging.getLogger(__name__)


class ModelCache:
    """
    Cache for trained ML models with TTL and eviction policies.
    Prevents retraining models for similar data patterns.
    """

    def __init__(self, ttl_minutes: int = 60, max_cache_size: int = 10):
        """
        Initialize model cache.

        Args:
            ttl_minutes: Time-to-live for cached models in minutes
            max_cache_size: Maximum number of models to cache
        """
        self.ttl_minutes = ttl_minutes
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.RLock()  # Thread-safe cache operations

    def _generate_cache_key(self, anomaly_type: str, feature_count: int, data_size: int) -> str:
        """
        Generate a cache key based on anomaly type and data characteristics.

        Args:
            anomaly_type: Type of anomaly (network, site, link)
            feature_count: Number of features in data
            data_size: Number of data points

        Returns:
            Cache key string
        """
        return f"{anomaly_type}_{feature_count}_{data_size}"

    def get(self, anomaly_type: str, feature_count: int, data_size: int) -> Optional[AnomalyDetector]:
        """
        Retrieve a cached model if available and not expired.

        Args:
            anomaly_type: Type of anomaly
            feature_count: Number of features
            data_size: Size of data

        Returns:
            Cached AnomalyDetector instance or None
        """
        with self._lock:
            cache_key = self._generate_cache_key(anomaly_type, feature_count, data_size)

            if cache_key not in self._cache:
                logger.debug(f"Cache miss for key: {cache_key}")
                return None

            cached_item = self._cache[cache_key]

            # Check if cache entry has expired
            if datetime.utcnow() > cached_item["expires_at"]:
                logger.info(f"Cache entry expired for key: {cache_key}")
                del self._cache[cache_key]
                return None

            logger.debug(f"Cache hit for key: {cache_key}")
            cached_item["hits"] += 1
            cached_item["last_accessed"] = datetime.utcnow()
            return cached_item["model"]

    def set(
        self,
        anomaly_type: str,
        feature_count: int,
        data_size: int,
        model: AnomalyDetector
    ) -> None:
        """
        Cache a trained model.

        Args:
            anomaly_type: Type of anomaly
            feature_count: Number of features
            data_size: Size of data
            model: Trained AnomalyDetector instance
        """
        with self._lock:
            cache_key = self._generate_cache_key(anomaly_type, feature_count, data_size)

            # Check cache size and evict if necessary
            if len(self._cache) >= self.max_cache_size:
                self._evict_least_used()

            self._cache[cache_key] = {
                "model": model,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(minutes=self.ttl_minutes),
                "hits": 0,
                "last_accessed": datetime.utcnow(),
            }
            logger.info(f"Model cached for key: {cache_key}")

    def _evict_least_used(self) -> None:
        """Evict the least recently used model from cache."""
        if not self._cache:
            return

        # Find least recently used (by hits and access time)
        least_used_key = min(
            self._cache.keys(),
            key=lambda k: (
                self._cache[k]["hits"],
                self._cache[k]["last_accessed"]
            )
        )

        del self._cache[least_used_key]
        logger.info(f"Evicted least used model: {least_used_key}")

    def clear(self) -> None:
        """Clear all cached models."""
        with self._lock:
            size = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {size} models from cache")

    def cleanup_expired(self) -> int:
        """
        Remove expired models from cache.

        Returns:
            Number of models removed
        """
        with self._lock:
            expired_keys = [
                key
                for key, item in self._cache.items()
                if datetime.utcnow() > item["expires_at"]
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired models")

            return len(expired_keys)

    def get_stats(self) -> Dict:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total_hits = sum(item["hits"] for item in self._cache.values())
            return {
                "size": len(self._cache),
                "max_size": self.max_cache_size,
                "ttl_minutes": self.ttl_minutes,
                "total_hits": total_hits,
                "models": [
                    {
                        "key": key,
                        "hits": item["hits"],
                        "created_at": item["created_at"].isoformat(),
                        "expires_at": item["expires_at"].isoformat(),
                        "last_accessed": item["last_accessed"].isoformat(),
                    }
                    for key, item in self._cache.items()
                ]
            }


# Global cache instance
model_cache = ModelCache(ttl_minutes=60, max_cache_size=10)


def get_model_cache() -> ModelCache:
    """Get the global model cache instance."""
    return model_cache

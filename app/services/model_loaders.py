"""
ML Model Integration Utilities

This module provides helper functions to integrate pre-trained ML models
with the anomaly detection and recommendation services.
"""

import logging
from typing import Any, Optional, Dict
from datetime import datetime
from app.services.model_management import ModelManager, ModelMetadata

logger = logging.getLogger(__name__)


class AnomalyDetectorModelLoader:
    """
    Helper class to load and manage anomaly detection models.
    """

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.category = "anomaly_detection"
        self.cached_models: Dict[str, Any] = {}

    def load_network_detector(self, version: Optional[str] = None) -> Optional[Any]:
        """
        Load the network anomaly detection model.

        Args:
            version: Specific version to load, None for latest

        Returns:
            The loaded model or None if not found
        """
        model_name = "isolation_forest_network"

        # Check cache first
        cache_key = f"{model_name}_{version or 'latest'}"
        if cache_key in self.cached_models:
            logger.debug(f"Loaded {model_name} from cache")
            return self.cached_models[cache_key]

        # Load from disk
        if version:
            model, _ = self.model_manager.load_model(
                model_name, self.category, version
            )
        else:
            model, _, version = self.model_manager.load_latest_model(
                model_name, self.category
            )

        if model:
            self.cached_models[cache_key] = model
            logger.info(
                f"Loaded {model_name} version {version or 'latest'} from disk"
            )

        return model

    def load_site_detector(self, version: Optional[str] = None) -> Optional[Any]:
        """
        Load the site anomaly detection model.

        Args:
            version: Specific version to load, None for latest

        Returns:
            The loaded model or None if not found
        """
        model_name = "isolation_forest_site"

        # Check cache first
        cache_key = f"{model_name}_{version or 'latest'}"
        if cache_key in self.cached_models:
            logger.debug(f"Loaded {model_name} from cache")
            return self.cached_models[cache_key]

        # Load from disk
        if version:
            model, _ = self.model_manager.load_model(
                model_name, self.category, version
            )
        else:
            model, _, version = self.model_manager.load_latest_model(
                model_name, self.category
            )

        if model:
            self.cached_models[cache_key] = model
            logger.info(
                f"Loaded {model_name} version {version or 'latest'} from disk"
            )

        return model

    def load_link_detector(self, version: Optional[str] = None) -> Optional[Any]:
        """
        Load the link anomaly detection model.

        Args:
            version: Specific version to load, None for latest

        Returns:
            The loaded model or None if not found
        """
        model_name = "isolation_forest_link"

        # Check cache first
        cache_key = f"{model_name}_{version or 'latest'}"
        if cache_key in self.cached_models:
            logger.debug(f"Loaded {model_name} from cache")
            return self.cached_models[cache_key]

        # Load from disk
        if version:
            model, _ = self.model_manager.load_model(
                model_name, self.category, version
            )
        else:
            model, _, version = self.model_manager.load_latest_model(
                model_name, self.category
            )

        if model:
            self.cached_models[cache_key] = model
            logger.info(
                f"Loaded {model_name} version {version or 'latest'} from disk"
            )

        return model

    def list_available_models(self) -> Dict[str, list[str]]:
        """
        List all available anomaly detection models and versions.

        Returns:
            Dictionary mapping model names to versions
        """
        return self.model_manager.list_models(self.category)

    def clear_cache(self) -> None:
        """Clear the model cache"""
        self.cached_models.clear()
        logger.debug("Model cache cleared")


class RecommendationModelLoader:
    """
    Helper class to load and manage recommendation models.
    """

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.category = "recommendations"
        self.cached_models: Dict[str, Any] = {}

    def load_ranking_model(self, version: Optional[str] = None) -> Optional[Any]:
        """
        Load the recommendation ranking model.

        Args:
            version: Specific version to load, None for latest

        Returns:
            The loaded model or None if not found
        """
        model_name = "ranking_model"

        # Check cache first
        cache_key = f"{model_name}_{version or 'latest'}"
        if cache_key in self.cached_models:
            logger.debug(f"Loaded {model_name} from cache")
            return self.cached_models[cache_key]

        # Load from disk
        if version:
            model, _ = self.model_manager.load_model(
                model_name, self.category, version
            )
        else:
            model, _, version = self.model_manager.load_latest_model(
                model_name, self.category
            )

        if model:
            self.cached_models[cache_key] = model
            logger.info(
                f"Loaded {model_name} version {version or 'latest'} from disk"
            )

        return model

    def load_priority_classifier(self, version: Optional[str] = None) -> Optional[Any]:
        """
        Load the recommendation priority classifier model.

        Args:
            version: Specific version to load, None for latest

        Returns:
            The loaded model or None if not found
        """
        model_name = "priority_classifier"

        # Check cache first
        cache_key = f"{model_name}_{version or 'latest'}"
        if cache_key in self.cached_models:
            logger.debug(f"Loaded {model_name} from cache")
            return self.cached_models[cache_key]

        # Load from disk
        if version:
            model, _ = self.model_manager.load_model(
                model_name, self.category, version
            )
        else:
            model, _, version = self.model_manager.load_latest_model(
                model_name, self.category
            )

        if model:
            self.cached_models[cache_key] = model
            logger.info(
                f"Loaded {model_name} version {version or 'latest'} from disk"
            )

        return model

    def list_available_models(self) -> Dict[str, list[str]]:
        """
        List all available recommendation models and versions.

        Returns:
            Dictionary mapping model names to versions
        """
        return self.model_manager.list_models(self.category)

    def clear_cache(self) -> None:
        """Clear the model cache"""
        self.cached_models.clear()
        logger.debug("Model cache cleared")


def create_model_metadata(
    model_name: str,
    model_type: str,
    description: str = "",
    hyperparameters: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, float]] = None,
) -> ModelMetadata:
    """
    Create a ModelMetadata object with current timestamp.

    Args:
        model_name: Name of the model
        model_type: Type of model (e.g., 'isolation_forest', 'gradient_boosting')
        description: Optional description
        hyperparameters: Optional dict of hyperparameters
        metrics: Optional dict of performance metrics

    Returns:
        ModelMetadata instance
    """
    return ModelMetadata(
        model_name=model_name,
        version="1.0.0",  # Should be updated based on your versioning scheme
        model_type=model_type,
        training_date=datetime.now().isoformat(),
        description=description,
        hyperparameters=hyperparameters or {},
        metrics=metrics or {},
    )

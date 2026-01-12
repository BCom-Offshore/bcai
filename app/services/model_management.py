"""
ML Model Management and Serialization Utilities

This module provides utilities for loading, saving, and managing
pre-trained ML models (pickle files) with versioning support.
"""

import pickle
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


class ModelMetadata:
    """
    Metadata for tracking ML models including version, training date, and checksum.
    """

    def __init__(
        self,
        model_name: str,
        version: str,
        model_type: str,
        training_date: str,
        description: str = "",
        hyperparameters: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, float]] = None,
        checksum: Optional[str] = None,
    ):
        self.model_name = model_name
        self.version = version
        self.model_type = model_type  # e.g., "isolation_forest", "gradient_boosting"
        self.training_date = training_date
        self.description = description
        self.hyperparameters = hyperparameters or {}
        self.metrics = metrics or {}
        self.checksum = checksum

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            "model_name": self.model_name,
            "version": self.version,
            "model_type": self.model_type,
            "training_date": self.training_date,
            "description": self.description,
            "hyperparameters": self.hyperparameters,
            "metrics": self.metrics,
            "checksum": self.checksum,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ModelMetadata":
        """Create metadata from dictionary"""
        return ModelMetadata(
            model_name=str(data.get("model_name", "")),
            version=str(data.get("version", "")),
            model_type=str(data.get("model_type", "")),
            training_date=str(data.get("training_date", "")),
            description=str(data.get("description", "")),
            hyperparameters=data.get("hyperparameters", {}),
            metrics=data.get("metrics", {}),
            checksum=data.get("checksum"),
        )


class ModelManager:
    """
    Manages ML model lifecycle including loading, saving, and versioning.
    """

    def __init__(self, models_dir: str):
        """
        Initialize ModelManager.

        Args:
            models_dir: Root directory containing model subdirectories
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model: Any,
        model_name: str,
        category: str,
        version: str,
        metadata: ModelMetadata,
    ) -> Tuple[bool, str]:
        """
        Save a model to pickle file with metadata.

        Args:
            model: The trained ML model object
            model_name: Name of the model (e.g., 'isolation_forest')
            category: Category ('anomaly_detection' or 'recommendations')
            version: Version string (e.g., '1.0.0')
            metadata: ModelMetadata object containing training info

        Returns:
            Tuple[success: bool, path: str] - Success status and file path
        """
        try:
            # Create category directory
            category_dir = self.models_dir / category
            category_dir.mkdir(parents=True, exist_ok=True)

            # Create model directory with version
            model_dir = category_dir / f"{model_name}_v{version}"
            model_dir.mkdir(parents=True, exist_ok=True)

            # Save model pickle
            model_path = model_dir / "model.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Calculate checksum
            with open(model_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            metadata.checksum = file_hash

            # Save metadata JSON
            metadata_path = model_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata.to_dict(), f, indent=2)

            logger.info(f"Model saved: {model_path}")
            logger.info(f"Metadata saved: {metadata_path}")

            return True, str(model_path)

        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            return False, str(e)

    def load_model(
        self, model_name: str, category: str, version: str
    ) -> Tuple[Optional[Any], Optional[ModelMetadata]]:
        """
        Load a model from pickle file with metadata.

        Args:
            model_name: Name of the model
            category: Category ('anomaly_detection' or 'recommendations')
            version: Version string (e.g., '1.0.0')

        Returns:
            Tuple[model, metadata] - Model object and metadata, or (None, None) if not found
        """
        try:
            model_dir = self.models_dir / category / f"{model_name}_v{version}"

            # Check if directory exists
            if not model_dir.exists():
                logger.warning(f"Model directory not found: {model_dir}")
                return None, None

            # Load model pickle
            model_path = model_dir / "model.pkl"
            if not model_path.exists():
                logger.warning(f"Model file not found: {model_path}")
                return None, None

            with open(model_path, "rb") as f:
                model = pickle.load(f)

            # Load metadata
            metadata = None
            metadata_path = model_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, "r") as f:
                    metadata_dict = json.load(f)
                metadata = ModelMetadata.from_dict(metadata_dict)

            logger.info(f"Model loaded: {model_path}")
            return model, metadata

        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return None, None

    def load_latest_model(
        self, model_name: str, category: str
    ) -> Tuple[Optional[Any], Optional[ModelMetadata], Optional[str]]:
        """
        Load the latest version of a model.

        Args:
            model_name: Name of the model
            category: Category ('anomaly_detection' or 'recommendations')

        Returns:
            Tuple[model, metadata, version] - Model, metadata, and version string
        """
        try:
            category_dir = self.models_dir / category
            if not category_dir.exists():
                return None, None, None

            # Find all versions of this model
            pattern = f"{model_name}_v*"
            matching_dirs = sorted(category_dir.glob(pattern), reverse=True)

            if not matching_dirs:
                logger.warning(f"No versions found for {model_name}")
                return None, None, None

            # Load the latest (first) version
            latest_dir = matching_dirs[0]
            version = latest_dir.name.replace(f"{model_name}_v", "")

            model_path = latest_dir / "model.pkl"
            with open(model_path, "rb") as f:
                model = pickle.load(f)

            metadata = None
            metadata_path = latest_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, "r") as f:
                    metadata_dict = json.load(f)
                metadata = ModelMetadata.from_dict(metadata_dict)

            logger.info(f"Latest model loaded: {model_name} v{version}")
            return model, metadata, version

        except Exception as e:
            logger.error(f"Error loading latest model: {str(e)}")
            return None, None, None

    def list_models(self, category: str) -> Dict[str, list[str]]:
        """
        List all available models in a category.

        Args:
            category: Category ('anomaly_detection' or 'recommendations')

        Returns:
            Dictionary with model names and their versions
        """
        try:
            category_dir = self.models_dir / category
            if not category_dir.exists():
                return {}

            models: Dict[str, list[str]] = {}
            for model_dir in category_dir.iterdir():
                if model_dir.is_dir():
                    # Extract model name and version
                    parts = model_dir.name.rsplit("_v", 1)
                    if len(parts) == 2:
                        model_name, version = parts
                        if model_name not in models:
                            models[model_name] = []
                        models[model_name].append(version)

            # Sort versions
            for model_name in models:
                models[model_name] = sorted(models[model_name])

            logger.info(f"Models in {category}: {models}")
            return models

        except Exception as e:
            logger.error(f"Error listing models: {str(e)}")
            return {}

    def delete_model(self, model_name: str, category: str, version: str) -> bool:
        """
        Delete a specific model version.

        Args:
            model_name: Name of the model
            category: Category ('anomaly_detection' or 'recommendations')
            version: Version string

        Returns:
            Success status
        """
        try:
            model_dir = self.models_dir / category / f"{model_name}_v{version}"

            if not model_dir.exists():
                logger.warning(f"Model directory not found: {model_dir}")
                return False

            # Remove directory and contents
            import shutil

            shutil.rmtree(model_dir)
            logger.info(f"Model deleted: {model_dir}")
            return True

        except Exception as e:
            logger.error(f"Error deleting model: {str(e)}")
            return False

    def get_model_info(
        self, model_name: str, category: str, version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a model.

        Args:
            model_name: Name of the model
            category: Category ('anomaly_detection' or 'recommendations')
            version: Version string

        Returns:
            Dictionary with model information
        """
        try:
            model_dir = self.models_dir / category / f"{model_name}_v{version}"
            metadata_path = model_dir / "metadata.json"

            if not metadata_path.exists():
                return None

            with open(metadata_path, "r") as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Error getting model info: {str(e)}")
            return None

    def validate_model_checksum(
        self, model_name: str, category: str, version: str
    ) -> bool:
        """
        Validate model integrity using checksum.

        Args:
            model_name: Name of the model
            category: Category ('anomaly_detection' or 'recommendations')
            version: Version string

        Returns:
            True if checksum matches, False otherwise
        """
        try:
            model_dir = self.models_dir / category / f"{model_name}_v{version}"
            model_path = model_dir / "model.pkl"
            metadata_path = model_dir / "metadata.json"

            if not (model_path.exists() and metadata_path.exists()):
                return False

            # Get stored checksum
            with open(metadata_path, "r") as f:
                metadata_dict = json.load(f)
            stored_checksum = metadata_dict.get("checksum")

            # Calculate current checksum
            with open(model_path, "rb") as f:
                current_checksum = hashlib.md5(f.read()).hexdigest()

            is_valid = stored_checksum == current_checksum
            if is_valid:
                logger.info(f"Model checksum valid: {model_name} v{version}")
            else:
                logger.warning(f"Model checksum mismatch: {model_name} v{version}")

            return is_valid

        except Exception as e:
            logger.error(f"Error validating checksum: {str(e)}")
            return False

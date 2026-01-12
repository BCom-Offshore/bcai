"""
ML Model Training Pipeline

Trains anomaly detection models using data from PostgreSQL.

Usage:
    python -m scripts.train_models --all
    python -m scripts.train_models --network --site --link
    python -m scripts.train_models --all --batch-size 500

Features:
- Trains 3 Isolation Forest models (network, site, link)
- Saves models with versioning
- Generates training reports
- Supports batch processing
"""

import argparse
import logging
import pickle
import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import sys
import json

from dotenv import load_dotenv
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, init_db
from app.models.bcom_models import SiteGrade, KPIData, Link, ModelMetrics
from app.services.model_management import ModelManager, ModelMetadata
from app.services.data_loader import get_data_loader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelTrainer:
    """Trains ML models for anomaly detection."""

    def __init__(self, models_dir: str = "ml_models", version: str = "1.0.0"):
        """
        Initialize trainer.

        Args:
            models_dir: Directory to save trained models
            version: Model version (e.g., '1.0.0')
        """
        self.models_dir = models_dir
        self.version = version
        self.model_manager = ModelManager(models_dir)
        self.session = SessionLocal()
        
        logger.info(f"ModelTrainer initialized")
        logger.info(f"  Models directory: {models_dir}")
        logger.info(f"  Version: {version}")

    def close(self):
        """Close database session."""
        self.session.close()

    # ==================== DATA LOADING ====================

    def load_site_grades_data(self, limit: int = None) -> pd.DataFrame:
        """
        Load site grades from PostgreSQL.

        Args:
            limit: Maximum records to load (None for all)

        Returns:
            DataFrame with site grades
        """
        logger.info("Loading site grades from PostgreSQL...")
        
        query = self.session.query(SiteGrade)
        
        if limit:
            query = query.limit(limit)
        
        records = query.all()
        
        data = []
        for record in records:
            data.append({
                'link_id': record.link_id,
                'timestamp': record.timestamp,
                'availability': record.availability,
                'ib_degradation': record.ib_degradation,
                'ob_degradation': record.ob_degradation,
                'ib_instability': record.ib_instability,
                'ob_instability': record.ob_instability,
                'up_time': record.up_time,
                'performance': record.performance,
                'congestion': record.congestion,
                'latency': record.latency,
                'grade': record.grade,
            })
        
        df = pd.DataFrame(data)
        logger.info(f"Loaded {len(df)} site grade records")
        
        return df

    def load_kpi_data(self, limit: int = None) -> pd.DataFrame:
        """
        Load KPI data from PostgreSQL.

        Args:
            limit: Maximum records to load (None for all)

        Returns:
            DataFrame with KPI metrics
        """
        logger.info("Loading KPI data from PostgreSQL...")
        
        query = self.session.query(KPIData)
        
        if limit:
            query = query.limit(limit)
        
        records = query.all()
        
        data = []
        for record in records:
            data.append({
                'device_id': record.device_id,
                'timestamp': record.timestamp,
                'metric_name': record.metric_name,
                'metric_value': record.metric_value,
            })
        
        df = pd.DataFrame(data)
        logger.info(f"Loaded {len(df)} KPI records")
        
        return df

    # ==================== FEATURE ENGINEERING ====================

    def prepare_network_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare features for network anomaly detection.

        Args:
            df: DataFrame with site grades

        Returns:
            Tuple of (feature matrix, feature names)
        """
        logger.info("Preparing network features...")
        
        feature_columns = [
            'availability',
            'ib_degradation',
            'ob_degradation',
            'ib_instability',
            'ob_instability',
            'performance',
            'congestion',
            'latency'
        ]
        
        # Select features
        X = df[feature_columns].copy()
        
        # Handle missing values
        X = X.fillna(X.mean())
        
        # Remove infinite values
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        logger.info(f"Network features: {len(X)} samples, {len(feature_columns)} features")
        
        return X.values, feature_columns

    def prepare_site_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare features for site anomaly detection.

        Args:
            df: DataFrame with site grades

        Returns:
            Tuple of (feature matrix, feature names)
        """
        logger.info("Preparing site features...")
        
        feature_columns = [
            'availability',
            'ib_degradation',
            'ob_degradation',
            'performance',
            'latency'
        ]
        
        # Select features
        X = df[feature_columns].copy()
        
        # Handle missing values
        X = X.fillna(X.mean())
        
        # Remove infinite values
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        logger.info(f"Site features: {len(X)} samples, {len(feature_columns)} features")
        
        return X.values, feature_columns

    def prepare_link_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare features for link anomaly detection.

        Args:
            df: DataFrame with site grades

        Returns:
            Tuple of (feature matrix, feature names)
        """
        logger.info("Preparing link features...")
        
        feature_columns = [
            'ib_degradation',
            'ob_degradation',
            'ib_instability',
            'ob_instability',
            'latency',
            'congestion'
        ]
        
        # Select features
        X = df[feature_columns].copy()
        
        # Handle missing values
        X = X.fillna(X.mean())
        
        # Remove infinite values
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        logger.info(f"Link features: {len(X)} samples, {len(feature_columns)} features")
        
        return X.values, feature_columns

    # ==================== MODEL TRAINING ====================

    def train_isolation_forest(
        self,
        X: np.ndarray,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42
    ) -> Tuple[IsolationForest, StandardScaler]:
        """
        Train Isolation Forest model.

        Args:
            X: Feature matrix
            contamination: Expected anomaly proportion
            n_estimators: Number of trees
            random_state: Random seed

        Returns:
            Tuple of (trained model, fitted scaler)
        """
        logger.info("Training Isolation Forest...")
        logger.info(f"  Samples: {len(X)}")
        logger.info(f"  Features: {X.shape[1]}")
        logger.info(f"  Contamination: {contamination}")
        logger.info(f"  Estimators: {n_estimators}")
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train model
        model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1  # Use all CPU cores
        )
        
        model.fit(X_scaled)
        
        # Get predictions for validation
        predictions = model.predict(X_scaled)
        anomaly_count = (predictions == -1).sum()
        
        logger.info(f"✅ Training complete!")
        logger.info(f"  Anomalies detected: {anomaly_count}/{len(X)} ({100*anomaly_count/len(X):.2f}%)")
        
        return model, scaler

    def save_training_metrics(
        self,
        model_name: str,
        feature_count: int,
        samples_count: int,
        anomalies_count: int,
        feature_names: List[str]
    ) -> bool:
        """
        Save training metrics to database.

        Args:
            model_name: Name of the model (e.g., 'isolation_forest_network')
            feature_count: Number of features used
            samples_count: Number of samples in training data
            anomalies_count: Number of anomalies detected
            feature_names: List of feature names

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate anomaly percentage
            anomaly_percentage = (anomalies_count / samples_count * 100) if samples_count > 0 else 0
            
            # Create metrics record
            metric = ModelMetrics(
                model_name=model_name,
                model_version=self.version,
                metric_name="anomaly_detection_rate",
                metric_value=anomaly_percentage / 100.0,  # Normalize to 0-1
                training_date=datetime.datetime.now(),
                test_set_size=samples_count,
                false_positives=anomalies_count,
                model_metadata={
                    "features": feature_names,
                    "feature_count": feature_count,
                    "model_type": "isolation_forest",
                    "contamination": 0.05,
                    "n_estimators": 100
                }
            )
            
            # Save to database
            self.session.add(metric)
            self.session.commit()
            
            logger.info(f"✅ Training metrics saved to database")
            logger.info(f"  Model: {model_name}")
            logger.info(f"  Anomaly Rate: {anomaly_percentage:.2f}%")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving training metrics: {str(e)}")
            self.session.rollback()
            return False

    def train_network_anomaly_detector(self) -> bool:
        """
        Train network anomaly detection model.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("TRAINING NETWORK ANOMALY DETECTOR")
            logger.info("=" * 60)
            
            # Load data
            df = self.load_site_grades_data()
            if len(df) < 10:
                logger.error("Insufficient data for training")
                return False
            
            # Prepare features
            X, feature_names = self.prepare_network_features(df)
            
            # Train model
            model, scaler = self.train_isolation_forest(X)
            
            # Save model
            metadata = ModelMetadata(
                model_name="isolation_forest_network",
                version=self.version,
                model_type="isolation_forest",
                training_date=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                description="Isolation Forest for network anomaly detection",
                hyperparameters={
                    "contamination": 0.05,
                    "n_estimators": 100,
                    "random_state": 42,
                    "features": feature_names
                },
                metrics={
                    "samples_trained": len(X),
                    "features": len(feature_names)
                }
            )
            
            success, path = self.model_manager.save_model(
                model=model,
                model_name="isolation_forest_network",
                category="anomaly_detection",
                version=self.version,
                metadata=metadata
            )
            
            if success:
                logger.info(f"✅ Network model saved: {path}")
                
                # Save scaler too
                scaler_path = Path(path).parent / "scaler.pkl"
                with open(scaler_path, "wb") as f:
                    pickle.dump(scaler, f)
                logger.info(f"✅ Scaler saved: {scaler_path}")
                
                # Save training metrics to database
                predictions = model.predict(StandardScaler().fit_transform(X))
                anomaly_count = (predictions == -1).sum()
                self.save_training_metrics(
                    model_name="isolation_forest_network",
                    feature_count=len(feature_names),
                    samples_count=len(X),
                    anomalies_count=int(anomaly_count),
                    feature_names=feature_names
                )
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error training network model: {str(e)}")
            return False

    def train_site_anomaly_detector(self) -> bool:
        """
        Train site anomaly detection model.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("TRAINING SITE ANOMALY DETECTOR")
            logger.info("=" * 60)
            
            # Load data
            df = self.load_site_grades_data()
            if len(df) < 10:
                logger.error("Insufficient data for training")
                return False
            
            # Prepare features
            X, feature_names = self.prepare_site_features(df)
            
            # Train model
            model, scaler = self.train_isolation_forest(X)
            
            # Save model
            metadata = ModelMetadata(
                model_name="isolation_forest_site",
                version=self.version,
                model_type="isolation_forest",
                training_date=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                description="Isolation Forest for site anomaly detection",
                hyperparameters={
                    "contamination": 0.05,
                    "n_estimators": 100,
                    "random_state": 42,
                    "features": feature_names
                },
                metrics={
                    "samples_trained": len(X),
                    "features": len(feature_names)
                }
            )
            
            success, path = self.model_manager.save_model(
                model=model,
                model_name="isolation_forest_site",
                category="anomaly_detection",
                version=self.version,
                metadata=metadata
            )
            
            if success:
                logger.info(f"✅ Site model saved: {path}")
                
                # Save scaler too
                scaler_path = Path(path).parent / "scaler.pkl"
                with open(scaler_path, "wb") as f:
                    pickle.dump(scaler, f)
                logger.info(f"✅ Scaler saved: {scaler_path}")
                
                # Save training metrics to database
                predictions = model.predict(StandardScaler().fit_transform(X))
                anomaly_count = (predictions == -1).sum()
                self.save_training_metrics(
                    model_name="isolation_forest_site",
                    feature_count=len(feature_names),
                    samples_count=len(X),
                    anomalies_count=int(anomaly_count),
                    feature_names=feature_names
                )
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error training site model: {str(e)}")
            return False

    def train_link_anomaly_detector(self) -> bool:
        """
        Train link anomaly detection model.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("TRAINING LINK ANOMALY DETECTOR")
            logger.info("=" * 60)
            
            # Load data
            df = self.load_site_grades_data()
            if len(df) < 10:
                logger.error("Insufficient data for training")
                return False
            
            # Prepare features
            X, feature_names = self.prepare_link_features(df)
            
            # Train model
            model, scaler = self.train_isolation_forest(X)
            
            # Save model
            metadata = ModelMetadata(
                model_name="isolation_forest_link",
                version=self.version,
                model_type="isolation_forest",
                training_date=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                description="Isolation Forest for link anomaly detection",
                hyperparameters={
                    "contamination": 0.05,
                    "n_estimators": 100,
                    "random_state": 42,
                    "features": feature_names
                },
                metrics={
                    "samples_trained": len(X),
                    "features": len(feature_names)
                }
            )
            
            success, path = self.model_manager.save_model(
                model=model,
                model_name="isolation_forest_link",
                category="anomaly_detection",
                version=self.version,
                metadata=metadata
            )
            
            if success:
                logger.info(f"✅ Link model saved: {path}")
                
                # Save scaler too
                scaler_path = Path(path).parent / "scaler.pkl"
                with open(scaler_path, "wb") as f:
                    pickle.dump(scaler, f)
                logger.info(f"✅ Scaler saved: {scaler_path}")
                
                # Save training metrics to database
                predictions = model.predict(StandardScaler().fit_transform(X))
                anomaly_count = (predictions == -1).sum()
                self.save_training_metrics(
                    model_name="isolation_forest_link",
                    feature_count=len(feature_names),
                    samples_count=len(X),
                    anomalies_count=int(anomaly_count),
                    feature_names=feature_names
                )
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error training link model: {str(e)}")
            return False

    def train_all(self) -> Dict[str, bool]:
        """
        Train all models.

        Returns:
            Dictionary with results for each model
        """
        logger.info("\n" + "=" * 60)
        logger.info("TRAINING ALL MODELS")
        logger.info("=" * 60 + "\n")
        
        results = {
            "network": self.train_network_anomaly_detector(),
            "site": self.train_site_anomaly_detector(),
            "link": self.train_link_anomaly_detector(),
        }
        
        return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train ML models for anomaly detection"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Train all models"
    )
    parser.add_argument(
        "--network",
        action="store_true",
        help="Train network anomaly detector"
    )
    parser.add_argument(
        "--site",
        action="store_true",
        help="Train site anomaly detector"
    )
    parser.add_argument(
        "--link",
        action="store_true",
        help="Train link anomaly detector"
    )
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Model version (default: 1.0.0)"
    )
    parser.add_argument(
        "--models-dir",
        default="ml_models",
        help="Directory to save models (default: ml_models)"
    )
    
    args = parser.parse_args()
    
    # Initialize database
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return 1
    
    # Create trainer
    trainer = ModelTrainer(
        models_dir=args.models_dir,
        version=args.version
    )
    
    try:
        # Train models based on arguments
        if args.all:
            results = trainer.train_all()
        else:
            results = {}
            if args.network:
                results["network"] = trainer.train_network_anomaly_detector()
            if args.site:
                results["site"] = trainer.train_site_anomaly_detector()
            if args.link:
                results["link"] = trainer.train_link_anomaly_detector()
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("TRAINING SUMMARY")
        logger.info("=" * 60)
        
        for model_name, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            logger.info(f"{model_name.upper()}: {status}")
        
        all_success = all(results.values())
        if all_success:
            logger.info("\n🎉 All models trained successfully!")
            return 0
        else:
            logger.info("\n⚠️ Some models failed to train")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Training error: {str(e)}")
        return 1
    finally:
        trainer.close()


if __name__ == "__main__":
    exit(main())

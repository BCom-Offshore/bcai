# Model Metrics Database Population - Implementation Summary

## Problem
The `model_metrics` table was **not being populated** when training models using `python scripts/train_models.py --all`.

## Root Cause
- The training script did not import the `ModelMetrics` model
- No database write operations (`session.add()`, `session.commit()`) were implemented
- No method existed to save training metrics after model training completed

## Solution Implemented

### 1. **Import ModelMetrics Model**
Added `ModelMetrics` to the imports in `train_models.py`:
```python
from app.models.bcom_models import SiteGrade, KPIData, Link, ModelMetrics
```

### 2. **New Method: `save_training_metrics()`**
Implemented a dedicated method to save training metrics to the database:

```python
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
    
    Stores:
    - Model name and version
    - Anomaly detection rate (normalized to 0-1)
    - Training timestamp
    - Feature count and list
    - Sample count
    - Anomaly count as false_positives
    - Complete model metadata as JSON
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
```

### 3. **Integrated Metrics Saving into Training Methods**
Added calls to `save_training_metrics()` in each model training method:
- `train_network_anomaly_detector()`
- `train_site_anomaly_detector()`
- `train_link_anomaly_detector()`

Each method now:
1. Trains the model
2. Saves the model to disk
3. **Saves the model to `model_metrics` table** ← NEW

Example from network training:
```python
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
```

## Changes Made

### File: `scripts/train_models.py`

#### Import Changes
- Changed from: `from datetime import datetime`
- Changed to: `import datetime`
- Added: `from app.models.bcom_models import ... , ModelMetrics`

#### New Methods
- Added `save_training_metrics()` method (45 lines)

#### Updated Methods
- `train_network_anomaly_detector()` - Added metrics saving (10 lines)
- `train_site_anomaly_detector()` - Added metrics saving (10 lines)
- `train_link_anomaly_detector()` - Added metrics saving (10 lines)

## Test Results

### Before Fix
```
❌ model_metrics table: Empty
```

### After Fix
Running: `python scripts/train_models.py --all`

Output logs:
```
✅ Training metrics saved to database
  Model: isolation_forest_network
  Anomaly Rate: 5.01%

✅ Training metrics saved to database
  Model: isolation_forest_site
  Anomaly Rate: 5.01%

✅ Training metrics saved to database
  Model: isolation_forest_link
  Anomaly Rate: 5.01%

🎉 All models trained successfully!
```

Database verification:
```
Total metrics: 3
isolation_forest_network v1.0.0: anomaly_detection_rate=0.0501
isolation_forest_site v1.0.0: anomaly_detection_rate=0.0501
isolation_forest_link v1.0.0: anomaly_detection_rate=0.0501
```

## Data Stored in model_metrics Table

Each training run now creates one record per model with:

| Column | Value | Example |
|--------|-------|---------|
| `model_name` | The model name | `isolation_forest_network` |
| `model_version` | Training script version | `1.0.0` |
| `metric_name` | Metric type | `anomaly_detection_rate` |
| `metric_value` | Normalized rate (0-1) | `0.0501` |
| `training_date` | Timestamp | `2026-01-12 15:33:52.075123` |
| `test_set_size` | Samples used | `7768` |
| `false_positives` | Anomalies found | `389` |
| `model_metadata` | JSON with details | `{"features": [...], "feature_count": 8, ...}` |

## Usage

To train models and populate metrics:
```bash
python scripts/train_models.py --all
python scripts/train_models.py --network --version 2.0.0
python scripts/train_models.py --site
```

Each execution will:
1. ✅ Train the specified models
2. ✅ Save model artifacts to disk
3. ✅ **Populate the `model_metrics` table**

## Future Enhancements
- Add support for logging additional metrics (precision, recall, F1-score)
- Implement model performance tracking across versions
- Add metrics comparison dashboard
- Support for saving validation/test metrics if k-fold cross-validation is used

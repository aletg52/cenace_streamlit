# Energy Demand Forecaster 📊⚡

A comprehensive Python module for forecasting electricity demand using multiple time series and machine learning methods.

## Features

- **Multiple Forecasting Methods:**
  - SARIMA (Seasonal AutoRegressive Integrated Moving Average)
  - Exponential Smoothing (Holt-Winters)
  - Random Forest
  - Gradient Boosting
  - Facebook Prophet (optional)
  - LSTM Neural Networks (optional)

- **Flexible Data Handling:**
  - Supports CSV, Excel, and JSON formats
  - Automatic date parsing and preprocessing
  - Handles missing values
  - Configurable column names

- **Advanced Features:**
  - Automatic feature engineering (lag features, rolling statistics, cyclical encoding)
  - Seasonal decomposition analysis
  - Model comparison and evaluation
  - Comprehensive metrics (RMSE, MAE, MAPE, R²)
  - Interactive visualizations

- **Easy to Use:**
  - Simple API for quick forecasting
  - Automatic multi-model forecasting
  - Export forecasts to various formats

## Installation

### Basic Installation

```bash
# Clone or download the repository
# Install required dependencies
pip install -r requirements.txt
```

### Optional Dependencies

For advanced features, install additional packages:

```bash
# For Facebook Prophet
pip install prophet

# For LSTM and deep learning
pip install tensorflow keras

# For additional ML models
pip install xgboost lightgbm
```

## Quick Start

### 1. Basic Usage

```python
from energy_demand_forecaster import EnergyDemandForecaster

# Initialize forecaster
forecaster = EnergyDemandForecaster(
    data_path='your_demand_data.csv',
    date_column='date',
    demand_column='demand'
)

# Load and prepare data
forecaster.load_data()
forecaster.split_data(test_size=0.2)

# Fit a model
forecaster.fit_sarima()

# Generate forecast
forecast = forecaster.forecast(steps=24, model_name='sarima')

# Evaluate
metrics = forecaster.evaluate('sarima')

# Visualize
forecaster.plot_forecast('sarima')
```

### 2. One-Line Forecasting

```python
from energy_demand_forecaster import quick_forecast

# Generate forecast in one line
forecast = quick_forecast(
    data_path='demand_data.csv',
    steps=48,
    method='random_forest'
)
```

### 3. Compare Multiple Models

```python
# Fit multiple models
forecaster.fit_sarima()
forecaster.fit_exponential_smoothing()
forecaster.fit_random_forest()
forecaster.fit_gradient_boosting()

# Compare all models
comparison = forecaster.compare_models()
print(comparison)
```

## Data Format

Your data file should contain at least two columns:
- A date/time column
- A demand/load column

### Example CSV Format:

```csv
date,demand
2024-01-01 00:00:00,1250.5
2024-01-01 01:00:00,1180.3
2024-01-01 02:00:00,1095.8
...
```

### Supported File Formats:
- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)
- JSON (`.json`)

## Available Methods

### 1. SARIMA
Seasonal ARIMA model, best for data with clear seasonal patterns.

```python
forecaster.fit_sarima(
    order=(1, 1, 1),           # (p, d, q) parameters
    seasonal_order=(1, 1, 1, 24)  # (P, D, Q, s) parameters
)
```

### 2. Exponential Smoothing
Holt-Winters method, good for data with trend and seasonality.

```python
forecaster.fit_exponential_smoothing(
    seasonal_periods=24,
    trend='add',
    seasonal='add'
)
```

### 3. Random Forest
Machine learning ensemble method, handles complex patterns.

```python
forecaster.fit_random_forest(
    n_estimators=100
)
```

### 4. Gradient Boosting
Advanced ML method, often provides high accuracy.

```python
forecaster.fit_gradient_boosting(
    n_estimators=100,
    learning_rate=0.1
)
```

### 5. Prophet (Optional)
Facebook's forecasting tool, handles holidays and multiple seasonalities.

```python
forecaster.fit_prophet()
```

## API Reference

### Main Class: `EnergyDemandForecaster`

#### Initialization
```python
EnergyDemandForecaster(
    data_path: str = None,
    date_column: str = 'date',
    demand_column: str = 'demand'
)
```

#### Key Methods

**Data Loading & Preparation:**
- `load_data()` - Load data from file
- `split_data(test_size, validation_size)` - Split into train/test sets
- `create_features(df)` - Generate time-based features

**Model Fitting:**
- `fit_sarima(order, seasonal_order)` - Fit SARIMA model
- `fit_exponential_smoothing(seasonal_periods, trend, seasonal)` - Fit Exponential Smoothing
- `fit_random_forest(n_estimators)` - Fit Random Forest
- `fit_gradient_boosting(n_estimators, learning_rate)` - Fit Gradient Boosting
- `fit_prophet()` - Fit Prophet model

**Forecasting & Evaluation:**
- `forecast(steps, model_name)` - Generate forecast
- `evaluate(model_name)` - Evaluate model performance
- `compare_models(steps)` - Compare all fitted models
- `auto_forecast(steps, methods)` - Automatic multi-model forecasting

**Visualization:**
- `plot_forecast(model_name)` - Plot forecast vs actual
- `plot_decomposition(period)` - Plot seasonal decomposition

**Export:**
- `save_forecast(filepath, model_name)` - Save forecast to file

### Quick Function: `quick_forecast`

```python
quick_forecast(
    data_path: str,
    steps: int,
    date_column: str = 'date',
    demand_column: str = 'demand',
    method: str = 'sarima'
) -> pd.Series
```

## Examples

### Example 1: Hourly Demand Forecasting

```python
from energy_demand_forecaster import EnergyDemandForecaster

# Load hourly demand data
forecaster = EnergyDemandForecaster(
    data_path='hourly_demand.csv',
    date_column='timestamp',
    demand_column='load_mw'
)

forecaster.load_data()
forecaster.split_data(test_size=0.2)

# Fit SARIMA with 24-hour seasonality
forecaster.fit_sarima(
    order=(2, 1, 2),
    seasonal_order=(1, 1, 1, 24)
)

# Forecast next 48 hours
forecast = forecaster.forecast(steps=48, model_name='sarima')

# Evaluate and plot
forecaster.evaluate('sarima')
forecaster.plot_forecast('sarima')
```

### Example 2: Daily Demand with Multiple Models

```python
# Load daily data
forecaster = EnergyDemandForecaster('daily_demand.csv')
forecaster.load_data()
forecaster.split_data(test_size=0.15)

# Fit multiple models
models = ['sarima', 'exp_smoothing', 'random_forest', 'gradient_boosting']
forecasts = forecaster.auto_forecast(steps=30, methods=models)

# Compare performance
comparison = forecaster.compare_models()
print("\nBest Model:", comparison.iloc[0]['Model'])

# Use best model for final forecast
best_model = comparison.iloc[0]['Model']
forecaster.plot_forecast(best_model)
```

### Example 3: Seasonal Decomposition

```python
forecaster = EnergyDemandForecaster('demand_data.csv')
forecaster.load_data()

# Analyze seasonal patterns
forecaster.plot_decomposition(period=24)  # For hourly data
# or
forecaster.plot_decomposition(period=7)   # For daily data
```

### Example 4: Custom Feature Engineering

```python
import pandas as pd

# Load data
forecaster = EnergyDemandForecaster('demand_data.csv')
forecaster.load_data()

# Create custom features
data_with_features = forecaster.create_features(forecaster.data)
print("Available features:", data_with_features.columns.tolist())

# The module automatically creates:
# - Time features (hour, day, month, etc.)
# - Cyclical encodings (sin/cos transformations)
# - Lag features
# - Rolling statistics
# - Weekend indicators
```

## Evaluation Metrics

The module provides comprehensive evaluation metrics:

- **RMSE** (Root Mean Squared Error): Overall prediction error
- **MAE** (Mean Absolute Error): Average absolute error
- **MAPE** (Mean Absolute Percentage Error): Percentage error
- **R²** (R-squared): Proportion of variance explained

Lower values are better for RMSE, MAE, and MAPE. Higher values are better for R².

## Tips for Best Results

1. **Data Preparation:**
   - Ensure consistent time intervals (no gaps)
   - Handle outliers appropriately
   - Include at least 2-3 seasonal cycles for training

2. **Model Selection:**
   - SARIMA: Best for clear seasonal patterns
   - Random Forest/GB: Best for complex, non-linear patterns
   - Exponential Smoothing: Fast and reliable for simple trends
   - Prophet: Great for data with holidays and multiple seasonalities

3. **Parameter Tuning:**
   - For SARIMA, use ACF/PACF plots to determine orders
   - For ML models, use cross-validation
   - Start with default parameters, then optimize

4. **Validation:**
   - Always use a test set for evaluation
   - Compare multiple models
   - Check residual plots for patterns

## Troubleshooting

### Common Issues:

**Issue**: `ValueError: No data loaded`
- **Solution**: Call `load_data()` before other operations

**Issue**: `ImportError: prophet not installed`
- **Solution**: Install Prophet: `pip install prophet`

**Issue**: Slow training with large datasets
- **Solution**: 
  - Reduce data frequency (e.g., hourly to daily)
  - Use fewer estimators for RF/GB models
  - Sample data for initial testing

**Issue**: Poor forecast accuracy
- **Solution**:
  - Try different models
  - Tune hyperparameters
  - Add more training data
  - Check for data quality issues

## Advanced Features

### Custom Seasonality

```python
# For data with custom seasonal patterns
forecaster.fit_sarima(
    order=(1, 1, 1),
    seasonal_order=(1, 1, 1, 168)  # Weekly seasonality for hourly data
)
```

### Ensemble Forecasting

```python
# Combine predictions from multiple models
forecasts = forecaster.auto_forecast(steps=24, methods=['sarima', 'random_forest'])

# Average predictions
ensemble_forecast = sum(forecasts.values()) / len(forecasts)
```

### Custom Evaluation Period

```python
# Evaluate on specific test size
forecaster.split_data(test_size=0.15)
metrics = forecaster.evaluate('sarima')
```

## Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

## License

This module is provided as-is for educational and commercial use.

## Contact

For questions or issues, please open an issue in the repository.

## Acknowledgments

Built with:
- pandas, numpy: Data manipulation
- scikit-learn: Machine learning
- statsmodels: Statistical models
- matplotlib, seaborn: Visualization

---

**Happy Forecasting! ⚡📈**

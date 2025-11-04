"""
Example Usage of Energy Demand Forecaster

This script demonstrates how to use the EnergyDemandForecaster module
with various forecasting methods.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from energy_demand_forecaster import EnergyDemandForecaster, quick_forecast

# ============================================================================
# EXAMPLE 1: Generate Sample Data
# ============================================================================
print("=" * 70)
print("EXAMPLE 1: Creating Sample Data")
print("=" * 70)

def generate_sample_data(n_days=365, freq='H'):
    """
    Generate synthetic electricity demand data with realistic patterns.
    """
    # Create date range
    dates = pd.date_range(start='2024-01-01', periods=n_days*24 if freq=='H' else n_days, freq=freq)
    
    # Base demand
    base_demand = 1000
    
    # Create components
    time_index = np.arange(len(dates))
    
    # Trend (slight increase over time)
    trend = time_index * 0.05
    
    # Yearly seasonality (summer peak)
    yearly = 200 * np.sin(2 * np.pi * time_index / (365 * 24))
    
    # Weekly seasonality (weekday vs weekend)
    weekly = 100 * np.sin(2 * np.pi * time_index / (7 * 24))
    
    # Daily seasonality (peak during day)
    daily = 300 * np.sin(2 * np.pi * (time_index % 24) / 24 - np.pi/2) + 300
    
    # Random noise
    noise = np.random.normal(0, 50, len(dates))
    
    # Combine all components
    demand = base_demand + trend + yearly + weekly + daily + noise
    
    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'demand': demand
    })
    
    return df

# Generate and save sample data
sample_data = generate_sample_data(n_days=365)
sample_data.to_csv('sample_demand_data.csv', index=False)
print(f"Sample data created: {len(sample_data)} records")
print(f"Date range: {sample_data['date'].min()} to {sample_data['date'].max()}")
print(f"\nFirst few rows:")
print(sample_data.head())
print(f"\nData saved to: sample_demand_data.csv")

# ============================================================================
# EXAMPLE 2: Basic Forecasting with SARIMA
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLE 2: Basic Forecasting with SARIMA")
print("=" * 70)

# Initialize forecaster
forecaster = EnergyDemandForecaster(
    data_path='sample_demand_data.csv',
    date_column='date',
    demand_column='demand'
)

# Load data
forecaster.load_data()

# Split data (80% train, 20% test)
train, test, _ = forecaster.split_data(test_size=0.2)
print(f"\nTrain set: {len(train)} records")
print(f"Test set: {len(test)} records")

# Fit SARIMA model
forecaster.fit_sarima(
    order=(1, 1, 1),
    seasonal_order=(1, 1, 1, 24)  # 24-hour seasonality
)

# Generate forecast
forecast_steps = len(test)
forecast = forecaster.forecast(steps=forecast_steps, model_name='sarima')
print(f"\nGenerated {len(forecast)} forecast points")

# Evaluate model
metrics = forecaster.evaluate('sarima')

# Plot forecast
print("\nGenerating forecast plot...")
forecaster.plot_forecast('sarima')

# ============================================================================
# EXAMPLE 3: Multiple Models Comparison
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLE 3: Comparing Multiple Forecasting Methods")
print("=" * 70)

# Fit multiple models
print("\nFitting Exponential Smoothing...")
forecaster.fit_exponential_smoothing(seasonal_periods=24)

print("\nFitting Random Forest...")
forecaster.fit_random_forest(n_estimators=100)

print("\nFitting Gradient Boosting...")
forecaster.fit_gradient_boosting(n_estimators=100, learning_rate=0.1)

# Compare all models
print("\n" + "-" * 70)
comparison = forecaster.compare_models()
print("\nBest model by RMSE: " + comparison.iloc[0]['Model'])

# ============================================================================
# EXAMPLE 4: Automatic Forecasting
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLE 4: Automatic Multi-Model Forecasting")
print("=" * 70)

# Create new forecaster instance
auto_forecaster = EnergyDemandForecaster(
    data_path='sample_demand_data.csv',
    date_column='date',
    demand_column='demand'
)

auto_forecaster.load_data()
auto_forecaster.split_data(test_size=0.15)

# Automatically fit and forecast with multiple methods
forecasts = auto_forecaster.auto_forecast(
    steps=24,  # Forecast 24 hours ahead
    methods=['sarima', 'exp_smoothing', 'random_forest']
)

print(f"\nGenerated forecasts using {len(forecasts)} methods:")
for method, forecast in forecasts.items():
    print(f"  - {method}: {len(forecast)} points")

# ============================================================================
# EXAMPLE 5: Quick Forecast (One-liner approach)
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLE 5: Quick Forecast Function")
print("=" * 70)

# Generate forecast in one line
quick_result = quick_forecast(
    data_path='sample_demand_data.csv',
    steps=48,  # 48 hours ahead
    date_column='date',
    demand_column='demand',
    method='random_forest'
)

print(f"\nQuick forecast generated: {len(quick_result)} points")
print(f"Forecast range: {quick_result.index[0]} to {quick_result.index[-1]}")
print(f"\nFirst few predictions:")
print(quick_result.head())

# ============================================================================
# EXAMPLE 6: Save Forecast Results
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLE 6: Saving Forecast Results")
print("=" * 70)

# Save forecasts in different formats
forecaster.save_forecast('forecast_sarima.csv', 'sarima')
forecaster.save_forecast('forecast_rf.csv', 'random_forest')

print("\nForecasts saved successfully!")
print("  - forecast_sarima.csv")
print("  - forecast_rf.csv")

# ============================================================================
# EXAMPLE 7: Seasonal Decomposition
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLE 7: Seasonal Decomposition Analysis")
print("=" * 70)

print("\nGenerating seasonal decomposition plot...")
forecaster.plot_decomposition(period=24)

# ============================================================================
# EXAMPLE 8: Custom Data Format
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLE 8: Working with Custom Data Format")
print("=" * 70)

# Create data with different column names
custom_data = sample_data.copy()
custom_data.columns = ['timestamp', 'load_mw']
custom_data.to_csv('custom_demand_data.csv', index=False)

# Load with custom column names
custom_forecaster = EnergyDemandForecaster(
    data_path='custom_demand_data.csv',
    date_column='timestamp',
    demand_column='load_mw'
)

custom_forecaster.load_data()
print("\nCustom data loaded successfully!")
print(f"Columns: {custom_forecaster.data.columns.tolist()}")

# ============================================================================
# EXAMPLE 9: Feature Importance (for ML models)
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLE 9: Feature Importance Analysis")
print("=" * 70)

if 'random_forest' in forecaster.models:
    import matplotlib.pyplot as plt
    
    rf_model = forecaster.models['random_forest']
    feature_names = forecaster.models['random_forest_features']
    importances = rf_model.feature_importances_
    
    # Get top 10 features
    indices = np.argsort(importances)[-10:]
    
    plt.figure(figsize=(10, 6))
    plt.barh(range(len(indices)), importances[indices])
    plt.yticks(range(len(indices)), [feature_names[i] for i in indices])
    plt.xlabel('Feature Importance')
    plt.title('Top 10 Most Important Features - Random Forest')
    plt.tight_layout()
    plt.savefig('feature_importance.png', dpi=150)
    print("\nFeature importance plot saved to: feature_importance.png")
    plt.show()

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
print("EXAMPLES COMPLETED!")
print("=" * 70)
print("""
Summary of what we demonstrated:
1. Generated realistic sample electricity demand data
2. Performed basic SARIMA forecasting
3. Compared multiple forecasting methods
4. Used automatic multi-model forecasting
5. Quick one-line forecasting
6. Saved forecast results to files
7. Analyzed seasonal patterns
8. Handled custom data formats
9. Analyzed feature importance

Files created:
- sample_demand_data.csv: Sample electricity demand data
- custom_demand_data.csv: Custom format data
- forecast_sarima.csv: SARIMA forecast results
- forecast_rf.csv: Random Forest forecast results
- feature_importance.png: Feature importance visualization

You can now use this module with your own demand data!
""")

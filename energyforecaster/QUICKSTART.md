# Quick Start Guide

## Installation (3 minutes)

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify installation:**
   ```bash
   python test_forecaster.py
   ```
   
   All tests should pass ✓

## Your First Forecast (5 minutes)

### Option 1: Use the Example Script

```bash
python example_usage.py
```

This will:
- Generate sample electricity demand data
- Demonstrate multiple forecasting methods
- Create visualizations and save results

### Option 2: Write Your Own Script

Create a file `my_forecast.py`:

```python
from energy_demand_forecaster import EnergyDemandForecaster

# Initialize with your data
forecaster = EnergyDemandForecaster(
    data_path='your_demand_data.csv',  # Your CSV file
    date_column='date',                # Name of date column
    demand_column='demand'             # Name of demand column
)

# Load and prepare
forecaster.load_data()
forecaster.split_data(test_size=0.2)

# Fit model and forecast
forecaster.fit_sarima()
forecast = forecaster.forecast(steps=24)  # 24 hours ahead

# Evaluate and visualize
forecaster.evaluate('sarima')
forecaster.plot_forecast('sarima')

# Save results
forecaster.save_forecast('my_forecast.csv')
```

Run it:
```bash
python my_forecast.py
```

## Data Format

Your CSV should look like this:

```csv
date,demand
2024-01-01 00:00:00,1250.5
2024-01-01 01:00:00,1180.3
2024-01-01 02:00:00,1095.8
...
```

### Supported formats:
- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`) 
- JSON (`.json`)

## Common Use Cases

### Hourly Forecasting
```python
forecaster.fit_sarima(
    order=(1, 1, 1),
    seasonal_order=(1, 1, 1, 24)  # 24-hour cycle
)
forecast = forecaster.forecast(steps=48)  # 2 days
```

### Daily Forecasting
```python
forecaster.fit_sarima(
    order=(1, 1, 1),
    seasonal_order=(1, 1, 1, 7)  # 7-day cycle
)
forecast = forecaster.forecast(steps=30)  # 30 days
```

### Compare Multiple Models
```python
# Fit several models
forecaster.fit_sarima()
forecaster.fit_random_forest()
forecaster.fit_gradient_boosting()

# Compare automatically
comparison = forecaster.compare_models()
print(comparison)

# Use best model
best_model = comparison.iloc[0]['Model']
forecaster.plot_forecast(best_model)
```

## Troubleshooting

**Problem**: Module not found
```bash
# Make sure you're in the right directory
cd /path/to/energy-demand-forecaster
python -c "import energy_demand_forecaster"
```

**Problem**: Missing dependencies
```bash
pip install -r requirements.txt --upgrade
```

**Problem**: Data loading error
- Check your CSV has date and demand columns
- Ensure dates are properly formatted
- Check for missing values

## Next Steps

1. Read the full [README.md](README.md) for detailed documentation
2. Explore [example_usage.py](example_usage.py) for more examples
3. Try different forecasting methods
4. Tune model parameters for your specific data

## Need Help?

- Check the README.md for detailed API documentation
- Run the test suite: `python test_forecaster.py`
- Review example_usage.py for code examples

## File Overview

```
energy-demand-forecaster/
├── energy_demand_forecaster.py  # Main module
├── requirements.txt              # Dependencies
├── setup.py                      # Installation config
├── example_usage.py              # Complete examples
├── test_forecaster.py           # Test suite
├── README.md                    # Full documentation
└── QUICKSTART.md               # This file
```

Happy forecasting! 📊⚡

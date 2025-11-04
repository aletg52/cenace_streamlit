"""
Test Script for Energy Demand Forecaster

This script runs basic tests to verify the module is working correctly.
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    try:
        from energy_demand_forecaster import EnergyDemandForecaster, quick_forecast
        print("✓ Module imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_sample_data_generation():
    """Test sample data generation"""
    print("\nTesting sample data generation...")
    try:
        dates = pd.date_range(start='2024-01-01', periods=1000, freq='H')
        demand = 1000 + 200 * np.sin(2 * np.pi * np.arange(1000) / 24) + np.random.normal(0, 50, 1000)
        df = pd.DataFrame({'date': dates, 'demand': demand})
        df.to_csv('test_data.csv', index=False)
        print(f"✓ Sample data created: {len(df)} records")
        return True
    except Exception as e:
        print(f"✗ Data generation failed: {e}")
        return False

def test_data_loading():
    """Test data loading functionality"""
    print("\nTesting data loading...")
    try:
        from energy_demand_forecaster import EnergyDemandForecaster
        forecaster = EnergyDemandForecaster(
            data_path='test_data.csv',
            date_column='date',
            demand_column='demand'
        )
        forecaster.load_data()
        assert len(forecaster.data) > 0, "No data loaded"
        print(f"✓ Data loaded successfully: {len(forecaster.data)} records")
        return True, forecaster
    except Exception as e:
        print(f"✗ Data loading failed: {e}")
        return False, None

def test_data_splitting(forecaster):
    """Test data splitting"""
    print("\nTesting data splitting...")
    try:
        train, test, _ = forecaster.split_data(test_size=0.2)
        assert len(train) > 0, "No training data"
        assert len(test) > 0, "No test data"
        print(f"✓ Data split successful: {len(train)} train, {len(test)} test")
        return True
    except Exception as e:
        print(f"✗ Data splitting failed: {e}")
        return False

def test_sarima_fitting(forecaster):
    """Test SARIMA model fitting"""
    print("\nTesting SARIMA model...")
    try:
        forecaster.fit_sarima(order=(1, 1, 1), seasonal_order=(1, 1, 1, 24))
        assert 'sarima' in forecaster.models, "SARIMA model not stored"
        print("✓ SARIMA model fitted successfully")
        return True
    except Exception as e:
        print(f"✗ SARIMA fitting failed: {e}")
        return False

def test_forecasting(forecaster):
    """Test forecast generation"""
    print("\nTesting forecast generation...")
    try:
        forecast = forecaster.forecast(steps=24, model_name='sarima')
        assert len(forecast) == 24, f"Expected 24 forecasts, got {len(forecast)}"
        assert not forecast.isnull().any(), "Forecast contains NaN values"
        print(f"✓ Forecast generated: {len(forecast)} points")
        return True
    except Exception as e:
        print(f"✗ Forecasting failed: {e}")
        return False

def test_evaluation(forecaster):
    """Test model evaluation"""
    print("\nTesting model evaluation...")
    try:
        metrics = forecaster.evaluate('sarima')
        required_metrics = ['RMSE', 'MAE', 'MAPE', 'R2']
        for metric in required_metrics:
            assert metric in metrics, f"Missing metric: {metric}"
        print("✓ Model evaluation successful")
        print(f"  RMSE: {metrics['RMSE']:.2f}")
        print(f"  MAE: {metrics['MAE']:.2f}")
        print(f"  MAPE: {metrics['MAPE']:.2f}%")
        return True
    except Exception as e:
        print(f"✗ Evaluation failed: {e}")
        return False

def test_quick_forecast():
    """Test quick forecast function"""
    print("\nTesting quick forecast function...")
    try:
        from energy_demand_forecaster import quick_forecast
        forecast = quick_forecast(
            data_path='test_data.csv',
            steps=12,
            method='sarima'
        )
        assert len(forecast) == 12, f"Expected 12 forecasts, got {len(forecast)}"
        print(f"✓ Quick forecast successful: {len(forecast)} points")
        return True
    except Exception as e:
        print(f"✗ Quick forecast failed: {e}")
        return False

def test_feature_creation(forecaster):
    """Test feature engineering"""
    print("\nTesting feature creation...")
    try:
        features = forecaster.create_features(forecaster.data)
        expected_features = ['hour', 'day_of_week', 'month', 'is_weekend']
        for feature in expected_features:
            assert feature in features.columns, f"Missing feature: {feature}"
        print(f"✓ Features created: {len(features.columns)} total features")
        return True
    except Exception as e:
        print(f"✗ Feature creation failed: {e}")
        return False

def test_ml_models(forecaster):
    """Test machine learning models"""
    print("\nTesting machine learning models...")
    try:
        # Random Forest
        print("  Testing Random Forest...")
        forecaster.fit_random_forest(n_estimators=10)
        assert 'random_forest' in forecaster.models
        print("  ✓ Random Forest fitted")
        
        # Gradient Boosting
        print("  Testing Gradient Boosting...")
        forecaster.fit_gradient_boosting(n_estimators=10)
        assert 'gradient_boosting' in forecaster.models
        print("  ✓ Gradient Boosting fitted")
        
        return True
    except Exception as e:
        print(f"  ✗ ML models failed: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("ENERGY DEMAND FORECASTER - TEST SUITE")
    print("=" * 70)
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: Sample Data
    results.append(("Sample Data Generation", test_sample_data_generation()))
    
    # Test 3: Data Loading
    success, forecaster = test_data_loading()
    results.append(("Data Loading", success))
    
    if success and forecaster:
        # Test 4: Data Splitting
        results.append(("Data Splitting", test_data_splitting(forecaster)))
        
        # Test 5: Feature Creation
        results.append(("Feature Creation", test_feature_creation(forecaster)))
        
        # Test 6: SARIMA
        sarima_success = test_sarima_fitting(forecaster)
        results.append(("SARIMA Fitting", sarima_success))
        
        if sarima_success:
            # Test 7: Forecasting
            results.append(("Forecast Generation", test_forecasting(forecaster)))
            
            # Test 8: Evaluation
            results.append(("Model Evaluation", test_evaluation(forecaster)))
        
        # Test 9: ML Models
        results.append(("ML Models", test_ml_models(forecaster)))
    
    # Test 10: Quick Forecast
    results.append(("Quick Forecast", test_quick_forecast()))
    
    # Print Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "-" * 70)
    print(f"Results: {passed}/{total} tests passed ({100*passed/total:.1f}%)")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 All tests passed! Module is working correctly.")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

"""
Energy Demand Forecasting Module

A comprehensive module for forecasting electricity demand using various 
time series forecasting methods.

Date: 2025-11-02
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Core libraries
from typing import Dict, List, Optional, Tuple, Union
import json

# Visualization
import matplotlib.pyplot as plt
import seaborn as sns

# Statistical models
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

# Machine Learning
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor


class EnergyDemandForecaster:
    """
    A comprehensive class for electricity demand forecasting.
    
    Supports multiple forecasting methods:
    - SARIMA (Seasonal ARIMA)
    - Exponential Smoothing
    - Random Forest
    - Gradient Boosting
    - Prophet (if available)
    - LSTM (if tensorflow available)
    """
    
    def __init__(self, data_path: Optional[str] = None, 
                 date_column: str = 'date', 
                 demand_column: str = 'demand'):
        """
        Initialize the forecaster.
        
        Parameters:
        -----------
        data_path : str, optional
            Path to the demand data file (CSV, Excel, or JSON)
        date_column : str
            Name of the datetime column
        demand_column : str
            Name of the demand column
        """
        self.data_path = data_path
        self.date_column = date_column
        self.demand_column = demand_column
        self.data = None
        self.train_data = None
        self.test_data = None
        self.models = {}
        self.forecasts = {}
        self.metrics = {}
        
    def load_data(self, data_path: Optional[str] = None, 
                  date_column: Optional[str] = None,
                  demand_column: Optional[str] = None) -> pd.DataFrame:
        """
        Load demand data from various file formats.
        
        Parameters:
        -----------
        data_path : str, optional
            Path to the data file
        date_column : str, optional
            Name of the datetime column
        demand_column : str, optional
            Name of the demand column
            
        Returns:
        --------
        pd.DataFrame
            Loaded and preprocessed data
        """
        if data_path is not None:
            self.data_path = data_path
        if date_column is not None:
            self.date_column = date_column
        if demand_column is not None:
            self.demand_column = demand_column
            
        if self.data_path is None:
            raise ValueError("No data path provided")
        
        # Detect file format and load
        if self.data_path.endswith('.csv'):
            self.data = pd.read_csv(self.data_path)
        elif self.data_path.endswith(('.xls', '.xlsx')):
            self.data = pd.read_excel(self.data_path)
        elif self.data_path.endswith('.json'):
            self.data = pd.read_json(self.data_path)
        else:
            raise ValueError("Unsupported file format. Use CSV, Excel, or JSON.")
        
        # Preprocess
        self.data = self._preprocess_data()
        
        print(f"Data loaded successfully: {len(self.data)} records")
        print(f"Date range: {self.data.index.min()} to {self.data.index.max()}")
        
        return self.data
    
    def _preprocess_data(self) -> pd.DataFrame:
        """
        Preprocess the data: convert dates, handle missing values, set index.
        """
        df = self.data.copy()
        
        # Convert date column to datetime
        if self.date_column in df.columns:
            df[self.date_column] = pd.to_datetime(df[self.date_column])
            df = df.set_index(self.date_column)
        
        # Sort by date
        df = df.sort_index()
        
        # Handle missing values
        if df[self.demand_column].isnull().any():
            print(f"Warning: {df[self.demand_column].isnull().sum()} missing values found")
            # Forward fill then backward fill
            df[self.demand_column] = df[self.demand_column].fillna(method='ffill').fillna(method='bfill')
        
        # Remove duplicates
        df = df[~df.index.duplicated(keep='first')]
        
        return df
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create time-based features for machine learning models.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input dataframe with datetime index
            
        Returns:
        --------
        pd.DataFrame
            Dataframe with additional features
        """
        features = df.copy()
        
        # Time features
        features['hour'] = features.index.hour
        features['day_of_week'] = features.index.dayofweek
        features['day_of_month'] = features.index.day
        features['day_of_year'] = features.index.dayofyear
        features['month'] = features.index.month
        features['quarter'] = features.index.quarter
        features['year'] = features.index.year
        features['week_of_year'] = features.index.isocalendar().week
        
        # Cyclical encoding for periodic features
        features['hour_sin'] = np.sin(2 * np.pi * features['hour'] / 24)
        features['hour_cos'] = np.cos(2 * np.pi * features['hour'] / 24)
        features['day_sin'] = np.sin(2 * np.pi * features['day_of_week'] / 7)
        features['day_cos'] = np.cos(2 * np.pi * features['day_of_week'] / 7)
        features['month_sin'] = np.sin(2 * np.pi * features['month'] / 12)
        features['month_cos'] = np.cos(2 * np.pi * features['month'] / 12)
        
        # Is weekend
        features['is_weekend'] = (features['day_of_week'] >= 5).astype(int)
        
        # Lag features
        for lag in [1, 2, 3, 7, 24, 168]:  # Various lags
            if len(df) > lag:
                features[f'lag_{lag}'] = features[self.demand_column].shift(lag)
        
        # Rolling statistics
        for window in [24, 168]:  # 1 day, 1 week
            if len(df) > window:
                features[f'rolling_mean_{window}'] = features[self.demand_column].rolling(window=window).mean()
                features[f'rolling_std_{window}'] = features[self.demand_column].rolling(window=window).std()
        
        # Drop NaN values created by lag and rolling features
        features = features.dropna()
        
        return features
    
    def split_data(self, test_size: float = 0.2, 
                   validation_size: float = 0.0) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
        """
        Split data into train, test, and optionally validation sets.
        
        Parameters:
        -----------
        test_size : float
            Proportion of data for testing
        validation_size : float
            Proportion of data for validation
            
        Returns:
        --------
        Tuple of train, test, and validation dataframes
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        n = len(self.data)
        test_n = int(n * test_size)
        val_n = int(n * validation_size)
        train_n = n - test_n - val_n
        
        self.train_data = self.data.iloc[:train_n]
        
        if validation_size > 0:
            self.val_data = self.data.iloc[train_n:train_n + val_n]
            self.test_data = self.data.iloc[train_n + val_n:]
            return self.train_data, self.test_data, self.val_data
        else:
            self.test_data = self.data.iloc[train_n:]
            return self.train_data, self.test_data, None
    
    def fit_sarima(self, order: Tuple[int, int, int] = (1, 1, 1),
                   seasonal_order: Tuple[int, int, int, int] = (1, 1, 1, 24),
                   **kwargs) -> None:
        """
        Fit SARIMA model.
        
        Parameters:
        -----------
        order : tuple
            (p, d, q) order of the ARIMA model
        seasonal_order : tuple
            (P, D, Q, s) seasonal order
        """
        if self.train_data is None:
            raise ValueError("No training data. Call split_data() first.")
        
        print("Fitting SARIMA model...")
        
        model = SARIMAX(
            self.train_data[self.demand_column],
            order=order,
            seasonal_order=seasonal_order,
            **kwargs
        )
        
        self.models['sarima'] = model.fit(disp=False)
        print("SARIMA model fitted successfully")
    
    def fit_exponential_smoothing(self, seasonal_periods: int = 24,
                                  trend: str = 'add',
                                  seasonal: str = 'add',
                                  **kwargs) -> None:
        """
        Fit Exponential Smoothing model.
        
        Parameters:
        -----------
        seasonal_periods : int
            Number of periods in a complete seasonal cycle
        trend : str
            Type of trend component ('add', 'mul', or None)
        seasonal : str
            Type of seasonal component ('add', 'mul', or None)
        """
        if self.train_data is None:
            raise ValueError("No training data. Call split_data() first.")
        
        print("Fitting Exponential Smoothing model...")
        
        model = ExponentialSmoothing(
            self.train_data[self.demand_column],
            seasonal_periods=seasonal_periods,
            trend=trend,
            seasonal=seasonal,
            **kwargs
        )
        
        self.models['exp_smoothing'] = model.fit()
        print("Exponential Smoothing model fitted successfully")
    
    def fit_random_forest(self, n_estimators: int = 100, **kwargs) -> None:
        """
        Fit Random Forest model.
        
        Parameters:
        -----------
        n_estimators : int
            Number of trees in the forest
        """
        if self.train_data is None:
            raise ValueError("No training data. Call split_data() first.")
        
        print("Fitting Random Forest model...")
        
        # Create features
        train_features = self.create_features(self.train_data)
        
        X_train = train_features.drop(columns=[self.demand_column])
        y_train = train_features[self.demand_column]
        
        model = RandomForestRegressor(n_estimators=n_estimators, 
                                     random_state=42, 
                                     n_jobs=-1,
                                     **kwargs)
        model.fit(X_train, y_train)
        
        self.models['random_forest'] = model
        self.models['random_forest_features'] = X_train.columns.tolist()
        
        print("Random Forest model fitted successfully")
    
    def fit_gradient_boosting(self, n_estimators: int = 100, 
                             learning_rate: float = 0.1,
                             **kwargs) -> None:
        """
        Fit Gradient Boosting model.
        
        Parameters:
        -----------
        n_estimators : int
            Number of boosting stages
        learning_rate : float
            Learning rate shrinks the contribution of each tree
        """
        if self.train_data is None:
            raise ValueError("No training data. Call split_data() first.")
        
        print("Fitting Gradient Boosting model...")
        
        # Create features
        train_features = self.create_features(self.train_data)
        
        X_train = train_features.drop(columns=[self.demand_column])
        y_train = train_features[self.demand_column]
        
        model = GradientBoostingRegressor(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            random_state=42,
            **kwargs
        )
        model.fit(X_train, y_train)
        
        self.models['gradient_boosting'] = model
        self.models['gradient_boosting_features'] = X_train.columns.tolist()
        
        print("Gradient Boosting model fitted successfully")
    
    def fit_prophet(self) -> None:
        """
        Fit Facebook Prophet model (if available).
        """
        try:
            from prophet import Prophet
        except ImportError:
            print("Prophet not installed. Install with: pip install prophet")
            return
        
        if self.train_data is None:
            raise ValueError("No training data. Call split_data() first.")
        
        print("Fitting Prophet model...")
        
        # Prepare data for Prophet
        prophet_data = pd.DataFrame({
            'ds': self.train_data.index,
            'y': self.train_data[self.demand_column].values
        })
        
        model = Prophet(yearly_seasonality=True,
                       weekly_seasonality=True,
                       daily_seasonality=True)
        model.fit(prophet_data)
        
        self.models['prophet'] = model
        print("Prophet model fitted successfully")
    
    def forecast(self, steps: int, model_name: str = 'sarima') -> pd.Series:
        """
        Generate forecast for specified number of steps ahead.
        
        Parameters:
        -----------
        steps : int
            Number of time steps to forecast
        model_name : str
            Name of the model to use for forecasting
            
        Returns:
        --------
        pd.Series
            Forecasted values
        """
        if model_name not in self.models:
            raise ValueError(f"Model '{model_name}' not fitted. Available models: {list(self.models.keys())}")
        
        print(f"Generating forecast using {model_name} model...")
        
        if model_name == 'sarima':
            forecast = self.models['sarima'].forecast(steps=steps)
            
        elif model_name == 'exp_smoothing':
            forecast = self.models['exp_smoothing'].forecast(steps=steps)
            
        elif model_name in ['random_forest', 'gradient_boosting']:
            # For ML models, we need to create future features
            last_date = self.data.index[-1]
            freq = pd.infer_freq(self.data.index)
            
            if freq is None:
                freq = self.data.index.to_series().diff().median()
            
            future_dates = pd.date_range(start=last_date, periods=steps + 1, freq=freq)[1:]
            future_df = pd.DataFrame(index=future_dates)
            future_df[self.demand_column] = np.nan
            
            # Combine with historical data to create features
            combined = pd.concat([self.data[[self.demand_column]], future_df])
            
            # For ML models, we predict iteratively
            predictions = []
            for i in range(steps):
                features = self.create_features(combined)
                
                # Get the latest row features
                latest_features = features.iloc[-1:].drop(columns=[self.demand_column])
                
                # Ensure features match training features
                if model_name == 'random_forest':
                    feature_cols = self.models['random_forest_features']
                else:
                    feature_cols = self.models['gradient_boosting_features']
                
                X_pred = latest_features[feature_cols]
                
                # Predict
                pred = self.models[model_name].predict(X_pred)[0]
                predictions.append(pred)
                
                # Update the combined dataframe with the prediction
                combined.iloc[-steps + i, combined.columns.get_loc(self.demand_column)] = pred
            
            forecast = pd.Series(predictions, index=future_dates)
            
        elif model_name == 'prophet':
            last_date = self.data.index[-1]
            freq = pd.infer_freq(self.data.index)
            future_dates = pd.date_range(start=last_date, periods=steps + 1, freq=freq)[1:]
            
            future = pd.DataFrame({'ds': future_dates})
            forecast_df = self.models['prophet'].predict(future)
            forecast = pd.Series(forecast_df['yhat'].values, index=future_dates)
        
        else:
            raise ValueError(f"Forecasting not implemented for {model_name}")
        
        self.forecasts[model_name] = forecast
        
        return forecast
    
    def evaluate(self, model_name: str = 'sarima') -> Dict[str, float]:
        """
        Evaluate model performance on test data.
        
        Parameters:
        -----------
        model_name : str
            Name of the model to evaluate
            
        Returns:
        --------
        dict
            Dictionary containing evaluation metrics
        """
        if self.test_data is None:
            raise ValueError("No test data. Call split_data() first.")
        
        if model_name not in self.models:
            raise ValueError(f"Model '{model_name}' not fitted.")
        
        # Generate forecast for test period
        test_steps = len(self.test_data)
        forecast = self.forecast(test_steps, model_name)
        
        # Calculate metrics
        actual = self.test_data[self.demand_column].values
        predicted = forecast.values[:len(actual)]
        
        mse = mean_squared_error(actual, predicted)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(actual, predicted)
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100
        r2 = r2_score(actual, predicted)
        
        metrics = {
            'MSE': mse,
            'RMSE': rmse,
            'MAE': mae,
            'MAPE': mape,
            'R2': r2
        }
        
        self.metrics[model_name] = metrics
        
        print(f"\n{model_name.upper()} Model Evaluation Metrics:")
        print(f"  RMSE: {rmse:.2f}")
        print(f"  MAE: {mae:.2f}")
        print(f"  MAPE: {mape:.2f}%")
        print(f"  R²: {r2:.4f}")
        
        return metrics
    
    def plot_forecast(self, model_name: str = 'sarima', 
                     figsize: Tuple[int, int] = (15, 6),
                     show_train: bool = True) -> None:
        """
        Plot the forecast along with historical data.
        
        Parameters:
        -----------
        model_name : str
            Name of the model
        figsize : tuple
            Figure size
        show_train : bool
            Whether to show training data
        """
        if model_name not in self.forecasts:
            raise ValueError(f"No forecast available for {model_name}. Call forecast() first.")
        
        plt.figure(figsize=figsize)
        
        # Plot training data
        if show_train and self.train_data is not None:
            plt.plot(self.train_data.index, self.train_data[self.demand_column],
                    label='Training Data', alpha=0.7)
        
        # Plot test data
        if self.test_data is not None:
            plt.plot(self.test_data.index, self.test_data[self.demand_column],
                    label='Test Data', alpha=0.7)
        
        # Plot forecast
        forecast = self.forecasts[model_name]
        plt.plot(forecast.index, forecast.values, 
                label=f'{model_name.upper()} Forecast', 
                linestyle='--', linewidth=2)
        
        plt.xlabel('Date')
        plt.ylabel('Demand')
        plt.title(f'Energy Demand Forecast - {model_name.upper()}')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
    
    def plot_decomposition(self, period: int = 24, figsize: Tuple[int, int] = (15, 10)) -> None:
        """
        Plot seasonal decomposition of the time series.
        
        Parameters:
        -----------
        period : int
            Period of the seasonal component
        figsize : tuple
            Figure size
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        decomposition = seasonal_decompose(
            self.data[self.demand_column],
            model='additive',
            period=period
        )
        
        fig, axes = plt.subplots(4, 1, figsize=figsize)
        
        decomposition.observed.plot(ax=axes[0], title='Original')
        axes[0].set_ylabel('Demand')
        
        decomposition.trend.plot(ax=axes[1], title='Trend')
        axes[1].set_ylabel('Demand')
        
        decomposition.seasonal.plot(ax=axes[2], title='Seasonal')
        axes[2].set_ylabel('Demand')
        
        decomposition.resid.plot(ax=axes[3], title='Residual')
        axes[3].set_ylabel('Demand')
        
        plt.tight_layout()
        plt.show()
    
    def compare_models(self, steps: int = None) -> pd.DataFrame:
        """
        Compare all fitted models.
        
        Parameters:
        -----------
        steps : int, optional
            Number of steps to forecast. If None, uses test data length.
            
        Returns:
        --------
        pd.DataFrame
            Comparison of model metrics
        """
        if not self.models:
            raise ValueError("No models fitted.")
        
        if steps is None and self.test_data is not None:
            steps = len(self.test_data)
        elif steps is None:
            raise ValueError("Specify steps parameter or split data first.")
        
        results = []
        
        for model_name in self.models.keys():
            if model_name.endswith('_features'):
                continue
            
            try:
                metrics = self.evaluate(model_name)
                metrics['Model'] = model_name
                results.append(metrics)
            except Exception as e:
                print(f"Error evaluating {model_name}: {e}")
        
        comparison_df = pd.DataFrame(results)
        comparison_df = comparison_df[['Model', 'RMSE', 'MAE', 'MAPE', 'R2']]
        comparison_df = comparison_df.sort_values('RMSE')
        
        print("\nModel Comparison:")
        print(comparison_df.to_string(index=False))
        
        return comparison_df
    
    def save_forecast(self, filepath: str, model_name: str = 'sarima') -> None:
        """
        Save forecast to file.
        
        Parameters:
        -----------
        filepath : str
            Path to save the forecast
        model_name : str
            Name of the model
        """
        if model_name not in self.forecasts:
            raise ValueError(f"No forecast available for {model_name}")
        
        forecast_df = pd.DataFrame({
            'date': self.forecasts[model_name].index,
            'forecast': self.forecasts[model_name].values
        })
        
        if filepath.endswith('.csv'):
            forecast_df.to_csv(filepath, index=False)
        elif filepath.endswith(('.xls', '.xlsx')):
            forecast_df.to_excel(filepath, index=False)
        elif filepath.endswith('.json'):
            forecast_df.to_json(filepath, orient='records', date_format='iso')
        else:
            raise ValueError("Unsupported file format. Use CSV, Excel, or JSON.")
        
        print(f"Forecast saved to {filepath}")
    
    def auto_forecast(self, steps: int, methods: List[str] = None) -> Dict[str, pd.Series]:
        """
        Automatically fit multiple models and generate forecasts.
        
        Parameters:
        -----------
        steps : int
            Number of steps to forecast
        methods : list, optional
            List of methods to use. If None, uses all available methods.
            
        Returns:
        --------
        dict
            Dictionary of forecasts from each method
        """
        if methods is None:
            methods = ['sarima', 'exp_smoothing', 'random_forest', 'gradient_boosting']
        
        forecasts = {}
        
        for method in methods:
            try:
                if method == 'sarima':
                    self.fit_sarima()
                elif method == 'exp_smoothing':
                    self.fit_exponential_smoothing()
                elif method == 'random_forest':
                    self.fit_random_forest()
                elif method == 'gradient_boosting':
                    self.fit_gradient_boosting()
                elif method == 'prophet':
                    self.fit_prophet()
                
                forecast = self.forecast(steps, method)
                forecasts[method] = forecast
                
            except Exception as e:
                print(f"Error with {method}: {e}")
        
        return forecasts


def quick_forecast(data_path: str, 
                  steps: int,
                  date_column: str = 'date',
                  demand_column: str = 'demand',
                  method: str = 'sarima') -> pd.Series:
    """
    Quick forecast function for simple use cases.
    
    Parameters:
    -----------
    data_path : str
        Path to the demand data file
    steps : int
        Number of steps to forecast
    date_column : str
        Name of the date column
    demand_column : str
        Name of the demand column
    method : str
        Forecasting method to use
        
    Returns:
    --------
    pd.Series
        Forecasted values
    """
    forecaster = EnergyDemandForecaster(data_path, date_column, demand_column)
    forecaster.load_data()
    forecaster.split_data(test_size=0.2)
    
    if method == 'sarima':
        forecaster.fit_sarima()
    elif method == 'exp_smoothing':
        forecaster.fit_exponential_smoothing()
    elif method == 'random_forest':
        forecaster.fit_random_forest()
    elif method == 'gradient_boosting':
        forecaster.fit_gradient_boosting()
    elif method == 'prophet':
        forecaster.fit_prophet()
    else:
        raise ValueError(f"Unknown method: {method}")
    
    forecast = forecaster.forecast(steps, method)
    
    return forecast


if __name__ == "__main__":
    # Example usage
    print("Energy Demand Forecasting Module")
    print("=" * 50)
    print("\nExample usage:")
    print("""
    # Initialize forecaster
    forecaster = EnergyDemandForecaster(
        data_path='demand_data.csv',
        date_column='datetime',
        demand_column='demand_mw'
    )
    
    # Load and prepare data
    forecaster.load_data()
    forecaster.split_data(test_size=0.2)
    
    # Fit models
    forecaster.fit_sarima()
    forecaster.fit_random_forest()
    
    # Generate forecasts
    forecast = forecaster.forecast(steps=24, model_name='sarima')
    
    # Evaluate and compare
    forecaster.evaluate('sarima')
    forecaster.compare_models()
    
    # Visualize
    forecaster.plot_forecast('sarima')
    
    # Save forecast
    forecaster.save_forecast('forecast.csv', 'sarima')
    """)

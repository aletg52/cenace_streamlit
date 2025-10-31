"""
Data Assembler
==============
Handles data concatenation, cleaning, and export to various formats
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
import logging
import zipfile
import io
from pathlib import Path

logger = logging.getLogger(__name__)


class DataAssembler:
    """
    Assembles and cleans CENACE data from multiple API responses
    
    Features:
    - Concatenates data from multiple chunks
    - Cleans and validates data
    - Handles duplicates
    - Exports to CSV, Excel, and ZIP formats
    - Calculates derived metrics
    """
    
    def __init__(self):
        """Initialize the data assembler"""
        self.data = None
        self.assembled_at = None
    
    def assemble_data(self, raw_data: List[Dict]) -> pd.DataFrame:
        """
        Assemble raw data into a clean DataFrame
        
        Parameters:
        -----------
        raw_data : List[Dict]
            Raw data from API responses
        
        Returns:
        --------
        pd.DataFrame : Clean, assembled dataframe
        """
        if not raw_data:
            logger.warning("No data to assemble")
            # Return empty DataFrame with expected columns to prevent KeyError
            return pd.DataFrame(columns=['sistema', 'zona_carga', 'fecha', 'hora', 'demanda', 'datetime'])
        
        logger.info(f"Assembling {len(raw_data)} records")
        
        # Convert to DataFrame
        df = pd.DataFrame(raw_data)
        
        # Clean and transform data
        df = self._clean_data(df)
        
        # Add derived columns
        df = self._add_derived_columns(df)
        
        # Remove duplicates
        df = self._remove_duplicates(df)
        
        # Sort data
        df = self._sort_data(df)
        
        # Validate data
        df = self._validate_data(df)
        
        # Store assembled data
        self.data = df
        self.assembled_at = datetime.now()
        
        logger.info(f"Assembled {len(df)} clean records")
        
        return df
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize the data"""
        # Ensure required columns exist
        required_columns = ['sistema', 'zona_carga', 'fecha', 'hora', 'demanda']
        for col in required_columns:
            if col not in df.columns:
                if col == 'sistema':
                    df['sistema'] = 'SIN'  # Default system if not specified
                else:
                    logger.error(f"Missing required column: {col}")
                    return pd.DataFrame()
        
        # Clean zone names (ensure spaces are preserved)
        df['zona_carga'] = df['zona_carga'].str.strip()
        df['zona_carga'] = df['zona_carga'].str.replace('-', ' ')  # Convert dashes back to spaces
        
        # Parse dates
        df['fecha'] = pd.to_datetime(df['fecha'], format='%Y-%m-%d', errors='coerce')
        
        # Clean numeric columns
        df['hora'] = pd.to_numeric(df['hora'], errors='coerce').fillna(1).astype(int)
        df['demanda'] = pd.to_numeric(df['demanda'], errors='coerce').fillna(0.0)
        
        # Remove rows with invalid dates
        df = df[df['fecha'].notna()]
        
        # Ensure hora is in valid range (1-24)
        df['hora'] = df['hora'].clip(1, 24)
        
        # Remove negative demand values
        df.loc[df['demanda'] < 0, 'demanda'] = 0
        
        return df
    
    def _add_derived_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add derived columns for analysis"""
        if df.empty:
            return df
        
        # Create datetime column
        df['datetime'] = pd.to_datetime(df['fecha']) + pd.to_timedelta(df['hora'] - 1, unit='h')
        
        # Add time-based features
        df['year'] = df['fecha'].dt.year
        df['month'] = df['fecha'].dt.month
        df['day'] = df['fecha'].dt.day
        df['weekday'] = df['fecha'].dt.weekday
        df['is_weekend'] = df['weekday'].isin([5, 6])
        df['week'] = df['fecha'].dt.isocalendar().week
        
        # Add season
        df['season'] = df['month'].apply(self._get_season)
        
        # Add day type
        df['day_type'] = df['is_weekend'].map({True: 'Weekend', False: 'Weekday'})
        
        # Add hour categories
        df['hour_category'] = pd.cut(
            df['hora'],
            bins=[0, 6, 12, 18, 24],
            labels=['Night', 'Morning', 'Afternoon', 'Evening']
        )
        
        return df
    
    def _get_season(self, month: int) -> str:
        """Get season from month"""
        if month in [12, 1, 2]:
            return 'Winter'
        elif month in [3, 4, 5]:
            return 'Spring'
        elif month in [6, 7, 8]:
            return 'Summer'
        else:
            return 'Fall'
    
    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate records"""
        if df.empty:
            return df
        
        # Identify duplicates
        duplicate_cols = ['sistema', 'zona_carga', 'fecha', 'hora']
        duplicates = df.duplicated(subset=duplicate_cols, keep='first')
        
        if duplicates.any():
            logger.warning(f"Removing {duplicates.sum()} duplicate records")
            df = df[~duplicates]
        
        return df
    
    def _sort_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sort data by system, zone, and datetime"""
        if df.empty:
            return df
        
        df = df.sort_values(['sistema', 'zona_carga', 'datetime'])
        df = df.reset_index(drop=True)
        
        return df
    
    def _validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate data and flag anomalies"""
        if df.empty:
            return df
        
        # Calculate statistics for anomaly detection
        for zona in df['zona_carga'].unique():
            zona_data = df[df['zona_carga'] == zona]
            
            # Calculate mean and std
            mean_demand = zona_data['demanda'].mean()
            std_demand = zona_data['demanda'].std()
            
            # Flag anomalies (values beyond 3 standard deviations)
            if std_demand > 0:
                df.loc[df['zona_carga'] == zona, 'is_anomaly'] = (
                    abs(df.loc[df['zona_carga'] == zona, 'demanda'] - mean_demand) > 3 * std_demand
                )
            else:
                df.loc[df['zona_carga'] == zona, 'is_anomaly'] = False
        
        # Log anomalies
        anomalies = df[df.get('is_anomaly', False) == True]
        if len(anomalies) > 0:
            logger.info(f"Found {len(anomalies)} anomalous readings")
        
        return df
    
    def get_statistics(self) -> Dict:
        """Get statistics about the assembled data"""
        if self.data is None or self.data.empty:
            return {}
        
        df = self.data
        
        stats = {
            'total_records': len(df),
            'date_range': f"{df['fecha'].min().date()} to {df['fecha'].max().date()}",
            'systems': df['sistema'].unique().tolist(),
            'num_systems': df['sistema'].nunique(),
            'zones': df['zona_carga'].unique().tolist(),
            'num_zones': df['zona_carga'].nunique(),
            'total_demand_mwh': df['demanda'].sum(),
            'avg_demand_mw': df['demanda'].mean(),
            'peak_demand_mw': df['demanda'].max(),
            'min_demand_mw': df['demanda'].min(),
            'anomalies': df.get('is_anomaly', pd.Series([False])).sum(),
            'assembled_at': self.assembled_at.isoformat() if self.assembled_at else None
        }
        
        return stats
    
    def get_zone_statistics(self, zona: Optional[str] = None) -> pd.DataFrame:
        """Get statistics by zone"""
        if self.data is None or self.data.empty:
            return pd.DataFrame()
        
        df = self.data
        
        if zona:
            df = df[df['zona_carga'] == zona]
        
        stats = df.groupby('zona_carga').agg({
            'demanda': ['count', 'mean', 'std', 'min', 'max', 'sum'],
            'fecha': ['min', 'max']
        }).round(2)
        
        # Flatten column names
        stats.columns = ['_'.join(col).strip() for col in stats.columns.values]
        
        # Calculate additional metrics
        stats['load_factor'] = (stats['demanda_mean'] / stats['demanda_max'] * 100).round(2)
        stats['cv'] = (stats['demanda_std'] / stats['demanda_mean'] * 100).round(2)  # Coefficient of variation
        
        return stats
    
    def get_daily_summary(self) -> pd.DataFrame:
        """Get daily summary statistics"""
        if self.data is None or self.data.empty:
            return pd.DataFrame()
        
        df = self.data
        
        daily = df.groupby([df['fecha'].dt.date, 'sistema', 'zona_carga']).agg({
            'demanda': ['mean', 'max', 'min', 'sum']
        }).round(2)
        
        # Flatten column names
        daily.columns = ['_'.join(col).strip() for col in daily.columns.values]
        
        return daily
    
    def get_hourly_profile(self, zona: Optional[str] = None) -> pd.DataFrame:
        """Get average hourly profile"""
        if self.data is None or self.data.empty:
            return pd.DataFrame()
        
        df = self.data
        
        if zona:
            df = df[df['zona_carga'] == zona]
        
        hourly = df.groupby(['hora', 'day_type']).agg({
            'demanda': ['mean', 'std']
        }).round(2)
        
        # Flatten column names
        hourly.columns = ['_'.join(col).strip() for col in hourly.columns.values]
        
        return hourly
    
    def export_to_csv(self, filepath: str, zona: Optional[str] = None):
        """Export data to CSV file"""
        if self.data is None or self.data.empty:
            logger.warning("No data to export")
            return
        
        df = self.data
        
        if zona:
            df = df[df['zona_carga'] == zona]
        
        df.to_csv(filepath, index=False)
        logger.info(f"Exported {len(df)} records to {filepath}")
    
    def export_to_excel(self, filepath: str, include_analysis: bool = True):
        """Export data to Excel with multiple sheets"""
        if self.data is None or self.data.empty:
            logger.warning("No data to export")
            return
        
        with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
            # Raw data
            self.data.to_excel(writer, sheet_name='Raw Data', index=False)
            
            if include_analysis:
                # Zone statistics
                zone_stats = self.get_zone_statistics()
                if not zone_stats.empty:
                    zone_stats.to_excel(writer, sheet_name='Zone Statistics')
                
                # Daily summary
                daily_summary = self.get_daily_summary()
                if not daily_summary.empty:
                    daily_summary.to_excel(writer, sheet_name='Daily Summary')
                
                # Hourly profile
                hourly_profile = self.get_hourly_profile()
                if not hourly_profile.empty:
                    hourly_profile.to_excel(writer, sheet_name='Hourly Profile')
                
                # Overall statistics
                stats_df = pd.DataFrame([self.get_statistics()]).T
                stats_df.to_excel(writer, sheet_name='Overall Statistics', header=['Value'])
        
        logger.info(f"Exported data with analysis to {filepath}")
    
    def export_to_zip(self, filepath: str, by_zone: bool = True, by_system: bool = True):
        """Export data to ZIP file with multiple CSVs"""
        if self.data is None or self.data.empty:
            logger.warning("No data to export")
            return
        
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Combined data
            combined_csv = io.StringIO()
            self.data.to_csv(combined_csv, index=False)
            zipf.writestr('all_data.csv', combined_csv.getvalue())
            
            # By zone
            if by_zone:
                for zona in self.data['zona_carga'].unique():
                    zona_df = self.data[self.data['zona_carga'] == zona]
                    zona_csv = io.StringIO()
                    zona_df.to_csv(zona_csv, index=False)
                    safe_zona_name = zona.replace(' ', '_').replace('/', '_')
                    zipf.writestr(f'zones/{safe_zona_name}.csv', zona_csv.getvalue())
            
            # By system
            if by_system:
                for sistema in self.data['sistema'].unique():
                    system_df = self.data[self.data['sistema'] == sistema]
                    system_csv = io.StringIO()
                    system_df.to_csv(system_csv, index=False)
                    zipf.writestr(f'systems/{sistema}.csv', system_csv.getvalue())
            
            # Statistics
            stats_csv = io.StringIO()
            self.get_zone_statistics().to_csv(stats_csv)
            zipf.writestr('statistics/zone_statistics.csv', stats_csv.getvalue())
            
            daily_csv = io.StringIO()
            self.get_daily_summary().to_csv(daily_csv)
            zipf.writestr('statistics/daily_summary.csv', daily_csv.getvalue())
        
        logger.info(f"Exported data to ZIP file: {filepath}")
    
    def get_data_quality_report(self) -> Dict:
        """Generate a data quality report"""
        if self.data is None or self.data.empty:
            return {}
        
        df = self.data
        
        report = {
            'total_records': len(df),
            'complete_records': len(df.dropna()),
            'missing_values': df.isnull().sum().to_dict(),
            'duplicate_records': df.duplicated().sum(),
            'anomalies': df.get('is_anomaly', pd.Series([False])).sum(),
            'zero_demand_records': (df['demanda'] == 0).sum(),
            'negative_demand_records': (df['demanda'] < 0).sum(),
            'date_range_consistency': {
                'expected_hours': ((df['fecha'].max() - df['fecha'].min()).days + 1) * 24,
                'actual_records_per_zone': len(df) / df['zona_carga'].nunique() if df['zona_carga'].nunique() > 0 else 0
            },
            'zones_with_gaps': []
        }
        
        # Check for gaps in data
        for zona in df['zona_carga'].unique():
            zona_df = df[df['zona_carga'] == zona]
            expected_records = ((zona_df['fecha'].max() - zona_df['fecha'].min()).days + 1) * 24
            actual_records = len(zona_df)
            
            if actual_records < expected_records * 0.95:  # Allow 5% missing
                report['zones_with_gaps'].append({
                    'zone': zona,
                    'expected': expected_records,
                    'actual': actual_records,
                    'completeness': f"{(actual_records/expected_records*100):.1f}%"
                })
        
        return report

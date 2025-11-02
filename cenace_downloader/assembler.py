"""
Data Assembler
==============
Handles data concatenation, cleaning, and export to various formats
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Sequence
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
    
    def assemble_data(
        self,
        demand_data: Optional[Sequence[Dict]] = None,
        price_data: Optional[Sequence[Dict]] = None
    ) -> pd.DataFrame:
        """Assemble raw demand and price data into a clean DataFrame."""

        if demand_data is None and price_data is None:
            logger.warning("No data to assemble")
            return pd.DataFrame(columns=['sistema', 'zona_carga', 'fecha', 'hora', 'demanda', 'datetime'])

        def _to_dataframe(records: Optional[Sequence[Dict]]) -> pd.DataFrame:
            if records is None:
                return pd.DataFrame()
            if isinstance(records, pd.DataFrame):
                return records.copy()
            return pd.DataFrame(list(records)) if records else pd.DataFrame()

        demand_df = _to_dataframe(demand_data)
        price_df = _to_dataframe(price_data)

        merge_keys = ['sistema', 'zona_carga', 'fecha', 'hora']

        if demand_df.empty and price_df.empty:
            logger.warning("Provided data frames are empty")
            return pd.DataFrame(columns=merge_keys + ['demanda', 'datetime'])

        if price_df.empty:
            df = demand_df
        elif demand_df.empty:
            df = price_df
        else:
            rename_map = {}
            for col in price_df.columns:
                if col in merge_keys:
                    continue
                if col in demand_df.columns:
                    rename_map[col] = f"{col}_price"

            price_df = price_df.rename(columns=rename_map)
            price_columns = [col for col in price_df.columns if col not in merge_keys]
            df = pd.merge(
                demand_df,
                price_df[merge_keys + price_columns],
                on=merge_keys,
                how='outer'
            )

        logger.info(f"Assembling {len(df)} records")

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
    
    def _get_price_columns(self, df: pd.DataFrame) -> List[str]:
        """Identify columns that contain price information."""
        price_prefixes = ('precio', 'componente')
        price_suffix = '_precio'
        return [
            col for col in df.columns
            if col not in {'demanda'}
            and (col.startswith(price_prefixes) or col.endswith(price_suffix))
        ]

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize the data"""
        # Ensure required columns exist
        required_columns = ['sistema', 'zona_carga', 'fecha', 'hora']
        for col in required_columns:
            if col not in df.columns:
                if col == 'sistema':
                    df['sistema'] = 'SIN'  # Default system if not specified
                else:
                    logger.error(f"Missing required column: {col}")
                    return pd.DataFrame()

        if 'demanda' not in df.columns:
            df['demanda'] = np.nan

        # Clean zone names (ensure spaces are preserved)
        df['zona_carga'] = df['zona_carga'].astype(str).str.strip()
        df['zona_carga'] = df['zona_carga'].str.replace('-', ' ')  # Convert dashes back to spaces

        # Parse dates
        df['fecha'] = pd.to_datetime(df['fecha'], format='%Y-%m-%d', errors='coerce')

        # Clean numeric columns
        df['hora'] = pd.to_numeric(df['hora'], errors='coerce')
        df['hora'] = df['hora'].clip(1, 24)
        df['hora'] = df['hora'].fillna(1).astype(int)
        df['demanda'] = pd.to_numeric(df['demanda'], errors='coerce')

        # Normalize price-related columns
        price_columns = self._get_price_columns(df)
        for col in price_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Remove rows with invalid dates
        df = df[df['fecha'].notna()]

        # Remove negative demand values
        df.loc[df['demanda'] < 0, 'demanda'] = np.nan

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
        
        price_columns = self._get_price_columns(df)

        df['is_demand_anomaly'] = False
        df['is_price_anomaly'] = False
        for col in price_columns:
            anomaly_col = f'is_anomaly_{col}'
            if anomaly_col not in df.columns:
                df[anomaly_col] = False

        # Calculate statistics for anomaly detection
        for zona in df['zona_carga'].dropna().unique():
            zona_mask = df['zona_carga'] == zona
            zona_data = df.loc[zona_mask]

            demand_series = zona_data['demanda'].dropna()
            if not demand_series.empty:
                mean_demand = demand_series.mean()
                std_demand = demand_series.std()
                if pd.notna(std_demand) and std_demand > 0:
                    anomalies = (zona_data['demanda'] - mean_demand).abs() > 3 * std_demand
                    df.loc[zona_mask, 'is_demand_anomaly'] = anomalies.fillna(False)
                else:
                    df.loc[zona_mask, 'is_demand_anomaly'] = False
            else:
                df.loc[zona_mask, 'is_demand_anomaly'] = False

            for price_col in price_columns:
                anomaly_col = f'is_anomaly_{price_col}'
                price_series = zona_data[price_col].dropna()
                if price_series.empty:
                    df.loc[zona_mask, anomaly_col] = False
                    continue

                mean_price = price_series.mean()
                std_price = price_series.std()
                if pd.notna(std_price) and std_price > 0:
                    price_anomalies = (zona_data[price_col] - mean_price).abs() > 3 * std_price
                    price_anomalies = price_anomalies.fillna(False)
                    df.loc[zona_mask, anomaly_col] = price_anomalies
                    df.loc[zona_mask, 'is_price_anomaly'] = df.loc[zona_mask, 'is_price_anomaly'] | price_anomalies
                else:
                    df.loc[zona_mask, anomaly_col] = False

        # Log anomalies
        demand_anomalies = df[df.get('is_demand_anomaly', False) == True]
        price_anomalies = df[df.get('is_price_anomaly', False) == True]
        if len(demand_anomalies) > 0:
            logger.info(f"Found {len(demand_anomalies)} anomalous demand readings")
        if len(price_anomalies) > 0:
            logger.info(f"Found {len(price_anomalies)} anomalous price readings")

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
            'demand_anomalies': df.get('is_demand_anomaly', pd.Series([False])).sum(),
            'price_anomalies': df.get('is_price_anomaly', pd.Series([False])).sum(),
            'assembled_at': self.assembled_at.isoformat() if self.assembled_at else None
        }

        price_columns = self._get_price_columns(df)
        if price_columns:
            stats['price_columns'] = price_columns
            stats['avg_prices'] = {col: float(df[col].mean()) for col in price_columns}
            stats['peak_prices'] = {col: float(df[col].max()) for col in price_columns}
            stats['min_prices'] = {col: float(df[col].min()) for col in price_columns}

        return stats
    
    def get_zone_statistics(self, zona: Optional[str] = None) -> pd.DataFrame:
        """Get statistics by zone"""
        if self.data is None or self.data.empty:
            return pd.DataFrame()
        
        df = self.data
        
        if zona:
            df = df[df['zona_carga'] == zona]
        
        aggregations: Dict[str, List[str]] = {
            'demanda': ['count', 'mean', 'std', 'min', 'max', 'sum'],
            'fecha': ['min', 'max']
        }

        for col in self._get_price_columns(df):
            aggregations[col] = ['mean', 'std', 'min', 'max']

        stats = df.groupby('zona_carga').agg(aggregations).round(2)

        # Flatten column names
        stats.columns = ['_'.join(col).strip() for col in stats.columns.values]

        # Calculate additional metrics
        if 'demanda_mean' in stats.columns and 'demanda_max' in stats.columns:
            load_factor = stats['demanda_mean'] / stats['demanda_max'] * 100
            stats['load_factor'] = load_factor.replace([np.inf, -np.inf], np.nan).round(2)
        if 'demanda_std' in stats.columns and 'demanda_mean' in stats.columns:
            cv = stats['demanda_std'] / stats['demanda_mean'] * 100
            stats['cv'] = cv.replace([np.inf, -np.inf], np.nan).round(2)

        return stats
    
    def get_daily_summary(self) -> pd.DataFrame:
        """Get daily summary statistics"""
        if self.data is None or self.data.empty:
            return pd.DataFrame()
        
        df = self.data
        
        aggregations: Dict[str, List[str]] = {
            'demanda': ['mean', 'max', 'min', 'sum']
        }

        for col in self._get_price_columns(df):
            aggregations[col] = ['mean', 'max', 'min']

        daily = df.groupby([df['fecha'].dt.date, 'sistema', 'zona_carga']).agg(aggregations).round(2)

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
        
        aggregations: Dict[str, List[str]] = {
            'demanda': ['mean', 'std']
        }

        for col in self._get_price_columns(df):
            aggregations[col] = ['mean', 'std']

        hourly = df.groupby(['hora', 'day_type']).agg(aggregations).round(2)
        
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
        
        price_columns = self._get_price_columns(df)

        report = {
            'total_records': len(df),
            'complete_records': len(df.dropna()),
            'complete_demand_records': int(df['demanda'].notna().sum()),
            'complete_price_records': {col: int(df[col].notna().sum()) for col in price_columns},
            'missing_values': df.isnull().sum().to_dict(),
            'duplicate_records': df.duplicated().sum(),
            'demand_anomalies': df.get('is_demand_anomaly', pd.Series([False])).sum(),
            'price_anomalies': df.get('is_price_anomaly', pd.Series([False])).sum(),
            'zero_demand_records': int((df['demanda'] == 0).sum()),
            'negative_demand_records': int((df['demanda'] < 0).sum()),
            'zero_price_records': {col: int((df[col] == 0).sum()) for col in price_columns},
            'date_range_consistency': {
                'expected_hours': ((df['fecha'].max() - df['fecha'].min()).days + 1) * 24,
                'actual_records_per_zone': len(df) / df['zona_carga'].nunique() if df['zona_carga'].nunique() > 0 else 0
            },
            'zones_with_gaps': [],
            'price_columns': price_columns,
            'help_text': (
                "Report covers demand and price completeness, zero-value counts, "
                "and anomaly detection for both metrics."
            )
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

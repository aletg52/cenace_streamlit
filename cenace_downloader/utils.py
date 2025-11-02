"""
Utility Functions
=================
Helper functions for the CENACE downloader package
"""

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def estimate_download_time(num_zones: int, num_days: int, delay_per_request: float = 1.0) -> str:
    """
    Estimate the download time based on parameters
    
    Parameters:
    -----------
    num_zones : int
        Number of zones to download
    num_days : int  
        Number of days in the date range
    delay_per_request : float
        Delay between requests in seconds
    
    Returns:
    --------
    str : Human-readable time estimate
    """
    # Calculate number of API calls needed
    zone_batches = (num_zones + 9) // 10  # Ceiling division for 10-zone batches
    day_chunks = (num_days + 6) // 7  # Ceiling division for 7-day chunks

    # Each chunk now requires one demand call (SWCAEZC) and one price call (SWPEND)
    total_requests = zone_batches * day_chunks * 2

    # Estimate time per request (API response + processing + delay)
    demand_response_time = 2.0  # Average demand API response time in seconds
    price_response_time = 2.3  # Average price API response time in seconds
    processing_time = 0.5  # Time to process each response

    time_per_cycle = (
        demand_response_time
        + price_response_time
        + 2 * processing_time
        + 2 * delay_per_request
    )

    total_time = (zone_batches * day_chunks) * time_per_cycle

    return format_duration(total_time)


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string
    
    Parameters:
    -----------
    seconds : float
        Duration in seconds
    
    Returns:
    --------
    str : Human-readable duration
    """
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        remaining_seconds = int(seconds % 60)
        if remaining_seconds > 0:
            return f"{minutes} min {remaining_seconds} sec"
        return f"{minutes} minutes"
    else:
        hours = int(seconds / 3600)
        remaining_minutes = int((seconds % 3600) / 60)
        if remaining_minutes > 0:
            return f"{hours} hr {remaining_minutes} min"
        return f"{hours} hours"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human-readable string
    
    Parameters:
    -----------
    size_bytes : int
        Size in bytes
    
    Returns:
    --------
    str : Human-readable file size
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def chunk_date_range(start_date: datetime.date, end_date: datetime.date, 
                    chunk_size: int = 7) -> List[Tuple[datetime.date, datetime.date]]:
    """
    Split a date range into chunks
    
    Parameters:
    -----------
    start_date : datetime.date
        Start date
    end_date : datetime.date
        End date
    chunk_size : int
        Maximum days per chunk
    
    Returns:
    --------
    List[Tuple[datetime.date, datetime.date]] : List of date range chunks
    """
    chunks = []
    current_start = start_date
    
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=chunk_size - 1), end_date)
        chunks.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    
    return chunks


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """
    Split a list into chunks of specified size
    
    Parameters:
    -----------
    lst : List
        List to chunk
    chunk_size : int
        Maximum items per chunk
    
    Returns:
    --------
    List[List] : List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def generate_cache_key(params: Dict) -> str:
    """
    Generate a cache key from parameters
    
    Parameters:
    -----------
    params : Dict
        Parameters to include in cache key
    
    Returns:
    --------
    str : MD5 hash as cache key
    """
    # Sort keys for consistency
    sorted_params = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(sorted_params.encode()).hexdigest()


def validate_date_range(start_date: datetime.date, end_date: datetime.date,
                       max_days: int = 365) -> Tuple[bool, str]:
    """
    Validate a date range
    
    Parameters:
    -----------
    start_date : datetime.date
        Start date
    end_date : datetime.date
        End date
    max_days : int
        Maximum allowed days in range
    
    Returns:
    --------
    Tuple[bool, str] : (is_valid, error_message)
    """
    # Check start date is before end date
    if start_date > end_date:
        return False, "Start date must be before end date"
    
    # Check date range is not too long
    days_diff = (end_date - start_date).days + 1
    if days_diff > max_days:
        return False, f"Date range exceeds maximum of {max_days} days"
    
    # Check dates are not in the future
    today = datetime.now().date()
    if start_date > today:
        return False, "Start date cannot be in the future"
    
    # CENACE data typically has 1-day delay
    if end_date >= today:
        return False, "End date should be at least 1 day in the past for data availability"
    
    return True, ""


def parse_cenace_datetime(fecha: str, hora: int) -> datetime:
    """
    Parse CENACE date and hour into datetime
    
    Parameters:
    -----------
    fecha : str
        Date string (YYYY-MM-DD)
    hora : int
        Hour (1-24)
    
    Returns:
    --------
    datetime : Combined datetime object
    """
    try:
        date = datetime.strptime(fecha, "%Y-%m-%d")
        # CENACE uses hours 1-24, convert to 0-23 for datetime
        hour = max(0, min(23, hora - 1))
        return date.replace(hour=hour)
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing datetime: {fecha} hour {hora}: {e}")
        return datetime.now()


def calculate_statistics(data: List[float]) -> Dict:
    """
    Calculate basic statistics for a list of values
    
    Parameters:
    -----------
    data : List[float]
        List of numeric values
    
    Returns:
    --------
    Dict : Statistics dictionary
    """
    if not data:
        return {
            'count': 0,
            'mean': 0,
            'std': 0,
            'min': 0,
            'max': 0,
            'sum': 0
        }
    
    import numpy as np
    
    data_array = np.array(data)
    
    return {
        'count': len(data),
        'mean': float(np.mean(data_array)),
        'std': float(np.std(data_array)),
        'min': float(np.min(data_array)),
        'max': float(np.max(data_array)),
        'sum': float(np.sum(data_array)),
        'median': float(np.median(data_array)),
        'q1': float(np.percentile(data_array, 25)),
        'q3': float(np.percentile(data_array, 75))
    }


def create_progress_message(current: int, total: int, prefix: str = "Progress",
                           suffix: str = "Complete") -> str:
    """
    Create a progress message
    
    Parameters:
    -----------
    current : int
        Current progress value
    total : int
        Total value
    prefix : str
        Prefix for the message
    suffix : str
        Suffix for the message
    
    Returns:
    --------
    str : Progress message
    """
    if total == 0:
        percent = 0
    else:
        percent = min(100, (current * 100) / total)
    
    return f"{prefix}: {current}/{total} ({percent:.1f}%) {suffix}"


def safe_filename(filename: str) -> str:
    """
    Convert a string to a safe filename
    
    Parameters:
    -----------
    filename : str
        Original filename
    
    Returns:
    --------
    str : Safe filename
    """
    # Remove or replace unsafe characters
    safe_chars = [c if c.isalnum() or c in (' ', '-', '_', '.') else '_' 
                  for c in filename]
    safe_name = ''.join(safe_chars)
    
    # Remove multiple underscores
    while '__' in safe_name:
        safe_name = safe_name.replace('__', '_')
    
    return safe_name.strip('_')


def get_season_from_date(date: datetime.date) -> str:
    """
    Get the season for a given date (Mexican seasons)
    
    Parameters:
    -----------
    date : datetime.date
        Date to check
    
    Returns:
    --------
    str : Season name
    """
    month = date.month
    
    if month in [12, 1, 2]:
        return 'Winter'
    elif month in [3, 4, 5]:
        return 'Spring'
    elif month in [6, 7, 8]:
        return 'Summer'
    else:
        return 'Fall'


def is_peak_hour(hour: int) -> bool:
    """
    Check if an hour is during peak demand time
    
    Parameters:
    -----------
    hour : int
        Hour (1-24)
    
    Returns:
    --------
    bool : True if peak hour
    """
    # Peak hours in Mexico are typically 18:00-22:00 (hours 19-23 in 1-24 format)
    return 19 <= hour <= 23


def is_business_day(date: datetime.date) -> bool:
    """
    Check if a date is a business day (Mon-Fri)
    
    Parameters:
    -----------
    date : datetime.date
        Date to check
    
    Returns:
    --------
    bool : True if business day
    """
    return date.weekday() < 5  # Monday = 0, Friday = 4


def format_demand_value(value: float, precision: int = 2) -> str:
    """
    Format a demand value with units
    
    Parameters:
    -----------
    value : float
        Demand value in MW
    precision : int
        Decimal precision
    
    Returns:
    --------
    str : Formatted value with units
    """
    if value >= 1000:
        return f"{value/1000:.{precision}f} GW"
    else:
        return f"{value:.{precision}f} MW"

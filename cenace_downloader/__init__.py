"""
CENACE Downloader Package
========================
A modular package for downloading electrical demand data from CENACE's web service
"""

from .client import CENACEClient
from .assembler import DataAssembler
from .zones import (
    get_all_zones, 
    get_all_zones_with_regional,
    get_regional_controls_for_system,
    get_zones_for_regional_control,
    get_regional_control_for_zone,
    ZONES_BY_SYSTEM,
    ZONES_BY_SYSTEM_REGIONAL
)
from .utils import estimate_download_time, format_file_size

__version__ = "1.0.0"
__author__ = "CENACE Downloader"

__all__ = [
    'CENACEClient',
    'DataAssembler',
    'get_all_zones',
    'get_all_zones_with_regional',
    'get_regional_controls_for_system',
    'get_zones_for_regional_control',
    'get_regional_control_for_zone',
    'ZONES_BY_SYSTEM',
    'ZONES_BY_SYSTEM_REGIONAL',
    'estimate_download_time',
    'format_file_size'
]

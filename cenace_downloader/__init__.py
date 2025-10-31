"""
CENACE Downloader Package
========================
A modular package for downloading electrical demand data from CENACE's web service
"""

from .client import CENACEClient
from .assembler import DataAssembler
from .zones import get_all_zones, ZONES_BY_SYSTEM
from .utils import estimate_download_time, format_file_size

__version__ = "1.0.0"
__author__ = "CENACE Downloader"

__all__ = [
    'CENACEClient',
    'DataAssembler',
    'get_all_zones',
    'ZONES_BY_SYSTEM',
    'estimate_download_time',
    'format_file_size'
]

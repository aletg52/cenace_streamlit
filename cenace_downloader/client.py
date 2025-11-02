"""
CENACE API Client
=================
Handles HTTP calls to CENACE's web service with retries, caching, and automatic chunking
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple
import logging
import re
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = Path.home() / ".cenace_cache"
CACHE_DIR.mkdir(exist_ok=True)


class CENACEClient:
    """
    Client for interacting with CENACE's web service
    
    Features:
    - Automatic 7-day window chunking
    - 10-zone batch processing
    - Smart caching with 24-hour expiration
    - Configurable retry logic
    - Progress tracking
    """
    
    BASE_URL_DEMAND = "https://ws01.cenace.gob.mx:8082/SWCAEZC/SIM"
    BASE_URL_PRICE = "https://ws01.cenace.gob.mx:8082/SWPEND/SIM"
    MAX_DAYS_PER_REQUEST = 7
    MAX_ZONES_PER_REQUEST = 10
    CACHE_DURATION_HOURS = 24
    
    def __init__(self, verify_ssl=False, retry_attempts=3, delay=1.0, cache_enabled=True):
        """
        Initialize the CENACE client
        
        Parameters:
        -----------
        verify_ssl : bool
            Whether to verify SSL certificates
        retry_attempts : int
            Number of retry attempts for failed requests
        delay : float
            Delay between requests in seconds
        cache_enabled : bool
            Whether to use caching
        """
        self.verify_ssl = verify_ssl
        self.retry_attempts = retry_attempts
        self.delay = delay
        self.cache_enabled = cache_enabled
        self.session = requests.Session()
        
        # Disable SSL warnings if not verifying
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def _get_cache_key(self, system: str, zones: List[str], start_date: datetime.date,
                      end_date: datetime.date, process: str, data_type: str) -> str:
        """Generate a unique cache key for the request"""
        zones_str = ",".join(sorted(zones))
        key_str = f"{system}_{process}_{data_type}_{zones_str}_{start_date}_{end_date}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached_data(self, cache_key: str) -> Optional[Dict]:
        """Retrieve cached data if available and not expired"""
        if not self.cache_enabled:
            return None
        
        cache_file = CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                
                # Check if cache is expired (24 hours)
                cached_time = datetime.fromisoformat(cached['timestamp'])
                if datetime.now() - cached_time < timedelta(hours=self.CACHE_DURATION_HOURS):
                    logger.info(f"Using cached data for key: {cache_key}")
                    return cached['data']
                else:
                    logger.info(f"Cache expired for key: {cache_key}")
                    cache_file.unlink()  # Delete expired cache
            except Exception as e:
                logger.warning(f"Error reading cache: {e}")
        
        return None
    
    def _save_cache(self, cache_key: str, data: Dict):
        """Save data to cache"""
        if not self.cache_enabled:
            return
        
        cache_file = CACHE_DIR / f"{cache_key}.json"
        try:
            cached_data = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f)
            logger.info(f"Saved cache for key: {cache_key}")
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")
    
    def _format_date(self, date: datetime.date) -> str:
        """Format date for URL"""
        return f"{date.year}/{date.month:02d}/{date.day:02d}"
    
    def _build_url(self, base_url: str, system: str, zones: List[str], start_date: datetime.date,
                   end_date: datetime.date, process: str, response_format: str = "XML") -> str:
        """Build the service URL"""
        # Convert zone names with spaces to dashes for URL
        zones_str = ",".join(z.strip().replace(" ", "-") for z in zones)

        url_parts = [base_url, system, process]

        if zones_str:
            url_parts.append(zones_str)

        url_parts.extend([
            self._format_date(start_date),
            self._format_date(end_date)
        ])

        if response_format.upper() == "JSON":
            url_parts.extend(["formato", "JSON"])

        return "/".join(url_parts)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError))
    )
    def _make_request(self, url: str, expected_format: str = "XML") -> str:
        """Make HTTP request with retry logic"""
        logger.info(f"Making request to: {url}")

        response = self.session.get(url, verify=self.verify_ssl, timeout=30)
        response.raise_for_status()

        if expected_format.upper() == "XML":
            # Check if we got valid XML
            if not response.text or response.text.startswith('<!DOCTYPE'):
                raise ValueError("Invalid response from server")

        return response.text
    
    def _parse_xml_response(self, xml_content: str) -> List[Dict]:
        """Parse XML response from CENACE"""
        try:
            # Clean the XML content
            xml_content = xml_content.strip()
            if xml_content.startswith('<?xml'):
                xml_content = xml_content.split('>', 1)[1]
            
            # Parse XML
            root = ET.fromstring(f'<root>{xml_content}</root>')
            
            data = []
            # Parse the actual XML structure: <Resultados><Zona_Carga>...</Zona_Carga></Resultados>
            for zona_carga_elem in root.findall('.//Zona_Carga'):
                # Get zona_carga from child element text, not attribute
                zona_carga = zona_carga_elem.findtext('zona_carga', '').strip()
                
                if not zona_carga:
                    logger.warning("Could not find zona_carga in Zona_Carga element")
                    continue
                
                # Find Valores container
                valores_elem = zona_carga_elem.find('Valores')
                if valores_elem is None:
                    continue
                
                # Iterate through Valor elements (capital V, not lowercase valores)
                for valor in valores_elem.findall('Valor'):
                    try:
                        # Get values from child element text, not attributes
                        fecha = valor.findtext('fecha', '').strip()
                        hora_str = valor.findtext('hora', '0').strip()
                        demanda_str = valor.findtext('total_cargas', '0').strip()
                        
                        if not fecha:
                            logger.warning("Missing fecha in Valor element")
                            continue
                        
                        record = {
                            'zona_carga': zona_carga,
                            'fecha': fecha,
                            'hora': int(hora_str) if hora_str else 0,
                            'demanda': float(demanda_str) if demanda_str else 0.0
                        }
                        data.append(record)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing Valor record: {e}")
                        continue
            
            if not data:
                logger.warning("No data extracted from XML. Checking structure...")
                # Log XML structure for debugging
                logger.debug(f"XML root: {root.tag}")
                logger.debug(f"Found elements: {[elem.tag for elem in root.iter()][:20]}")
            
            return data
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            # Try alternative parsing for different XML structure
            return self._parse_alternative_xml(xml_content)
    
    def _parse_alternative_xml(self, xml_content: str) -> List[Dict]:
        """Alternative XML parsing for different response structures"""
        try:
            # Handle case where response might have different structure
            root = ET.fromstring(xml_content)
            
            data = []
            
            # Try to find Zona_Carga elements (with underscore) or Zona elements
            for zona_elem in root.findall('.//Zona_Carga') + root.findall('.//Zona'):
                # Try to get zona_carga from child element or attribute
                zona_carga = zona_elem.findtext('zona_carga', '')
                if not zona_carga:
                    zona_carga = zona_elem.get('zona_carga', zona_elem.get('zona', '')).strip()
                
                if not zona_carga:
                    continue
                
                # Look for Valores container
                valores_container = zona_elem.find('Valores')
                if valores_container is None:
                    continue
                
                # Look for Valor or valores elements (try both capital and lowercase)
                for valor in valores_container.findall('Valor') + valores_container.findall('valores'):
                    # Try to get from child elements first (using findtext)
                    fecha = valor.findtext('fecha', '')
                    if not fecha:
                        fecha = valor.get('fecha', '')
                    
                    hora_str = valor.findtext('hora', '')
                    if not hora_str:
                        hora_str = valor.get('hora', valor.get('hour', '0'))
                    
                    demanda_str = valor.findtext('total_cargas', '')
                    if not demanda_str:
                        demanda_str = valor.get('total_cargas', valor.get('demanda', '0'))
                    
                    if fecha and demanda_str:
                        try:
                            record = {
                                'zona_carga': zona_carga.strip(),
                                'fecha': fecha.strip(),
                                'hora': int(hora_str) if hora_str else 0,
                                'demanda': float(demanda_str) if demanda_str else 0.0
                            }
                            data.append(record)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error parsing record in alternative parser: {e}")
                            continue
            
            return data
            
        except Exception as e:
            logger.error(f"Alternative XML parsing failed: {e}")
            logger.error(f"XML content (first 500 chars): {xml_content[:500]}")
            return []

    def _parse_price_response(self, json_content: str) -> List[Dict]:
        """Parse JSON response for zonal prices"""
        try:
            payload = json.loads(json_content)
        except json.JSONDecodeError as exc:
            logger.error(f"JSON parsing error: {exc}")
            return []

        records: List[Dict] = []
        total_keys = {
            'precio_total',
            'precioTotal',
            'precio_nodo',
            'precioNodo',
            'precioMarginalLocal',
            'precio_marginal_local'
        }

        def collect(obj, current_system=None, current_zone=None):
            if isinstance(obj, dict):
                system = obj.get('sistema') or obj.get('Sistema') or current_system
                zone = (obj.get('zona_carga') or obj.get('zonaCarga') or
                        obj.get('zona') or obj.get('Zona_Carga') or current_zone)

                for key, value in obj.items():
                    if key.lower() == 'valores' and isinstance(value, list):
                        for entry in value:
                            if not isinstance(entry, dict):
                                continue

                            fecha = entry.get('fecha') or entry.get('Fecha')
                            if not fecha:
                                continue

                            hora_val = (entry.get('hora') or entry.get('Hora') or
                                        entry.get('horaProgramada') or entry.get('HoraProgramada') or 0)
                            try:
                                hora = int(hora_val)
                            except (TypeError, ValueError):
                                hora = 0

                            record = {
                                'zona_carga': str(zone).strip() if zone else '',
                                'fecha': str(fecha).strip(),
                                'hora': hora
                            }

                            precio_total = None
                            used_total_key = None
                            for candidate in total_keys:
                                if candidate in entry:
                                    precio_total = self._safe_float(entry[candidate])
                                    used_total_key = candidate
                                    break

                            component_values = []
                            for component_key, component_value in entry.items():
                                if component_key in total_keys or component_key == used_total_key:
                                    continue

                                if component_key.lower() in {'fecha', 'hora'}:
                                    continue

                                numeric_value = self._safe_float(component_value)
                                if numeric_value is None:
                                    continue

                                normalized_key = self._normalize_component_key(component_key)
                                if normalized_key == 'precio_total':
                                    continue

                                record[normalized_key] = numeric_value
                                component_values.append(numeric_value)

                            if precio_total is None:
                                precio_total = sum(component_values) if component_values else 0.0

                            record['precio_total'] = precio_total if precio_total is not None else 0.0

                            if system:
                                record['sistema'] = str(system).strip()

                            records.append(record)
                    else:
                        collect(value, system, zone)
            elif isinstance(obj, list):
                for item in obj:
                    collect(item, current_system, current_zone)

        collect(payload)

        if not records:
            logger.warning("No price records extracted from JSON response")

        return records

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """Safely convert values to float"""
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                sanitized = value.replace(',', '')
                return float(sanitized)
            except ValueError:
                return None

        return None

    @staticmethod
    def _normalize_component_key(key: str) -> str:
        """Normalize JSON keys to snake_case"""
        key = key.replace(' ', '_').replace('-', '_')
        key = re.sub(r'(?<!^)(?=[A-Z])', '_', key)
        return key.lower()
    
    def _download_chunk(self, system: str, zones: List[str], start_date: datetime.date,
                       end_date: datetime.date, process: str, data_type: str = "demand") -> List[Dict]:
        """Download a single chunk of data (max 7 days, max 10 zones)"""
        dataset = data_type.lower()

        if dataset not in {"demand", "price"}:
            raise ValueError(f"Unsupported data type: {data_type}")

        # Check cache first
        cache_key = self._get_cache_key(system, zones, start_date, end_date, process, dataset)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        # Build URL and make request
        base_url = self.BASE_URL_DEMAND if dataset == "demand" else self.BASE_URL_PRICE
        response_format = "XML" if dataset == "demand" else "JSON"
        url = self._build_url(base_url, system, zones, start_date, end_date, process, response_format)

        try:
            response_content = self._make_request(url, expected_format=response_format)

            if dataset == "demand":
                data = self._parse_xml_response(response_content)
            else:
                data = self._parse_price_response(response_content)

            # Add system info to each record
            for record in data:
                record['sistema'] = system

            # Save to cache
            self._save_cache(cache_key, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error downloading chunk: {e}")
            return []
    
    def download_data(self, system: str, zones: List[str], start_date: datetime.date,
                     end_date: datetime.date, process: str = "MDA",
                     data_type: str = "combined",
                     progress_callback: Optional[Callable] = None) -> List[Dict]:
        """
        Download data with automatic chunking for API limits

        Parameters:
        -----------
        system : str
            Electric system (SIN, BCA, BCS)
        zones : List[str]
            List of load zones
        start_date : datetime.date
            Start date
        end_date : datetime.date
            End date
        process : str
            Process type (MDA)
        data_type : str
            Type of dataset to download ('demand', 'price', 'combined')
        progress_callback : Callable
            Optional callback for progress updates (current, total, message)

        Returns:
        --------
        List[Dict] : Combined data from all chunks
        """
        dataset = data_type.lower()
        if dataset not in {"demand", "price", "combined"}:
            raise ValueError(f"Unsupported data type: {data_type}")

        all_data = []
        
        # Calculate total operations for progress
        zone_batches = [zones[i:i+self.MAX_ZONES_PER_REQUEST] 
                       for i in range(0, len(zones), self.MAX_ZONES_PER_REQUEST)]
        
        current_date = start_date
        total_operations = 0

        # Calculate total operations
        while current_date <= end_date:
            chunk_end = min(current_date + timedelta(days=self.MAX_DAYS_PER_REQUEST - 1), end_date)
            total_operations += len(zone_batches)
            current_date = chunk_end + timedelta(days=1)
        
        # Reset current_date for actual download
        current_date = start_date
        current_operation = 0
        
        # Download data in 7-day chunks
        while current_date <= end_date:
            chunk_end = min(current_date + timedelta(days=self.MAX_DAYS_PER_REQUEST - 1), end_date)
            
            # Process each batch of zones
            for batch_idx, zone_batch in enumerate(zone_batches):
                if progress_callback:
                    progress_callback(
                        current_operation,
                        total_operations,
                        f"Downloading {system}: {current_date} to {chunk_end}, "
                        f"Zones batch {batch_idx + 1}/{len(zone_batches)}"
                    )
                
                # Download chunk
                demand_chunk: List[Dict] = []
                price_chunk: List[Dict] = []

                if dataset in {"demand", "combined"}:
                    demand_chunk = self._download_chunk(
                        system, zone_batch, current_date, chunk_end, process, data_type="demand"
                    )

                if dataset in {"price", "combined"}:
                    price_chunk = self._download_chunk(
                        system, zone_batch, current_date, chunk_end, process, data_type="price"
                    )

                if dataset == "combined":
                    merged_chunk = self._merge_records(demand_chunk, price_chunk)
                    if merged_chunk:
                        all_data.extend(merged_chunk)
                elif dataset == "demand":
                    if demand_chunk:
                        all_data.extend(demand_chunk)
                else:
                    if price_chunk:
                        all_data.extend(price_chunk)

                # Delay between requests
                if self.delay > 0:
                    time.sleep(self.delay)

                current_operation += 1

            current_date = chunk_end + timedelta(days=1)

        logger.info(f"Downloaded {len(all_data)} {dataset} records for {system}")
        return all_data

    def _merge_records(self, demand_records: List[Dict], price_records: List[Dict]) -> List[Dict]:
        """Merge demand and price records on system, zone, date, and hour"""
        merged: Dict[Tuple[str, str, str, int], Dict] = {}

        for record in demand_records:
            key = (
                record.get('sistema', ''),
                record.get('zona_carga', ''),
                record.get('fecha', ''),
                record.get('hora', 0)
            )
            merged[key] = record.copy()

        for record in price_records:
            key = (
                record.get('sistema', ''),
                record.get('zona_carga', ''),
                record.get('fecha', ''),
                record.get('hora', 0)
            )

            if key in merged:
                for field, value in record.items():
                    if field in {'sistema', 'zona_carga', 'fecha', 'hora'}:
                        continue
                    merged[key][field] = value
            else:
                merged[key] = record.copy()

        return list(merged.values())
    
    def clear_cache(self):
        """Clear all cached data"""
        cache_files = list(CACHE_DIR.glob("*.json"))
        for cache_file in cache_files:
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"Error deleting cache file {cache_file}: {e}")
        
        logger.info(f"Cleared {len(cache_files)} cache files")
    
    def get_cache_info(self) -> Dict:
        """Get information about current cache"""
        cache_files = list(CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'cache_dir': str(CACHE_DIR),
            'num_files': len(cache_files),
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'cache_enabled': self.cache_enabled
        }

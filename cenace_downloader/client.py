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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# Enable debug logging for price API troubleshooting
# Set to DEBUG temporarily to troubleshoot price API issues
# logger.setLevel(logging.DEBUG)

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
            # Check if we got valid XML (but allow HTML error pages to pass through for better error handling)
            if not response.text:
                raise ValueError("Empty response from server")
            # Only reject if it's clearly an HTML error page
            if response.text.strip().startswith('<!DOCTYPE html'):
                raise ValueError("Received HTML error page instead of data")

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

    def _parse_price_xml_response(self, xml_content: str) -> List[Dict]:
        """Parse XML response for zonal prices from SWPEND"""
        try:
            # Clean the XML content
            xml_content = xml_content.strip()
            if xml_content.startswith('<?xml'):
                xml_content = xml_content.split('>', 1)[1]
            
            # Parse XML - SW-PEND API returns <Reporte> as root element
            # Try to parse directly first, then wrap if needed
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError:
                # If direct parsing fails, try wrapping
                root = ET.fromstring(f'<root>{xml_content}</root>')
            
            data = []
            # Price field names based on actual SW-PEND API response structure
            # Primary field: pz (precio zonal / zonal price) - this is the main price
            # Components: pz_ene (energy), pz_per (losses), pz_cng (congestion)
            total_keys = {
                'pz', 'PZ',  # Primary price field in SW-PEND
                'precio_total', 'precioTotal', 'PrecioTotal', 'PRECIO_TOTAL',
                'precio_nodo', 'precioNodo', 'PrecioNodo', 'PRECIO_NODO',
                'precio_marginal_local', 'precioMarginalLocal', 'PrecioMarginalLocal',
                'Precio_Marginal_Local', 'PRECIO_MARGINAL_LOCAL',
                'precio_marginal', 'precioMarginal', 'PrecioMarginal', 'PRECIO_MARGINAL',
                'precio', 'Precio', 'PRECIO'
            }
            
            # Component field names in SW-PEND
            component_keys = {
                'pz_ene', 'pz_ene', 'PZ_ENE',  # Energy component
                'pz_per', 'pz_per', 'PZ_PER',  # Losses component
                'pz_cng', 'pz_cng', 'PZ_CNG'   # Congestion component
            }
            
            # SW-PEND structure: <Reporte><Resultados><Zona_Carga>...</Zona_Carga></Resultados></Reporte>
            # Parse the XML structure - look for Zona_Carga under Resultados or Reporte
            zona_elements = (root.findall('.//Zona_Carga') + 
                           root.findall('.//Zona') + 
                           root.findall('.//ZonaCarga'))
            
            # Log XML structure for debugging if no data found
            if not zona_elements:
                logger.warning(f"Price XML structure: root={root.tag}, top elements: {[e.tag for e in root[:10]]}")
                # Check if we have Resultados element
                resultados = root.find('.//Resultados') or root.find('Resultados')
                if resultados is not None:
                    logger.debug(f"Found Resultados element with {len(list(resultados))} children")
                # Log first 1000 chars of XML for debugging
                logger.debug(f"XML content preview: {ET.tostring(root, encoding='unicode')[:1000]}")
            
            for zona_carga_elem in zona_elements:
                # Get zona_carga from child element text or attribute
                zona_carga = zona_carga_elem.findtext('zona_carga', '').strip()
                if not zona_carga:
                    zona_carga = zona_carga_elem.findtext('zonaCarga', '').strip()
                if not zona_carga:
                    zona_carga = zona_carga_elem.get('zona_carga', zona_carga_elem.get('zona', '')).strip()
                
                if not zona_carga:
                    logger.warning("Could not find zona_carga in zone element")
                    continue
                
                # Find Valores container - try multiple possible names
                valores_elem = (zona_carga_elem.find('Valores') or 
                               zona_carga_elem.find('valores') or
                               zona_carga_elem.find('Valores'))
                
                if valores_elem is None:
                    # Maybe values are directly under zona_carga_elem
                    valores_elem = zona_carga_elem
                
                # Iterate through Valor elements - try multiple variations
                valor_elements = (valores_elem.findall('Valor') + 
                                 valores_elem.findall('valores') +
                                 valores_elem.findall('Valor'))
                
                if not valor_elements:
                    logger.debug(f"No Valor elements found in zona_carga={zona_carga}")
                    continue
                
                for valor in valor_elements:
                    try:
                        fecha = valor.findtext('fecha', '').strip()
                        if not fecha:
                            fecha = valor.get('fecha', '')
                        
                        hora_str = valor.findtext('hora', '0').strip()
                        if not hora_str:
                            hora_str = valor.get('hora', '0')
                        
                        if not fecha:
                            logger.warning("Missing fecha in Valor element")
                            continue
                        
                        record = {
                            'zona_carga': zona_carga,
                            'fecha': fecha,
                            'hora': int(hora_str) if hora_str else 0
                        }
                        
                        # Extract price fields - check all possible field names
                        precio_total = None
                        component_values = []
                        
                        # Look for precio_total or similar fields in text content
                        # Priority: pz field first (SW-PEND standard), then fallback to other names
                        for price_key in total_keys:
                            # Check pz first since it's the SW-PEND standard
                            if price_key == 'pz':
                                price_value = valor.findtext('pz', '') or valor.findtext('PZ', '')
                                if price_value:
                                    precio_total = self._safe_float(str(price_value).strip())
                                    if precio_total is not None:
                                        record['precio_total'] = precio_total
                                        logger.debug(f"Found precio_total={precio_total} from pz field")
                                        break
                                continue
                            
                            price_value = valor.findtext(price_key, '')
                            if not price_value:
                                # Try with different case variations
                                price_value = (valor.findtext(price_key.lower(), '') or 
                                             valor.findtext(price_key.upper(), '') or
                                             valor.findtext(price_key.capitalize(), ''))
                            if not price_value:
                                # Try as attribute
                                price_value = (valor.get(price_key, '') or
                                             valor.get(price_key.lower(), '') or
                                             valor.get(price_key.upper(), ''))
                            
                            if price_value:
                                precio_total = self._safe_float(str(price_value).strip())
                                if precio_total is not None:
                                    record['precio_total'] = precio_total
                                    logger.debug(f"Found precio_total={precio_total} using field {price_key}")
                                    break
                        
                        # Extract all other price-related fields from child elements
                        for child in valor:
                            if child.tag.lower() in {'fecha', 'hora'}:
                                continue
                            
                            # Check if it's a price field
                            tag_lower = child.tag.lower()
                            tag_text = child.text if child.text else ''
                            
                            # SW-PEND uses pz, pz_ene, pz_per, pz_cng fields
                            if tag_lower == 'pz':
                                # This is the total price
                                price_value = self._safe_float(tag_text)
                                if price_value is not None:
                                    if 'precio_total' not in record:
                                        record['precio_total'] = price_value
                                        logger.debug(f"Found precio_total from pz field: {price_value}")
                            elif tag_lower in ['pz_ene', 'pz_per', 'pz_cng']:
                                # These are price components
                                price_value = self._safe_float(tag_text)
                                if price_value is not None:
                                    # Map to more readable names
                                    component_map = {
                                        'pz_ene': 'componente_energia',
                                        'pz_per': 'componente_perdidas',
                                        'pz_cng': 'componente_congestion'
                                    }
                                    normalized_key = component_map.get(tag_lower, tag_lower)
                                    record[normalized_key] = price_value
                                    component_values.append(price_value)
                                    logger.debug(f"Found price component {normalized_key}={price_value}")
                            elif 'precio' in tag_lower or 'price' in tag_lower:
                                # Legacy/alternative price field names
                                price_value = self._safe_float(tag_text)
                                if price_value is not None:
                                    normalized_key = self._normalize_component_key(child.tag)
                                    if normalized_key != 'precio_total' and normalized_key not in record:
                                        record[normalized_key] = price_value
                                        component_values.append(price_value)
                            # Also check numeric values that might be prices (fallback)
                            elif tag_text and tag_text.strip().replace('.', '').replace('-', '').replace('e', '').replace('E', '').isdigit():
                                numeric_val = self._safe_float(tag_text)
                                if numeric_val is not None and abs(numeric_val) > 0:
                                    # If it's a reasonable price value (between 0 and 50000 MXN/MWh)
                                    if 0 < abs(numeric_val) < 50000:
                                        logger.debug(f"Found potential price field: {child.tag}={numeric_val}")
                                        normalized_key = self._normalize_component_key(child.tag)
                                        if 'precio' not in normalized_key:
                                            normalized_key = f'precio_{normalized_key}'
                                        if normalized_key != 'precio_total' and normalized_key not in record:
                                            record[normalized_key] = numeric_val
                                            component_values.append(numeric_val)
                        
                        # If no precio_total found, try to sum components
                        if 'precio_total' not in record:
                            if component_values:
                                record['precio_total'] = sum(component_values)
                                logger.debug(f"Calculated precio_total from components: {record['precio_total']}")
                            else:
                                # Log warning but still add record with 0.0
                                logger.warning(f"No price value found for {zona_carga} {fecha} hora={record['hora']}")
                                record['precio_total'] = 0.0
                        
                        data.append(record)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing Valor record: {e}")
                        continue
            
            if not data:
                logger.warning("No price data extracted from XML. Checking structure...")
                logger.debug(f"XML root: {root.tag}")
                logger.debug(f"Found top-level elements: {[elem.tag for elem in list(root)[:20]]}")
                # Try to find any price-related elements
                all_elements = [elem.tag for elem in root.iter()][:50]
                logger.debug(f"All XML elements (first 50): {all_elements}")
                # Log a sample of the XML structure
                try:
                    sample_xml = ET.tostring(root, encoding='unicode', method='xml')[:2000]
                    logger.debug(f"XML structure sample: {sample_xml}")
                except:
                    pass
            
            return data
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            logger.error(f"XML content (first 500 chars): {xml_content[:500]}")
            # Try alternative parsing
            return self._parse_alternative_price_xml(xml_content)
        except Exception as e:
            logger.error(f"Error parsing price XML: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _parse_alternative_price_xml(self, xml_content: str) -> List[Dict]:
        """Alternative XML parsing for price responses with different structures"""
        try:
            root = ET.fromstring(xml_content)
            data = []
            total_keys = {
                'precio_total', 'precioTotal', 'precio_nodo', 'precioNodo',
                'precio_marginal_local', 'precioMarginalLocal'
            }
            
            # Try to find Zona_Carga elements or Zona elements
            for zona_elem in root.findall('.//Zona_Carga') + root.findall('.//Zona'):
                zona_carga = zona_elem.findtext('zona_carga', '')
                if not zona_carga:
                    zona_carga = zona_elem.get('zona_carga', zona_elem.get('zona', '')).strip()
                
                if not zona_carga:
                    continue
                
                valores_container = zona_elem.find('Valores')
                if valores_container is None:
                    continue
                
                for valor in valores_container.findall('Valor') + valores_container.findall('valores'):
                    fecha = valor.findtext('fecha', '')
                    if not fecha:
                        fecha = valor.get('fecha', '')
                    
                    hora_str = valor.findtext('hora', '')
                    if not hora_str:
                        hora_str = valor.get('hora', '0')
                    
                    if not fecha:
                        continue
                    
                    try:
                        record = {
                            'zona_carga': zona_carga.strip(),
                            'fecha': fecha.strip(),
                            'hora': int(hora_str) if hora_str else 0
                        }
                        
                        # Extract price values
                        precio_total = None
                        for price_key in total_keys:
                            price_val = valor.findtext(price_key, '') or valor.get(price_key, '')
                            if price_val:
                                precio_total = self._safe_float(price_val)
                                if precio_total is not None:
                                    break
                        
                        record['precio_total'] = precio_total if precio_total is not None else 0.0
                        data.append(record)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing record in alternative price XML parser: {e}")
                        continue
            
            return data
        except Exception as e:
            logger.error(f"Alternative price XML parsing failed: {e}")
            return []
    
    def _is_xml_content(self, content: str) -> bool:
        """Detect if content is XML"""
        if not content:
            return False
        content_stripped = content.strip()
        return (content_stripped.startswith('<?xml') or 
                content_stripped.startswith('<') or
                content_stripped.startswith('<Resultados>') or
                content_stripped.startswith('<Zona_Carga>'))
    
    def _parse_price_response(self, response_content: str) -> List[Dict]:
        """Parse response for zonal prices - handles both JSON and XML"""
        # Detect format and parse accordingly
        if self._is_xml_content(response_content):
            logger.info("Detected XML format for price response")
            return self._parse_price_xml_response(response_content)
        
        # Try JSON parsing
        try:
            payload = json.loads(response_content)
        except json.JSONDecodeError as exc:
            logger.error(f"JSON parsing error: {exc}")
            # If JSON fails, try XML as fallback
            logger.info("JSON parsing failed, attempting XML parsing as fallback")
            return self._parse_price_xml_response(response_content)

        # Parse JSON payload
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
        # For prices, try XML first (SWPEND), but allow fallback to JSON
        response_format = "XML" if dataset == "demand" else "XML"
        url = self._build_url(base_url, system, zones, start_date, end_date, process, response_format)

        try:
            # For prices, try XML first, but don't enforce format validation
            if dataset == "price":
                response_content = self._make_request(url, expected_format="XML")
                # Log response preview for debugging
                logger.debug(f"Price API response length: {len(response_content)} chars")
                logger.debug(f"Price API response preview (first 500 chars): {response_content[:500]}")
                # _parse_price_response will auto-detect XML vs JSON
                data = self._parse_price_response(response_content)
                if not data:
                    logger.warning(f"No price data parsed from response. URL: {url}")
                    logger.warning(f"Response content type check: starts with XML={response_content.strip().startswith('<?xml') or response_content.strip().startswith('<')}")
            else:
                response_content = self._make_request(url, expected_format=response_format)
                data = self._parse_xml_response(response_content)

            # Add system info to each record
            for record in data:
                record['sistema'] = system

            # Log successful retrieval
            if data:
                logger.info(f"Successfully retrieved {len(data)} {dataset} records for {system}, zones: {zones}")

            # Save to cache
            self._save_cache(cache_key, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error downloading chunk for {dataset}: {e}")
            logger.error(f"Failed URL: {url}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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

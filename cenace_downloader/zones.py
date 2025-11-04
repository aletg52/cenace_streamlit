"""
CENACE Zones Configuration
==========================
Complete list of zones for each electrical system in Mexico, organized by Regional Control
"""

# Zone definitions with Regional Control aggregation
# Structure: System -> Regional Control -> Zones
ZONES_BY_SYSTEM_REGIONAL = {
    "BCA": {
        "BAJA CALIFORNIA": [
            "ENSENADA",
            "MEXICALI",
            "SANLUIS",
            "TIJUANA"
        ]
    },
    
    "BCS": {
        "BAJA CALIFORNIA SUR": [
            "CONSTITUCION",
            "LA PAZ",
            "LOS CABOS"
        ]
    },
    
    "SIN": {
        "CENTRAL": [
            "CENTRO ORIENTE",
            "CENTRO SUR",
            "LAZARO CARDENAS",
            "VDM CENTRO",
            "VDM NORTE",
            "VDM SUR"
        ],
        "NORESTE": [
            "HUASTECA",
            "HUEJUTLA",
            "MATAMOROS",
            "MONCLOVA",
            "MONTEMORELOS",
            "MONTERREY",
            "NUEVO LAREDO",
            "PIEDRAS NEGRAS",
            "REYNOSA",
            "SABINAS",
            "SALTILLO",
            "TAMPICO",
            "VICTORIA"
        ],
        "NOROESTE": [
            "CABORCA",
            "CULIACAN",
            "GUASAVE",
            "GUAYMAS",
            "HERMOSILLO",
            "LOS MOCHIS",
            "MAZATLAN",
            "NAVOJOA",
            "NOGALES",
            "OBREGON"
        ],
        "NORTE": [
            "CAMARGO",
            "CASAS GRANDES",
            "CHIHUAHUA",
            "CUAUHTEMOC",
            "DURANGO",
            "JUAREZ",
            "LAGUNA"
        ],
        "OCCIDENTAL": [
            "AGUASCALIENTES",
            "APATZINGAN",
            "CELAYA",
            "CIENEGA",
            "COLIMA",
            "FRESNILLO",
            "GUADALAJARA",
            "IRAPUATO",
            "IXMIQUILPAN",
            "JIQUILPAN",
            "LEON",
            "LOS ALTOS",
            "MANZANILLO",
            "MATEHUALA",
            "MINAS",
            "MORELIA",
            "QUERETARO",
            "SALVATIERRA",
            "SAN JUAN DEL RIO",
            "SAN LUIS POTOSI",
            "TEPIC VALLARTA",
            "URUAPAN",
            "ZACAPU",
            "ZACATECAS",
            "ZAMORA",
            "ZAPOTLAN"
        ],
        "ORIENTAL": [
            "ACAPULCO",
            "CENTRO ORIENTE",
            "CHILPANCINGO",
            "CHONTALPA",
            "COATZACOALCOS",
            "CORDOBA",
            "CUAUTLA",
            "CUERNAVACA",
            "HUAJUAPAN",
            "HUATULCO",
            "IGUALA",
            "IZUCAR",
            "LOS RIOS",
            "LOS TUXTLAS",
            "MORELOS",
            "OAXACA",
            "ORIZABA",
            "POZA RICA",
            "PUEBLA",
            "SAN CRISTOBAL",
            "SAN MARTIN",
            "TAPACHULA",
            "TECAMACHALCO",
            "TEHUACAN",
            "TEHUANTEPEC",
            "TEZIUTLAN",
            "TLAXCALA",
            "TUXTLA",
            "VERACRUZ",
            "VILLAHERMOSA",
            "XALAPA",
            "ZIHUATANEJO"
        ],
        "PENINSULAR": [
            "CAMPECHE",
            "CANCUN",
            "CARMEN",
            "CHETUMAL",
            "MERIDA",
            "MOTUL TIZIMIN",
            "RIVIERA MAYA",
            "TICUL"
        ]
    }
}

# Flattened version for backward compatibility (System -> Zones list)
# Generated automatically from the regional structure
def _flatten_zones():
    """Generate flattened zone structure from regional structure, removing duplicates"""
    flattened = {}
    for system, regional_controls in ZONES_BY_SYSTEM_REGIONAL.items():
        all_zones = []
        seen_zones = set()
        for regional_control, zones in regional_controls.items():
            for zone in zones:
                # Add zone only if not already seen (handles duplicates across regional controls)
                if zone.upper() not in seen_zones:
                    all_zones.append(zone)
                    seen_zones.add(zone.upper())
        flattened[system] = all_zones
    return flattened

ZONES_BY_SYSTEM = _flatten_zones()

# Alternative names and mappings (for data cleaning)
ZONE_NAME_MAPPINGS = {
    # Common variations
    "CD JUAREZ": "JUAREZ",
    "CD. JUAREZ": "JUAREZ",
    "CIUDAD JUAREZ": "JUAREZ",
    "SAN LUIS": "SAN LUIS POTOSI",
    "VALLE MEXICO": "VALLE DE MEXICO",
    "CDMX": "VALLE DE MEXICO",
    "MEXICO CITY": "VALLE DE MEXICO",
    "CD OBREGON": "OBREGON",
    "CIUDAD OBREGON": "OBREGON",
    # Add more mappings as needed
}

# Zone to State mapping (Entidad Federativa)
# Maps zone names to their corresponding federal entities (states)
# Structure: zone_name -> list of (full_state_name, state_code) tuples
# Some zones may span multiple states
ZONE_TO_STATE_MAPPING = {
    # BCA (Baja California)
    "ENSENADA": [("BAJA CALIFORNIA", "BN")],
    "MEXICALI": [("BAJA CALIFORNIA", "BN"), ("SONORA", "SO")],
    "SANLUIS": [("BAJA CALIFORNIA", "BN")],
    "TIJUANA": [("BAJA CALIFORNIA", "BN")],
    
    # BCS (Baja California Sur)
    "CONSTITUCION": [("BAJA CALIFORNIA SUR", "BS")],
    "LA PAZ": [("BAJA CALIFORNIA SUR", "BS")],
    "LOS CABOS": [("BAJA CALIFORNIA SUR", "BS")],
    
    # SIN - Central
    "CENTRO ORIENTE": [("HIDALGO", "HI")],
    "CENTRO SUR": [("MORELOS", "MO")],
    "LAZARO CARDENAS": [("MICHOACAN DE OCAMPO", "MC")],
    "VDM CENTRO": [("CIUDAD DE MEXICO", "DF")],
    "VDM NORTE": [("CIUDAD DE MEXICO", "DF"), ("ESTADO DE MEXICO", "MX")],
    "VDM SUR": [("CIUDAD DE MEXICO", "DF"), ("ESTADO DE MEXICO", "MX")],
    
    # SIN - Noreste
    "HUASTECA": [("HIDALGO", "HI"), ("SAN LUIS POTOSI", "SL"), ("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "HUEJUTLA": [("HIDALGO", "HI")],
    "MATAMOROS": [("TAMAULIPAS", "TM")],
    "MONCLOVA": [("COAHUILA DE ZARAGOZA", "CO")],
    "MONTEMORELOS": [("NUEVO LEON", "NL")],
    "MONTERREY": [("NUEVO LEON", "NL")],
    "NUEVO LAREDO": [("TAMAULIPAS", "TM")],
    "PIEDRAS NEGRAS": [("COAHUILA DE ZARAGOZA", "CO")],
    "REYNOSA": [("TAMAULIPAS", "TM")],
    "SABINAS": [("COAHUILA DE ZARAGOZA", "CO")],
    "SALTILLO": [("COAHUILA DE ZARAGOZA", "CO")],
    "TAMPICO": [("TAMAULIPAS", "TM")],
    "VICTORIA": [("TAMAULIPAS", "TM")],
    
    # SIN - Noroeste
    "CABORCA": [("SONORA", "SO")],
    "CULIACAN": [("SINALOA", "SI")],
    "GUASAVE": [("SINALOA", "SI")],
    "GUAYMAS": [("SONORA", "SO")],
    "HERMOSILLO": [("SONORA", "SO")],
    "LOS MOCHIS": [("SINALOA", "SI")],
    "MAZATLAN": [("SINALOA", "SI")],
    "NAVOJOA": [("SONORA", "SO")],
    "NOGALES": [("SONORA", "SO")],
    "OBREGON": [("SONORA", "SO")],
    
    # SIN - Norte
    "CAMARGO": [("CHIHUAHUA", "CH")],
    "CASAS GRANDES": [("CHIHUAHUA", "CH")],
    "CHIHUAHUA": [("CHIHUAHUA", "CH")],
    "CUAUHTEMOC": [("CHIHUAHUA", "CH")],
    "DURANGO": [("DURANGO", "DU")],
    "JUAREZ": [("CHIHUAHUA", "CH")],
    "LAGUNA": [("COAHUILA DE ZARAGOZA", "CO"), ("DURANGO", "DU")],
    
    # SIN - Occidental
    "AGUASCALIENTES": [("AGUASCALIENTES", "AG")],
    "APATZINGAN": [("MICHOACAN DE OCAMPO", "MC")],
    "CELAYA": [("GUANAJUATO", "GT")],
    "CIENEGA": [("GUANAJUATO", "GT")],
    "COLIMA": [("COLIMA", "CL")],
    "FRESNILLO": [("ZACATECAS", "ZA")],
    "GUADALAJARA": [("JALISCO", "JA")],
    "IRAPUATO": [("GUANAJUATO", "GT")],
    "IXMIQUILPAN": [("HIDALGO", "HI")],
    "JIQUILPAN": [("MICHOACAN DE OCAMPO", "MC")],
    "LEON": [("GUANAJUATO", "GT")],
    "LOS ALTOS": [("JALISCO", "JA")],
    "MANZANILLO": [("COLIMA", "CL")],
    "MATEHUALA": [("SAN LUIS POTOSI", "SL")],
    "MINAS": [("GUANAJUATO", "GT")],
    "MORELIA": [("MICHOACAN DE OCAMPO", "MC")],
    "QUERETARO": [("QUERETARO", "QE")],
    "SALVATIERRA": [("GUANAJUATO", "GT")],
    "SAN JUAN DEL RIO": [("QUERETARO", "QE")],
    "SAN LUIS POTOSI": [("SAN LUIS POTOSI", "SL")],
    "TEPIC VALLARTA": [("NAYARIT", "NY")],
    "URUAPAN": [("MICHOACAN DE OCAMPO", "MC")],
    "ZACAPU": [("MICHOACAN DE OCAMPO", "MC")],
    "ZACATECAS": [("ZACATECAS", "ZA")],
    "ZAMORA": [("MICHOACAN DE OCAMPO", "MC")],
    "ZAPOTLAN": [("JALISCO", "JA")],
    
    # SIN - Oriental
    "ACAPULCO": [("GUERRERO", "GR")],
    "CHILPANCINGO": [("GUERRERO", "GR")],
    "CHONTALPA": [("TABASCO", "TB")],
    "COATZACOALCOS": [("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "CORDOBA": [("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "CUAUTLA": [("MORELOS", "MO")],
    "CUERNAVACA": [("MORELOS", "MO")],
    "HUAJUAPAN": [("OAXACA", "OA")],
    "HUATULCO": [("OAXACA", "OA")],
    "IGUALA": [("GUERRERO", "GR")],
    "IZUCAR": [("PUEBLA", "PU")],
    "LOS RIOS": [("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "LOS TUXTLAS": [("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "MORELOS": [("MORELOS", "MO")],
    "OAXACA": [("OAXACA", "OA")],
    "ORIZABA": [("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "POZA RICA": [("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "PUEBLA": [("PUEBLA", "PU")],
    "SAN CRISTOBAL": [("CHIAPAS", "CS")],
    "SAN MARTIN": [("PUEBLA", "PU")],
    "TAPACHULA": [("CHIAPAS", "CS")],
    "TECAMACHALCO": [("PUEBLA", "PU")],
    "TEHUACAN": [("PUEBLA", "PU")],
    "TEHUANTEPEC": [("OAXACA", "OA")],
    "TEZIUTLAN": [("PUEBLA", "PU")],
    "TLAXCALA": [("TLAXCALA", "TL")],
    "TUXTLA": [("CHIAPAS", "CS")],
    "VERACRUZ": [("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "VILLAHERMOSA": [("TABASCO", "TB")],
    "XALAPA": [("VERACRUZ DE IGNACIO DE LA LLAVE", "VE")],
    "ZIHUATANEJO": [("GUERRERO", "GR")],
    
    # SIN - Peninsular
    "CAMPECHE": [("CAMPECHE", "CM")],
    "CANCUN": [("QUINTANA ROO", "QR")],
    "CARMEN": [("CAMPECHE", "CM")],
    "CHETUMAL": [("QUINTANA ROO", "QR")],
    "MERIDA": [("YUCATAN", "YU")],
    "MOTUL TIZIMIN": [("YUCATAN", "YU")],
    "RIVIERA MAYA": [("QUINTANA ROO", "QR")],
    "TICUL": [("YUCATAN", "YU")],
}


def get_states_for_zone(zone_name: str) -> list:
    """
    Get the federal entities (states) associated with a zone
    
    Parameters:
    -----------
    zone_name : str
        Zone name (will be normalized)
    
    Returns:
    --------
    list : List of tuples (full_state_name, state_code) for the zone.
           Returns empty list if zone not found.
           Some zones may span multiple states.
    """
    normalized = normalize_zone_name(zone_name)
    return ZONE_TO_STATE_MAPPING.get(normalized, [])


def get_state_names_for_zone(zone_name: str) -> list:
    """
    Get the full state names (Entidad Federativa) for a zone
    
    Parameters:
    -----------
    zone_name : str
        Zone name (will be normalized)
    
    Returns:
    --------
    list : List of full state names. Returns empty list if zone not found.
    """
    states = get_states_for_zone(zone_name)
    return [state[0] for state in states]


def get_state_codes_for_zone(zone_name: str) -> list:
    """
    Get the two-letter state codes for a zone
    
    Parameters:
    -----------
    zone_name : str
        Zone name (will be normalized)
    
    Returns:
    --------
    list : List of two-letter state codes. Returns empty list if zone not found.
    """
    states = get_states_for_zone(zone_name)
    return [state[1] for state in states]


def get_primary_state_for_zone(zone_name: str) -> tuple:
    """
    Get the primary state (first state) for a zone
    
    Parameters:
    -----------
    zone_name : str
        Zone name (will be normalized)
    
    Returns:
    --------
    tuple : (full_state_name, state_code) or ("", "") if zone not found.
            Returns the first state if zone spans multiple states.
    """
    states = get_states_for_zone(zone_name)
    if states:
        return states[0]
    return ("", "")


def get_all_zones():
    """
    Get all zones organized by system (flattened structure for backward compatibility)
    
    Returns:
    --------
    Dict[str, List[str]] : Dictionary mapping system names to zone lists
    """
    return ZONES_BY_SYSTEM.copy()


def get_all_zones_with_regional():
    """
    Get all zones organized by system and regional control
    
    Returns:
    --------
    Dict[str, Dict[str, List[str]]] : Dictionary mapping system names to regional controls,
                                      each containing a list of zones
    """
    return ZONES_BY_SYSTEM_REGIONAL.copy()


def get_regional_controls_for_system(system: str):
    """
    Get regional controls for a specific system
    
    Parameters:
    -----------
    system : str
        System name (SIN, BCA, BCS)
    
    Returns:
    --------
    List[str] : List of regional control names for the system
    """
    system_data = ZONES_BY_SYSTEM_REGIONAL.get(system.upper(), {})
    return list(system_data.keys())


def get_zones_for_regional_control(system: str, regional_control: str):
    """
    Get zones for a specific system and regional control
    
    Parameters:
    -----------
    system : str
        System name (SIN, BCA, BCS)
    regional_control : str
        Regional control name
    
    Returns:
    --------
    List[str] : List of zones for the regional control
    """
    system_data = ZONES_BY_SYSTEM_REGIONAL.get(system.upper(), {})
    return system_data.get(regional_control.upper(), [])


def get_regional_control_for_zone(zone_name: str) -> tuple:
    """
    Get the system and regional control that a zone belongs to
    
    Parameters:
    -----------
    zone_name : str
        Zone name
    
    Returns:
    --------
    tuple : (system, regional_control) or ("", "") if not found
    """
    normalized = normalize_zone_name(zone_name)
    
    for system, regional_controls in ZONES_BY_SYSTEM_REGIONAL.items():
        for regional_control, zones in regional_controls.items():
            if normalized in [z.upper() for z in zones]:
                return system, regional_control
    
    return "", ""


def get_zones_for_system(system: str):
    """
    Get zones for a specific system
    
    Parameters:
    -----------
    system : str
        System name (SIN, BCA, BCS)
    
    Returns:
    --------
    List[str] : List of zones for the system
    """
    return ZONES_BY_SYSTEM.get(system.upper(), [])


def get_total_zones():
    """
    Get total number of zones across all systems
    
    Returns:
    --------
    int : Total number of zones
    """
    return sum(len(zones) for zones in ZONES_BY_SYSTEM.values())


def normalize_zone_name(zone_name: str) -> str:
    """
    Normalize a zone name to match the standard format
    
    Parameters:
    -----------
    zone_name : str
        Zone name to normalize
    
    Returns:
    --------
    str : Normalized zone name
    """
    # Convert to uppercase and strip whitespace
    normalized = zone_name.upper().strip()
    
    # Replace dashes with spaces
    normalized = normalized.replace('-', ' ')
    
    # Check for known mappings
    if normalized in ZONE_NAME_MAPPINGS:
        normalized = ZONE_NAME_MAPPINGS[normalized]
    
    return normalized


def get_system_for_zone(zone_name: str) -> str:
    """
    Get the system that a zone belongs to
    
    Parameters:
    -----------
    zone_name : str
        Zone name
    
    Returns:
    --------
    str : System name or empty string if not found
    """
    system, _ = get_regional_control_for_zone(zone_name)
    return system


def validate_zones(zones: list, system: str = None) -> tuple:
    """
    Validate a list of zones
    
    Parameters:
    -----------
    zones : list
        List of zone names to validate
    system : str, optional
        If provided, validate zones belong to this system
    
    Returns:
    --------
    tuple : (valid_zones, invalid_zones)
    """
    valid_zones = []
    invalid_zones = []
    
    for zone in zones:
        normalized = normalize_zone_name(zone)
        
        if system:
            # Check if zone belongs to specified system
            system_zones = [z.upper() for z in ZONES_BY_SYSTEM.get(system.upper(), [])]
            if normalized in system_zones:
                valid_zones.append(zone)
            else:
                invalid_zones.append(zone)
        else:
            # Check if zone exists in any system
            found = False
            for sys_zones in ZONES_BY_SYSTEM.values():
                if normalized in [z.upper() for z in sys_zones]:
                    valid_zones.append(zone)
                    found = True
                    break
            if not found:
                invalid_zones.append(zone)
    
    return valid_zones, invalid_zones


def group_zones_by_system(zones: list) -> dict:
    """
    Group a list of zones by their system
    
    Parameters:
    -----------
    zones : list
        List of zone names
    
    Returns:
    --------
    dict : Dictionary mapping system names to lists of zones
    """
    grouped = {}
    
    for zone in zones:
        system = get_system_for_zone(zone)
        if system:
            if system not in grouped:
                grouped[system] = []
            grouped[system].append(zone)
    
    return grouped


# Export zone information as a structured format
def _build_zone_info():
    """Build comprehensive zone information structure"""
    systems_info = {}
    for system, regional_controls in ZONES_BY_SYSTEM_REGIONAL.items():
        system_data = {
            "name": {
                "BCA": "Baja California",
                "BCS": "Baja California Sur",
                "SIN": "Sistema Interconectado Nacional"
            }.get(system, system),
            "description": {
                "BCA": "Isolated grid serving Baja California",
                "BCS": "Isolated grid serving Baja California Sur",
                "SIN": "Main national grid covering most of Mexico"
            }.get(system, ""),
            "total_zones": len(ZONES_BY_SYSTEM[system]),
            "regional_controls": {}
        }
        
        for regional_control, zones in regional_controls.items():
            system_data["regional_controls"][regional_control] = {
                "zones": zones,
                "zone_count": len(zones)
            }
        
        systems_info[system] = system_data
    
    return {
        "total_zones": get_total_zones(),
        "systems": systems_info
    }

ZONE_INFO = _build_zone_info()

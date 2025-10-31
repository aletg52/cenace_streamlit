"""
CENACE Zones Configuration
==========================
Complete list of zones for each electrical system in Mexico
"""

# Zone definitions based on the CENACE system
ZONES_BY_SYSTEM = {
    "BCA": [
        "ENSENADA",
        "MEXICALI", 
        "SAN LUIS",
        "TIJUANA"
    ],
    
    "BCS": [
        "CONSTITUCION",
        "LA PAZ",
        "LOS CABOS"
    ],
    
    "SIN": [
        "ACAPULCO", "AGUASCALIENTES", "APATZINGAN", "CABORCA", "CAMARGO", "CAMPECHE", "CANCUN",
        "CANANEA", "CARMEN", "CASAS GRANDES", "CELAYA", "CENTRO", "CENTRO ORIENTE", "CENTRO SUR",
        "CERRO AZUL", "CHARCAS", "CHETUMAL", "CHIHUAHUA", "CHILPANCINGO", "CHONTALPA", 
        "CIENEGA", "COATZACOALCOS", "COLIMA", "CONSTITUCION DE 1857", "CORDOBA", "COSTA", 
        "CUAUHTEMOC", "CUERNAVACA", "CULIACAN", "DELICIAS", "DURANGO", "EL FUERTE", 
        "ESCARCEGA", "FRESNILLO", "GUADALAJARA", "GUAMUCHIL", "GUANAJUATO", "GUASAVE", 
        "GUAYMAS", "HERMOSILLO", "HEROICA NOGALES", "HUAJUAPAN", "HUASTECA", "HUATULCO", 
        "HUEJUTLA", "HUEXCA", "IGUALA", "IRAPUATO", "IXMIQUILPAN", "IXTEPEC", "IZUCAR", 
        "JIQUILPAN", "JUAREZ", "JUCHITAN", "LA LAGUNA", "LA PIEDAD", "LAZARO CARDENAS", 
        "LEON", "LOS ALTOS", "LOS MOCHIS", "LOS RIOS", "MACUSPANA", "MANZANILLO", "MATAMOROS",
        "MATEHUALA", "MAZATLAN", "MERIDA", "MEXICALI", "MINAS", "MONCLOVA", "MONTERREY", 
        "MORELIA", "MORELOS", "MOTUL", "NAVOJOA", "NAYARIT", "NUEVO LAREDO", "OAXACA", 
        "OBREGON", "OCOTLAN", "ORIZABA", "PACIFICO", "PACHUCA", "PAPANTLA", "PARRAL", 
        "PIE DE LA CUESTA", "PIEDRAS NEGRAS", "POZA RICA", "PUEBLA", "PUERTO ESCONDIDO", 
        "PUERTO LIBERTAD", "PUERTO PENASCO", "QUERETARO", "REYNOSA", "RIVIERA MAYA", 
        "SALAMANCA", "SALTILLO", "SAN CRISTOBAL", "SAN FERNANDO", "SAN JUAN DEL RIO", 
        "SAN LUIS POTOSI", "SANTA ROSALIA", "SINALOA", "TABASCO", "TAMAZUNCHALE", "TAMPICO", 
        "TAPACHULA", "TECALI", "TECATE", "TEHUACAN", "TEHUANTEPEC", "TEPIC", "TEZIUTLAN", 
        "TICUL", "TIJUANA", "TLAXCALA", "TORREON", "TULA", "TUXPAN", "TUXTLA", 
        "URUAPAN", "VALLADOLID", "VALLE DE MEXICO", "VERACRUZ", "VILLA CONSTITUCION", 
        "VILLAHERMOSA", "XALAPA", "ZACATECAS", "ZAMORA", "ZAPOPAN", "ZIHUATANEJO"
    ]
}

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


def get_all_zones():
    """
    Get all zones organized by system
    
    Returns:
    --------
    Dict[str, List[str]] : Dictionary mapping system names to zone lists
    """
    return ZONES_BY_SYSTEM.copy()


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
    normalized = normalize_zone_name(zone_name)
    
    for system, zones in ZONES_BY_SYSTEM.items():
        if normalized in [z.upper() for z in zones]:
            return system
    
    return ""


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
ZONE_INFO = {
    "total_zones": get_total_zones(),
    "systems": {
        "BCA": {
            "name": "Baja California",
            "zones": len(ZONES_BY_SYSTEM["BCA"]),
            "description": "Isolated grid serving Baja California"
        },
        "BCS": {
            "name": "Baja California Sur", 
            "zones": len(ZONES_BY_SYSTEM["BCS"]),
            "description": "Isolated grid serving Baja California Sur"
        },
        "SIN": {
            "name": "Sistema Interconectado Nacional",
            "zones": len(ZONES_BY_SYSTEM["SIN"]),
            "description": "Main national grid covering most of Mexico"
        }
    }
}

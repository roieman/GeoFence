"""
Shipping chokepoints and regional classifications.

These waypoints ensure ocean routes pass through real shipping lanes
instead of cutting across land masses.
"""

# Major shipping chokepoints with waypoints (lon, lat format)
CHOKEPOINTS = {
    "suez": {
        "name": "Suez Canal",
        "waypoints": [(32.37, 31.23), (32.55, 30.00), (32.53, 29.93)],
        "connects": [("EU", "ASIA"), ("MENA", "ASIA"), ("US_EAST", "ASIA"), ("MED", "ASIA")]
    },
    "panama": {
        "name": "Panama Canal",
        "waypoints": [(-79.92, 9.38), (-79.55, 8.95)],
        "connects": [("US_EAST", "US_WEST"), ("US_EAST", "ASIA_PACIFIC"), ("EU", "US_WEST")]
    },
    "malacca": {
        "name": "Strait of Malacca",
        "waypoints": [(100.0, 5.0), (103.5, 1.2)],
        "connects": [("INDIA", "CHINA"), ("INDIA", "ASIA"), ("MENA", "ASIA"), ("EU", "ASIA")]
    },
    "gibraltar": {
        "name": "Strait of Gibraltar",
        "waypoints": [(-5.6, 35.95), (-5.95, 35.9)],
        "connects": [("MED", "ATLANTIC"), ("MED", "US_EAST"), ("MED", "US_WEST"), ("EU", "MED")]
    },
    "cape_good_hope": {
        "name": "Cape of Good Hope",
        "waypoints": [(18.47, -34.36), (20.0, -35.0), (25.0, -34.0)],
        "connects": [("ATLANTIC", "INDIAN"), ("EU", "ASIA"), ("US_EAST", "ASIA")]
    },
    "english_channel": {
        "name": "English Channel",
        "waypoints": [(-1.5, 50.0), (1.5, 51.0)],
        "connects": [("EU", "ATLANTIC"), ("EU", "US_EAST")]
    },
    "bab_el_mandeb": {
        "name": "Bab el-Mandeb Strait",
        "waypoints": [(43.3, 12.6), (43.5, 12.4)],
        "connects": [("MED", "INDIAN"), ("MENA", "INDIA"), ("EU", "INDIA")]
    },
    "singapore": {
        "name": "Singapore Strait",
        "waypoints": [(103.8, 1.25), (104.1, 1.2)],
        "connects": [("ASIA", "INDIA"), ("ASIA", "MENA"), ("CHINA", "INDIA")]
    },
    "taiwan": {
        "name": "Taiwan Strait",
        "waypoints": [(119.5, 24.0), (120.0, 25.0)],
        "connects": [("CHINA", "JAPAN"), ("CHINA", "KOREA")]
    },
    "hormuz": {
        "name": "Strait of Hormuz",
        "waypoints": [(56.4, 26.5), (56.0, 26.0)],
        "connects": [("MENA", "INDIA"), ("MENA", "ASIA")]
    }
}

# Region classifications based on country codes
REGION_PREFIXES = {
    "US_EAST": {
        "countries": ["US"],
        "lon_filter": lambda lon: lon > -100  # East of -100 longitude
    },
    "US_WEST": {
        "countries": ["US"],
        "lon_filter": lambda lon: lon <= -100  # West of -100 longitude
    },
    "CANADA": {
        "countries": ["CA"],
        "lon_filter": None
    },
    "EU": {
        "countries": ["GB", "DE", "NL", "BE", "FR", "ES", "IT", "PT", "PL", "SE", "NO", "DK", "FI", "IE"],
        "lon_filter": None
    },
    "MED": {
        "countries": ["ES", "IT", "GR", "TR", "HR", "SI", "MT", "CY"],
        "lon_filter": None
    },
    "CHINA": {
        "countries": ["CN", "HK"],
        "lon_filter": None
    },
    "JAPAN": {
        "countries": ["JP"],
        "lon_filter": None
    },
    "KOREA": {
        "countries": ["KR"],
        "lon_filter": None
    },
    "ASIA": {
        "countries": ["CN", "JP", "KR", "TW", "HK", "SG", "MY", "TH", "VN", "ID", "PH"],
        "lon_filter": None
    },
    "INDIA": {
        "countries": ["IN", "BD", "LK", "PK"],
        "lon_filter": None
    },
    "MENA": {
        "countries": ["AE", "SA", "EG", "IL", "TR", "JO", "OM", "QA", "KW", "BH"],
        "lon_filter": None
    },
    "OCEANIA": {
        "countries": ["AU", "NZ"],
        "lon_filter": None
    },
    "ATLANTIC": {
        "countries": ["BR", "AR", "CL", "CO", "VE", "PE", "EC"],
        "lon_filter": None
    },
    "AFRICA": {
        "countries": ["ZA", "KE", "NG", "GH", "TZ", "MA", "DZ", "TN"],
        "lon_filter": None
    }
}

# Simplified region lookup by country code (for quick lookup)
COUNTRY_TO_REGIONS = {}
for region, config in REGION_PREFIXES.items():
    for country in config["countries"]:
        if country not in COUNTRY_TO_REGIONS:
            COUNTRY_TO_REGIONS[country] = []
        COUNTRY_TO_REGIONS[country].append(region)

# Route preferences: which chokepoints to use for region pairs
# Format: (origin_region, dest_region) -> [chokepoint_keys in order]
ROUTE_CHOKEPOINTS = {
    # Asia to Europe/US East
    ("ASIA", "EU"): ["malacca", "singapore", "bab_el_mandeb", "suez", "gibraltar"],
    ("CHINA", "EU"): ["taiwan", "malacca", "singapore", "bab_el_mandeb", "suez", "gibraltar"],
    ("JAPAN", "EU"): ["malacca", "singapore", "bab_el_mandeb", "suez", "gibraltar"],
    ("KOREA", "EU"): ["malacca", "singapore", "bab_el_mandeb", "suez", "gibraltar"],
    ("ASIA", "US_EAST"): ["malacca", "singapore", "bab_el_mandeb", "suez", "gibraltar"],
    ("CHINA", "US_EAST"): ["taiwan", "malacca", "singapore", "bab_el_mandeb", "suez", "gibraltar"],

    # Asia to US West (direct Pacific)
    ("ASIA", "US_WEST"): [],  # Direct Pacific route
    ("CHINA", "US_WEST"): [],
    ("JAPAN", "US_WEST"): [],
    ("KOREA", "US_WEST"): [],

    # Europe to US
    ("EU", "US_EAST"): ["english_channel"],
    ("EU", "US_WEST"): ["english_channel", "panama"],
    ("MED", "US_EAST"): ["gibraltar"],
    ("MED", "US_WEST"): ["gibraltar", "panama"],

    # US East to US West
    ("US_EAST", "US_WEST"): ["panama"],

    # Middle East routes
    ("MENA", "ASIA"): ["hormuz", "singapore", "malacca"],
    ("MENA", "EU"): ["suez", "gibraltar"],
    ("MENA", "US_EAST"): ["suez", "gibraltar"],

    # India routes
    ("INDIA", "EU"): ["bab_el_mandeb", "suez", "gibraltar"],
    ("INDIA", "US_EAST"): ["bab_el_mandeb", "suez", "gibraltar"],
    ("INDIA", "ASIA"): ["singapore", "malacca"],
    ("INDIA", "CHINA"): ["singapore", "malacca"],

    # Oceania routes
    ("OCEANIA", "ASIA"): ["singapore"],
    ("OCEANIA", "EU"): ["singapore", "malacca", "bab_el_mandeb", "suez", "gibraltar"],
    ("OCEANIA", "US_WEST"): [],  # Direct Pacific

    # Africa routes
    ("AFRICA", "EU"): ["cape_good_hope", "gibraltar"],
    ("AFRICA", "ASIA"): ["cape_good_hope", "singapore"],
    ("AFRICA", "US_EAST"): ["cape_good_hope"],
}


def get_terminal_region(terminal: dict, centroid: tuple = None) -> str:
    """
    Classify a terminal by its geographic region.

    Args:
        terminal: Terminal geofence dict with properties.name containing country code
        centroid: Optional (lon, lat) tuple for longitude-based region filtering

    Returns:
        Region string (e.g., "US_EAST", "ASIA", "EU")
    """
    name = terminal.get("properties", {}).get("name", "")
    country_code = name[:2] if len(name) >= 2 else ""

    if country_code not in COUNTRY_TO_REGIONS:
        return "UNKNOWN"

    possible_regions = COUNTRY_TO_REGIONS[country_code]

    # If only one possible region, return it
    if len(possible_regions) == 1:
        return possible_regions[0]

    # Check longitude filters for US East/West distinction
    if centroid and country_code == "US":
        lon = centroid[0]
        for region in possible_regions:
            lon_filter = REGION_PREFIXES[region].get("lon_filter")
            if lon_filter and lon_filter(lon):
                return region

    # Return first matching region (most specific)
    return possible_regions[0]


def get_route_chokepoints(origin_region: str, dest_region: str) -> list:
    """
    Get the chokepoints needed for a route between two regions.

    Args:
        origin_region: Origin region string
        dest_region: Destination region string

    Returns:
        List of chokepoint keys to pass through, in order
    """
    # Check direct route
    key = (origin_region, dest_region)
    if key in ROUTE_CHOKEPOINTS:
        return ROUTE_CHOKEPOINTS[key]

    # Check reverse route (use reversed chokepoints)
    reverse_key = (dest_region, origin_region)
    if reverse_key in ROUTE_CHOKEPOINTS:
        return list(reversed(ROUTE_CHOKEPOINTS[reverse_key]))

    # No specific route defined, return empty (direct route)
    return []

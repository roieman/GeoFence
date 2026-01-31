"""
Water region definitions for route validation.

Simple bounding boxes to check if waypoints are over water.
Used to validate ocean routes don't cut through land masses.
"""

# Water region bounding boxes: (min_lon, min_lat, max_lon, max_lat)
# These are approximate but sufficient for route validation
WATER_REGIONS = {
    "north_atlantic": {
        "bounds": (-80, 0, 0, 65),
        "name": "North Atlantic Ocean"
    },
    "south_atlantic": {
        "bounds": (-70, -60, 20, 0),
        "name": "South Atlantic Ocean"
    },
    "north_pacific": {
        "bounds": (100, 0, -100, 65),  # Wraps around 180
        "name": "North Pacific Ocean",
        "wraps_dateline": True
    },
    "south_pacific": {
        "bounds": (140, -60, -70, 0),
        "name": "South Pacific Ocean",
        "wraps_dateline": True
    },
    "indian_ocean": {
        "bounds": (20, -60, 120, 30),
        "name": "Indian Ocean"
    },
    "mediterranean": {
        "bounds": (-6, 30, 42, 47),
        "name": "Mediterranean Sea"
    },
    "red_sea": {
        "bounds": (32, 12, 44, 30),
        "name": "Red Sea"
    },
    "arabian_sea": {
        "bounds": (45, 5, 78, 26),
        "name": "Arabian Sea"
    },
    "bay_of_bengal": {
        "bounds": (78, 5, 100, 23),
        "name": "Bay of Bengal"
    },
    "south_china_sea": {
        "bounds": (100, 0, 122, 25),
        "name": "South China Sea"
    },
    "east_china_sea": {
        "bounds": (117, 23, 132, 35),
        "name": "East China Sea"
    },
    "sea_of_japan": {
        "bounds": (127, 33, 142, 52),
        "name": "Sea of Japan"
    },
    "caribbean": {
        "bounds": (-90, 8, -60, 28),
        "name": "Caribbean Sea"
    },
    "gulf_of_mexico": {
        "bounds": (-98, 18, -80, 31),
        "name": "Gulf of Mexico"
    },
    "north_sea": {
        "bounds": (-5, 50, 10, 62),
        "name": "North Sea"
    },
    "baltic_sea": {
        "bounds": (9, 53, 30, 66),
        "name": "Baltic Sea"
    },
    "persian_gulf": {
        "bounds": (47, 23, 57, 31),
        "name": "Persian Gulf"
    },
    "gulf_of_aden": {
        "bounds": (43, 10, 52, 16),
        "name": "Gulf of Aden"
    },
    "malacca_strait": {
        "bounds": (95, -1, 105, 8),
        "name": "Strait of Malacca"
    },
    "english_channel": {
        "bounds": (-6, 48, 2, 52),
        "name": "English Channel"
    },
    "suez_canal_region": {
        "bounds": (31, 29, 35, 32),
        "name": "Suez Canal Region"
    },
    "panama_canal_region": {
        "bounds": (-82, 7, -77, 11),
        "name": "Panama Canal Region"
    }
}

# Known land masses to avoid (rough polygons as bounding boxes)
# Format: (min_lon, min_lat, max_lon, max_lat)
LAND_MASSES = {
    "north_america": [
        (-170, 25, -52, 85),  # Main continent
    ],
    "south_america": [
        (-82, -56, -34, 12),
    ],
    "europe": [
        (-10, 36, 40, 72),  # Western Europe
    ],
    "africa": [
        (-18, -35, 52, 37),
    ],
    "asia": [
        (25, 1, 180, 78),  # Main Asia block
        (-180, 50, -170, 72),  # Far east Russia
    ],
    "australia": [
        (113, -45, 154, -10),
    ],
    "india": [
        (68, 6, 98, 38),
    ]
}


def is_point_in_water(lon: float, lat: float) -> bool:
    """
    Check if a point is likely over water.

    Uses simple bounding box checks against known water regions.
    This is an approximation but works well for ocean route validation.

    Args:
        lon: Longitude (-180 to 180)
        lat: Latitude (-90 to 90)

    Returns:
        True if point is likely in water, False if likely on land
    """
    # Normalize longitude to -180 to 180
    while lon > 180:
        lon -= 360
    while lon < -180:
        lon += 360

    # Check if in any water region
    for region_id, region in WATER_REGIONS.items():
        bounds = region["bounds"]
        min_lon, min_lat, max_lon, max_lat = bounds

        # Handle regions that wrap around the dateline
        if region.get("wraps_dateline"):
            # Split check: lon > min_lon OR lon < max_lon (where max is negative)
            if max_lon < min_lon:  # Wrapping case
                lon_match = lon >= min_lon or lon <= max_lon
            else:
                lon_match = min_lon <= lon <= max_lon
        else:
            lon_match = min_lon <= lon <= max_lon

        lat_match = min_lat <= lat <= max_lat

        if lon_match and lat_match:
            return True

    # If not in any known water region, do a land mass check
    for continent, boxes in LAND_MASSES.items():
        for box in boxes:
            min_lon, min_lat, max_lon, max_lat = box
            if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                return False

    # Default: if not explicitly land, assume water for ocean routes
    return True


def is_point_clearly_on_land(lon: float, lat: float) -> bool:
    """
    Check if a point is clearly on land (inside a known land mass).

    More conservative check - only returns True if definitely on land.

    Args:
        lon: Longitude
        lat: Latitude

    Returns:
        True if point is clearly on land
    """
    # Normalize longitude
    while lon > 180:
        lon -= 360
    while lon < -180:
        lon += 360

    # Check against land masses with some tolerance for coastal areas
    tolerance = 2  # degrees - don't flag points near coasts

    for continent, boxes in LAND_MASSES.items():
        for box in boxes:
            min_lon, min_lat, max_lon, max_lat = box
            # Add tolerance to shrink the "definitely land" region
            if (min_lon + tolerance <= lon <= max_lon - tolerance and
                    min_lat + tolerance <= lat <= max_lat - tolerance):
                # Additional check: not near known water regions
                in_water_region = False
                for region_id, region in WATER_REGIONS.items():
                    bounds = region["bounds"]
                    w_min_lon, w_min_lat, w_max_lon, w_max_lat = bounds
                    if w_min_lon <= lon <= w_max_lon and w_min_lat <= lat <= w_max_lat:
                        in_water_region = True
                        break

                if not in_water_region:
                    return True

    return False


def get_nearest_water_point(lon: float, lat: float) -> tuple:
    """
    Find the nearest water point for a land-bound waypoint.

    Simple heuristic: move toward the nearest water region center.

    Args:
        lon: Longitude of land point
        lat: Latitude of land point

    Returns:
        (lon, lat) tuple of adjusted point
    """
    # Find the nearest water region
    min_dist = float('inf')
    nearest_region = None

    for region_id, region in WATER_REGIONS.items():
        bounds = region["bounds"]
        min_lon, min_lat, max_lon, max_lat = bounds

        # Calculate center of water region
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2

        # Simple distance (not haversine, just for comparison)
        dist = ((lon - center_lon) ** 2 + (lat - center_lat) ** 2) ** 0.5

        if dist < min_dist:
            min_dist = dist
            nearest_region = region

    if nearest_region:
        bounds = nearest_region["bounds"]
        min_lon, min_lat, max_lon, max_lat = bounds

        # Clamp point to within the water region bounds
        adjusted_lon = max(min_lon, min(max_lon, lon))
        adjusted_lat = max(min_lat, min(max_lat, lat))

        return (adjusted_lon, adjusted_lat)

    return (lon, lat)

"""
Geofence checker - determines if a point is inside any geofence polygon.
Uses MongoDB's $geoWithin for efficient geospatial queries.
"""
from typing import Optional, List, Dict, Any
from pymongo import MongoClient
from pymongo.database import Database

from simulator.config import COLLECTIONS


class GeofenceChecker:
    """
    Check if GPS coordinates are inside any geofence polygon.
    Uses MongoDB geospatial queries for efficiency.
    """

    def __init__(self, db: Database):
        self.db = db
        self.geofences = db[COLLECTIONS["geofences"]]
        self._geofence_cache: Dict[str, dict] = {}

    def check_point(self, lon: float, lat: float) -> Optional[dict]:
        """
        Check if a point is inside any geofence.

        Args:
            lon: Longitude
            lat: Latitude

        Returns:
            Geofence document if point is inside, None otherwise
        """
        result = self.geofences.find_one({
            "geometry": {
                "$geoIntersects": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                }
            }
        })

        return result

    def check_point_all(self, lon: float, lat: float) -> List[dict]:
        """
        Find all geofences containing a point (for nested polygons).

        Args:
            lon: Longitude
            lat: Latitude

        Returns:
            List of geofence documents containing the point
        """
        results = self.geofences.find({
            "geometry": {
                "$geoIntersects": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                }
            }
        })

        return list(results)

    def get_geofence_by_name(self, name: str) -> Optional[dict]:
        """Get a geofence by name (with caching)."""
        if name in self._geofence_cache:
            return self._geofence_cache[name]

        geofence = self.geofences.find_one({"properties.name": name})
        if geofence:
            self._geofence_cache[name] = geofence

        return geofence

    def get_geofences_by_type(self, type_id: str) -> List[dict]:
        """Get all geofences of a specific type."""
        return list(self.geofences.find({"properties.typeId": type_id}))

    def get_geofences_by_country(self, country_code: str) -> List[dict]:
        """Get all geofences in a country (based on UNLOCode prefix)."""
        return list(self.geofences.find({
            "properties.UNLOCode": {"$regex": f"^{country_code}", "$options": "i"}
        }))

    def get_nearby_geofences(self, lon: float, lat: float, max_distance_meters: int = 50000) -> List[dict]:
        """
        Find geofences near a point.

        Args:
            lon: Longitude
            lat: Latitude
            max_distance_meters: Maximum distance in meters (default 50km)

        Returns:
            List of nearby geofences sorted by distance
        """
        # Use $near requires a 2dsphere index on geometry
        # This finds geofences whose geometry is near the point
        pipeline = [
            {
                "$geoNear": {
                    "near": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    },
                    "distanceField": "distance",
                    "maxDistance": max_distance_meters,
                    "spherical": True,
                    "key": "geometry"
                }
            },
            {"$limit": 20}
        ]

        try:
            return list(self.geofences.aggregate(pipeline))
        except Exception as e:
            # Fallback if index doesn't exist yet
            print(f"Warning: $geoNear failed ({e}), using basic query")
            return []

    def get_centroid(self, geofence: dict) -> tuple:
        """
        Calculate the centroid of a geofence polygon.

        Args:
            geofence: Geofence document

        Returns:
            (longitude, latitude) of centroid
        """
        geometry = geofence.get("geometry", {})
        coords = geometry.get("coordinates", [[]])

        if geometry.get("type") == "Polygon":
            # For polygon, average all points
            ring = coords[0]  # Outer ring
            if not ring:
                return (0, 0)

            lon_sum = sum(p[0] for p in ring)
            lat_sum = sum(p[1] for p in ring)
            count = len(ring)

            return (lon_sum / count, lat_sum / count)

        return (0, 0)

    def clear_cache(self):
        """Clear the geofence cache."""
        self._geofence_cache.clear()

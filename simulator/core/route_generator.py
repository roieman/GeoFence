"""
Route generator - creates realistic shipping routes between geofences.
Handles both ocean routes (vessel) and land routes (truck).
"""
import math
import random
from typing import List, Tuple, Optional
from pymongo.database import Database

from simulator.config import COLLECTIONS, GeofenceType
from simulator.core.geofence_checker import GeofenceChecker


class RouteGenerator:
    """
    Generate realistic routes between geofences.
    """

    def __init__(self, db: Database):
        self.db = db
        self.geofences = db[COLLECTIONS["geofences"]]
        self.checker = GeofenceChecker(db)

        # Cache for terminals, depots, rail ramps
        self._terminals: List[dict] = []
        self._depots: List[dict] = []
        self._rail_ramps: List[dict] = []
        self._loaded = False

    def _load_geofences(self):
        """Load and categorize all geofences."""
        if self._loaded:
            return

        self._terminals = list(self.geofences.find({"properties.typeId": GeofenceType.TERMINAL}))
        self._depots = list(self.geofences.find({"properties.typeId": GeofenceType.DEPOT}))
        self._rail_ramps = list(self.geofences.find({"properties.typeId": GeofenceType.RAIL_RAMP}))
        self._loaded = True

        print(f"Loaded {len(self._terminals)} terminals, {len(self._depots)} depots, {len(self._rail_ramps)} rail ramps")

    def get_random_terminal(self, exclude: Optional[str] = None) -> Optional[dict]:
        """Get a random terminal, optionally excluding one."""
        self._load_geofences()
        candidates = [t for t in self._terminals if t["properties"]["name"] != exclude] if exclude else self._terminals
        return random.choice(candidates) if candidates else None

    def get_random_depot(self, near_terminal: Optional[dict] = None) -> Optional[dict]:
        """
        Get a random depot, preferring ones near a terminal if specified.
        """
        self._load_geofences()

        if not self._depots:
            return None

        if near_terminal:
            # Try to find a depot in the same country/region
            terminal_name = near_terminal["properties"]["name"]
            country_code = terminal_name[:2] if len(terminal_name) >= 2 else ""

            same_country = [d for d in self._depots
                           if d["properties"]["name"].startswith(country_code)]

            if same_country:
                return random.choice(same_country)

        return random.choice(self._depots)

    def generate_ocean_route(
        self,
        origin: dict,
        destination: dict,
        num_waypoints: int = 20
    ) -> List[Tuple[float, float]]:
        """
        Generate a realistic ocean route between two terminals.

        Creates a great circle route with some randomization to simulate
        actual shipping lanes. Points are placed in water (not on land).

        Args:
            origin: Origin terminal geofence
            destination: Destination terminal geofence
            num_waypoints: Number of intermediate waypoints

        Returns:
            List of (lon, lat) waypoints
        """
        origin_centroid = self.checker.get_centroid(origin)
        dest_centroid = self.checker.get_centroid(destination)

        # Generate great circle route
        waypoints = self._great_circle_points(
            origin_centroid[0], origin_centroid[1],
            dest_centroid[0], dest_centroid[1],
            num_waypoints
        )

        # Add some randomization to make route more realistic
        # (simulating actual shipping lanes, weather routing, etc.)
        waypoints = self._add_route_variation(waypoints, max_deviation_km=50)

        return waypoints

    def generate_land_route(
        self,
        origin: dict,
        destination: dict,
        num_waypoints: int = 10
    ) -> List[Tuple[float, float]]:
        """
        Generate a land route between two geofences (depot to terminal or vice versa).

        Args:
            origin: Origin geofence
            destination: Destination geofence
            num_waypoints: Number of intermediate waypoints

        Returns:
            List of (lon, lat) waypoints
        """
        origin_centroid = self.checker.get_centroid(origin)
        dest_centroid = self.checker.get_centroid(destination)

        # For land routes, use simple linear interpolation with some variation
        waypoints = []
        for i in range(num_waypoints + 1):
            t = i / num_waypoints
            lon = origin_centroid[0] + t * (dest_centroid[0] - origin_centroid[0])
            lat = origin_centroid[1] + t * (dest_centroid[1] - origin_centroid[1])
            waypoints.append((lon, lat))

        # Add road-like variation
        waypoints = self._add_route_variation(waypoints, max_deviation_km=5)

        return waypoints

    def _great_circle_points(
        self,
        lon1: float, lat1: float,
        lon2: float, lat2: float,
        num_points: int
    ) -> List[Tuple[float, float]]:
        """
        Generate points along a great circle route.
        """
        # Convert to radians
        lon1_r, lat1_r = math.radians(lon1), math.radians(lat1)
        lon2_r, lat2_r = math.radians(lon2), math.radians(lat2)

        # Calculate great circle distance
        d = 2 * math.asin(math.sqrt(
            math.sin((lat2_r - lat1_r) / 2) ** 2 +
            math.cos(lat1_r) * math.cos(lat2_r) * math.sin((lon2_r - lon1_r) / 2) ** 2
        ))

        waypoints = []
        for i in range(num_points + 1):
            f = i / num_points

            # Intermediate point on great circle
            A = math.sin((1 - f) * d) / math.sin(d) if d > 0 else 1 - f
            B = math.sin(f * d) / math.sin(d) if d > 0 else f

            x = A * math.cos(lat1_r) * math.cos(lon1_r) + B * math.cos(lat2_r) * math.cos(lon2_r)
            y = A * math.cos(lat1_r) * math.sin(lon1_r) + B * math.cos(lat2_r) * math.sin(lon2_r)
            z = A * math.sin(lat1_r) + B * math.sin(lat2_r)

            lat = math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))
            lon = math.degrees(math.atan2(y, x))

            waypoints.append((lon, lat))

        return waypoints

    def _add_route_variation(
        self,
        waypoints: List[Tuple[float, float]],
        max_deviation_km: float = 20
    ) -> List[Tuple[float, float]]:
        """
        Add realistic variation to a route.
        Don't modify start and end points.
        """
        if len(waypoints) <= 2:
            return waypoints

        result = [waypoints[0]]

        for i in range(1, len(waypoints) - 1):
            lon, lat = waypoints[i]

            # Convert km to approximate degrees
            # 1 degree latitude ≈ 111 km
            # 1 degree longitude ≈ 111 km * cos(lat)
            km_to_lat = 1 / 111
            km_to_lon = 1 / (111 * math.cos(math.radians(lat))) if lat != 90 else 0

            # Random deviation
            deviation = random.gauss(0, max_deviation_km / 3)  # 99.7% within max_deviation
            angle = random.uniform(0, 2 * math.pi)

            lon_offset = deviation * km_to_lon * math.cos(angle)
            lat_offset = deviation * km_to_lat * math.sin(angle)

            result.append((lon + lon_offset, lat + lat_offset))

        result.append(waypoints[-1])
        return result

    def calculate_distance_km(
        self,
        lon1: float, lat1: float,
        lon2: float, lat2: float
    ) -> float:
        """
        Calculate distance between two points in kilometers using Haversine formula.
        """
        R = 6371  # Earth's radius in km

        lon1_r, lat1_r = math.radians(lon1), math.radians(lat1)
        lon2_r, lat2_r = math.radians(lon2), math.radians(lat2)

        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def calculate_route_distance(self, waypoints: List[Tuple[float, float]]) -> float:
        """Calculate total distance of a route in kilometers."""
        if len(waypoints) < 2:
            return 0

        total = 0
        for i in range(len(waypoints) - 1):
            total += self.calculate_distance_km(
                waypoints[i][0], waypoints[i][1],
                waypoints[i + 1][0], waypoints[i + 1][1]
            )

        return total

    def select_journey(self) -> dict:
        """
        Select a complete journey: depot -> terminal -> terminal -> depot.

        Returns:
            Dictionary with origin_depot, origin_terminal, destination_terminal, destination_depot
        """
        self._load_geofences()

        # Pick random terminals for origin and destination
        origin_terminal = self.get_random_terminal()
        if not origin_terminal:
            raise ValueError("No terminals available")

        destination_terminal = self.get_random_terminal(exclude=origin_terminal["properties"]["name"])
        if not destination_terminal:
            destination_terminal = origin_terminal  # Same terminal if only one

        # Pick depots near each terminal
        origin_depot = self.get_random_depot(near_terminal=origin_terminal)
        destination_depot = self.get_random_depot(near_terminal=destination_terminal)

        return {
            "origin_depot": origin_depot,
            "origin_terminal": origin_terminal,
            "destination_terminal": destination_terminal,
            "destination_depot": destination_depot
        }

"""
Route generator - creates realistic shipping routes between geofences.
Handles both ocean routes (vessel) and land routes (truck/rail).

Includes:
- Ocean chokepoint routing (Suez, Panama, Malacca, etc.)
- Rail ramp routing for US/Canada/UK
- Route validation to avoid land masses
"""
import math
import random
from typing import List, Tuple, Optional
from pymongo.database import Database

from simulator.config import (
    COLLECTIONS, GeofenceType,
    RAIL_ROUTING_PROBABILITY, RAIL_ENABLED_COUNTRIES
)
from simulator.core.geofence_checker import GeofenceChecker
from simulator.data.chokepoints import (
    CHOKEPOINTS, get_terminal_region, get_route_chokepoints
)
from simulator.data.water_regions import is_point_in_water, is_point_clearly_on_land, get_nearest_water_point


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

        Creates routes through appropriate shipping chokepoints (Suez, Panama, etc.)
        based on origin and destination regions. Uses great circle segments between
        waypoints with randomization for realism.

        Args:
            origin: Origin terminal geofence
            destination: Destination terminal geofence
            num_waypoints: Number of intermediate waypoints per segment

        Returns:
            List of (lon, lat) waypoints
        """
        origin_centroid = self.checker.get_centroid(origin)
        dest_centroid = self.checker.get_centroid(destination)

        # Determine which chokepoints are needed based on regions
        origin_region = get_terminal_region(origin, origin_centroid)
        dest_region = get_terminal_region(destination, dest_centroid)

        chokepoint_keys = get_route_chokepoints(origin_region, dest_region)

        # Build route through chokepoints
        waypoints = self._build_chokepoint_route(
            origin_centroid, dest_centroid,
            chokepoint_keys, num_waypoints
        )

        # Validate route stays in water
        waypoints = self._validate_ocean_route(waypoints)

        # Add some randomization to make route more realistic
        waypoints = self._add_route_variation(waypoints, max_deviation_km=50)

        return waypoints

    def _build_chokepoint_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        chokepoint_keys: List[str],
        waypoints_per_segment: int = 10
    ) -> List[Tuple[float, float]]:
        """
        Build a route passing through specified chokepoints.

        Args:
            origin: (lon, lat) of origin
            destination: (lon, lat) of destination
            chokepoint_keys: List of chokepoint keys to pass through
            waypoints_per_segment: Number of waypoints per route segment

        Returns:
            List of (lon, lat) waypoints
        """
        if not chokepoint_keys:
            # Direct route if no chokepoints needed
            return self._great_circle_points(
                origin[0], origin[1],
                destination[0], destination[1],
                waypoints_per_segment * 2
            )

        # Build list of all waypoints including chokepoint waypoints
        all_waypoints = []
        current_point = origin

        for key in chokepoint_keys:
            chokepoint = CHOKEPOINTS.get(key)
            if not chokepoint:
                continue

            cp_waypoints = chokepoint["waypoints"]
            if not cp_waypoints:
                continue

            # Route from current point to first chokepoint waypoint
            segment = self._great_circle_points(
                current_point[0], current_point[1],
                cp_waypoints[0][0], cp_waypoints[0][1],
                waypoints_per_segment
            )
            all_waypoints.extend(segment[:-1])  # Exclude last to avoid duplicates

            # Add chokepoint waypoints
            all_waypoints.extend(cp_waypoints)

            # Update current point to last chokepoint waypoint
            current_point = cp_waypoints[-1]

        # Route from last chokepoint to destination
        final_segment = self._great_circle_points(
            current_point[0], current_point[1],
            destination[0], destination[1],
            waypoints_per_segment
        )
        all_waypoints.extend(final_segment)

        return all_waypoints

    def _validate_ocean_route(
        self,
        waypoints: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """
        Validate ocean route waypoints stay in water.
        Adjust any points that appear to be on land.

        Args:
            waypoints: List of (lon, lat) waypoints

        Returns:
            Adjusted waypoints list
        """
        if len(waypoints) <= 2:
            return waypoints

        validated = [waypoints[0]]  # Keep origin

        for i in range(1, len(waypoints) - 1):
            lon, lat = waypoints[i]

            if is_point_clearly_on_land(lon, lat):
                # Adjust point toward water
                adjusted = get_nearest_water_point(lon, lat)
                validated.append(adjusted)
            else:
                validated.append((lon, lat))

        validated.append(waypoints[-1])  # Keep destination
        return validated

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
        May include rail ramps for eligible countries.

        Returns:
            Dictionary with origin_depot, origin_terminal, destination_terminal, destination_depot,
            plus optional origin_rail_ramp, destination_rail_ramp, and use_rail flag.
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

        journey = {
            "origin_depot": origin_depot,
            "origin_terminal": origin_terminal,
            "destination_terminal": destination_terminal,
            "destination_depot": destination_depot,
            "origin_rail_ramp": None,
            "destination_rail_ramp": None,
            "use_rail": False
        }

        # Check if rail routing should be used
        if self.should_use_rail(origin_depot, origin_terminal):
            rail_ramp = self.get_random_rail_ramp(near_terminal=origin_terminal)
            if rail_ramp:
                journey["origin_rail_ramp"] = rail_ramp
                journey["use_rail"] = True

        if self.should_use_rail(destination_depot, destination_terminal):
            rail_ramp = self.get_random_rail_ramp(near_terminal=destination_terminal)
            if rail_ramp:
                journey["destination_rail_ramp"] = rail_ramp
                journey["use_rail"] = True

        return journey

    def get_random_rail_ramp(self, near_terminal: Optional[dict] = None) -> Optional[dict]:
        """
        Get a random rail ramp, preferring ones near a terminal.

        Args:
            near_terminal: Optional terminal to find rail ramps near

        Returns:
            Rail ramp geofence dict or None
        """
        self._load_geofences()

        if not self._rail_ramps:
            return None

        if near_terminal:
            # Find rail ramps in the same country
            terminal_name = near_terminal["properties"]["name"]
            country_code = terminal_name[:2] if len(terminal_name) >= 2 else ""

            same_country = [r for r in self._rail_ramps
                           if r["properties"]["name"].startswith(country_code)]

            if same_country:
                return random.choice(same_country)

        return random.choice(self._rail_ramps)

    def should_use_rail(self, depot: Optional[dict], terminal: Optional[dict]) -> bool:
        """
        Determine if rail routing should be used for a journey segment.

        Uses RAIL_ROUTING_PROBABILITY and checks if the country supports rail.

        Args:
            depot: Depot geofence
            terminal: Terminal geofence

        Returns:
            True if rail should be used, False otherwise
        """
        if not depot or not terminal:
            return False

        # Check if terminal is in a rail-enabled country
        terminal_name = terminal["properties"]["name"]
        country_code = terminal_name[:2] if len(terminal_name) >= 2 else ""

        if country_code not in RAIL_ENABLED_COUNTRIES:
            return False

        # Check if we have rail ramps in this country
        self._load_geofences()
        country_ramps = [r for r in self._rail_ramps
                         if r["properties"]["name"].startswith(country_code)]

        if not country_ramps:
            return False

        # Apply probability
        return random.random() < RAIL_ROUTING_PROBABILITY

    def generate_rail_route(
        self,
        origin: dict,
        destination: dict,
        num_waypoints: int = 15
    ) -> List[Tuple[float, float]]:
        """
        Generate a rail route between two geofences.

        Similar to land route but with longer segments and less variation
        since trains follow fixed tracks.

        Args:
            origin: Origin geofence (rail ramp or terminal)
            destination: Destination geofence (rail ramp or terminal)
            num_waypoints: Number of intermediate waypoints

        Returns:
            List of (lon, lat) waypoints
        """
        origin_centroid = self.checker.get_centroid(origin)
        dest_centroid = self.checker.get_centroid(destination)

        # Rail routes are more direct than truck routes
        waypoints = []
        for i in range(num_waypoints + 1):
            t = i / num_waypoints
            lon = origin_centroid[0] + t * (dest_centroid[0] - origin_centroid[0])
            lat = origin_centroid[1] + t * (dest_centroid[1] - origin_centroid[1])
            waypoints.append((lon, lat))

        # Add minimal variation for rail routes
        waypoints = self._add_route_variation(waypoints, max_deviation_km=2)

        return waypoints

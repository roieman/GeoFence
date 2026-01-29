"""
Vessel model for ships carrying containers.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional
import random
import string


def generate_vessel_name() -> str:
    """Generate a realistic vessel name."""
    prefixes = ["ZIM", "MSC", "MAERSK", "COSCO", "EVERGREEN", "CMA CGM"]
    names = [
        "ATLANTIC", "PACIFIC", "MEDITERRANEAN", "SHANGHAI", "ROTTERDAM",
        "SINGAPORE", "HAMBURG", "ANTWERP", "SANTOS", "DURBAN",
        "EXPLORER", "VOYAGER", "NAVIGATOR", "PIONEER", "GUARDIAN"
    ]
    return f"{random.choice(prefixes)} {random.choice(names)}"


def generate_imo_number() -> str:
    """Generate a realistic IMO number."""
    return f"IMO{random.randint(9000000, 9999999)}"


@dataclass
class Vessel:
    """
    Vessel carrying containers between ports.
    """
    name: str = field(default_factory=generate_vessel_name)
    imo_number: str = field(default_factory=generate_imo_number)

    # Current position
    latitude: float = 0.0
    longitude: float = 0.0

    # Route
    origin_terminal: Optional[dict] = None
    destination_terminal: Optional[dict] = None
    route_waypoints: List[Tuple[float, float]] = field(default_factory=list)
    current_waypoint_index: int = 0

    # Speed (in knots)
    speed: float = 18.0

    # Containers on board
    container_ids: List[str] = field(default_factory=list)
    capacity: int = field(default_factory=lambda: random.randint(5000, 20000))

    # Status
    is_at_port: bool = True
    current_port: Optional[str] = None

    # Timestamps
    departure_time: Optional[datetime] = None
    eta: Optional[datetime] = None

    def set_position(self, lat: float, lon: float):
        """Update vessel position."""
        self.latitude = lat
        self.longitude = lon

    def get_position(self) -> Tuple[float, float]:
        """Get current position."""
        return (self.latitude, self.longitude)

    def load_container(self, container_id: str):
        """Load a container onto the vessel."""
        if container_id not in self.container_ids:
            self.container_ids.append(container_id)

    def unload_container(self, container_id: str):
        """Unload a container from the vessel."""
        if container_id in self.container_ids:
            self.container_ids.remove(container_id)

    def depart(self, departure_time: datetime):
        """Depart from current port."""
        self.is_at_port = False
        self.departure_time = departure_time
        self.current_port = None

    def arrive(self, port_name: str):
        """Arrive at a port."""
        self.is_at_port = True
        self.current_port = port_name

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB."""
        return {
            "name": self.name,
            "imo_number": self.imo_number,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed": self.speed,
            "container_count": len(self.container_ids),
            "capacity": self.capacity,
            "is_at_port": self.is_at_port,
            "current_port": self.current_port,
            "origin_terminal": self.origin_terminal.get("name") if self.origin_terminal else None,
            "destination_terminal": self.destination_terminal.get("name") if self.destination_terminal else None,
        }

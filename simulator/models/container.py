"""
Container model with state machine for tracking container lifecycle.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple, List
from enum import Enum
import random
import string

from simulator.config import ContainerState, EventType


def generate_container_id() -> str:
    """Generate a realistic Zim container ID (e.g., ZIMU3170479)."""
    prefix = "ZIMU"  # Zim's owner code
    number = ''.join(random.choices(string.digits, k=7))
    return f"{prefix}{number}"


def generate_tracker_id() -> str:
    """Generate a tracker ID (e.g., A0000669)."""
    return f"A{random.randint(0, 9999999):07d}"


@dataclass
class ContainerMetadata:
    """Container metadata."""
    container_id: str = field(default_factory=generate_container_id)
    tracker_id: str = field(default_factory=generate_tracker_id)
    asset_id: int = field(default_factory=lambda: random.randint(30000, 40000))
    container_type: str = field(default_factory=lambda: random.choice(["20ft", "40ft", "40ft HC", "45ft HC"]))
    refrigerated: bool = field(default_factory=lambda: random.random() < 0.15)  # 15% reefer
    cargo_type: str = field(default_factory=lambda: random.choice([
        "General Cargo", "Electronics", "Textiles", "Machinery",
        "Food Products", "Chemicals", "Auto Parts", "Furniture"
    ]))


@dataclass
class Container:
    """
    Container with state machine for tracking its journey.
    """
    metadata: ContainerMetadata = field(default_factory=ContainerMetadata)
    state: str = ContainerState.AT_ORIGIN_DEPOT

    # Staggered reporting slot (for large-scale simulation)
    report_slot: int = 0  # Assigned slot for staggered event generation

    # Current position
    latitude: float = 0.0
    longitude: float = 0.0

    # Journey information
    origin_depot: Optional[dict] = None
    origin_rail_ramp: Optional[dict] = None
    origin_terminal: Optional[dict] = None
    destination_terminal: Optional[dict] = None
    destination_rail_ramp: Optional[dict] = None
    destination_depot: Optional[dict] = None
    vessel_id: Optional[str] = None
    use_rail: bool = False  # Whether this journey uses rail routing

    # Route waypoints
    current_route: List[Tuple[float, float]] = field(default_factory=list)
    route_index: int = 0

    # State tracking
    is_moving: bool = False
    door_open: bool = False
    current_geofence: Optional[str] = None  # Name of geofence container is currently in

    # Timestamps
    last_event_time: Optional[datetime] = None
    journey_start_time: Optional[datetime] = None

    def set_position(self, lat: float, lon: float):
        """Update container position."""
        self.latitude = lat
        self.longitude = lon

    def get_position(self) -> Tuple[float, float]:
        """Get current position as (lat, lon)."""
        return (self.latitude, self.longitude)

    def start_motion(self) -> str:
        """Start moving, return event type."""
        self.is_moving = True
        return EventType.IN_MOTION

    def stop_motion(self) -> str:
        """Stop moving, return event type."""
        self.is_moving = False
        return EventType.MOTION_STOP

    def open_door(self) -> str:
        """Open container door."""
        self.door_open = True
        return EventType.DOOR_OPENED

    def close_door(self) -> str:
        """Close container door."""
        self.door_open = False
        return EventType.DOOR_CLOSED

    def enter_geofence(self, geofence_name: str) -> str:
        """Enter a geofence."""
        self.current_geofence = geofence_name
        return EventType.GATE_IN

    def exit_geofence(self) -> str:
        """Exit current geofence."""
        self.current_geofence = None
        return EventType.GATE_OUT

    def transition_to(self, new_state: str):
        """Transition to a new state."""
        valid_transitions = {
            # Standard journey (no rail)
            ContainerState.AT_ORIGIN_DEPOT: [
                ContainerState.IN_TRANSIT_TO_TERMINAL,
                ContainerState.IN_TRANSIT_TO_RAIL_RAMP  # Rail option
            ],
            ContainerState.IN_TRANSIT_TO_TERMINAL: [ContainerState.AT_ORIGIN_TERMINAL],
            ContainerState.AT_ORIGIN_TERMINAL: [ContainerState.LOADED_ON_VESSEL],
            ContainerState.LOADED_ON_VESSEL: [ContainerState.IN_TRANSIT_OCEAN],
            ContainerState.IN_TRANSIT_OCEAN: [ContainerState.AT_DESTINATION_TERMINAL],
            ContainerState.AT_DESTINATION_TERMINAL: [
                ContainerState.IN_TRANSIT_TO_DEPOT,
                ContainerState.IN_TRANSIT_FROM_TERMINAL  # Rail option
            ],
            ContainerState.IN_TRANSIT_TO_DEPOT: [ContainerState.AT_DESTINATION_DEPOT],
            ContainerState.AT_DESTINATION_DEPOT: [
                ContainerState.IN_TRANSIT_TO_TERMINAL,
                ContainerState.IN_TRANSIT_TO_RAIL_RAMP  # New journey can use rail
            ],

            # Origin rail routing (depot -> rail ramp -> terminal)
            ContainerState.IN_TRANSIT_TO_RAIL_RAMP: [ContainerState.AT_ORIGIN_RAIL_RAMP],
            ContainerState.AT_ORIGIN_RAIL_RAMP: [ContainerState.IN_TRANSIT_RAIL],
            ContainerState.IN_TRANSIT_RAIL: [ContainerState.IN_TRANSIT_TO_TERMINAL],

            # Destination rail routing (terminal -> rail ramp -> depot)
            ContainerState.IN_TRANSIT_FROM_TERMINAL: [ContainerState.AT_DESTINATION_RAIL_RAMP],
            ContainerState.AT_DESTINATION_RAIL_RAMP: [ContainerState.IN_TRANSIT_RAIL_TO_DEPOT],
            ContainerState.IN_TRANSIT_RAIL_TO_DEPOT: [ContainerState.IN_TRANSIT_TO_DEPOT],
        }

        if new_state in valid_transitions.get(self.state, []):
            self.state = new_state
        else:
            raise ValueError(f"Invalid transition from {self.state} to {new_state}")

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB."""
        def get_name(obj):
            if obj is None:
                return None
            if isinstance(obj, dict):
                return obj.get("properties", {}).get("name") or obj.get("name")
            return None

        return {
            "container_id": self.metadata.container_id,
            "tracker_id": self.metadata.tracker_id,
            "asset_id": self.metadata.asset_id,
            "container_type": self.metadata.container_type,
            "refrigerated": self.metadata.refrigerated,
            "cargo_type": self.metadata.cargo_type,
            "state": self.state,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_moving": self.is_moving,
            "door_open": self.door_open,
            "current_geofence": self.current_geofence,
            "vessel_id": self.vessel_id,
            "use_rail": self.use_rail,
            "origin_depot": get_name(self.origin_depot),
            "origin_rail_ramp": get_name(self.origin_rail_ramp),
            "origin_terminal": get_name(self.origin_terminal),
            "destination_terminal": get_name(self.destination_terminal),
            "destination_rail_ramp": get_name(self.destination_rail_ramp),
            "destination_depot": get_name(self.destination_depot),
        }

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

    # Current position
    latitude: float = 0.0
    longitude: float = 0.0

    # Journey information
    origin_depot: Optional[dict] = None
    origin_terminal: Optional[dict] = None
    destination_terminal: Optional[dict] = None
    destination_depot: Optional[dict] = None
    vessel_id: Optional[str] = None

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
            ContainerState.AT_ORIGIN_DEPOT: [ContainerState.IN_TRANSIT_TO_TERMINAL],
            ContainerState.IN_TRANSIT_TO_TERMINAL: [ContainerState.AT_ORIGIN_TERMINAL],
            ContainerState.AT_ORIGIN_TERMINAL: [ContainerState.LOADED_ON_VESSEL],
            ContainerState.LOADED_ON_VESSEL: [ContainerState.IN_TRANSIT_OCEAN],
            ContainerState.IN_TRANSIT_OCEAN: [ContainerState.AT_DESTINATION_TERMINAL],
            ContainerState.AT_DESTINATION_TERMINAL: [ContainerState.IN_TRANSIT_TO_DEPOT],
            ContainerState.IN_TRANSIT_TO_DEPOT: [ContainerState.AT_DESTINATION_DEPOT],
            ContainerState.AT_DESTINATION_DEPOT: [ContainerState.IN_TRANSIT_TO_TERMINAL],  # New journey
        }

        if new_state in valid_transitions.get(self.state, []):
            self.state = new_state
        else:
            raise ValueError(f"Invalid transition from {self.state} to {new_state}")

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB."""
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
            "origin_depot": self.origin_depot.get("name") if self.origin_depot else None,
            "origin_terminal": self.origin_terminal.get("name") if self.origin_terminal else None,
            "destination_terminal": self.destination_terminal.get("name") if self.destination_terminal else None,
            "destination_depot": self.destination_depot.get("name") if self.destination_depot else None,
        }

"""
Configuration for the Zim GeoFence Simulator.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "zim_geofence")
USE_TIMESERIES = os.getenv("USE_TIMESERIES", "false").lower() in ("true", "1", "yes")

# Collection names
COLLECTIONS = {
    "geofences": "geofences",
    "iot_events": "iot_events",  # Regular collection
    "iot_events_ts": "iot_events_ts",  # TimeSeries collection
    "gate_events": "gate_events",  # Geofence crossing events
    "containers": "containers",  # Container metadata
    "vessels": "vessels",  # Vessel information
}

# Simulator settings
SIMULATION_SPEED = float(os.getenv("SIMULATION_SPEED", "60"))  # 60x = 1 minute real = 1 hour simulated
EVENT_INTERVAL_SECONDS = 300  # IoT reports every 5 minutes (in simulation time)
DOOR_EVENT_PROBABILITY = 0.3  # 30% chance of door event at stops

# Vessel speeds (in knots)
VESSEL_SPEED_MIN = 12
VESSEL_SPEED_MAX = 24
VESSEL_SPEED_AVG = 18

# Land transport speeds (in km/h)
TRUCK_SPEED_MIN = 40
TRUCK_SPEED_MAX = 80
TRUCK_SPEED_AVG = 60

# Container states
class ContainerState:
    AT_ORIGIN_DEPOT = "at_origin_depot"
    IN_TRANSIT_TO_TERMINAL = "in_transit_to_terminal"
    AT_ORIGIN_TERMINAL = "at_origin_terminal"
    LOADED_ON_VESSEL = "loaded_on_vessel"
    IN_TRANSIT_OCEAN = "in_transit_ocean"
    AT_DESTINATION_TERMINAL = "at_destination_terminal"
    IN_TRANSIT_TO_DEPOT = "in_transit_to_depot"
    AT_DESTINATION_DEPOT = "at_destination_depot"

# Event types (matching Zim's IoT events)
class EventType:
    IN_MOTION = "In Motion"
    MOTION_STOP = "Motion Stop"
    LOCATION_UPDATE = "Location Update"
    DOOR_OPENED = "Door Opened"
    DOOR_CLOSED = "Door Closed"
    GATE_IN = "Gate In"
    GATE_OUT = "Gate Out"

# Geofence types
class GeofenceType:
    TERMINAL = "Terminal"
    DEPOT = "Depot"
    RAIL_RAMP = "Rail ramp"

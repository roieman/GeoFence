"""
Backend configuration - shared settings for the Zim GeoFence application.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "zim_geofence")
DB_NAME_OLD = os.getenv("DB_NAME_OLD", "geofence")
USE_TIMESERIES = os.getenv("USE_TIMESERIES", "false").lower() in ("true", "1", "yes")
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# Collection names for new Zim database
COLLECTIONS = {
    "geofences": "geofences",
    "iot_events": "iot_events",
    "iot_events_ts": "iot_events_ts",
    "gate_events": "gate_events",
    "containers": "containers",
    "vessels": "vessels",
}

# Geofence types
GEOFENCE_TYPES = ["Terminal", "Depot", "Rail ramp"]

# Event types
EVENT_TYPES = [
    "In Motion",
    "Motion Stop",
    "Location Update",
    "Door Opened",
    "Door Closed",
    "Gate In",
    "Gate Out",
]

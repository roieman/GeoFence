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
    "clusters": "clusters",  # Groups of geofences (e.g., all terminals in a port)
    "iot_events": "iot_events",
    "iot_events_ts": "iot_events_ts",
    "gate_events": "gate_events",
    "containers": "containers",
    "vessels": "vessels",
}

# Geofence types
GEOFENCE_TYPES = ["Terminal", "Depot", "Rail ramp"]

# IOT Providers (for provider-specific geofence layers)
IOT_PROVIDERS = ["Hoopo", "Orbcom", "ZIM-Internal", "All"]

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

# User roles for permissions
USER_ROLES = {
    "admin": {"read": True, "write": True, "delete": True, "manage_users": True},
    "editor": {"read": True, "write": True, "delete": False, "manage_users": False},
    "viewer": {"read": True, "write": False, "delete": False, "manage_users": False},
}

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# External API endpoints for webhooks (API Out)
EXTERNAL_WEBHOOKS = {
    "hoopo": os.getenv("HOOPO_WEBHOOK_URL", ""),
    "orbcom": os.getenv("ORBCOM_WEBHOOK_URL", ""),
    "myzim": os.getenv("MYZIM_NOTIFICATION_URL", ""),
}

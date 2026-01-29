"""
Event generator - creates IoT events based on container state and movement.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import random

from simulator.config import EventType, DOOR_EVENT_PROBABILITY


class IoTEvent:
    """
    Represents an IoT event from a container tracker.
    """

    def __init__(
        self,
        tracker_id: str,
        asset_name: str,  # Container ID
        asset_id: int,
        event_time: datetime,
        report_time: datetime,
        latitude: float,
        longitude: float,
        event_type: str,
        event_location: Optional[str] = None,
        event_location_country: Optional[str] = None,
    ):
        self.tracker_id = tracker_id
        self.asset_name = asset_name
        self.asset_id = asset_id
        self.event_time = event_time
        self.report_time = report_time
        self.latitude = latitude
        self.longitude = longitude
        self.event_type = event_type
        self.event_location = event_location or "In Transit"
        self.event_location_country = event_location_country

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB (matches Zim's format)."""
        return {
            "TrackerID": self.tracker_id,
            "assetname": self.asset_name,
            "AssetId": self.asset_id,
            "EventTime": self.event_time,
            "ReportTime": self.report_time,
            "EventLocation": self.event_location,
            "EventLocationCountry": self.event_location_country,
            "Lat": self.latitude,
            "Lon": self.longitude,
            "EventType": self.event_type,
            # Additional fields for MongoDB geospatial
            "location": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            }
        }

    def to_timeseries_dict(self) -> dict:
        """Convert to TimeSeries format with metadata."""
        return {
            "metadata": {
                "TrackerID": self.tracker_id,
                "assetname": self.asset_name,
                "AssetId": self.asset_id,
            },
            "timestamp": self.event_time,
            "ReportTime": self.report_time,
            "EventLocation": self.event_location,
            "EventLocationCountry": self.event_location_country,
            "Lat": self.latitude,
            "Lon": self.longitude,
            "EventType": self.event_type,
            "location": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            }
        }


class EventGenerator:
    """
    Generate IoT events for containers.
    """

    def __init__(self):
        self._report_delay_min = 30  # seconds
        self._report_delay_max = 600  # seconds (10 minutes max delay)

    def _get_report_time(self, event_time: datetime) -> datetime:
        """
        Calculate report time with realistic delay (IoT transmission latency).
        """
        delay_seconds = random.randint(self._report_delay_min, self._report_delay_max)
        return event_time + timedelta(seconds=delay_seconds)

    def _get_country_from_geofence(self, geofence: Optional[dict]) -> Optional[str]:
        """Extract country code from geofence name or UNLO code."""
        if not geofence:
            return None

        properties = geofence.get("properties", {})

        # Try UNLO code first (first 2 chars)
        unlo = properties.get("UNLOCode", "")
        if len(unlo) >= 2:
            return unlo[:2]

        # Try name (first 2 chars)
        name = properties.get("name", "")
        if len(name) >= 2:
            return name[:2]

        return None

    def create_location_update(
        self,
        container,
        event_time: datetime,
        geofence: Optional[dict] = None
    ) -> IoTEvent:
        """
        Create a location update event.
        """
        geofence_name = geofence["properties"]["name"] if geofence else None
        country = self._get_country_from_geofence(geofence)

        return IoTEvent(
            tracker_id=container.metadata.tracker_id,
            asset_name=container.metadata.container_id,
            asset_id=container.metadata.asset_id,
            event_time=event_time,
            report_time=self._get_report_time(event_time),
            latitude=container.latitude,
            longitude=container.longitude,
            event_type=EventType.LOCATION_UPDATE,
            event_location=geofence_name,
            event_location_country=country
        )

    def create_motion_event(
        self,
        container,
        event_time: datetime,
        is_start: bool,
        geofence: Optional[dict] = None
    ) -> IoTEvent:
        """
        Create a motion start or stop event.
        """
        event_type = EventType.IN_MOTION if is_start else EventType.MOTION_STOP
        geofence_name = geofence["properties"]["name"] if geofence else None
        country = self._get_country_from_geofence(geofence)

        return IoTEvent(
            tracker_id=container.metadata.tracker_id,
            asset_name=container.metadata.container_id,
            asset_id=container.metadata.asset_id,
            event_time=event_time,
            report_time=self._get_report_time(event_time),
            latitude=container.latitude,
            longitude=container.longitude,
            event_type=event_type,
            event_location=geofence_name,
            event_location_country=country
        )

    def create_door_event(
        self,
        container,
        event_time: datetime,
        is_open: bool,
        geofence: Optional[dict] = None
    ) -> IoTEvent:
        """
        Create a door open or close event.
        """
        event_type = EventType.DOOR_OPENED if is_open else EventType.DOOR_CLOSED
        geofence_name = geofence["properties"]["name"] if geofence else None
        country = self._get_country_from_geofence(geofence)

        return IoTEvent(
            tracker_id=container.metadata.tracker_id,
            asset_name=container.metadata.container_id,
            asset_id=container.metadata.asset_id,
            event_time=event_time,
            report_time=self._get_report_time(event_time),
            latitude=container.latitude,
            longitude=container.longitude,
            event_type=event_type,
            event_location=geofence_name,
            event_location_country=country
        )

    def create_gate_event(
        self,
        container,
        event_time: datetime,
        is_entry: bool,
        geofence: dict
    ) -> IoTEvent:
        """
        Create a gate in or gate out event.
        """
        event_type = EventType.GATE_IN if is_entry else EventType.GATE_OUT
        geofence_name = geofence["properties"]["name"]
        country = self._get_country_from_geofence(geofence)

        return IoTEvent(
            tracker_id=container.metadata.tracker_id,
            asset_name=container.metadata.container_id,
            asset_id=container.metadata.asset_id,
            event_time=event_time,
            report_time=self._get_report_time(event_time),
            latitude=container.latitude,
            longitude=container.longitude,
            event_type=event_type,
            event_location=geofence_name,
            event_location_country=country
        )

    def generate_stop_events(
        self,
        container,
        event_time: datetime,
        geofence: Optional[dict] = None,
        include_door_events: bool = True
    ) -> List[IoTEvent]:
        """
        Generate events for a container stop.
        Includes motion stop and optionally door events.
        """
        events = []

        # Motion stop
        events.append(self.create_motion_event(container, event_time, is_start=False, geofence=geofence))

        # Optionally add door events
        if include_door_events and random.random() < DOOR_EVENT_PROBABILITY:
            # Door open shortly after stop
            door_open_time = event_time + timedelta(seconds=random.randint(30, 300))
            events.append(self.create_door_event(container, door_open_time, is_open=True, geofence=geofence))

            # Door close after some time
            door_close_time = door_open_time + timedelta(seconds=random.randint(60, 1800))
            events.append(self.create_door_event(container, door_close_time, is_open=False, geofence=geofence))

        return events

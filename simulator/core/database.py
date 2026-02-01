"""
Database handler - manages MongoDB connections and writes to both regular and TimeSeries collections.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from pymongo import MongoClient, ASCENDING, GEOSPHERE
from pymongo.database import Database
from pymongo.errors import CollectionInvalid

from simulator.config import MONGODB_URI, DB_NAME, COLLECTIONS, USE_TIMESERIES
from simulator.core.event_generator import IoTEvent


class DatabaseHandler:
    """
    Handles all database operations.
    Writes events to both regular and TimeSeries collections.
    """

    def __init__(self, uri: str = None, db_name: str = None):
        self.uri = uri or MONGODB_URI
        self.db_name = db_name or DB_NAME
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None

    def connect(self):
        """Establish database connection with connection pooling for high throughput."""
        print(f"Connecting to MongoDB: {self.uri[:50]}...")
        self.client = MongoClient(
            self.uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            maxPoolSize=50,  # Connection pool for high throughput
            minPoolSize=10,
        )

        # Test connection
        self.client.admin.command('ping')
        print(f"Connected successfully!")

        self.db = self.client[self.db_name]
        print(f"Using database: {self.db_name}")

        return self.db

    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            print("Database connection closed.")

    def setup_collections(self):
        """Create collections and indexes."""
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        print("\nSetting up collections...")

        # 1. Geofences collection
        geofences = self.db[COLLECTIONS["geofences"]]
        geofences.create_index([("geometry", GEOSPHERE)])
        geofences.create_index("properties.name", unique=True)
        geofences.create_index("properties.typeId")
        geofences.create_index("properties.UNLOCode")
        print(f"  - {COLLECTIONS['geofences']}: indexes created")

        # 2. Regular IoT events collection
        iot_events = self.db[COLLECTIONS["iot_events"]]
        iot_events.create_index([("location", GEOSPHERE)])
        iot_events.create_index("TrackerID")
        iot_events.create_index("assetname")
        iot_events.create_index("EventTime")
        iot_events.create_index("EventType")
        iot_events.create_index("EventLocation")
        iot_events.create_index([("assetname", ASCENDING), ("EventTime", ASCENDING)])
        print(f"  - {COLLECTIONS['iot_events']}: indexes created")

        # 3. TimeSeries IoT events collection
        try:
            self.db.create_collection(
                COLLECTIONS["iot_events_ts"],
                timeseries={
                    "timeField": "timestamp",
                    "metaField": "metadata",
                    "granularity": "minutes"
                },
                expireAfterSeconds=60 * 60 * 24 * 90  # 90 days retention
            )
            print(f"  - {COLLECTIONS['iot_events_ts']}: TimeSeries collection created")
        except CollectionInvalid:
            print(f"  - {COLLECTIONS['iot_events_ts']}: already exists")

        # TimeSeries indexes
        iot_events_ts = self.db[COLLECTIONS["iot_events_ts"]]
        try:
            iot_events_ts.create_index([("location", GEOSPHERE)])
            iot_events_ts.create_index("EventType")
            iot_events_ts.create_index("EventLocation")
            print(f"  - {COLLECTIONS['iot_events_ts']}: indexes created")
        except Exception as e:
            print(f"  - {COLLECTIONS['iot_events_ts']}: index warning: {e}")

        # 4. Gate events collection (geofence crossings)
        gate_events = self.db[COLLECTIONS["gate_events"]]
        gate_events.create_index([("location", GEOSPHERE)])
        gate_events.create_index("TrackerID")
        gate_events.create_index("assetname")
        gate_events.create_index("EventTime")
        gate_events.create_index("EventType")
        gate_events.create_index("geofence_name")
        print(f"  - {COLLECTIONS['gate_events']}: indexes created")

        # 5. Containers metadata collection
        containers = self.db[COLLECTIONS["containers"]]
        containers.create_index("container_id", unique=True)
        containers.create_index("tracker_id")
        containers.create_index("state")
        print(f"  - {COLLECTIONS['containers']}: indexes created")

        # 6. Vessels collection
        vessels = self.db[COLLECTIONS["vessels"]]
        vessels.create_index("imo_number", unique=True)
        vessels.create_index("name")
        print(f"  - {COLLECTIONS['vessels']}: indexes created")

        print("\nAll collections and indexes set up successfully!")

    def write_event(self, event: IoTEvent):
        """
        Write a single event to both regular and TimeSeries collections.
        """
        if self.db is None:
            raise RuntimeError("Database not connected.")

        # Write to regular collection
        self.db[COLLECTIONS["iot_events"]].insert_one(event.to_dict())

        # Write to TimeSeries collection
        self.db[COLLECTIONS["iot_events_ts"]].insert_one(event.to_timeseries_dict())

    def write_events(self, events: List[IoTEvent]):
        """
        Write multiple events to both collections.
        """
        if self.db is None or len(events) == 0:
            return

        # Write to regular collection
        regular_docs = [e.to_dict() for e in events]
        self.db[COLLECTIONS["iot_events"]].insert_many(regular_docs)

        # Write to TimeSeries collection
        ts_docs = [e.to_timeseries_dict() for e in events]
        self.db[COLLECTIONS["iot_events_ts"]].insert_many(ts_docs)

    def write_gate_event(self, event: IoTEvent, geofence: dict):
        """
        Write a gate event (geofence crossing) to the gate_events collection.
        """
        if self.db is None:
            raise RuntimeError("Database not connected.")

        doc = event.to_dict()
        doc["geofence_name"] = geofence["properties"]["name"]
        doc["geofence_type"] = geofence["properties"]["typeId"]
        doc["geofence_id"] = geofence["_id"]

        self.db[COLLECTIONS["gate_events"]].insert_one(doc)

    def update_container(self, container):
        """
        Update or insert container metadata.
        """
        if self.db is None:
            raise RuntimeError("Database not connected.")

        self.db[COLLECTIONS["containers"]].update_one(
            {"container_id": container.metadata.container_id},
            {"$set": container.to_dict()},
            upsert=True
        )

    def update_containers_batch(self, containers: list):
        """
        Batch update or insert multiple containers using bulk_write for performance.
        """
        if self.db is None:
            raise RuntimeError("Database not connected.")

        if not containers:
            return

        from pymongo import UpdateOne

        operations = [
            UpdateOne(
                {"container_id": c.metadata.container_id},
                {"$set": c.to_dict()},
                upsert=True
            )
            for c in containers
        ]

        self.db[COLLECTIONS["containers"]].bulk_write(operations, ordered=False)

    def update_vessel(self, vessel):
        """
        Update or insert vessel information.
        """
        if self.db is None:
            raise RuntimeError("Database not connected.")

        self.db[COLLECTIONS["vessels"]].update_one(
            {"imo_number": vessel.imo_number},
            {"$set": vessel.to_dict()},
            upsert=True
        )

    def get_stats(self) -> dict:
        """Get collection statistics."""
        if self.db is None:
            return {}

        stats = {}
        for name, collection_name in COLLECTIONS.items():
            try:
                count = self.db[collection_name].count_documents({})
                stats[name] = count
            except Exception:
                stats[name] = 0

        return stats

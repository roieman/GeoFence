#!/usr/bin/env python3
"""
Monitor containers collection for new insertions and create alerts
when a container's location is within any location's polygon.
"""

import pymongo
import os
from dotenv import load_dotenv
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Load environment variables
load_dotenv()


def check_container_in_location(
    container_location: Dict[str, Any],
    locations_collection: pymongo.collection.Collection
) -> Optional[Dict[str, Any]]:
    """
    Check if a container's location is within any location's polygon.
    
    Args:
        container_location: The container's location GeoJSON object
        locations_collection: MongoDB collection for locations
    
    Returns:
        The matching location document if found, None otherwise
    """
    # Use $geoIntersects to find locations whose polygon contains the container point
    query = {
        "location": {
            "$geoIntersects": {
                "$geometry": container_location
            }
        },
        "location.type": "Polygon"  # Only check against polygons
    }
    
    matching_location = locations_collection.find_one(query)
    return matching_location


def create_alert(
    container_doc: Dict[str, Any],
    location_doc: Dict[str, Any],
    alerts_collection: pymongo.collection.Collection
) -> str:
    """
    Create an alert document when a container is within a location.
    
    Args:
        container_doc: The container document
        location_doc: The location document that contains the container
        alerts_collection: MongoDB collection for alerts
    
    Returns:
        The ID of the created alert document
    """
    alert = {
        "alert_type": "container_in_location",
        "timestamp": datetime.utcnow(),
        "container": {
            "container_id": container_doc.get("metadata", {}).get("container_id"),
            "shipping_line": container_doc.get("metadata", {}).get("shipping_line"),
            "container_type": container_doc.get("metadata", {}).get("container_type"),
            "refrigerated": container_doc.get("metadata", {}).get("refrigerated"),
            "cargo_type": container_doc.get("metadata", {}).get("cargo_type"),
            "location": container_doc.get("location"),
            "status": container_doc.get("status"),
            "weight_kg": container_doc.get("weight_kg"),
            "temperature_celsius": container_doc.get("temperature_celsius")
        },
        "location": {
            "name": location_doc.get("name"),
            "type": location_doc.get("type"),
            "city": location_doc.get("city"),
            "country": location_doc.get("country"),
            "location": location_doc.get("location")
        },
        "severity": "info",  # Can be: info, warning, critical
        "acknowledged": False,
        "created_at": datetime.utcnow()
    }
    
    result = alerts_collection.insert_one(alert)
    return result.inserted_id


def process_new_container(
    container_doc: Dict[str, Any],
    locations_collection: pymongo.collection.Collection,
    alerts_collection: pymongo.collection.Collection
) -> Optional[str]:
    """
    Process a new container document and create alert if needed.
    
    Args:
        container_doc: The new container document
        locations_collection: MongoDB collection for locations
        alerts_collection: MongoDB collection for alerts
    
    Returns:
        Alert ID if alert was created, None otherwise
    """
    container_location = container_doc.get("location")
    
    if not container_location:
        print("Warning: Container document has no location field")
        return None
    
    # Check if container is within any location polygon
    matching_location = check_container_in_location(
        container_location,
        locations_collection
    )
    
    if matching_location:
        # Create alert
        alert_id = create_alert(container_doc, matching_location, alerts_collection)
        print(f"✓ Alert created: Container {container_doc.get('metadata', {}).get('container_id')} "
              f"is within {matching_location.get('name')} (Alert ID: {alert_id})")
        return alert_id
    else:
        print(f"  No alert: Container {container_doc.get('metadata', {}).get('container_id')} "
              f"not within any location polygon")
        return None


def monitor_containers(
    connection_string: str = None,
    database_name: str = "geofence",
    containers_collection: str = "containers_regular",  # Changed default to containers_regular
    locations_collection: str = "locations",
    alerts_collection: str = "alerts"
):
    """
    Monitor containers collection using Change Streams and create alerts.
    """
    # Get connection string from environment or parameter
    if not connection_string:
        connection_string = os.getenv("MONGODB_URI")
    
    if not connection_string:
        print("Error: MongoDB connection string not found.")
        print("Please set MONGODB_URI environment variable or pass connection string as argument.")
        sys.exit(1)
    
    client = pymongo.MongoClient(connection_string)
    db = client[database_name]
    containers = db[containers_collection]
    locations = db[locations_collection]
    alerts = db[alerts_collection]
    
    # Ensure alerts collection has indexes
    alerts.create_index("timestamp")
    alerts.create_index("container.container_id")
    alerts.create_index("location.name")
    alerts.create_index("acknowledged")
    alerts.create_index([("container.location", "2dsphere")])
    
    print("=" * 60)
    print("Container Location Monitor")
    print("=" * 60)
    print(f"Database: {database_name}")
    print(f"Monitoring: {containers_collection}")
    print(f"Checking against: {locations_collection}")
    print(f"Creating alerts in: {alerts_collection}")
    print("=" * 60)
    print("\nMonitoring for new container insertions...")
    print("Press Ctrl+C to stop\n")
    
    try:
        # Create change stream to monitor insertions
        with containers.watch([{"$match": {"operationType": "insert"}}]) as stream:
            for change in stream:
                if change["operationType"] == "insert":
                    container_doc = change["fullDocument"]
                    process_new_container(container_doc, locations, alerts)
    
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
    except Exception as e:
        print(f"\nError: {e}")
        raise
    finally:
        client.close()


def check_existing_container(
    container_id: str,
    connection_string: str = None,
    database_name: str = "geofence",
    containers_collection: str = "containers_regular",  # Changed default to containers_regular
    locations_collection: str = "locations",
    alerts_collection: str = "alerts"
):
    """
    Check a specific existing container and create alert if needed.
    Useful for testing or processing existing containers.
    """
    if not connection_string:
        connection_string = os.getenv("MONGODB_URI")
    
    if not connection_string:
        print("Error: MongoDB connection string not found.")
        sys.exit(1)
    
    client = pymongo.MongoClient(connection_string)
    db = client[database_name]
    containers = db[containers_collection]
    locations = db[locations_collection]
    alerts = db[alerts_collection]
    
    # Find container by ID (checking metadata.container_id)
    container = containers.find_one({"metadata.container_id": container_id})
    
    if not container:
        print(f"Error: Container {container_id} not found.")
        client.close()
        return
    
    print(f"Checking container: {container_id}")
    alert_id = process_new_container(container, locations, alerts)
    
    if alert_id:
        print(f"\n✓ Alert created with ID: {alert_id}")
    else:
        print("\n  No alert needed - container not within any location polygon")
    
    client.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Monitor containers and create alerts when within location polygons"
    )
    parser.add_argument(
        "--check",
        type=str,
        help="Check a specific container ID instead of monitoring"
    )
    parser.add_argument(
        "--connection-string",
        type=str,
        help="MongoDB connection string (or use MONGODB_URI env var)"
    )
    parser.add_argument(
        "--database",
        type=str,
        default="geofence",
        help="Database name (default: geofence)"
    )
    parser.add_argument(
        "--containers-collection",
        type=str,
        default="containers_regular",
        help="Containers collection name (default: containers_regular)"
    )
    parser.add_argument(
        "--locations-collection",
        type=str,
        default="locations",
        help="Locations collection name (default: locations)"
    )
    parser.add_argument(
        "--alerts-collection",
        type=str,
        default="alerts",
        help="Alerts collection name (default: alerts)"
    )
    
    args = parser.parse_args()
    
    if args.check:
        # Check a specific container
        check_existing_container(
            args.check,
            args.connection_string,
            args.database,
            args.containers_collection,
            args.locations_collection,
            args.alerts_collection
        )
    else:
        # Start monitoring
        monitor_containers(
            args.connection_string,
            args.database,
            args.containers_collection,
            args.locations_collection,
            args.alerts_collection
        )


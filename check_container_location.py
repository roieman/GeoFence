#!/usr/bin/env python3
"""
Helper function to check if a container is within a location polygon.
Can be used after inserting a container document.
"""

import pymongo
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional
from datetime import datetime


def check_and_create_alert(
    container_doc: Dict[str, Any],
    connection_string: str = None,
    database_name: str = "geofence",
    locations_collection: str = "locations",
    alerts_collection: str = "alerts"
) -> Optional[str]:
    """
    Check if a container is within any location polygon and create alert if so.
    
    This function can be called after inserting a container document.
    
    Args:
        container_doc: The container document that was just inserted
        connection_string: MongoDB connection string (or use MONGODB_URI env var)
        database_name: Database name
        locations_collection: Locations collection name
        alerts_collection: Alerts collection name
    
    Returns:
        Alert document ID if alert was created, None otherwise
    
    Example:
        # After inserting a container
        result = containers.insert_one(new_container)
        container_doc = containers.find_one({"_id": result.inserted_id})
        
        # Check and create alert
        alert_id = check_and_create_alert(container_doc)
        if alert_id:
            print(f"Alert created: {alert_id}")
    """
    # Load environment variables
    load_dotenv()
    
    # Get connection string
    if not connection_string:
        connection_string = os.getenv("MONGODB_URI")
    
    if not connection_string:
        raise ValueError("MongoDB connection string not found. Set MONGODB_URI or pass connection_string.")
    
    client = pymongo.MongoClient(connection_string)
    db = client[database_name]
    locations = db[locations_collection]
    alerts = db[alerts_collection]
    
    try:
        container_location = container_doc.get("location")
        
        if not container_location:
            return None
        
        # Check if container point is within any location polygon
        # Use $geoIntersects to find locations whose polygon contains the container point
        query = {
            "location": {
                "$geoIntersects": {
                    "$geometry": container_location
                }
            },
            "location.type": "Polygon"
        }
        
        matching_location = locations.find_one(query)
        
        if matching_location:
            # Create alert document
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
                    "temperature_celsius": container_doc.get("temperature_celsius"),
                    "timestamp": container_doc.get("timestamp")
                },
                "location": {
                    "name": matching_location.get("name"),
                    "type": matching_location.get("type"),
                    "city": matching_location.get("city"),
                    "country": matching_location.get("country"),
                    "location": matching_location.get("location")
                },
                "severity": "info",
                "acknowledged": False,
                "created_at": datetime.utcnow()
            }
            
            result = alerts.insert_one(alert)
            return str(result.inserted_id)
        
        return None
    
    finally:
        client.close()


# Example usage function
def example_usage():
    """Example of how to use this function after inserting a container."""
    load_dotenv()
    connection_string = os.getenv("MONGODB_URI")
    
    client = pymongo.MongoClient(connection_string)
    db = client["geofence"]
    containers = db["containers"]
    
    # Example: Insert a new container
    new_container = {
        "metadata": {
            "container_id": "TEST1234567",
            "shipping_line": "Maersk",
            "container_type": "standard",
            "refrigerated": False,
            "cargo_type": "electronics"
        },
        "timestamp": datetime.utcnow(),
        "location": {
            "type": "Point",
            "coordinates": [121.4737, 31.2304]  # Near Port of Shanghai
        },
        "status": "in_transit",
        "weight_kg": 15000
    }
    
    # Insert container
    result = containers.insert_one(new_container)
    print(f"Container inserted with ID: {result.inserted_id}")
    
    # Get the full document
    container_doc = containers.find_one({"_id": result.inserted_id})
    
    # Check and create alert
    alert_id = check_and_create_alert(container_doc)
    
    if alert_id:
        print(f"✓ Alert created: {alert_id}")
    else:
        print("  No alert - container not within any location polygon")
    
    client.close()


if __name__ == "__main__":
    example_usage()


#!/usr/bin/env python3
"""
Simple alert generator: picks 5 containers and 5 locations,
places each container inside a location, and sends 1 document every 10 seconds.
Stops after 5 documents.
"""

import os
import sys
import time
from pymongo import MongoClient
from datetime import datetime
import random
from dotenv import load_dotenv

load_dotenv()

# Check for DEBUG mode
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

if DEBUG_MODE:
    connection_string = "mongodb://localhost:27017/"
    print("🔧 DEBUG MODE: Using localhost MongoDB")
else:
    connection_string = os.getenv("MONGODB_URI")
    if not connection_string:
        print("❌ ERROR: MONGODB_URI not set. Set DEBUG=true for localhost or provide MONGODB_URI")
        sys.exit(1)
    if sys.stdin.isatty():
        print("⚠️  WARNING: Not in DEBUG mode. Make sure you want to use this connection!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            sys.exit(0)

print(f"Connecting to: {connection_string}")
sys.stdout.flush()

try:
    client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✓ Connection test successful")
    sys.stdout.flush()
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    sys.exit(1)

db = client["geofence"]
containers_collection = db["containers_regular"]
locations_collection = db["locations"]
alerts_collection = db["alerts"]

print(f"✓ Using database: {db.name}")

# Ensure indexes exist
try:
    containers_collection.create_index([("location", "2dsphere")])
    containers_collection.create_index([("metadata.container_id", 1)])
    containers_collection.create_index([("timestamp", 1)])
    alerts_collection.create_index([("timestamp", 1)])
    alerts_collection.create_index([("acknowledged", 1)])
    print("✓ Indexes verified/created")
except Exception as e:
    print(f"⚠️  Index creation: {e}")

def get_point_inside_location(location_geo):
    """
    Get a point that is guaranteed to be inside the location geometry.
    For Point: returns the center coordinates.
    For Polygon: returns the centroid of the polygon.
    """
    geo_type = location_geo.get("type")
    
    if geo_type == "Point":
        # For Point locations, use the center
        coords = location_geo.get("coordinates", [])
        if len(coords) >= 2:
            return [coords[0], coords[1]]  # [lon, lat]
        return None
    
    elif geo_type == "Polygon":
        # For Polygon, calculate the centroid
        coordinates = location_geo.get("coordinates", [])
        if not coordinates or not coordinates[0]:
            return None
        
        # Get the outer ring (first array in coordinates)
        ring = coordinates[0]
        
        # Calculate centroid (average of all points)
        total_lon = 0
        total_lat = 0
        count = 0
        
        for point in ring:
            if len(point) >= 2:
                total_lon += point[0]
                total_lat += point[1]
                count += 1
        
        if count > 0:
            return [total_lon / count, total_lat / count]
    
    return None

def pick_containers_and_locations():
    """Pick 5 random containers and 5 random locations."""
    print("\n📦 Picking 5 containers from containers_regular...")
    
    # Get 5 random containers
    containers = list(containers_collection.aggregate([
        {"$sample": {"size": 5}}
    ]))
    
    if len(containers) < 5:
        print(f"⚠️  WARNING: Only found {len(containers)} containers in database")
        print("   Need at least 5 containers. Run seed_local_data.py first.")
        return None, None
    
    print(f"✓ Selected {len(containers)} containers:")
    for i, container in enumerate(containers, 1):
        container_id = container.get("metadata", {}).get("container_id", "Unknown")
        print(f"   {i}. {container_id}")
    
    print("\n📍 Picking 5 locations...")
    
    # Get 5 random locations
    locations = list(locations_collection.aggregate([
        {"$sample": {"size": 5}}
    ]))
    
    if len(locations) < 5:
        print(f"⚠️  WARNING: Only found {len(locations)} locations in database")
        print("   Need at least 5 locations. Run seed_local_data.py first.")
        return None, None
    
    print(f"✓ Selected {len(locations)} locations:")
    for i, location in enumerate(locations, 1):
        name = location.get("name", "Unknown")
        geo_type = location.get("location", {}).get("type", "Unknown")
        print(f"   {i}. {name} ({geo_type})")
    
    return containers, locations

def create_container_document(container, location):
    """Create a new container document based on existing container, placed inside location."""
    # Get point inside location
    location_geo = location.get("location", {})
    point_coords = get_point_inside_location(location_geo)
    
    if not point_coords:
        print(f"⚠️  WARNING: Could not get point inside location {location.get('name')}")
        return None
    
    # Copy container metadata
    metadata = container.get("metadata", {}).copy()
    
    # Create new document with current timestamp and location coordinates
    new_doc = {
        "metadata": metadata,
        "timestamp": datetime.utcnow(),
        "location": {
            "type": "Point",
            "coordinates": point_coords  # [lon, lat]
        },
        "weight_kg": container.get("weight_kg", 15000),
        "temperature_celsius": container.get("temperature_celsius"),
        "speed_knots": container.get("speed_knots", 0),
        "status": container.get("status", "in_transit")
    }
    
    return new_doc

def create_alert(container_doc, location):
    """Create an alert document for a container hitting a location."""
    alert_doc = {
        "timestamp": datetime.utcnow(),
        "container": {
            "container_id": container_doc["metadata"]["container_id"],
            "shipping_line": container_doc["metadata"].get("shipping_line", "Unknown"),
            "container_type": container_doc["metadata"].get("container_type", "Unknown"),
            "cargo_type": container_doc["metadata"].get("cargo_type", "Unknown"),
            "refrigerated": container_doc["metadata"].get("refrigerated", False)
        },
        "location": {
            "name": location.get("name", "Unknown"),
            "type": location.get("type", "Unknown"),
            "city": location.get("city", "N/A"),
            "country": location.get("country", "N/A"),
            "location_id": str(location.get("_id", ""))
        },
        "container_location": container_doc["location"],
        "acknowledged": False,
        "alert_type": "location_hit",
        "message": f"Container {container_doc['metadata']['container_id']} detected at {location.get('name', 'Unknown Location')}"
    }
    
    return alert_doc

def main():
    # Setup logging
    log_file_path = "/tmp/alert_generation.log"
    log_file = open(log_file_path, "a", buffering=1)
    
    def log_print(*args, **kwargs):
        """Print to both stdout and log file"""
        message = ' '.join(str(arg) for arg in args)
        print(message, **kwargs)
        log_file.write(message + '\n')
        log_file.flush()
        sys.stdout.flush()
    
    log_print("=" * 60)
    log_print("Simple Alert Generator")
    log_print("=" * 60)
    log_print("Strategy: Pick 5 containers and 5 locations")
    log_print("         Place each container inside a location")
    log_print("         Send 1 document every 10 seconds")
    log_print("         Stop after 5 documents")
    log_print("=" * 60)
    log_print()
    
    # Pick containers and locations
    containers, locations = pick_containers_and_locations()
    
    if not containers or not locations:
        log_print("❌ ERROR: Failed to pick containers or locations")
        log_file.close()
        return
    
    log_print()
    log_print("🚀 Starting generation...")
    log_print()
    
    # Generate 5 documents, one every 10 seconds
    for i in range(5):
        container = containers[i]
        location = locations[i]
        
        container_id = container.get("metadata", {}).get("container_id", "Unknown")
        location_name = location.get("name", "Unknown")
        
        log_print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Generating document {i+1}/5...")
        log_print(f"   Container: {container_id}")
        log_print(f"   Location: {location_name}")
        
        # Create container document
        container_doc = create_container_document(container, location)
        
        if not container_doc:
            log_print(f"   ❌ ERROR: Failed to create container document")
            continue
        
        # Insert container
        try:
            result = containers_collection.insert_one(container_doc)
            log_print(f"   ✓ Container inserted (ID: {result.inserted_id})")
        except Exception as e:
            log_print(f"   ❌ ERROR inserting container: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # Create alert
        try:
            alert_doc = create_alert(container_doc, location)
            alert_result = alerts_collection.insert_one(alert_doc)
            log_print(f"   ⚠️  ALERT created (ID: {alert_result.inserted_id})")
        except Exception as e:
            log_print(f"   ❌ ERROR creating alert: {e}")
            import traceback
            traceback.print_exc()
        
        # Wait 10 seconds before next document (except for the last one)
        if i < 4:  # Don't wait after the 5th document
            log_print(f"   ⏳ Waiting 10 seconds before next document...")
            log_print()
            time.sleep(10)
    
    log_print()
    log_print("=" * 60)
    log_print("✓ Generation complete! 5 documents sent.")
    log_print("=" * 60)
    log_file.close()

if __name__ == "__main__":
    main()

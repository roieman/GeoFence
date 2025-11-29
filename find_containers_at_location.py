#!/usr/bin/env python3
"""
Script to find all containers that passed through a specific location using aggregation pipeline.
Example: Find all containers that passed through Port of Shanghai.
"""

import pymongo
import os
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()


def find_containers_at_location(
    location_name: str,
    radius_meters: float = 5000,  # 5km default radius
    connection_string: str = None,
    database_name: str = "geofence",
    locations_collection: str = "locations",
    containers_collection: str = "containers"
):
    """
    Find all containers that passed through a specific location.
    
    Args:
        location_name: Name of the location (e.g., "Port of Shanghai")
        radius_meters: Radius in meters to consider "passing through"
        connection_string: MongoDB connection string
        database_name: Database name
        locations_collection: Locations collection name
        containers_collection: Containers collection name
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
    locations = db[locations_collection]
    containers = db[containers_collection]
    
    print(f"Finding containers that passed through: {location_name}")
    print(f"Search radius: {radius_meters:,} meters ({radius_meters/1000:.1f} km)\n")
    
    # Step 1: Find the location coordinates
    location = locations.find_one({"name": location_name})
    
    if not location:
        print(f"Error: Location '{location_name}' not found.")
        print("\nAvailable locations:")
        sample_locations = locations.find({}, {"name": 1, "type": 1}).limit(10)
        for loc in sample_locations:
            print(f"  - {loc.get('name')} ({loc.get('type')})")
        client.close()
        sys.exit(1)
    
    # Extract coordinates from location
    location_geo = location.get("location", {})
    
    if location_geo.get("type") == "Point":
        coordinates = location_geo.get("coordinates")
        center_lon, center_lat = coordinates[0], coordinates[1]
    elif location_geo.get("type") == "Polygon":
        # For polygons, use the first coordinate as center (or calculate centroid)
        # For simplicity, we'll use the first coordinate
        coords = location_geo.get("coordinates", [[[]]])[0]
        if coords:
            center_lon, center_lat = coords[0][0], coords[0][1]
        else:
            print("Error: Could not extract coordinates from polygon.")
            client.close()
            sys.exit(1)
    else:
        print(f"Error: Unsupported location type: {location_geo.get('type')}")
        client.close()
        sys.exit(1)
    
    print(f"Location found: {location_name}")
    print(f"Coordinates: [{center_lon}, {center_lat}]")
    print(f"Type: {location.get('type')}")
    if location.get('city'):
        print(f"City: {location.get('city')}")
    if location.get('country'):
        print(f"Country: {location.get('country')}")
    print()
    
    # Step 2: Build aggregation pipeline to find containers near this location
    pipeline = [
        # Stage 1: Use $geoNear to find containers within radius
        # Note: $geoNear must be the first stage in the pipeline
        # For TimeSeries collections, we must specify the 'key' option
        {
            "$geoNear": {
                "near": {
                    "type": "Point",
                    "coordinates": [center_lon, center_lat]
                },
                "distanceField": "distance",  # Distance in meters
                "maxDistance": radius_meters,
                "spherical": True,
                "key": "location",  # Required for TimeSeries collections
                "query": {}  # Can add additional filters here
            }
        },
        # Stage 2: Group by container ID to get unique containers
        {
            "$group": {
                "_id": "$metadata.container_id",
                "container_id": {"$first": "$metadata.container_id"},
                "shipping_line": {"$first": "$metadata.shipping_line"},
                "container_type": {"$first": "$metadata.container_type"},
                "refrigerated": {"$first": "$metadata.refrigerated"},
                "cargo_type": {"$first": "$metadata.cargo_type"},
                "first_seen": {"$min": "$timestamp"},
                "last_seen": {"$max": "$timestamp"},
                "min_distance": {"$min": "$distance"},
                "readings_count": {"$sum": 1}
            }
        },
        # Stage 3: Sort by first seen time
        {
            "$sort": {"first_seen": 1}
        },
        # Stage 4: Add computed fields
        {
            "$addFields": {
                "time_at_location": {
                    "$subtract": ["$last_seen", "$first_seen"]
                }
            }
        }
    ]
    
    print("Running aggregation pipeline...")
    print("=" * 60)
    
    # Execute pipeline
    results = list(containers.aggregate(pipeline))
    
    print(f"\nFound {len(results):,} unique containers that passed through {location_name}")
    print("=" * 60)
    
    if results:
        # Show summary statistics
        total_readings = sum(r.get("readings_count", 0) for r in results)
        avg_readings = total_readings / len(results) if results else 0
        
        print(f"\nSummary:")
        print(f"  Total unique containers: {len(results):,}")
        print(f"  Total readings: {total_readings:,}")
        print(f"  Average readings per container: {avg_readings:.1f}")
        
        # Show first 10 results
        print(f"\nFirst 10 containers:")
        print("-" * 60)
        for i, container in enumerate(results[:10], 1):
            print(f"\n{i}. Container ID: {container.get('container_id')}")
            print(f"   Shipping Line: {container.get('shipping_line')}")
            print(f"   Type: {container.get('container_type')} ({'Refrigerated' if container.get('refrigerated') else 'Standard'})")
            print(f"   Cargo: {container.get('cargo_type')}")
            print(f"   First seen: {container.get('first_seen')}")
            print(f"   Last seen: {container.get('last_seen')}")
            print(f"   Closest distance: {container.get('min_distance', 0):.0f} meters")
            print(f"   Readings at location: {container.get('readings_count')}")
        
        if len(results) > 10:
            print(f"\n... and {len(results) - 10:,} more containers")
    
    client.close()
    return results


def find_containers_at_location_alternative(
    location_name: str,
    radius_meters: float = 5000,
    connection_string: str = None,
    database_name: str = "geofence",
    locations_collection: str = "locations",
    containers_collection: str = "containers"
):
    """
    Alternative approach using $lookup to join with locations collection.
    This is useful if you want to find containers near multiple locations.
    """
    if not connection_string:
        connection_string = os.getenv("MONGODB_URI")
    
    if not connection_string:
        print("Error: MongoDB connection string not found.")
        sys.exit(1)
    
    client = pymongo.MongoClient(connection_string)
    db = client[database_name]
    locations = db[locations_collection]
    containers = db[containers_collection]
    
    # Get location
    location = locations.find_one({"name": location_name})
    if not location:
        print(f"Error: Location '{location_name}' not found.")
        client.close()
        sys.exit(1)
    
    location_geo = location.get("location", {})
    if location_geo.get("type") == "Point":
        coordinates = location_geo.get("coordinates")
        center_lon, center_lat = coordinates[0], coordinates[1]
    else:
        coords = location_geo.get("coordinates", [[[]]])[0]
        center_lon, center_lat = coords[0][0], coords[0][1]
    
    # Alternative pipeline using $match with $near
    pipeline = [
        {
            "$match": {
                "location": {
                    "$near": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [center_lon, center_lat]
                        },
                        "$maxDistance": radius_meters
                    }
                }
            }
        },
        {
            "$group": {
                "_id": "$metadata.container_id",
                "container_id": {"$first": "$metadata.container_id"},
                "shipping_line": {"$first": "$metadata.shipping_line"},
                "first_seen": {"$min": "$timestamp"},
                "last_seen": {"$max": "$timestamp"},
                "readings_count": {"$sum": 1}
            }
        },
        {
            "$sort": {"first_seen": 1}
        }
    ]
    
    results = list(containers.aggregate(pipeline))
    client.close()
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python find_containers_at_location.py <location_name> [radius_meters]")
        print("\nExample:")
        print("  python find_containers_at_location.py 'Port of Shanghai' 5000")
        print("  python find_containers_at_location.py 'Port of Shanghai' 10000")
        sys.exit(1)
    
    location_name = sys.argv[1]
    radius_meters = float(sys.argv[2]) if len(sys.argv) > 2 else 5000
    
    find_containers_at_location(location_name, radius_meters)


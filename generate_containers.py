#!/usr/bin/env python3
"""
Script to generate container time-series data.
Creates a MongoDB TimeSeries collection with periodic readings every 15 minutes.
"""

import pymongo
import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any
import uuid

# Container types and their characteristics
CONTAINER_TYPES = [
    {"type": "standard", "refrigerated": False, "size": "20ft", "max_weight_kg": 28000},
    {"type": "standard", "refrigerated": False, "size": "40ft", "max_weight_kg": 30480},
    {"type": "standard", "refrigerated": False, "size": "40ft_high_cube", "max_weight_kg": 30480},
    {"type": "refrigerated", "refrigerated": True, "size": "20ft", "max_weight_kg": 28000},
    {"type": "refrigerated", "refrigerated": True, "size": "40ft", "max_weight_kg": 30480},
    {"type": "tank", "refrigerated": False, "size": "20ft", "max_weight_kg": 28000},
    {"type": "open_top", "refrigerated": False, "size": "40ft", "max_weight_kg": 30480},
    {"type": "flat_rack", "refrigerated": False, "size": "40ft", "max_weight_kg": 30480},
]

# Shipping lines
SHIPPING_LINES = [
    "Maersk", "MSC", "CMA CGM", "COSCO", "Evergreen", "Hapag-Lloyd",
    "ONE", "Yang Ming", "HMM", "ZIM", "PIL", "Wan Hai", "OOCL", "Hyundai"
]

# Common cargo types
CARGO_TYPES = [
    "electronics", "textiles", "automotive", "machinery", "food", "chemicals",
    "furniture", "toys", "pharmaceuticals", "steel", "lumber", "agricultural"
]

# Major shipping routes (start and end coordinates)
SHIPPING_ROUTES = [
    {"origin": {"lat": 31.2304, "lon": 121.4737}, "destination": {"lat": 33.7420, "lon": -118.2642}, "name": "Shanghai-Los Angeles"},
    {"origin": {"lat": 1.2897, "lon": 103.8501}, "destination": {"lat": 51.9225, "lon": 4.4772}, "name": "Singapore-Rotterdam"},
    {"origin": {"lat": 35.1796, "lon": 129.0756}, "destination": {"lat": 40.6892, "lon": -74.0445}, "name": "Busan-New York"},
    {"origin": {"lat": 22.3193, "lon": 114.1694}, "destination": {"lat": 51.9225, "lon": 4.4772}, "name": "Hong Kong-Rotterdam"},
    {"origin": {"lat": 35.6762, "lon": 139.6503}, "destination": {"lat": 33.7420, "lon": -118.2642}, "name": "Tokyo-Los Angeles"},
]


def generate_container_id() -> str:
    """Generate a realistic container ID (format: ABCD1234567)."""
    letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
    numbers = ''.join(random.choices('0123456789', k=7))
    return f"{letters}{numbers}"


def interpolate_position(origin: Dict, destination: Dict, progress: float) -> Dict[str, float]:
    """Interpolate position between origin and destination based on progress (0.0 to 1.0)."""
    lat = origin["lat"] + (destination["lat"] - origin["lat"]) * progress
    lon = origin["lon"] + (destination["lon"] - origin["lon"]) * progress
    return {"lat": lat, "lon": lon}


def generate_container_metadata() -> Dict[str, Any]:
    """Generate metadata for a container."""
    container_type = random.choice(CONTAINER_TYPES)
    return {
        "container_id": generate_container_id(),
        "shipping_line": random.choice(SHIPPING_LINES),
        "container_type": container_type["type"],
        "size": container_type["size"],
        "refrigerated": container_type["refrigerated"],
        "cargo_type": random.choice(CARGO_TYPES),
        "weight_kg": random.randint(5000, int(container_type["max_weight_kg"] * 0.9)),
        "temperature_celsius": random.uniform(-25, 25) if container_type["refrigerated"] else None,
    }


def generate_timeseries_readings(
    container_metadata: Dict[str, Any],
    start_time: datetime,
    end_time: datetime,
    route: Dict[str, Any],
    num_readings: int = None
) -> List[Dict[str, Any]]:
    """Generate time-series readings for a container."""
    if num_readings is None:
        # Calculate number of readings (every 15 minutes)
        duration = end_time - start_time
        num_readings = int(duration.total_seconds() / (15 * 60))
    
    readings = []
    time_interval = (end_time - start_time) / num_readings
    
    for i in range(num_readings):
        timestamp = start_time + (time_interval * i)
        progress = i / num_readings
        
        # Add some randomness to the route
        noise_lat = random.uniform(-0.5, 0.5)
        noise_lon = random.uniform(-0.5, 0.5)
        
        position = interpolate_position(route["origin"], route["destination"], progress)
        position["lat"] += noise_lat
        position["lon"] += noise_lon
        
        reading = {
            "metadata": {
                "container_id": container_metadata["container_id"],
                "shipping_line": container_metadata["shipping_line"],
                "container_type": container_metadata["container_type"],
                "size": container_metadata["size"],
                "refrigerated": container_metadata["refrigerated"],
                "cargo_type": container_metadata["cargo_type"],
            },
            "timestamp": timestamp,
            "location": {
                "type": "Point",
                "coordinates": [position["lon"], position["lat"]]
            },
            "weight_kg": container_metadata["weight_kg"] + random.randint(-100, 100),
            "temperature_celsius": (
                container_metadata["temperature_celsius"] + random.uniform(-2, 2)
                if container_metadata["refrigerated"] else None
            ),
            "speed_knots": random.uniform(10, 25) if progress > 0.05 and progress < 0.95 else random.uniform(0, 5),
            "status": random.choice(["in_transit", "at_port", "at_terminal", "loading", "unloading"]),
        }
        readings.append(reading)
    
    return readings


def generate_containers(
    connection_string: str,
    database_name: str = "geofence",
    collection_name: str = "containers",
    num_containers: int = 1000000,
    days_of_data: int = 7,
    batch_size: int = 10000
):
    """Generate and insert container time-series data into MongoDB."""
    client = pymongo.MongoClient(connection_string)
    db = client[database_name]
    
    # Drop existing collection if it exists
    if collection_name in db.list_collection_names():
        db[collection_name].drop()
        print(f"✓ Dropped existing collection '{collection_name}'")
    
    # Create TimeSeries collection
    db.create_collection(
        collection_name,
        timeseries={
            "timeField": "timestamp",
            "metaField": "metadata",
            "granularity": "hours"
        }
    )
    
    collection = db[collection_name]
    
    # Create geospatial index on location
    collection.create_index([("location", "2dsphere")])
    collection.create_index("timestamp")
    collection.create_index("metadata.container_id")
    collection.create_index("metadata.shipping_line")
    
    print(f"✓ Created TimeSeries collection '{collection_name}'")
    print(f"  - Time field: timestamp")
    print(f"  - Meta field: metadata")
    print(f"  - Granularity: hours\n")
    
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days_of_data)
    
    print(f"Generating data for {num_containers:,} containers...")
    print(f"Time range: {start_time} to {end_time}")
    print(f"Days of data: {days_of_data}\n")
    
    total_readings = 0
    containers_processed = 0
    
    # Generate containers in batches
    for batch_start in range(0, num_containers, batch_size):
        batch_end = min(batch_start + batch_size, num_containers)
        batch_readings = []
        
        for _ in range(batch_start, batch_end):
            # Generate container metadata
            container_metadata = generate_container_metadata()
            
            # Randomly assign a route
            route = random.choice(SHIPPING_ROUTES)
            
            # Generate time-series readings for this container
            # Each container gets readings over a random period within the time range
            container_start = start_time + timedelta(
                days=random.uniform(0, days_of_data - 1)
            )
            container_duration = timedelta(days=random.uniform(1, min(3, days_of_data)))
            container_end = min(container_start + container_duration, end_time)
            
            readings = generate_timeseries_readings(
                container_metadata,
                container_start,
                container_end,
                route
            )
            
            batch_readings.extend(readings)
            containers_processed += 1
        
        # Insert batch
        if batch_readings:
            collection.insert_many(batch_readings)
            total_readings += len(batch_readings)
            
            progress = (containers_processed / num_containers) * 100
            print(f"Progress: {containers_processed:,}/{num_containers:,} containers ({progress:.1f}%) - {total_readings:,} readings inserted", end='\r')
    
    print()  # New line after progress updates
    
    # Print statistics
    print(f"\n✓ Data generation complete!")
    print(f"  - Containers: {containers_processed:,}")
    print(f"  - Total readings: {total_readings:,}")
    print(f"  - Average readings per container: {total_readings / containers_processed:.1f}")
    
    # Print sample document
    sample = collection.find_one()
    if sample:
        print(f"\nSample document:")
        print(f"  Container ID: {sample['metadata']['container_id']}")
        print(f"  Shipping Line: {sample['metadata']['shipping_line']}")
        print(f"  Type: {sample['metadata']['container_type']}")
        print(f"  Refrigerated: {sample['metadata']['refrigerated']}")
        print(f"  Timestamp: {sample['timestamp']}")
        print(f"  Location: {sample['location']['coordinates']}")
        print(f"  Status: {sample['status']}")
    
    client.close()


if __name__ == "__main__":
    import sys
    import os
    from dotenv import load_dotenv
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get connection string from environment variable or command line
    connection_string = os.getenv("MONGODB_URI") or (sys.argv[1] if len(sys.argv) > 1 else None)
    
    if not connection_string:
        print("Usage: python generate_containers.py [mongodb_connection_string] [options]")
        print("\nConnection string can be provided via:")
        print("  1. MONGODB_URI environment variable (recommended)")
        print("  2. .env file with MONGODB_URI=...")
        print("  3. Command line argument")
        print("\nOptions:")
        print("  [database_name]          Database name (default: geofence)")
        print("  [collection_name]        Collection name (default: containers)")
        print("  [num_containers]          Number of containers (default: 1000000)")
        print("  [days_of_data]           Days of historical data (default: 7)")
        print("\nExample:")
        print("  export MONGODB_URI='mongodb://localhost:27017'")
        print("  python generate_containers.py geofence containers 1000000 7")
        print("\nOr with command line:")
        print("  python generate_containers.py 'mongodb://localhost:27017' geofence containers 1000000 7")
        sys.exit(1)
    
    # Adjust argument positions if connection string was provided via env
    arg_start = 1 if os.getenv("MONGODB_URI") else 2
    database_name = sys.argv[arg_start] if len(sys.argv) > arg_start else "geofence"
    collection_name = sys.argv[arg_start + 1] if len(sys.argv) > arg_start + 1 else "containers"
    num_containers = int(sys.argv[arg_start + 2]) if len(sys.argv) > arg_start + 2 else 1000000
    days_of_data = int(sys.argv[arg_start + 3]) if len(sys.argv) > arg_start + 3 else 7
    
    print(f"Generating container time-series data...")
    print(f"Connection: {connection_string}")
    print(f"Database: {database_name}")
    print(f"Collection: {collection_name}")
    print(f"Containers: {num_containers:,}")
    print(f"Days of data: {days_of_data}\n")
    
    generate_containers(connection_string, database_name, collection_name, num_containers, days_of_data)
    print("\n✓ Container data generation complete!")


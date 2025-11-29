#!/usr/bin/env python3
"""
Quick seed script for localhost MongoDB.
Adds 10 locations and 1000 containers for local development/testing.
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime, timedelta
import random
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

# Check for DEBUG mode
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

if DEBUG_MODE:
    # In DEBUG mode, always use localhost MongoDB (ignore MONGODB_URI from .env)
    connection_string = "mongodb://localhost:27017/"
    print("🔧 DEBUG MODE: Using localhost MongoDB")
    print("   (MONGODB_URI from .env is ignored in DEBUG mode)")
else:
    connection_string = os.getenv("MONGODB_URI")
    if not connection_string:
        print("❌ ERROR: MONGODB_URI not set. Set DEBUG=true for localhost or provide MONGODB_URI")
        sys.exit(1)
    print("⚠️  WARNING: Not in DEBUG mode. Make sure you want to use this connection!")
    response = input("Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        sys.exit(0)

print(f"Connecting to: {connection_string}")
try:
    client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
    # Test connection immediately
    client.admin.command('ping')
    print("✓ Connection test successful")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    print(f"   Connection string: {connection_string}")
    print("\nTroubleshooting:")
    print("   1. Is MongoDB running? Try: mongosh --eval 'db.adminCommand(\"ping\")'")
    print("   2. Is authentication disabled?")
    print("   3. Is the port correct? (default: 27017)")
    sys.exit(1)

db = client["geofence"]
print(f"✓ Using database: {db.name}")

fake = Faker()

# Sample locations data
SAMPLE_LOCATIONS = [
    {"name": "Port of Los Angeles", "city": "Los Angeles", "country": "USA", "type": "port", "coords": [-118.2642, 33.7420]},
    {"name": "Port of Long Beach", "city": "Long Beach", "country": "USA", "type": "port", "coords": [-118.1937, 33.7701]},
    {"name": "Port of New York/New Jersey", "city": "New York", "country": "USA", "type": "port", "coords": [-74.0060, 40.7128]},
    {"name": "Port of Hamburg", "city": "Hamburg", "country": "Germany", "type": "port", "coords": [9.9937, 53.5555]},
    {"name": "Port of Rotterdam", "city": "Rotterdam", "country": "Netherlands", "type": "port", "coords": [4.4777, 51.9225]},
    {"name": "Port of Shanghai", "city": "Shanghai", "country": "China", "type": "port", "coords": [121.4737, 31.2304]},
    {"name": "Port of Singapore", "city": "Singapore", "country": "Singapore", "type": "port", "coords": [103.8198, 1.3521]},
    {"name": "Grand Central Terminal", "city": "New York", "country": "USA", "type": "train_terminal", "coords": [-73.9772, 40.7527]},
    {"name": "Tokyo Station", "city": "Tokyo", "country": "Japan", "type": "train_terminal", "coords": [139.7671, 35.6812]},
    {"name": "London Paddington", "city": "London", "country": "UK", "type": "train_terminal", "coords": [-0.1755, 51.5154]},
]

def create_locations():
    """Create 10 sample locations."""
    locations_collection = db["locations"]
    
    # Check if locations already exist
    existing_count = locations_collection.count_documents({})
    if existing_count > 0:
        print(f"⚠️  Found {existing_count} existing locations. Skipping location creation.")
        print("   (Delete existing locations if you want to recreate them)")
        return existing_count
    
    print("Creating 10 locations...")
    locations = []
    
    for loc_data in SAMPLE_LOCATIONS:
        # Create Point geometry
        location_doc = {
            "name": loc_data["name"],
            "type": loc_data["type"],
            "city": loc_data["city"],
            "country": loc_data["country"],
            "location": {
                "type": "Point",
                "coordinates": loc_data["coords"]
            },
            "created_at": datetime.utcnow()
        }
        
        # Add port-specific fields
        if loc_data["type"] == "port":
            location_doc["capacity"] = random.randint(10000, 50000)
        
        locations.append(location_doc)
    
    result = locations_collection.insert_many(locations)
    print(f"✓ Created {len(result.inserted_ids)} locations")
    
    # Create 2dsphere index
    try:
        locations_collection.create_index([("location", "2dsphere")])
        print("✓ Created 2dsphere index on location field")
    except Exception as e:
        print(f"⚠️  Index creation: {e}")
    
    return len(result.inserted_ids)

def create_containers():
    """Create 1000 sample containers."""
    containers_collection = db["containers_regular"]
    
    # Check if containers already exist
    existing_count = containers_collection.count_documents({})
    if existing_count > 0:
        print(f"⚠️  Found {existing_count} existing containers. Skipping container creation.")
        print("   (Delete existing containers if you want to recreate them)")
        return existing_count
    
    print("Creating 1000 containers...")
    
    shipping_lines = ["Maersk", "MSC", "CMA CGM", "COSCO", "Evergreen", "Hapag-Lloyd", "ONE", "Yang Ming"]
    container_types = ["dry", "refrigerated", "tank", "flat_rack", "open_top"]
    cargo_types = ["electronics", "food", "clothing", "machinery", "chemicals", "automotive", "furniture"]
    statuses = ["in_transit", "at_port", "at_terminal", "delivered", "customs"]
    
    # Get location coordinates for realistic routes
    locations_collection = db["locations"]
    ports = list(locations_collection.find({"type": "port"}))
    if not ports:
        print("⚠️  No ports found. Creating containers with random locations.")
        ports = []
    
    containers = []
    batch_size = 100
    
    # Generate container IDs
    container_ids = []
    for i in range(1000):
        # Format: 4 letters + 7 digits (standard container ID format)
        letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
        digits = ''.join(random.choices('0123456789', k=7))
        container_id = f"{letters}{digits}"
        container_ids.append(container_id)
    
    # Generate readings for each container
    start_time = datetime.utcnow() - timedelta(days=7)
    
    for idx, container_id in enumerate(container_ids):
        if idx % 100 == 0:
            print(f"  Progress: {idx}/1000 containers...")
        
        shipping_line = random.choice(shipping_lines)
        container_type = random.choice(container_types)
        refrigerated = container_type == "refrigerated"
        cargo_type = random.choice(cargo_types) if not refrigerated else "food"
        
        # Generate 3-5 readings per container (simulating movement)
        num_readings = random.randint(3, 5)
        
        # Start from a random port or random location
        if ports:
            start_port = random.choice(ports)
            current_lon, current_lat = start_port["location"]["coordinates"]
        else:
            current_lon = random.uniform(-180, 180)
            current_lat = random.uniform(-90, 90)
        
        for reading_num in range(num_readings):
            # Move container (simulate shipping route)
            if reading_num > 0:
                # Move towards another port or random direction
                if ports and random.random() > 0.3:
                    target_port = random.choice(ports)
                    target_lon, target_lat = target_port["location"]["coordinates"]
                    # Interpolate between current and target
                    progress = reading_num / num_readings
                    current_lon = current_lon + (target_lon - current_lon) * progress
                    current_lat = current_lat + (target_lat - current_lat) * progress
                else:
                    # Random movement
                    current_lon += random.uniform(-5, 5)
                    current_lat += random.uniform(-5, 5)
                    # Keep within bounds
                    current_lon = max(-180, min(180, current_lon))
                    current_lat = max(-90, min(90, current_lat))
            
            timestamp = start_time + timedelta(
                days=random.randint(0, 6),
                hours=random.randint(0, 23),
                minutes=random.choice([0, 15, 30, 45])
            )
            
            container_doc = {
                "metadata": {
                    "container_id": container_id,
                    "shipping_line": shipping_line,
                    "container_type": container_type,
                    "size": random.choice(["20ft", "40ft", "45ft"]),
                    "refrigerated": refrigerated,
                    "cargo_type": cargo_type
                },
                "timestamp": timestamp,
                "location": {
                    "type": "Point",
                    "coordinates": [current_lon, current_lat]
                },
                "weight_kg": random.randint(5000, 30000),
                "temperature_celsius": random.uniform(-20, 5) if refrigerated else None,
                "speed_knots": random.uniform(10, 25) if reading_num < num_readings - 1 else 0,
                "status": random.choice(statuses)
            }
            
            containers.append(container_doc)
            
            # Insert in batches
            if len(containers) >= batch_size:
                containers_collection.insert_many(containers)
                containers = []
    
    # Insert remaining containers
    if containers:
        containers_collection.insert_many(containers)
    
    print(f"✓ Created container readings for 1000 containers")
    
    # Create indexes
    try:
        containers_collection.create_index([("location", "2dsphere")])
        containers_collection.create_index([("metadata.container_id", 1)])
        containers_collection.create_index([("timestamp", 1)])
        containers_collection.create_index([("metadata.shipping_line", 1)])
        print("✓ Created indexes on containers collection")
    except Exception as e:
        print(f"⚠️  Index creation: {e}")
    
    return 1000

def main():
    print("=" * 60)
    print("Seeding Local MongoDB Database")
    print("=" * 60)
    print()
    
    try:
        # Test connection with timeout
        client.admin.command('ping')
        print("✓ Connected to MongoDB")
        
        # Verify database access
        test_db = client["geofence"]
        collections = test_db.list_collection_names()
        print(f"✓ Database 'geofence' accessible")
        print(f"  Existing collections: {collections}")
        print()
        
        # Create locations
        location_count = create_locations()
        print()
        
        # Create containers
        container_count = create_containers()
        print()
        
        # Summary
        print("=" * 60)
        print("Summary:")
        print(f"  Locations: {location_count}")
        print(f"  Containers: {container_count}")
        print("=" * 60)
        print()
        print("✓ Database seeded successfully!")
        print()
        print("You can now:")
        print("  1. Start the backend: cd app/backend && python3 main.py")
        print("  2. Start the frontend: cd app/frontend && npm run dev")
        print("  3. Test the app at http://localhost:3000")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()


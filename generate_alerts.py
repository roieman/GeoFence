#!/usr/bin/env python3
"""
Continuous data generator for containers_regular collection.
Generates 1 container document every 10 seconds.
Every 10th document triggers an alert for a random location.
"""

import os
import sys
import time
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
    # Check if running in non-interactive mode (e.g., from backend API)
    # If stdin is not a TTY, skip the confirmation prompt
    if sys.stdin.isatty():
        print("⚠️  WARNING: Not in DEBUG mode. Make sure you want to use this connection!")
        response = input("Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            sys.exit(0)
    else:
        print("⚠️  Running in non-interactive mode. Using MONGODB_URI from environment.")

print(f"Connecting to: {connection_string}")
import sys
sys.stdout.flush()

try:
    client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
    # Test connection immediately
    client.admin.command('ping')
    print("✓ Connection test successful")
    sys.stdout.flush()
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    print(f"   Connection string: {connection_string}")
    print("\nTroubleshooting:")
    print("   1. Is MongoDB running? Try: mongosh --eval 'db.adminCommand(\"ping\")'")
    print("   2. Is authentication disabled?")
    print("   3. Is the port correct? (default: 27017)")
    sys.stdout.flush()
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

fake = Faker()

# Container data templates
shipping_lines = ["Maersk", "MSC", "CMA CGM", "COSCO", "Evergreen", "Hapag-Lloyd", "ONE", "Yang Ming"]
container_types = ["dry", "refrigerated", "tank", "flat_rack", "open_top"]
cargo_types = ["electronics", "food", "clothing", "machinery", "chemicals", "automotive", "furniture"]
statuses = ["in_transit", "at_port", "at_terminal", "delivered", "customs"]

# Track document count (reset in main function)
document_count = 0

def generate_container_id():
    """Generate a random container ID in standard format (4 letters + 7 digits)."""
    letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=4))
    digits = ''.join(random.choices('0123456789', k=7))
    return f"{letters}{digits}"

# Store 5 fixed locations for alert generation
alert_locations = []

def initialize_alert_locations():
    """Initialize 5 random locations for alert generation at startup."""
    global alert_locations
    try:
        # Use limit to avoid loading all 300k+ locations
        locations = list(locations_collection.find({}).limit(1000))
        if not locations:
            print("⚠️  WARNING: No locations found in database!")
            alert_locations = []
            return
        
        # Pick 5 random locations (or all if less than 5)
        num_locations = min(5, len(locations))
        alert_locations = random.sample(locations, num_locations)
        print(f"✓ Selected {len(alert_locations)} locations for alert generation:")
        for loc in alert_locations:
            print(f"   - {loc.get('name', 'Unknown')} ({loc.get('type', 'Unknown')})")
    except Exception as e:
        print(f"❌ ERROR initializing alert locations: {e}")
        import traceback
        traceback.print_exc()
        alert_locations = []

def initialize_alert_locations_with_log(log_func):
    """Initialize 5 random locations for alert generation at startup (with custom log function)."""
    global alert_locations
    try:
        # Use limit to avoid loading all 300k+ locations
        locations = list(locations_collection.find({}).limit(1000))
        if not locations:
            log_func("⚠️  WARNING: No locations found in database!")
            alert_locations = []
            return
        
        # Pick 5 random locations (or all if less than 5)
        num_locations = min(5, len(locations))
        alert_locations = random.sample(locations, num_locations)
        log_func(f"✓ Selected {len(alert_locations)} locations for alert generation:")
        for loc in alert_locations:
            log_func(f"   - {loc.get('name', 'Unknown')} ({loc.get('type', 'Unknown')})")
    except Exception as e:
        log_func(f"❌ ERROR initializing alert locations: {e}")
        import traceback
        traceback.print_exc()
        alert_locations = []

def get_alert_location():
    """Get a random location from the fixed alert locations."""
    if not alert_locations:
        return None
    return random.choice(alert_locations)

def get_random_location():
    """Get a random location from the database (for container positioning)."""
    locations = list(locations_collection.find({}))
    if not locations:
        return None
    return random.choice(locations)

def generate_container_document():
    """Generate a single container document."""
    container_id = generate_container_id()
    shipping_line = random.choice(shipping_lines)
    container_type = random.choice(container_types)
    refrigerated = container_type == "refrigerated"
    cargo_type = random.choice(cargo_types) if not refrigerated else "food"
    
    # Get a random location for the container's position
    location = get_random_location()
    if location and location.get("location"):
        # Use location coordinates with slight random offset
        coords = location["location"]["coordinates"]
        lon = coords[0] + random.uniform(-0.1, 0.1)
        lat = coords[1] + random.uniform(-0.1, 0.1)
    else:
        # Random coordinates if no locations found
        lon = random.uniform(-180, 180)
        lat = random.uniform(-90, 90)
    
    timestamp = datetime.utcnow()
    
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
            "coordinates": [lon, lat]
        },
        "weight_kg": random.randint(5000, 30000),
        "temperature_celsius": random.uniform(-20, 5) if refrigerated else None,
        "speed_knots": random.uniform(10, 25) if random.random() > 0.3 else 0,
        "status": random.choice(statuses)
    }
    
    return container_doc

def create_alert(container_doc, location):
    """Create an alert document for a container hitting a location."""
    alert_doc = {
        "timestamp": datetime.utcnow(),
        "container": {
            "container_id": container_doc["metadata"]["container_id"],
            "shipping_line": container_doc["metadata"]["shipping_line"],
            "container_type": container_doc["metadata"]["container_type"],
            "cargo_type": container_doc["metadata"]["cargo_type"],
            "refrigerated": container_doc["metadata"]["refrigerated"]
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
    # Run indefinitely (no document limit)
    MAX_DOCUMENTS = float('inf')  # No limit - run until stopped
    CONTAINERS_PER_SECOND = 10  # Generate 10 containers per second
    DELAY_BETWEEN_CONTAINERS = 1.0 / CONTAINERS_PER_SECOND  # 0.1 seconds
    
    # Also write to log file directly for debugging
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
    log_print("Container Data Generator with Alerts")
    log_print("=" * 60)
    log_print(f"Generating {CONTAINERS_PER_SECOND} container documents per second...")
    log_print("Every 10th document will trigger an alert (1 alert per second).")
    log_print("Running continuously until stopped.")
    log_print("Press Ctrl+C to stop.")
    log_print("=" * 60)
    log_print()
    
    # Verify locations exist and initialize alert locations
    location_count = locations_collection.count_documents({})
    if location_count == 0:
        log_print("⚠️  WARNING: No locations found in database!")
        log_print("   Alerts will still be created but without location information.")
        log_print("   Run seed_local_data.py first to create locations.")
        log_print()
    else:
        log_print(f"✓ Found {location_count} locations in database")
        log_print()
        # Initialize 5 fixed locations for alerts (pass log_print function)
        # We need to call this after log_print is defined, but it uses print() internally
        # So we'll update initialize_alert_locations to accept a log function
        initialize_alert_locations_with_log(log_print)
        log_print()
    
    global document_count
    document_count = 0  # Reset counter at start
    
    log_print("Starting continuous generation...")
    
    # Test database connection before starting (use estimated count to avoid hanging)
    try:
        # Use estimated_document_count() which is much faster for large collections
        test_result = containers_collection.estimated_document_count()
        log_print(f"✓ Database connection verified (containers collection has ~{test_result} documents)")
    except Exception as e:
        # Fallback: just try to find one document
        try:
            containers_collection.find_one()
            log_print("✓ Database connection verified (can access containers collection)")
        except Exception as e2:
            log_print(f"❌ ERROR: Cannot access containers collection: {e2}")
            import traceback
            traceback.print_exc()
            log_file.close()
            return
    
    try:
        while True:  # Run indefinitely
            document_count += 1
            
            # Generate container document
            container_doc = generate_container_document()
            
            # Insert container
            try:
                result = containers_collection.insert_one(container_doc)
                # Print every 10th container
                if document_count % 10 == 0:
                    log_print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Document #{document_count}: "
                              f"Container {container_doc['metadata']['container_id']} inserted")
            except Exception as e:
                log_print(f"❌ ERROR inserting container #{document_count}: {e}")
                import traceback
                traceback.print_exc()
                # Don't continue on insert errors - this is critical
                time.sleep(1)  # Wait a bit before retrying
                continue
            
            # Every 10th document, create an alert
            if document_count % 10 == 0:
                location = get_alert_location()
                if location:
                    try:
                        alert_doc = create_alert(container_doc, location)
                        alert_result = alerts_collection.insert_one(alert_doc)
                        log_print(f"  ⚠️  ALERT #{document_count // 10}: Container {container_doc['metadata']['container_id']} "
                                  f"hit location {location.get('name', 'Unknown')} (Alert ID: {alert_result.inserted_id})")
                    except Exception as e:
                        log_print(f"  ❌ ERROR creating alert #{document_count // 10}: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    log_print(f"  ⚠️  ALERT #{document_count // 10}: No alert locations available")
            
            # Wait before next document
            time.sleep(DELAY_BETWEEN_CONTAINERS)
    
    except KeyboardInterrupt:
        log_print()
        log_print("=" * 60)
        log_print(f"Generator stopped by user.")
        log_print(f"Total documents generated: {document_count}")
        log_print(f"Total alerts created: {document_count // 10}")
        log_print("=" * 60)
        log_file.close()
    except Exception as e:
        log_print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        log_print(f"Total documents generated: {document_count}")
        log_print(f"Total alerts created: {document_count // 10}")
        log_file.close()

if __name__ == "__main__":
    main()


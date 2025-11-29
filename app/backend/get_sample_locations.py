#!/usr/bin/env python3
"""
Get 10 random locations to use as static options in the UI.
"""

import pymongo
import os
from dotenv import load_dotenv
import json
import random

load_dotenv()

connection_string = os.getenv("MONGODB_URI")
if not connection_string:
    print("Error: MONGODB_URI not set")
    exit(1)

client = pymongo.MongoClient(connection_string)
db = client["geofence"]
locations = db["locations"]

# Get 10 random locations
all_locations = list(locations.find(
    {},
    {"name": 1, "type": 1, "city": 1, "country": 1, "location": 1}
).limit(100))

# Pick 10 random ones
sample_locations = random.sample(all_locations, min(10, len(all_locations)))

print("Selected 10 random locations:")
print("=" * 60)
for i, loc in enumerate(sample_locations, 1):
    print(f"{i}. {loc.get('name')} ({loc.get('type')}) - {loc.get('city')}, {loc.get('country')}")

# Save as JSON for the frontend
locations_data = []
for loc in sample_locations:
    locations_data.append({
        "name": loc.get("name"),
        "type": loc.get("type"),
        "city": loc.get("city"),
        "country": loc.get("country"),
        "location": loc.get("location")
    })

with open("sample_locations.json", "w") as f:
    json.dump(locations_data, f, indent=2, default=str)

print("\n✓ Saved to sample_locations.json")
print(f"\nTotal locations in database: {locations.count_documents({})}")
print(f"Selected {len(sample_locations)} locations for static UI")

client.close()



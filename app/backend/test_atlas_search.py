#!/usr/bin/env python3
"""
Test Atlas Search query directly to debug issues.
"""

import pymongo
import os
from dotenv import load_dotenv
import json

load_dotenv()

connection_string = os.getenv("MONGODB_URI")
if not connection_string:
    print("Error: MONGODB_URI not set")
    exit(1)

client = pymongo.MongoClient(connection_string)
db = client["geofence"]
locations = db["locations"]

search_term = "lon"
search_index_name = "default"

print(f"Testing Atlas Search with query: '{search_term}'")
print(f"Index name: '{search_index_name}'")
print("=" * 60)

# Test 1: Simple autocomplete on name field
print("\nTest 1: Simple autocomplete on 'name' field")
try:
    pipeline = [
        {
            "$search": {
                "index": search_index_name,
                "autocomplete": {
                    "query": search_term,
                    "path": "name"
                }
            }
        },
        {"$limit": 5},
        {"$project": {"name": 1, "city": 1, "country": 1, "score": {"$meta": "searchScore"}}}
    ]
    results = list(locations.aggregate(pipeline))
    print(f"Results: {len(results)}")
    for r in results:
        print(f"  - {r.get('name')} (score: {r.get('score', 'N/A')})")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Compound query with multiple fields
print("\nTest 2: Compound query with multiple fields")
try:
    pipeline = [
        {
            "$search": {
                "index": search_index_name,
                "compound": {
                    "should": [
                        {"autocomplete": {"query": search_term, "path": "name"}},
                        {"autocomplete": {"query": search_term, "path": "city"}},
                        {"autocomplete": {"query": search_term, "path": "country"}}
                    ],
                    "minimumShouldMatch": 1
                }
            }
        },
        {"$limit": 5},
        {"$project": {"name": 1, "city": 1, "country": 1, "score": {"$meta": "searchScore"}}}
    ]
    results = list(locations.aggregate(pipeline))
    print(f"Results: {len(results)}")
    for r in results:
        print(f"  - {r.get('name')} - {r.get('city')}, {r.get('country')} (score: {r.get('score', 'N/A')})")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Try with "London" to see if it's a matching issue
print("\nTest 3: Testing with 'London'")
try:
    pipeline = [
        {
            "$search": {
                "index": search_index_name,
                "autocomplete": {
                    "query": "London",
                    "path": "city"
                }
            }
        },
        {"$limit": 5},
        {"$project": {"name": 1, "city": 1, "country": 1, "score": {"$meta": "searchScore"}}}
    ]
    results = list(locations.aggregate(pipeline))
    print(f"Results: {len(results)}")
    for r in results:
        print(f"  - {r.get('name')} - {r.get('city')}, {r.get('country')} (score: {r.get('score', 'N/A')})")
except Exception as e:
    print(f"Error: {e}")

# Test 4: Check what locations exist with "lon" in name/city
print("\nTest 4: Regex search to see what exists")
try:
    results = list(locations.find({
        "$or": [
            {"name": {"$regex": "lon", "$options": "i"}},
            {"city": {"$regex": "lon", "$options": "i"}}
        ]
    }).limit(5))
    print(f"Found {len(results)} locations with 'lon' in name or city:")
    for r in results:
        print(f"  - {r.get('name')} - {r.get('city')}, {r.get('country')}")
except Exception as e:
    print(f"Error: {e}")

client.close()



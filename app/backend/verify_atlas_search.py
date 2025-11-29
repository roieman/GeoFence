#!/usr/bin/env python3
"""
Verify that the Atlas Search index exists and is working.
"""

import pymongo
import os
from dotenv import load_dotenv
import sys

load_dotenv()

def verify_atlas_search():
    """Verify Atlas Search index exists and test it."""
    connection_string = os.getenv("MONGODB_URI")
    
    if not connection_string:
        print("Error: MONGODB_URI environment variable not set")
        sys.exit(1)
    
    client = pymongo.MongoClient(connection_string)
    db = client["geofence"]
    locations = db["locations"]
    
    print("Verifying Atlas Search index...")
    print("=" * 60)
    
    search_index_name = "default"
    
    # Test the search aggregation
    try:
        pipeline = [
            {
                "$search": {
                    "index": search_index_name,
                    "compound": {
                        "should": [
                            {
                                "autocomplete": {
                                    "query": "Shanghai",
                                    "path": "name"
                                }
                            },
                            {
                                "autocomplete": {
                                    "query": "Shanghai",
                                    "path": "city"
                                }
                            },
                            {
                                "autocomplete": {
                                    "query": "Shanghai",
                                    "path": "country"
                                }
                            }
                        ],
                        "minimumShouldMatch": 1
                    }
                }
            },
            {
                "$limit": 5
            },
            {
                "$project": {
                    "name": 1,
                    "type": 1,
                    "city": 1,
                    "country": 1,
                    "score": {"$meta": "searchScore"}
                }
            }
        ]
        
        results = list(locations.aggregate(pipeline))
        
        if results:
            print(f"✓ Atlas Search index '{search_index_name}' is working!")
            print(f"\nTest query 'Shanghai' returned {len(results)} results:")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result.get('name')} - {result.get('city')}, {result.get('country')} (score: {result.get('score', 'N/A')})")
            print("\n✓ Atlas Search is properly configured and ready to use!")
        else:
            print(f"⚠ Index '{search_index_name}' exists but returned no results")
            print("  This might be normal if there's no data matching the test query")
    
    except Exception as e:
        error_msg = str(e)
        if "index" in error_msg.lower() or "not found" in error_msg.lower():
            print(f"✗ Atlas Search index '{search_index_name}' not found!")
            print("\nTo create the index:")
            print("1. Go to MongoDB Atlas UI")
            print("2. Navigate to Search > Create Search Index")
            print("3. Use the configuration from 'atlas_search_index.json'")
            print("4. Name it: 'default' (or use the default index name)")
            print("\nSee ATLAS_SEARCH_SETUP.md for detailed instructions")
        else:
            print(f"✗ Error testing Atlas Search: {e}")
            print("\nThe API will fall back to regex search until the index is created")
    
    client.close()

if __name__ == "__main__":
    verify_atlas_search()


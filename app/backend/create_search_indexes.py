#!/usr/bin/env python3
"""
Create search indexes for the locations collection to support autocomplete.
"""

import pymongo
import os
from dotenv import load_dotenv
import sys

load_dotenv()

def create_search_indexes():
    """Create text search index on locations collection."""
    connection_string = os.getenv("MONGODB_URI")
    
    if not connection_string:
        print("Error: MONGODB_URI environment variable not set")
        sys.exit(1)
    
    client = pymongo.MongoClient(connection_string)
    db = client["geofence"]
    locations = db["locations"]
    
    print("Creating search indexes on locations collection...")
    
    # Create text index for search on name, city, and country
    try:
        # Drop existing text indexes if they exist
        existing_indexes = list(locations.list_indexes())
        for idx in existing_indexes:
            if idx.get('name') and 'text' in idx['name']:
                try:
                    locations.drop_index(idx['name'])
                    print(f"  Dropped existing text index: {idx['name']}")
                except:
                    pass
        
        # Create new comprehensive text index
        locations.create_index([
            ("name", "text"),
            ("city", "text"),
            ("country", "text")
        ], name="name_text_city_text_country_text")
        
        print("✓ Created text search index on name, city, and country")
    except Exception as e:
        print(f"Error creating text index: {e}")
        print("  Note: You may need to manually drop existing text indexes first")
    
    # Also create regular indexes for faster filtering
    try:
        locations.create_index("type")
        print("✓ Created index on type")
    except:
        print("  Index on type already exists or error occurred")
    
    try:
        locations.create_index("country")
        print("✓ Created index on country")
    except:
        print("  Index on country already exists or error occurred")
    
    # List all indexes
    print("\nCurrent indexes on locations collection:")
    for idx in locations.list_indexes():
        print(f"  - {idx['name']}: {idx.get('key', {})}")
    
    client.close()
    print("\n✓ Search indexes created successfully!")

if __name__ == "__main__":
    create_search_indexes()


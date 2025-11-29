#!/usr/bin/env python3
"""
Instructions and script to create Atlas Search index for locations collection.
Note: Atlas Search indexes must be created via the Atlas UI or API, not via pymongo.
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

def print_instructions():
    """Print instructions for creating Atlas Search index."""
    print("=" * 60)
    print("MongoDB Atlas Search Index Setup")
    print("=" * 60)
    print("\nAtlas Search indexes must be created via the Atlas UI or REST API.")
    print("This script provides the index configuration and instructions.\n")
    
    print("OPTION 1: Create via Atlas UI")
    print("-" * 60)
    print("1. Go to your MongoDB Atlas cluster")
    print("2. Click on 'Search' in the left sidebar")
    print("3. Click 'Create Search Index'")
    print("4. Select 'JSON Editor'")
    print("5. Choose database: 'geofence'")
    print("6. Choose collection: 'locations'")
    print("7. Copy the contents of 'atlas_search_index.json' into the editor")
    print("8. Name the index: 'default' (or use the default index name)")
    print("9. Click 'Create Search Index'")
    print("10. Wait for the index to build (may take a few minutes)\n")
    
    print("OPTION 2: Create via Atlas API")
    print("-" * 60)
    print("You can use the Atlas Admin API to create the index programmatically.")
    print("See: https://www.mongodb.com/docs/atlas/atlas-search/create-index/\n")
    
    print("Index Configuration:")
    print("-" * 60)
    with open('atlas_search_index.json', 'r') as f:
        config = json.load(f)
        print(json.dumps(config, indent=2))
    
    print("\n" + "=" * 60)
    print("After creating the index, update the index name in main.py")
    print("The index name used in the code is: 'default'")
    print("=" * 60)

if __name__ == "__main__":
    print_instructions()


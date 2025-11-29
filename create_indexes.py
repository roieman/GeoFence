#!/usr/bin/env python3
"""
Script to create optimized indexes for geospatial queries on the locations collection.
"""

import pymongo
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()


def create_indexes(
    connection_string: str = None,
    database_name: str = "geofence",
    collection_name: str = "locations"
):
    """Create optimized indexes for geospatial queries."""
    # Get connection string from environment or parameter
    if not connection_string:
        connection_string = os.getenv("MONGODB_URI")
    
    if not connection_string:
        print("Error: MongoDB connection string not found.")
        print("Please set MONGODB_URI environment variable or pass connection string as argument.")
        sys.exit(1)
    
    client = pymongo.MongoClient(connection_string)
    db = client[database_name]
    collection = db[collection_name]
    
    print(f"Creating indexes for '{database_name}.{collection_name}'...")
    print(f"Connection: {connection_string}\n")
    
    # Get existing indexes
    existing_indexes = list(collection.list_indexes())
    existing_index_names = [idx["name"] for idx in existing_indexes]
    
    print(f"Existing indexes: {len(existing_indexes)}")
    for idx in existing_indexes:
        print(f"  - {idx['name']}: {idx.get('key', {})}")
    print()
    
    indexes_created = []
    indexes_skipped = []
    
    # 1. Geospatial 2dsphere index on location (most important for geospatial queries)
    if "location_2dsphere" not in existing_index_names:
        print("Creating geospatial 2dsphere index on 'location'...")
        collection.create_index([("location", "2dsphere")], name="location_2dsphere")
        indexes_created.append("location_2dsphere")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("location_2dsphere")
        print("  ⊘ location_2dsphere already exists\n")
    
    # 2. Compound index: type + location (for filtering by type with geospatial queries)
    if "type_location_2dsphere" not in existing_index_names:
        print("Creating compound index: type + location (2dsphere)...")
        collection.create_index([
            ("type", 1),
            ("location", "2dsphere")
        ], name="type_location_2dsphere")
        indexes_created.append("type_location_2dsphere")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("type_location_2dsphere")
        print("  ⊘ type_location_2dsphere already exists\n")
    
    # 3. Compound index: facility_type + location (for filtering facilities by type)
    if "facility_type_location_2dsphere" not in existing_index_names:
        print("Creating compound index: facility_type + location (2dsphere)...")
        collection.create_index([
            ("facility_type", 1),
            ("location", "2dsphere")
        ], name="facility_type_location_2dsphere")
        indexes_created.append("facility_type_location_2dsphere")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("facility_type_location_2dsphere")
        print("  ⊘ facility_type_location_2dsphere already exists\n")
    
    # 4. Compound index: country + location (for filtering by country with geospatial)
    if "country_location_2dsphere" not in existing_index_names:
        print("Creating compound index: country + location (2dsphere)...")
        collection.create_index([
            ("country", 1),
            ("location", "2dsphere")
        ], name="country_location_2dsphere")
        indexes_created.append("country_location_2dsphere")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("country_location_2dsphere")
        print("  ⊘ country_location_2dsphere already exists\n")
    
    # 5. Index on type (for filtering ports, terminals, facilities)
    if "type_1" not in existing_index_names:
        print("Creating index on 'type'...")
        collection.create_index([("type", 1)], name="type_1")
        indexes_created.append("type_1")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("type_1")
        print("  ⊘ type_1 already exists\n")
    
    # 6. Index on facility_type (for filtering by facility type)
    if "facility_type_1" not in existing_index_names:
        print("Creating index on 'facility_type'...")
        collection.create_index([("facility_type", 1)], name="facility_type_1")
        indexes_created.append("facility_type_1")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("facility_type_1")
        print("  ⊘ facility_type_1 already exists\n")
    
    # 7. Index on country (for filtering by country)
    if "country_1" not in existing_index_names:
        print("Creating index on 'country'...")
        collection.create_index([("country", 1)], name="country_1")
        indexes_created.append("country_1")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("country_1")
        print("  ⊘ country_1 already exists\n")
    
    # 8. Compound index: type + country (for filtering by both)
    if "type_1_country_1" not in existing_index_names:
        print("Creating compound index: type + country...")
        collection.create_index([
            ("type", 1),
            ("country", 1)
        ], name="type_1_country_1")
        indexes_created.append("type_1_country_1")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("type_1_country_1")
        print("  ⊘ type_1_country_1 already exists\n")
    
    # 9. Text index on name (for searching facility names)
    if "name_text" not in existing_index_names:
        print("Creating text index on 'name'...")
        collection.create_index([("name", "text")], name="name_text")
        indexes_created.append("name_text")
        print("  ✓ Created\n")
    else:
        indexes_skipped.append("name_text")
        print("  ⊘ name_text already exists\n")
    
    # Print summary
    print("=" * 60)
    print("Index Creation Summary")
    print("=" * 60)
    print(f"Indexes created: {len(indexes_created)}")
    if indexes_created:
        for idx_name in indexes_created:
            print(f"  ✓ {idx_name}")
    
    print(f"\nIndexes skipped (already exist): {len(indexes_skipped)}")
    if indexes_skipped:
        for idx_name in indexes_skipped:
            print(f"  ⊘ {idx_name}")
    
    # Show all indexes
    print("\n" + "=" * 60)
    print("All Indexes")
    print("=" * 60)
    final_indexes = list(collection.list_indexes())
    for idx in final_indexes:
        key_str = ", ".join([f"{k}: {v}" for k, v in idx.get("key", {}).items()])
        print(f"  {idx['name']}: {key_str}")
    
    # Get collection stats
    stats = db.command("collStats", collection_name)
    print("\n" + "=" * 60)
    print("Collection Statistics")
    print("=" * 60)
    print(f"Document count: {stats.get('count', 0):,}")
    print(f"Total size: {stats.get('size', 0):,} bytes ({stats.get('size', 0) / 1024 / 1024:.2f} MB)")
    print(f"Average document size: {stats.get('avgObjSize', 0):,} bytes")
    print(f"Index size: {stats.get('totalIndexSize', 0):,} bytes ({stats.get('totalIndexSize', 0) / 1024 / 1024:.2f} MB)")
    
    client.close()
    print("\n✓ Index creation complete!")


if __name__ == "__main__":
    connection_string = sys.argv[1] if len(sys.argv) > 1 else None
    database_name = sys.argv[2] if len(sys.argv) > 2 else "geofence"
    collection_name = sys.argv[3] if len(sys.argv) > 3 else "locations"
    
    create_indexes(connection_string, database_name, collection_name)



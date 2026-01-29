#!/usr/bin/env python3
"""
Import Zim geofences from GeoJSON file into MongoDB.
"""
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.core.database import DatabaseHandler
from simulator.config import COLLECTIONS


def import_geofences(geojson_path: str, clear_existing: bool = False):
    """
    Import geofences from GeoJSON file.

    Args:
        geojson_path: Path to GeoJSON file
        clear_existing: If True, delete existing geofences before import
    """
    # Load GeoJSON
    print(f"Loading geofences from: {geojson_path}")
    with open(geojson_path, 'r') as f:
        data = json.load(f)

    features = data.get("features", [])
    print(f"Found {len(features)} features")

    # Connect to database
    db_handler = DatabaseHandler()
    db = db_handler.connect()
    db_handler.setup_collections()

    geofences_collection = db[COLLECTIONS["geofences"]]

    # Optionally clear existing
    if clear_existing:
        result = geofences_collection.delete_many({})
        print(f"Deleted {result.deleted_count} existing geofences")

    # Import features
    imported = 0
    skipped = 0
    errors = 0

    for feature in features:
        try:
            # Validate structure
            if feature.get("type") != "Feature":
                print(f"  Skipping non-Feature: {feature.get('type')}")
                skipped += 1
                continue

            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})

            if not properties.get("name"):
                print(f"  Skipping feature without name")
                skipped += 1
                continue

            if not geometry.get("coordinates"):
                print(f"  Skipping feature without coordinates: {properties.get('name')}")
                skipped += 1
                continue

            # Create document
            doc = {
                "type": "Feature",
                "properties": {
                    "name": properties.get("name"),
                    "description": properties.get("description", ""),
                    "typeId": properties.get("typeId", "Unknown"),
                    "UNLOCode": properties.get("UNLOCode", ""),
                    "SMDGCode": properties.get("SMDGCode", ""),
                },
                "geometry": geometry
            }

            # Upsert (update if exists, insert if not)
            result = geofences_collection.update_one(
                {"properties.name": properties.get("name")},
                {"$set": doc},
                upsert=True
            )

            if result.upserted_id:
                imported += 1
            else:
                imported += 1  # Updated counts as imported too

        except Exception as e:
            print(f"  Error importing {properties.get('name', 'unknown')}: {e}")
            errors += 1

    print(f"\nImport complete:")
    print(f"  - Imported/Updated: {imported}")
    print(f"  - Skipped: {skipped}")
    print(f"  - Errors: {errors}")

    # Show summary by type
    print("\nGeofences by type:")
    pipeline = [
        {"$group": {"_id": "$properties.typeId", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for doc in geofences_collection.aggregate(pipeline):
        print(f"  - {doc['_id']}: {doc['count']}")

    db_handler.close()


def main():
    """Main entry point."""
    # Default path to Zim geofences
    default_path = Path(__file__).parent.parent / "Zim Data" / "Geofences.geojson"

    geojson_path = sys.argv[1] if len(sys.argv) > 1 else str(default_path)
    clear_existing = "--clear" in sys.argv

    if not Path(geojson_path).exists():
        print(f"Error: File not found: {geojson_path}")
        sys.exit(1)

    import_geofences(geojson_path, clear_existing)


if __name__ == "__main__":
    main()

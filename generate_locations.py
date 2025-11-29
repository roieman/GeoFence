#!/usr/bin/env python3
"""
Script to generate locations data for ports, train terminals, factories, and industrial facilities.
Creates a MongoDB collection with geospatial data (points and polygons).
"""

import pymongo
import random
import math
from datetime import datetime
from typing import List, Dict, Any

# Major ports around the world with their coordinates
MAJOR_PORTS = [
    {"name": "Port of Shanghai", "city": "Shanghai", "country": "China", "lat": 31.2304, "lon": 121.4737, "type": "port"},
    {"name": "Port of Singapore", "city": "Singapore", "country": "Singapore", "lat": 1.2897, "lon": 103.8501, "type": "port"},
    {"name": "Port of Rotterdam", "city": "Rotterdam", "country": "Netherlands", "lat": 51.9225, "lon": 4.4772, "type": "port"},
    {"name": "Port of Los Angeles", "city": "Los Angeles", "country": "USA", "lat": 33.7420, "lon": -118.2642, "type": "port"},
    {"name": "Port of Hamburg", "city": "Hamburg", "country": "Germany", "lat": 53.5511, "lon": 9.9937, "type": "port"},
    {"name": "Port of Antwerp", "city": "Antwerp", "country": "Belgium", "lat": 51.2194, "lon": 4.4025, "type": "port"},
    {"name": "Port of Busan", "city": "Busan", "country": "South Korea", "lat": 35.1796, "lon": 129.0756, "type": "port"},
    {"name": "Port of Hong Kong", "city": "Hong Kong", "country": "China", "lat": 22.3193, "lon": 114.1694, "type": "port"},
    {"name": "Port of Long Beach", "city": "Long Beach", "country": "USA", "lat": 33.7701, "lon": -118.1937, "type": "port"},
    {"name": "Port of New York/New Jersey", "city": "New York", "country": "USA", "lat": 40.6892, "lon": -74.0445, "type": "port"},
    {"name": "Port of Dubai", "city": "Dubai", "country": "UAE", "lat": 25.2048, "lon": 55.2708, "type": "port"},
    {"name": "Port of Tokyo", "city": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503, "type": "port"},
    {"name": "Port of Jebel Ali", "city": "Dubai", "country": "UAE", "lat": 25.0267, "lon": 55.0556, "type": "port"},
    {"name": "Port of Tanjung Pelepas", "city": "Johor", "country": "Malaysia", "lat": 1.3644, "lon": 103.5500, "type": "port"},
    {"name": "Port of Qingdao", "city": "Qingdao", "country": "China", "lat": 36.0671, "lon": 120.3826, "type": "port"},
    {"name": "Port of Ningbo-Zhoushan", "city": "Ningbo", "country": "China", "lat": 29.8683, "lon": 121.5440, "type": "port"},
    {"name": "Port of Bremerhaven", "city": "Bremerhaven", "country": "Germany", "lat": 53.5500, "lon": 8.5767, "type": "port"},
    {"name": "Port of Felixstowe", "city": "Felixstowe", "country": "UK", "lat": 51.9617, "lon": 1.3514, "type": "port"},
    {"name": "Port of Tanjung Priok", "city": "Jakarta", "country": "Indonesia", "lat": -6.1150, "lon": 106.8764, "type": "port"},
    {"name": "Port of Colombo", "city": "Colombo", "country": "Sri Lanka", "lat": 6.9271, "lon": 79.8612, "type": "port"},
]

# Major train terminals around the world
MAJOR_TRAIN_TERMINALS = [
    {"name": "Chicago Union Station", "city": "Chicago", "country": "USA", "lat": 41.8789, "lon": -87.6358, "type": "train_terminal"},
    {"name": "Grand Central Terminal", "city": "New York", "country": "USA", "lat": 40.7527, "lon": -73.9772, "type": "train_terminal"},
    {"name": "London King's Cross", "city": "London", "country": "UK", "lat": 51.5308, "lon": -0.1238, "type": "train_terminal"},
    {"name": "Paris Gare du Nord", "city": "Paris", "country": "France", "lat": 48.8809, "lon": 2.3553, "type": "train_terminal"},
    {"name": "Tokyo Station", "city": "Tokyo", "country": "Japan", "lat": 35.6812, "lon": 139.7671, "type": "train_terminal"},
    {"name": "Beijing Railway Station", "city": "Beijing", "country": "China", "lat": 39.9022, "lon": 116.4270, "type": "train_terminal"},
    {"name": "Moscow Yaroslavsky", "city": "Moscow", "country": "Russia", "lat": 55.7764, "lon": 37.6572, "type": "train_terminal"},
    {"name": "Berlin Hauptbahnhof", "city": "Berlin", "country": "Germany", "lat": 52.5250, "lon": 13.3694, "type": "train_terminal"},
    {"name": "Madrid Atocha", "city": "Madrid", "country": "Spain", "lat": 40.4070, "lon": -3.6917, "type": "train_terminal"},
    {"name": "Mumbai Central", "city": "Mumbai", "country": "India", "lat": 18.9750, "lon": 72.8258, "type": "train_terminal"},
    {"name": "Sydney Central", "city": "Sydney", "country": "Australia", "lat": -33.8836, "lon": 151.2069, "type": "train_terminal"},
    {"name": "Toronto Union Station", "city": "Toronto", "country": "Canada", "lat": 43.6452, "lon": -79.3806, "type": "train_terminal"},
    {"name": "Amsterdam Centraal", "city": "Amsterdam", "country": "Netherlands", "lat": 52.3792, "lon": 4.9003, "type": "train_terminal"},
    {"name": "Vienna Hauptbahnhof", "city": "Vienna", "country": "Austria", "lat": 48.1847, "lon": 16.3744, "type": "train_terminal"},
    {"name": "Zurich Hauptbahnhof", "city": "Zurich", "country": "Switzerland", "lat": 47.3779, "lon": 8.5402, "type": "train_terminal"},
]

# Major population centers for weighted distribution
POPULATION_CENTERS = [
    # Asia
    {"lat": 31.2304, "lon": 121.4737, "country": "China", "weight": 0.15},  # Shanghai
    {"lat": 39.9042, "lon": 116.4074, "country": "China", "weight": 0.12},  # Beijing
    {"lat": 22.3193, "lon": 114.1694, "country": "China", "weight": 0.10},  # Hong Kong
    {"lat": 19.0760, "lon": 72.8777, "country": "India", "weight": 0.12},   # Mumbai
    {"lat": 28.6139, "lon": 77.2090, "country": "India", "weight": 0.10},   # Delhi
    {"lat": 35.6762, "lon": 139.6503, "country": "Japan", "weight": 0.08},  # Tokyo
    {"lat": 37.5665, "lon": 126.9780, "country": "South Korea", "weight": 0.06},  # Seoul
    {"lat": 1.2897, "lon": 103.8501, "country": "Singapore", "weight": 0.04},  # Singapore
    {"lat": -6.2088, "lon": 106.8456, "country": "Indonesia", "weight": 0.08},  # Jakarta
    {"lat": 13.7563, "lon": 100.5018, "country": "Thailand", "weight": 0.05},  # Bangkok
    # Europe
    {"lat": 51.5074, "lon": -0.1278, "country": "UK", "weight": 0.06},  # London
    {"lat": 52.5200, "lon": 13.4050, "country": "Germany", "weight": 0.06},  # Berlin
    {"lat": 48.8566, "lon": 2.3522, "country": "France", "weight": 0.05},  # Paris
    {"lat": 41.9028, "lon": 12.4964, "country": "Italy", "weight": 0.05},  # Rome
    {"lat": 40.4168, "lon": -3.7038, "country": "Spain", "weight": 0.04},  # Madrid
    # Americas
    {"lat": 40.7128, "lon": -74.0060, "country": "USA", "weight": 0.08},  # New York
    {"lat": 34.0522, "lon": -118.2437, "country": "USA", "weight": 0.07},  # Los Angeles
    {"lat": 41.8781, "lon": -87.6298, "country": "USA", "weight": 0.06},  # Chicago
    {"lat": 29.7604, "lon": -95.3698, "country": "USA", "weight": 0.05},  # Houston
    {"lat": 23.6345, "lon": -102.5528, "country": "Mexico", "weight": 0.05},  # Mexico City
    {"lat": -23.5505, "lon": -46.6333, "country": "Brazil", "weight": 0.06},  # São Paulo
    {"lat": -34.6037, "lon": -58.3816, "country": "Argentina", "weight": 0.04},  # Buenos Aires
    # Other regions
    {"lat": -33.8688, "lon": 151.2093, "country": "Australia", "weight": 0.04},  # Sydney
    {"lat": -26.2041, "lon": 28.0473, "country": "South Africa", "weight": 0.03},  # Johannesburg
    {"lat": 30.0444, "lon": 31.2357, "country": "Egypt", "weight": 0.03},  # Cairo
    {"lat": 55.7558, "lon": 37.6173, "country": "Russia", "weight": 0.05},  # Moscow
]

# Industrial facility types
FACILITY_TYPES = [
    {"type": "factory", "subtypes": ["manufacturing", "assembly", "production", "processing"]},
    {"type": "warehouse", "subtypes": ["distribution", "storage", "fulfillment", "logistics"]},
    {"type": "distribution_center", "subtypes": ["regional", "national", "international"]},
    {"type": "manufacturing_plant", "subtypes": ["automotive", "electronics", "textiles", "food", "chemical"]},
    {"type": "industrial_facility", "subtypes": ["heavy_industry", "light_industry", "specialized"]},
]

# Company name prefixes and suffixes for realistic naming
COMPANY_PREFIXES = [
    "Global", "International", "Pacific", "Atlantic", "Continental", "United", "National",
    "Premier", "Elite", "Advanced", "Modern", "Industrial", "Commercial", "Regional",
    "Metro", "City", "Coastal", "Inland", "Central", "Eastern", "Western", "Northern", "Southern"
]

COMPANY_SUFFIXES = [
    "Industries", "Manufacturing", "Logistics", "Distribution", "Supply Chain", "Warehousing",
    "Facilities", "Operations", "Enterprises", "Group", "Corporation", "Holdings", "Systems"
]

INDUSTRY_NAMES = [
    "Tech", "Auto", "Electronics", "Textile", "Food", "Chemical", "Pharmaceutical",
    "Steel", "Plastic", "Paper", "Energy", "Materials", "Components", "Goods"
]


def generate_facility_name() -> str:
    """Generate a realistic facility name."""
    prefix = random.choice(COMPANY_PREFIXES)
    industry = random.choice(INDUSTRY_NAMES)
    suffix = random.choice(COMPANY_SUFFIXES)
    
    # Sometimes use just prefix + suffix, sometimes include industry
    if random.random() < 0.5:
        return f"{prefix} {industry} {suffix}"
    else:
        return f"{prefix} {suffix}"


def generate_coordinates_weighted() -> tuple:
    """Generate coordinates weighted towards population centers."""
    # Select a population center based on weights
    weights = [center["weight"] for center in POPULATION_CENTERS]
    center = random.choices(POPULATION_CENTERS, weights=weights)[0]
    
    # Add random offset (closer to center = more likely)
    # Use normal distribution for more realistic clustering
    lat_offset = random.gauss(0, 15)  # ~15 degrees std dev
    lon_offset = random.gauss(0, 15)
    
    lat = center["lat"] + lat_offset
    lon = center["lon"] + lon_offset
    
    # Keep within valid ranges
    lat = max(-85, min(85, lat))
    lon = max(-180, min(180, lon))
    
    return lat, lon, center["country"]


def generate_coordinates_uniform() -> tuple:
    """Generate uniformly distributed coordinates."""
    lat = random.uniform(-60, 70)  # Avoid extreme polar regions
    lon = random.uniform(-180, 180)
    
    # Determine country based on region (simplified)
    if 20 <= lat <= 50 and 100 <= lon <= 140:
        country = "China"
    elif 5 <= lat <= 35 and 65 <= lon <= 100:
        country = "India"
    elif 25 <= lat <= 50 and -130 <= lon <= -65:
        country = "USA"
    elif 35 <= lat <= 70 and -10 <= lon <= 40:
        country = random.choice(["Germany", "France", "UK", "Italy", "Spain"])
    else:
        country = "Various"
    
    return lat, lon, country


def create_point_geometry(lat: float, lon: float) -> Dict[str, Any]:
    """Create a GeoJSON Point geometry."""
    return {
        "type": "Point",
        "coordinates": [lon, lat]  # GeoJSON format: [longitude, latitude]
    }


def create_polygon_geometry(center_lat: float, center_lon: float, radius_km: float = 0.5) -> Dict[str, Any]:
    """Create a GeoJSON Polygon geometry representing a circular area around a point."""
    # Adjust radius if too close to longitude boundaries to avoid crossing 180/-180
    max_lon_offset = abs(radius_km / (111.0 * math.cos(math.radians(center_lat))))
    if abs(center_lon) + max_lon_offset > 180:
        # Reduce radius to stay within bounds
        max_allowed_offset = 180 - abs(center_lon) - 0.01  # Small buffer
        if max_allowed_offset > 0:
            radius_km = min(radius_km, max_allowed_offset * 111.0 * math.cos(math.radians(center_lat)))
        else:
            # Too close to edge, just use a point instead
            return create_point_geometry(center_lat, center_lon)
    
    # Create a polygon approximation of a circle
    num_points = 16
    coordinates = []
    
    for i in range(num_points + 1):
        angle = (2 * math.pi * i) / num_points
        # Convert km to degrees (approximate)
        lat_offset = (radius_km / 111.0) * math.cos(angle)
        lon_offset = (radius_km / (111.0 * math.cos(math.radians(center_lat)))) * math.sin(angle)
        
        lat = center_lat + lat_offset
        lon = center_lon + lon_offset
        
        # Ensure coordinates stay within valid bounds
        lat = max(-85, min(85, lat))  # Avoid polar regions
        lon = max(-180, min(180, lon))  # Valid longitude range
        
        coordinates.append([lon, lat])
    
    # Close the polygon
    coordinates.append(coordinates[0])
    
    return {
        "type": "Polygon",
        "coordinates": [coordinates]
    }


def generate_locations(
    connection_string: str,
    database_name: str = "geofence",
    collection_name: str = "locations",
    num_facilities: int = 300000,
    batch_size: int = 10000
):
    """Generate and insert location data into MongoDB."""
    client = pymongo.MongoClient(connection_string)
    db = client[database_name]
    collection = db[collection_name]
    
    # Clear existing data
    collection.delete_many({})
    
    # Create geospatial index
    collection.create_index([("location", "2dsphere")])
    collection.create_index("type")
    collection.create_index("country")
    collection.create_index("facility_type")
    
    print(f"Generating {num_facilities:,} industrial facilities...")
    
    # First, insert ports and train terminals
    documents = []
    
    # Generate port locations
    for port in MAJOR_PORTS:
        use_polygon = random.random() < 0.3
        if use_polygon:
            location = create_polygon_geometry(port["lat"], port["lon"], radius_km=random.uniform(0.3, 1.5))
        else:
            location = create_point_geometry(port["lat"], port["lon"])
        
        doc = {
            "name": port["name"],
            "city": port["city"],
            "country": port["country"],
            "type": port["type"],
            "location": location,
            "capacity": random.randint(1000, 50000),
            "created_at": datetime.utcnow()
        }
        documents.append(doc)
    
    # Generate train terminal locations
    for terminal in MAJOR_TRAIN_TERMINALS:
        use_polygon = random.random() < 0.2
        if use_polygon:
            location = create_polygon_geometry(terminal["lat"], terminal["lon"], radius_km=random.uniform(0.2, 0.8))
        else:
            location = create_point_geometry(terminal["lat"], terminal["lon"])
        
        doc = {
            "name": terminal["name"],
            "city": terminal["city"],
            "country": terminal["country"],
            "type": terminal["type"],
            "location": location,
            "platforms": random.randint(5, 30),
            "created_at": datetime.utcnow()
        }
        documents.append(doc)
    
    # Insert ports and terminals
    if documents:
        collection.insert_many(documents)
        print(f"✓ Inserted {len(documents)} ports and train terminals")
    
    # Generate industrial facilities
    total_inserted = len(documents)
    
    for batch_start in range(0, num_facilities, batch_size):
        batch_end = min(batch_start + batch_size, num_facilities)
        batch_docs = []
        
        for _ in range(batch_start, batch_end):
            # Select facility type
            facility_type_data = random.choice(FACILITY_TYPES)
            facility_type = facility_type_data["type"]
            subtype = random.choice(facility_type_data["subtypes"])
            
            # Generate coordinates (mix of weighted and uniform for variety)
            if random.random() < 0.7:  # 70% weighted towards population centers
                lat, lon, country = generate_coordinates_weighted()
            else:  # 30% uniform distribution
                lat, lon, country = generate_coordinates_uniform()
            
            # Decide if point or polygon (factories more likely to be polygons)
            use_polygon = random.random() < 0.25  # 25% polygons
            
            if use_polygon:
                radius = random.uniform(0.1, 2.0)  # 0.1 to 2 km radius
                location = create_polygon_geometry(lat, lon, radius_km=radius)
            else:
                location = create_point_geometry(lat, lon)
            
            # Generate facility-specific metadata
            doc = {
                "name": generate_facility_name(),
                "type": "industrial_facility",
                "facility_type": facility_type,
                "subtype": subtype,
                "country": country,
                "location": location,
                "created_at": datetime.utcnow()
            }
            
            # Add type-specific fields
            if facility_type == "factory" or facility_type == "manufacturing_plant":
                doc["employees"] = random.randint(50, 5000)
                doc["production_capacity"] = random.randint(1000, 100000)
                doc["operating_hours"] = random.choice(["24/7", "16/5", "8/5"])
            elif facility_type == "warehouse":
                doc["storage_capacity_sqm"] = random.randint(5000, 100000)
                doc["docking_bays"] = random.randint(5, 50)
                doc["automated"] = random.random() < 0.3
            elif facility_type == "distribution_center":
                doc["coverage_area"] = random.choice(["regional", "national", "international"])
                doc["daily_throughput"] = random.randint(100, 10000)
                doc["vehicles"] = random.randint(10, 200)
            
            batch_docs.append(doc)
        
        # Insert batch
        if batch_docs:
            collection.insert_many(batch_docs)
            total_inserted += len(batch_docs)
            progress = (total_inserted / (num_facilities + len(documents))) * 100
            print(f"Progress: {total_inserted:,} locations inserted ({progress:.1f}%)", end='\r')
    
    print()  # New line after progress
    
    # Print statistics
    print(f"\n✓ Inserted {total_inserted:,} total locations into '{database_name}.{collection_name}'")
    print(f"  - Ports: {len(MAJOR_PORTS)}")
    print(f"  - Train Terminals: {len(MAJOR_TRAIN_TERMINALS)}")
    print(f"  - Industrial Facilities: {num_facilities:,}")
    
    # Print sample documents
    print(f"\nSample documents:")
    sample_port = collection.find_one({"type": "port"})
    if sample_port:
        print(f"  Port: {sample_port['name']} ({sample_port['location']['type']})")
    
    sample_facility = collection.find_one({"type": "industrial_facility"})
    if sample_facility:
        print(f"  Facility: {sample_facility['name']} - {sample_facility['facility_type']} ({sample_facility['location']['type']})")
    
    # Print type distribution
    pipeline = [
        {"$match": {"type": "industrial_facility"}},
        {"$group": {"_id": "$facility_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    type_dist = list(collection.aggregate(pipeline))
    if type_dist:
        print(f"\nFacility type distribution:")
        for item in type_dist[:5]:
            print(f"  {item['_id']}: {item['count']:,}")
    
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
        print("Usage: python generate_locations.py [mongodb_connection_string] [options]")
        print("\nConnection string can be provided via:")
        print("  1. MONGODB_URI environment variable (recommended)")
        print("  2. .env file with MONGODB_URI=...")
        print("  3. Command line argument")
        print("\nOptions:")
        print("  [database_name]          Database name (default: geofence)")
        print("  [collection_name]        Collection name (default: locations)")
        print("  [num_facilities]          Number of industrial facilities (default: 300000)")
        print("\nExample:")
        print("  export MONGODB_URI='mongodb://localhost:27017'")
        print("  python generate_locations.py geofence locations 300000")
        print("\nOr with command line:")
        print("  python generate_locations.py 'mongodb://localhost:27017' geofence locations 300000")
        sys.exit(1)
    
    # Adjust argument positions if connection string was provided via env
    arg_start = 1 if os.getenv("MONGODB_URI") else 2
    database_name = sys.argv[arg_start] if len(sys.argv) > arg_start else "geofence"
    collection_name = sys.argv[arg_start + 1] if len(sys.argv) > arg_start + 1 else "locations"
    num_facilities = int(sys.argv[arg_start + 2]) if len(sys.argv) > arg_start + 2 else 300000
    
    print(f"Generating locations data...")
    print(f"Connection: {connection_string}")
    print(f"Database: {database_name}")
    print(f"Collection: {collection_name}")
    print(f"Industrial Facilities: {num_facilities:,}\n")
    
    generate_locations(connection_string, database_name, collection_name, num_facilities)
    print("\n✓ Location data generation complete!")


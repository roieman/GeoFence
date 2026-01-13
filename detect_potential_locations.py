#!/usr/bin/env python3
"""
Script to detect potential new storage facilities from container data.
Can be run standalone or via API.
"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.backend.potential_locations_service import PotentialLocationsService

# Load environment variables
load_dotenv()


def main():
    """Main function to run location detection."""
    # Get connection string
    DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    if DEBUG_MODE:
        connection_string = "mongodb://localhost:27017/"
        print("🔧 DEBUG MODE: Using localhost MongoDB")
    else:
        connection_string = os.getenv("MONGODB_URI")
        if not connection_string:
            print("Error: MONGODB_URI environment variable not set (or set DEBUG=true for localhost)")
            sys.exit(1)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Detect potential locations from container data")
    parser.add_argument("--stop-radius", type=float, default=100, help="Radius to consider readings as same location (meters, default: 100)")
    parser.add_argument("--min-readings", type=int, default=3, help="Minimum readings to consider it a stop (default: 3)")
    parser.add_argument("--min-containers", type=int, default=10, help="Minimum containers needed (default: 10)")
    parser.add_argument("--min-total-readings", type=int, default=50, help="Minimum total readings (default: 50)")
    parser.add_argument("--cluster-radius", type=float, default=500, help="Radius for clustering stops (meters, default: 500)")
    parser.add_argument("--time-window", type=int, default=30, help="Time window in days (default: 30)")
    parser.add_argument("--min-confidence", type=float, default=0.5, help="Minimum confidence score (default: 0.5)")
    parser.add_argument("--use-timeseries", action="store_true", help="Use TimeSeries collection instead of regular")
    parser.add_argument("--collection", type=str, help="Override collection name")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Potential Location Detection")
    print("=" * 60)
    print(f"Connection: {connection_string}")
    print(f"Parameters:")
    print(f"  Stop radius: {args.stop_radius}m")
    print(f"  Min readings per stop: {args.min_readings}")
    print(f"  Min containers: {args.min_containers}")
    print(f"  Min total readings: {args.min_total_readings}")
    print(f"  Cluster radius: {args.cluster_radius}m")
    print(f"  Time window: {args.time_window} days")
    print(f"  Min confidence: {args.min_confidence}")
    print(f"  Use TimeSeries: {args.use_timeseries}")
    print("=" * 60)
    print()
    
    # Connect to MongoDB
    try:
        client = MongoClient(
            connection_string,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=300000
        )
        db = client["geofence"]
        
        # Verify connection
        client.server_info()
        print("✓ Connected to MongoDB")
        
        # Initialize service
        service = PotentialLocationsService(db)
        
        # Run detection
        print()
        result = service.detect_potential_locations(
            stop_radius_meters=args.stop_radius,
            min_readings_per_stop=args.min_readings,
            min_unique_containers=args.min_containers,
            min_total_readings=args.min_total_readings,
            cluster_radius_meters=args.cluster_radius,
            time_window_days=args.time_window,
            min_confidence_score=args.min_confidence,
            use_timeseries=args.use_timeseries,
            collection_name=args.collection
        )
        
        print()
        print("=" * 60)
        print("Detection Results")
        print("=" * 60)
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        print(f"Stops found: {result.get('stops_found', 0):,}")
        print(f"Clusters created: {result.get('clusters_created', 0):,}")
        print(f"Locations detected: {result.get('locations_detected', 0):,}")
        print(f"Locations created: {result.get('locations_created', 0):,}")
        print(f"Locations updated: {result.get('locations_updated', 0):,}")
        print("=" * 60)
        
        # Show some statistics
        stats = service.get_stats()
        print()
        print("Potential Locations Statistics:")
        print(f"  Total: {stats['total']}")
        print(f"  Pending review: {stats['pending_review']}")
        print(f"  Approved: {stats['approved']}")
        print(f"  Rejected: {stats['rejected']}")
        if 'avg_confidence' in stats:
            print(f"  Avg confidence: {stats['avg_confidence']:.3f}")
        
        client.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


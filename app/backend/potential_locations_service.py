"""
Service module for detecting potential locations from container data.
"""

from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import math


class PotentialLocationsService:
    """Service for detecting potential storage facilities from container stops."""
    
    def __init__(self, db):
        """Initialize with database connection."""
        self.db = db
        self.containers = db["containers_regular"]  # Use regular collection
        self.containers_timeseries = db["containers"]  # Also support TimeSeries
        self.locations = db["locations"]
        self.potential_locations = db["potential_locations"]
    
    def detect_potential_locations(
        self,
        stop_radius_meters: float = 100,
        min_readings_per_stop: int = 3,
        min_unique_containers: int = 10,
        min_total_readings: int = 50,
        cluster_radius_meters: float = 500,
        time_window_days: int = 30,
        min_confidence_score: float = 0.5,
        use_timeseries: bool = False,
        collection_name: str = None
    ) -> Dict[str, Any]:
        """
        Detect potential locations where containers have stopped multiple times.
        
        Args:
            stop_radius_meters: Radius to consider readings as "same location"
            min_readings_per_stop: Minimum readings to consider it a stop
            min_unique_containers: Minimum containers needed to create location
            min_total_readings: Minimum total readings across all containers
            cluster_radius_meters: Radius for clustering nearby stops
            time_window_days: How far back to analyze
            min_confidence_score: Minimum confidence to include
            use_timeseries: Whether to use TimeSeries collection
            collection_name: Override collection name
        
        Returns:
            Dictionary with detection results and statistics
        """
        # Select collection
        containers_collection = self.containers_timeseries if use_timeseries else self.containers
        
        # Calculate time window
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=time_window_days)
        
        print(f"Detecting potential locations...")
        print(f"  Time window: {start_time} to {end_time} ({time_window_days} days)")
        print(f"  Stop radius: {stop_radius_meters}m")
        print(f"  Min readings per stop: {min_readings_per_stop}")
        print(f"  Cluster radius: {cluster_radius_meters}m")
        print(f"  Min containers: {min_unique_containers}")
        print(f"  Min total readings: {min_total_readings}")
        
        # Step 1: Find all container stops (locations with multiple readings)
        stops = self._find_container_stops(
            containers_collection,
            start_time,
            end_time,
            stop_radius_meters,
            min_readings_per_stop
        )
        
        if not stops:
            return {
                "success": True,
                "message": "No stops found matching criteria",
                "stops_found": 0,
                "locations_detected": 0,
                "locations_created": 0
            }
        
        print(f"  Found {len(stops)} container stops")
        
        # Step 2: Cluster stops geographically
        clusters = self._cluster_stops(stops, cluster_radius_meters)
        
        print(f"  Created {len(clusters)} location clusters")
        
        # Step 3: Filter clusters by thresholds and calculate statistics
        potential_locations = []
        for cluster in clusters:
            location_data = self._analyze_cluster(cluster)
            
            # Check thresholds
            if (location_data["unique_container_count"] >= min_unique_containers and
                location_data["total_readings"] >= min_total_readings and
                location_data["confidence_score"] >= min_confidence_score):
                potential_locations.append(location_data)
        
        print(f"  {len(potential_locations)} locations passed thresholds")
        
        # Step 4: Check against existing locations and potential locations
        locations_created = 0
        locations_updated = 0
        
        for loc_data in potential_locations:
            # Check if this location already exists in locations or potential_locations
            existing = self._check_existing_location(loc_data["location"])
            
            if existing:
                # Update existing potential location
                self._update_potential_location(existing["_id"], loc_data)
                locations_updated += 1
            else:
                # Create new potential location
                self._create_potential_location(loc_data)
                locations_created += 1
        
        return {
            "success": True,
            "message": "Detection completed",
            "stops_found": len(stops),
            "clusters_created": len(clusters),
            "locations_detected": len(potential_locations),
            "locations_created": locations_created,
            "locations_updated": locations_updated,
            "time_window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "days": time_window_days
            }
        }
    
    def _find_container_stops(
        self,
        containers_collection,
        start_time: datetime,
        end_time: datetime,
        stop_radius_meters: float,
        min_readings_per_stop: int
    ) -> List[Dict[str, Any]]:
        """
        Find all locations where containers have multiple readings (stops).
        
        Uses aggregation pipeline to:
        1. Filter by time window
        2. Group by container_id
        3. For each container, find locations with multiple readings within radius
        """
        # Convert radius to degrees (approximate)
        # 1 degree latitude ≈ 111 km, 1 degree longitude ≈ 111 km * cos(latitude)
        # For simplicity, use average: 1 degree ≈ 111 km
        radius_degrees = stop_radius_meters / 111000.0
        
        # Optimized approach: Process containers in batches to avoid memory issues
        # First, get list of unique container IDs in time window
        container_ids_pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
            },
            {
                "$group": {
                    "_id": "$metadata.container_id"
                }
            }
        ]
        
        # Get container IDs in batches
        container_ids = []
        cursor = containers_collection.aggregate(container_ids_pipeline, allowDiskUse=True, batchSize=1000)
        for doc in cursor:
            container_ids.append(doc["_id"])
        
        print(f"  Processing {len(container_ids):,} containers in batches...")
        
        stops = []
        batch_size = 100  # Process 100 containers at a time
        
        for i in range(0, len(container_ids), batch_size):
            batch_ids = container_ids[i:i + batch_size]
            
            pipeline = [
                {
                    "$match": {
                        "metadata.container_id": {"$in": batch_ids},
                        "timestamp": {
                            "$gte": start_time,
                            "$lte": end_time
                        }
                    }
                },
                {
                    "$group": {
                        "_id": "$metadata.container_id",
                        "readings": {
                            "$push": {
                                "timestamp": "$timestamp",
                                "location": "$location",
                                "status": "$status",
                                "speed_knots": "$speed_knots"
                            }
                        }
                    }
                }
            ]
            
            try:
                container_groups = list(containers_collection.aggregate(pipeline, allowDiskUse=True, maxTimeMS=60000))
            except Exception as e:
                print(f"    Warning: Error processing batch {i//batch_size + 1}: {str(e)}")
                continue
            
            for container_group in container_groups:
                container_id = container_group["_id"]
                readings = container_group["readings"]
                
                # Find clusters of readings within stop_radius
                # Simple approach: group readings by rounded coordinates
                # More sophisticated: use actual distance calculation
                location_groups = {}
                
                for reading in readings:
                    coords = reading["location"]["coordinates"]
                    lon, lat = coords[0], coords[1]
                    
                    # Round to grid cells (based on radius)
                    # This groups nearby readings together
                    grid_size = radius_degrees
                    grid_lon = round(lon / grid_size) * grid_size
                    grid_lat = round(lat / grid_size) * grid_size
                    grid_key = f"{grid_lon:.6f},{grid_lat:.6f}"
                    
                    if grid_key not in location_groups:
                        location_groups[grid_key] = {
                            "readings": [],
                            "center_lon": 0,
                            "center_lat": 0
                        }
                    
                    location_groups[grid_key]["readings"].append(reading)
                    # Accumulate for center calculation
                    location_groups[grid_key]["center_lon"] += lon
                    location_groups[grid_key]["center_lat"] += lat
                
                # Process each location group
                for grid_key, group in location_groups.items():
                    if len(group["readings"]) >= min_readings_per_stop:
                        # Calculate center
                        n = len(group["readings"])
                        center_lon = group["center_lon"] / n
                        center_lat = group["center_lat"] / n
                        
                        # Sort readings by timestamp
                        group["readings"].sort(key=lambda x: x["timestamp"])
                        
                        # Calculate stop duration
                        first_reading = group["readings"][0]
                        last_reading = group["readings"][-1]
                        duration_seconds = (last_reading["timestamp"] - first_reading["timestamp"]).total_seconds()
                        
                        stops.append({
                            "container_id": container_id,
                            "location": {
                                "type": "Point",
                                "coordinates": [center_lon, center_lat]
                            },
                            "readings_count": n,
                            "first_seen": first_reading["timestamp"],
                            "last_seen": last_reading["timestamp"],
                            "duration_seconds": duration_seconds,
                            "readings": group["readings"]
                        })
            
            if (i + batch_size) % 1000 == 0 or i + batch_size >= len(container_ids):
                print(f"    Processed {min(i + batch_size, len(container_ids)):,}/{len(container_ids):,} containers, found {len(stops)} stops so far...")
        
        return stops
    
    def _cluster_stops(
        self,
        stops: List[Dict[str, Any]],
        cluster_radius_meters: float
    ) -> List[List[Dict[str, Any]]]:
        """
        Cluster stops that are geographically close together.
        
        Uses a simple grid-based clustering approach.
        """
        if not stops:
            return []
        
        # Convert radius to degrees
        radius_degrees = cluster_radius_meters / 111000.0
        
        # Group stops by grid cell
        clusters_dict = {}
        
        for stop in stops:
            coords = stop["location"]["coordinates"]
            lon, lat = coords[0], coords[1]
            
            # Round to grid cells
            grid_size = radius_degrees
            grid_lon = round(lon / grid_size) * grid_size
            grid_lat = round(lat / grid_size) * grid_size
            grid_key = f"{grid_lon:.6f},{grid_lat:.6f}"
            
            if grid_key not in clusters_dict:
                clusters_dict[grid_key] = []
            
            clusters_dict[grid_key].append(stop)
        
        # Convert to list of clusters
        clusters = list(clusters_dict.values())
        
        return clusters
    
    def _analyze_cluster(self, cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze a cluster of stops and calculate statistics.
        
        Returns location data with statistics.
        """
        if not cluster:
            return None
        
        # Calculate centroid
        total_lon = 0
        total_lat = 0
        total_readings = 0
        unique_containers = set()
        first_seen = None
        last_seen = None
        total_duration = 0
        
        for stop in cluster:
            coords = stop["location"]["coordinates"]
            total_lon += coords[0]
            total_lat += coords[1]
            total_readings += stop["readings_count"]
            unique_containers.add(stop["container_id"])
            
            if first_seen is None or stop["first_seen"] < first_seen:
                first_seen = stop["first_seen"]
            if last_seen is None or stop["last_seen"] > last_seen:
                last_seen = stop["last_seen"]
            
            total_duration += stop["duration_seconds"]
        
        n = len(cluster)
        centroid_lon = total_lon / n
        centroid_lat = total_lat / n
        
        # Calculate confidence score
        # Based on: number of containers, total readings, time span
        container_count = len(unique_containers)
        time_span_days = (last_seen - first_seen).total_seconds() / 86400 if last_seen > first_seen else 1
        
        # Normalize factors (0-1 scale)
        container_factor = min(container_count / 50.0, 1.0)  # Max at 50 containers
        readings_factor = min(total_readings / 500.0, 1.0)  # Max at 500 readings
        time_factor = min(time_span_days / 30.0, 1.0)  # Max at 30 days
        
        # Weighted confidence score
        confidence_score = (
            0.5 * container_factor +
            0.3 * readings_factor +
            0.2 * time_factor
        )
        
        avg_stop_duration = total_duration / n if n > 0 else 0
        
        return {
            "location": {
                "type": "Point",
                "coordinates": [centroid_lon, centroid_lat]
            },
            "first_seen": first_seen,
            "last_seen": last_seen,
            "unique_container_count": container_count,
            "total_readings": total_readings,
            "avg_stop_duration_seconds": avg_stop_duration,
            "confidence_score": confidence_score,
            "stops_count": n
        }
    
    def _check_existing_location(self, location: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if a location already exists in locations or potential_locations.
        
        Uses geospatial query to find nearby locations.
        """
        coords = location["coordinates"]
        lon, lat = coords[0], coords[1]
        
        # Check in potential_locations first (within 500m)
        # Use aggregation with $geoNear for better control
        try:
            pipeline = [
                {
                    "$geoNear": {
                        "near": location,
                        "distanceField": "distance",
                        "maxDistance": 500,  # 500 meters
                        "spherical": True,
                        "query": {"status": {"$ne": "rejected"}}
                    }
                },
                {"$limit": 1}
            ]
            results = list(self.potential_locations.aggregate(pipeline))
            if results:
                return results[0]
        except Exception:
            # Fallback to simple distance calculation if geoNear fails
            # This is less efficient but works without indexes
            all_potential = list(self.potential_locations.find({"status": {"$ne": "rejected"}}))
            for loc in all_potential:
                if "location" in loc and "coordinates" in loc["location"]:
                    existing_coords = loc["location"]["coordinates"]
                    distance = self._calculate_distance(lon, lat, existing_coords[0], existing_coords[1])
                    if distance <= 500:  # 500 meters
                        return loc
        
        # Check in locations collection (within 1000m)
        try:
            pipeline = [
                {
                    "$geoNear": {
                        "near": location,
                        "distanceField": "distance",
                        "maxDistance": 1000,  # 1000 meters
                        "spherical": True
                    }
                },
                {"$limit": 1}
            ]
            results = list(self.locations.aggregate(pipeline))
            if results:
                return results[0]
        except Exception:
            # Fallback
            all_locations = list(self.locations.find({}))
            for loc in all_locations:
                if "location" in loc and "coordinates" in loc["location"]:
                    existing_coords = loc["location"]["coordinates"]
                    distance = self._calculate_distance(lon, lat, existing_coords[0], existing_coords[1])
                    if distance <= 1000:  # 1000 meters
                        return loc
        
        return None
    
    def _calculate_distance(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        Calculate distance between two points in meters using Haversine formula.
        """
        from math import radians, sin, cos, sqrt, atan2
        
        # Earth's radius in meters
        R = 6371000
        
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)
        
        a = (sin(delta_lat / 2) ** 2 +
             cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2)
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    def _create_potential_location(self, location_data: Dict[str, Any]):
        """Create a new potential location document."""
        doc = {
            "location": location_data["location"],
            "first_seen": location_data["first_seen"],
            "last_seen": location_data["last_seen"],
            "unique_container_count": location_data["unique_container_count"],
            "total_readings": location_data["total_readings"],
            "avg_stop_duration_seconds": location_data["avg_stop_duration_seconds"],
            "confidence_score": location_data["confidence_score"],
            "stops_count": location_data["stops_count"],
            "status": "pending_review",
            "detected_at": datetime.utcnow(),
            "metadata": {}
        }
        
        self.potential_locations.insert_one(doc)
    
    def _update_potential_location(self, location_id, location_data: Dict[str, Any]):
        """Update an existing potential location with new data."""
        update = {
            "$set": {
                "last_seen": location_data["last_seen"],
                "unique_container_count": location_data["unique_container_count"],
                "total_readings": location_data["total_readings"],
                "avg_stop_duration_seconds": location_data["avg_stop_duration_seconds"],
                "confidence_score": location_data["confidence_score"],
                "stops_count": location_data["stops_count"],
                "detected_at": datetime.utcnow()
            },
            "$setOnInsert": {
                "first_seen": location_data["first_seen"],
                "location": location_data["location"],
                "status": "pending_review"
            }
        }
        
        self.potential_locations.update_one(
            {"_id": location_id},
            update,
            upsert=False
        )
    
    def get_potential_locations(
        self,
        status: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 100,
        skip: int = 0
    ) -> Dict[str, Any]:
        """Get list of potential locations with filters."""
        query = {}
        
        if status:
            query["status"] = status
        
        if min_confidence is not None:
            query["confidence_score"] = {"$gte": min_confidence}
        
        total = self.potential_locations.count_documents(query)
        
        cursor = self.potential_locations.find(query).sort("confidence_score", -1).skip(skip).limit(limit)
        locations = list(cursor)
        
        return {
            "locations": locations,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    
    def approve_location(self, location_id: str) -> Dict[str, Any]:
        """Approve a potential location and copy it to locations collection."""
        from bson import ObjectId
        
        potential_loc = self.potential_locations.find_one({"_id": ObjectId(location_id)})
        
        if not potential_loc:
            raise ValueError(f"Potential location {location_id} not found")
        
        if potential_loc["status"] == "approved":
            return {"success": True, "message": "Location already approved"}
        
        # Create location document
        location_doc = {
            "name": f"Detected Location {location_id[:8]}",
            "type": "storage_facility",
            "location": potential_loc["location"],
            "detected_from_containers": True,
            "original_potential_location_id": location_id,
            "unique_container_count": potential_loc.get("unique_container_count", 0),
            "confidence_score": potential_loc.get("confidence_score", 0),
            "first_seen": potential_loc.get("first_seen"),
            "last_seen": potential_loc.get("last_seen"),
            "created_at": datetime.utcnow()
        }
        
        # Insert into locations
        result = self.locations.insert_one(location_doc)
        
        # Update potential location status
        self.potential_locations.update_one(
            {"_id": ObjectId(location_id)},
            {
                "$set": {
                    "status": "approved",
                    "approved_at": datetime.utcnow(),
                    "location_id": str(result.inserted_id)
                }
            }
        )
        
        return {
            "success": True,
            "message": "Location approved and added to locations collection",
            "location_id": str(result.inserted_id),
            "potential_location_id": location_id
        }
    
    def reject_location(self, location_id: str) -> Dict[str, Any]:
        """Reject a potential location."""
        from bson import ObjectId
        
        result = self.potential_locations.update_one(
            {"_id": ObjectId(location_id)},
            {
                "$set": {
                    "status": "rejected",
                    "rejected_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise ValueError(f"Potential location {location_id} not found")
        
        return {
            "success": True,
            "message": "Location rejected",
            "potential_location_id": location_id
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about potential locations."""
        total = self.potential_locations.count_documents({})
        pending = self.potential_locations.count_documents({"status": "pending_review"})
        approved = self.potential_locations.count_documents({"status": "approved"})
        rejected = self.potential_locations.count_documents({"status": "rejected"})
        
        # Average confidence score
        pipeline = [
            {"$group": {
                "_id": None,
                "avg_confidence": {"$avg": "$confidence_score"},
                "max_confidence": {"$max": "$confidence_score"},
                "min_confidence": {"$min": "$confidence_score"}
            }}
        ]
        stats_result = list(self.potential_locations.aggregate(pipeline))
        
        stats = {
            "total": total,
            "pending_review": pending,
            "approved": approved,
            "rejected": rejected
        }
        
        if stats_result:
            stats.update(stats_result[0])
            del stats["_id"]
        
        return stats


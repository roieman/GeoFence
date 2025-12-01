"""
FastAPI backend for GeoFence container tracking application.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import Optional, List
import os
import subprocess
import signal
from dotenv import load_dotenv
from bson import ObjectId
import json

load_dotenv()

app = FastAPI(title="GeoFence API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection - Support DEBUG mode for localhost
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

if DEBUG_MODE:
    # In DEBUG mode, always use localhost MongoDB (ignore MONGODB_URI from .env)
    connection_string = "mongodb://localhost:27017/"
    print("🔧 DEBUG MODE: Using localhost MongoDB")
    print(f"   Connection: {connection_string}")
    print("   (MONGODB_URI from .env is ignored in DEBUG mode)")
else:
    # Use Atlas or configured MongoDB
    connection_string = os.getenv("MONGODB_URI")
    if not connection_string:
        raise ValueError("MONGODB_URI environment variable not set (or set DEBUG=true for localhost)")

if not connection_string:
    raise ValueError("MongoDB connection string not configured")

# Configure MongoDB client with timeouts to prevent hanging
client = MongoClient(
    connection_string,
    serverSelectionTimeoutMS=5000,  # 5 seconds to select server
    connectTimeoutMS=10000,  # 10 seconds to connect
    socketTimeoutMS=300000,  # 5 minutes for operations (for long queries)
    maxPoolSize=50,
    retryWrites=True
)
db = client["geofence"]
containers = db["containers_regular"]  # Regular collection (not TimeSeries)
containers_timeseries = db["containers"]  # TimeSeries collection
locations = db["locations"]
alerts = db["alerts"]

# Alert generation process management
alert_generation_process = None

# Log connection info
if DEBUG_MODE:
    print(f"   Database: {db.name}")
    print(f"   Collections: {db.list_collection_names()}")


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for ObjectId and datetime."""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def serialize_doc(doc):
    """Serialize MongoDB document to JSON-compatible dict."""
    if doc is None:
        return None
    if isinstance(doc, dict):
        return {k: serialize_doc(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc


@app.get("/")
async def root():
    return {"message": "GeoFence API", "version": "1.0.0"}


@app.get("/api/containers/{container_id}/track")
async def track_container(
    container_id: str,
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)")
):
    """
    Get movement history for a specific container.
    Returns all location readings for the container.
    """
    try:
        query = {"metadata.container_id": container_id}
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query["timestamp"] = {"$gte": start_dt}
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if "timestamp" in query:
                query["timestamp"]["$lte"] = end_dt
            else:
                query["timestamp"] = {"$lte": end_dt}
        
        cursor = containers.find(query).sort("timestamp", 1)
        results = list(cursor)
        
        if not results:
            raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
        
        # Get container metadata from first result
        metadata = results[0].get("metadata", {})
        
        # Format results
        movements = []
        for doc in results:
            movements.append({
                "timestamp": doc.get("timestamp"),
                "location": doc.get("location"),
                "status": doc.get("status"),
                "weight_kg": doc.get("weight_kg"),
                "temperature_celsius": doc.get("temperature_celsius"),
                "speed_knots": doc.get("speed_knots")
            })
        
        return {
            "container_id": container_id,
            "metadata": metadata,
            "movements": serialize_doc(movements),
            "total_readings": len(movements)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
async def get_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    container_id: Optional[str] = Query(None),
    shipping_line: Optional[str] = Query(None),
    location_name: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Get alerts with filtering options.
    """
    try:
        query = {}
        
        if container_id:
            query["container.container_id"] = container_id
        
        if shipping_line:
            query["container.shipping_line"] = shipping_line
        
        if location_name:
            query["location.name"] = {"$regex": location_name, "$options": "i"}
        
        if acknowledged is not None:
            query["acknowledged"] = acknowledged
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query["timestamp"] = {"$gte": start_dt}
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if "timestamp" in query:
                query["timestamp"]["$lte"] = end_dt
            else:
                query["timestamp"] = {"$lte": end_dt}
        
        # Get total count
        total = alerts.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * limit
        cursor = alerts.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        results = list(cursor)
        
        return {
            "alerts": serialize_doc(results),
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    try:
        result = alerts.update_one(
            {"_id": ObjectId(alert_id)},
            {"$set": {"acknowledged": True, "acknowledged_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"success": True, "alert_id": alert_id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/locations/static")
async def get_static_locations():
    """Get the 10 static locations for the UI dropdown."""
    try:
        # Load static locations from file
        import json
        import os
        
        file_path = os.path.join(os.path.dirname(__file__), "sample_locations.json")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                locations_data = json.load(f)
            # locations_data is already a list, serialize each item
            if isinstance(locations_data, list):
                serialized_locations = [serialize_doc(loc) for loc in locations_data]
            else:
                serialized_locations = [serialize_doc(locations_data)]
            return {"locations": serialized_locations}
        else:
            # Fallback: return empty array
            print(f"Warning: sample_locations.json not found at {file_path}")
            return {"locations": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/locations")
async def get_locations(
    search: Optional[str] = Query(None),
    location_type: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=500)  # Default to 10 for autocomplete
):
    """Get list of locations with Atlas Search autocomplete support (disabled in DEBUG mode)."""
    try:
        # If no search query, return first locations from DB
        if not search:
            query = {}
            if location_type:
                query["type"] = location_type
            results = list(locations.find(query).limit(limit))
            if DEBUG_MODE:
                print(f"🔧 DEBUG: Returning {len(results)} locations from local DB (no search)")
            return {"locations": serialize_doc(results)}
        
        # If search query provided
        if search:
            # In DEBUG mode, skip Atlas Search and use regex queries only
            if DEBUG_MODE:
                print(f"🔧 DEBUG: Using regex search (Atlas Search disabled in DEBUG mode)")
                query = {
                    "$or": [
                        {"name": {"$regex": search, "$options": "i"}},
                        {"city": {"$regex": search, "$options": "i"}},
                        {"country": {"$regex": search, "$options": "i"}}
                    ]
                }
                
                if location_type:
                    query["type"] = location_type
                
                cursor = locations.find(query, {"name": 1, "type": 1, "city": 1, "country": 1, "location": 1}).limit(limit)
                results = list(cursor)
                print(f"🔧 DEBUG: Found {len(results)} locations matching '{search}'")
                return {"locations": serialize_doc(results)}
            
            # Production mode: Use Atlas Search with autocomplete
            search_index_name = "default"
            
            # Build the search aggregation pipeline
            pipeline = [
                {
                    "$search": {
                        "index": search_index_name,
                        "compound": {
                            "should": [
                                {"autocomplete": {"query": search, "path": "name"}},
                                {"autocomplete": {"query": search, "path": "city"}},
                                {"autocomplete": {"query": search, "path": "country"}}
                            ],
                            "minimumShouldMatch": 1
                        }
                    }
                },
                {
                    "$limit": limit
                },
                {
                    "$project": {
                        "name": 1,
                        "type": 1,
                        "city": 1,
                        "country": 1,
                        "location": 1,
                        "score": {"$meta": "searchScore"}
                    }
                }
            ]
            
            # Add location_type filter if specified
            if location_type:
                pipeline.insert(-1, {"$match": {"type": location_type}})
            
            try:
                # Add timeout to prevent hanging (10 seconds max for search)
                results = list(locations.aggregate(pipeline, maxTimeMS=10000))
                if results:
                    has_search_score = any('score' in r for r in results)
                    if has_search_score:
                        print(f"✓ Using Atlas Search for query: '{search}'")
                    return {"locations": serialize_doc(results)}
                else:
                    raise Exception("No results from Atlas Search")
            except Exception as search_error:
                # Fallback to regex if Atlas Search is not available
                error_msg = str(search_error)
                if "index" in error_msg.lower() or "not found" in error_msg.lower():
                    print(f"⚠ Atlas Search index not found, using regex fallback")
                else:
                    print(f"⚠ Atlas Search error, using regex fallback: {error_msg[:100]}")
                
                query = {
                    "$or": [
                        {"name": {"$regex": search, "$options": "i"}},
                        {"city": {"$regex": search, "$options": "i"}},
                        {"country": {"$regex": search, "$options": "i"}}
                    ]
                }
                
                if location_type:
                    query["type"] = location_type
                
                cursor = locations.find(query, {"name": 1, "type": 1, "city": 1, "country": 1, "location": 1}).limit(limit)
                results = list(cursor)
                return {"locations": serialize_doc(results)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/locations/{location_name}/containers")
async def get_containers_at_location(
    location_name: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    radius_meters: float = Query(10000, ge=0),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get containers that passed through a specific location within a time period.
    Handles both Point (with radius) and Polygon (within polygon) locations.
    """
    try:
        # Find the location
        location = locations.find_one({"name": location_name})
        
        if not location:
            raise HTTPException(status_code=404, detail=f"Location '{location_name}' not found")
        
        location_geo = location.get("location", {})
        location_type = location_geo.get("type")
        
        # Build time query
        time_query = {}
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            time_query["$gte"] = start_dt
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            time_query["$lte"] = end_dt
        
        # Build aggregation pipeline based on location type
        if location_type == "Point":
            # For Point: use $geoNear with radius
            coordinates = location_geo.get("coordinates")
            center_lon, center_lat = coordinates[0], coordinates[1]
            
            pipeline = [
                {
                    "$geoNear": {
                        "near": {
                            "type": "Point",
                            "coordinates": [center_lon, center_lat]
                        },
                        "distanceField": "distance",
                        "maxDistance": radius_meters,
                        "spherical": True
                        # Note: "key" parameter is only for TimeSeries collections
                    }
                }
            ]
            
            # Add time filters
            if time_query:
                pipeline.append({"$match": {"timestamp": time_query}})
            
            # Group by container ID - get LAST entry of each container
            pipeline.extend([
                {
                    "$sort": {"timestamp": 1}  # Sort by timestamp ascending first
                },
                {
                    "$group": {
                        "_id": "$metadata.container_id",
                        "container_id": {"$last": "$metadata.container_id"},
                        "shipping_line": {"$last": "$metadata.shipping_line"},
                        "container_type": {"$last": "$metadata.container_type"},
                        "refrigerated": {"$last": "$metadata.refrigerated"},
                        "cargo_type": {"$last": "$metadata.cargo_type"},
                        "first_seen": {"$min": "$timestamp"},
                        "last_seen": {"$max": "$timestamp"},
                        "min_distance": {"$min": "$distance"},
                        "readings_count": {"$sum": 1},
                        "last_location": {"$last": "$location"},
                        "last_status": {"$last": "$status"},
                        "last_weight_kg": {"$last": "$weight_kg"},
                        "last_temperature_celsius": {"$last": "$temperature_celsius"},
                        "last_speed_knots": {"$last": "$speed_knots"}
                    }
                },
                {"$sort": {"last_seen": -1}},  # Sort by last seen descending
                {"$skip": (page - 1) * limit},
                {"$limit": limit}
            ])
            
        elif location_type == "Polygon":
            # For Polygon: use $geoWithin (ignore radius parameter)
            polygon_geometry = location_geo
            
            # Build match query for containers within polygon
            match_query = {
                "location": {
                    "$geoWithin": {
                        "$geometry": polygon_geometry
                    }
                }
            }
            
            # Add time filters to match query
            if time_query:
                match_query["timestamp"] = time_query
            
            pipeline = [
                {"$match": match_query},
                {
                    "$sort": {"timestamp": 1}  # Sort by timestamp ascending first
                },
                {
                    "$group": {
                        "_id": "$metadata.container_id",
                        "container_id": {"$last": "$metadata.container_id"},
                        "shipping_line": {"$last": "$metadata.shipping_line"},
                        "container_type": {"$last": "$metadata.container_type"},
                        "refrigerated": {"$last": "$metadata.refrigerated"},
                        "cargo_type": {"$last": "$metadata.cargo_type"},
                        "first_seen": {"$min": "$timestamp"},
                        "last_seen": {"$max": "$timestamp"},
                        "readings_count": {"$sum": 1},
                        "last_location": {"$last": "$location"},
                        "last_status": {"$last": "$status"},
                        "last_weight_kg": {"$last": "$weight_kg"},
                        "last_temperature_celsius": {"$last": "$temperature_celsius"},
                        "last_speed_knots": {"$last": "$speed_knots"}
                    }
                },
                {"$sort": {"last_seen": -1}},  # Sort by last seen descending
                {"$skip": (page - 1) * limit},
                {"$limit": limit}
            ]
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported location type: {location_type}")
        
        # Execute aggregation and measure time
        import time
        start_time = time.time()
        # Add timeout to prevent hanging (30 seconds max)
        results = list(containers.aggregate(pipeline, maxTimeMS=30000))
        query_time = time.time() - start_time
        
        # Get total count (separate aggregation without skip/limit)
        # Rebuild count pipeline: copy all stages except pagination and final sort
        count_pipeline = []
        for stage in pipeline:
            stage_key = list(stage.keys())[0] if stage else None
            # Skip pagination stages
            if stage_key in ["$skip", "$limit"]:
                continue
            # For $group stage, replace with simpler grouping
            elif stage_key == "$group":
                count_pipeline.append({"$group": {"_id": "$metadata.container_id"}})
                break
            # For $sort after group, skip it (we'll add count instead)
            elif stage_key == "$sort" and any("$group" in str(s) for s in count_pipeline):
                continue
            else:
                count_pipeline.append(stage)
        
        # Add count stage
        count_pipeline.append({"$count": "total"})
        
        count_start_time = time.time()
        try:
            # Add timeout to prevent hanging (30 seconds max)
            count_result = list(containers.aggregate(count_pipeline, maxTimeMS=30000))
            total = count_result[0]["total"] if count_result else len(results)
        except Exception as e:
            # Fallback: count distinct container IDs from results
            print(f"Count pipeline error: {e}")
            # Use a simpler approach - just count the grouped results
            container_ids = set(r.get("container_id") for r in results if r.get("container_id"))
            total = len(container_ids) if container_ids else len(results)
        count_time = time.time() - count_start_time
        total_query_time = query_time + count_time
        
        return {
            "location": serialize_doc({
                "name": location_name,
                "type": location.get("type"),
                "city": location.get("city"),
                "country": location.get("country"),
                "location_type": location_type,  # Include geometry type for UI (Point or Polygon)
                "geometry_type": location_type,
                "location": location_geo  # Include full geometry for map display
            }),
            "containers": serialize_doc(results),
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            },
            "query_time_ms": round(total_query_time * 1000, 2)  # Query time in milliseconds
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = str(e)
        
        # Provide more specific error messages
        if "timeout" in error_msg.lower() or "maxTimeMS" in error_msg:
            raise HTTPException(
                status_code=504,
                detail="Query timeout. The search is taking too long. Try reducing the radius or date range."
            )
        elif "index" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="Database index error. Please contact support."
            )
        else:
            print(f"Error in container search: {error_msg}")
            print(f"Traceback: {error_trace}")
            raise HTTPException(
                status_code=500,
                detail=f"Search error: {error_msg[:200]}"  # Limit error message length
            )


@app.get("/api/locations/{location_name}/containers/timeseries")
async def get_containers_at_location_timeseries(
    location_name: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    radius_meters: float = Query(10000, ge=0),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get containers from TimeSeries collection that passed through a specific location within a time period.
    Handles both Point (with radius) and Polygon (within polygon) locations.
    This is the same logic as the regular endpoint but queries the TimeSeries collection.
    """
    try:
        # Find the location
        location = locations.find_one({"name": location_name})
        
        if not location:
            raise HTTPException(status_code=404, detail=f"Location '{location_name}' not found")
        
        location_geo = location.get("location", {})
        location_type = location_geo.get("type")
        
        # Build time query
        time_query = {}
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            time_query["$gte"] = start_dt
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            time_query["$lte"] = end_dt
        
        # Build aggregation pipeline based on location type
        if location_type == "Point":
            # For Point: use $geoNear with radius
            # IMPORTANT: TimeSeries collections require "key" parameter
            coordinates = location_geo.get("coordinates")
            center_lon, center_lat = coordinates[0], coordinates[1]
            
            pipeline = [
                {
                    "$geoNear": {
                        "near": {
                            "type": "Point",
                            "coordinates": [center_lon, center_lat]
                        },
                        "distanceField": "distance",
                        "maxDistance": radius_meters,
                        "spherical": True,
                        "key": "location"  # Required for TimeSeries collections
                    }
                }
            ]
            
            # Add time filters
            if time_query:
                pipeline.append({"$match": {"timestamp": time_query}})
            
            # Group by container ID - get LAST entry of each container
            pipeline.extend([
                {
                    "$sort": {"timestamp": 1}  # Sort by timestamp ascending first
                },
                {
                    "$group": {
                        "_id": "$metadata.container_id",
                        "container_id": {"$last": "$metadata.container_id"},
                        "shipping_line": {"$last": "$metadata.shipping_line"},
                        "container_type": {"$last": "$metadata.container_type"},
                        "refrigerated": {"$last": "$metadata.refrigerated"},
                        "cargo_type": {"$last": "$metadata.cargo_type"},
                        "first_seen": {"$min": "$timestamp"},
                        "last_seen": {"$max": "$timestamp"},
                        "min_distance": {"$min": "$distance"},
                        "readings_count": {"$sum": 1},
                        "last_location": {"$last": "$location"},
                        "last_status": {"$last": "$status"},
                        "last_weight_kg": {"$last": "$weight_kg"},
                        "last_temperature_celsius": {"$last": "$temperature_celsius"},
                        "last_speed_knots": {"$last": "$speed_knots"}
                    }
                },
                {"$sort": {"last_seen": -1}},  # Sort by last seen descending
                {"$skip": (page - 1) * limit},
                {"$limit": limit}
            ])
            
        elif location_type == "Polygon":
            # For Polygon: use $geoWithin (ignore radius parameter)
            polygon_geometry = location_geo
            
            # Build match query for containers within polygon
            match_query = {
                "location": {
                    "$geoWithin": {
                        "$geometry": polygon_geometry
                    }
                }
            }
            
            # Add time filters to match query
            if time_query:
                match_query["timestamp"] = time_query
            
            pipeline = [
                {"$match": match_query},
                {
                    "$sort": {"timestamp": 1}  # Sort by timestamp ascending first
                },
                {
                    "$group": {
                        "_id": "$metadata.container_id",
                        "container_id": {"$last": "$metadata.container_id"},
                        "shipping_line": {"$last": "$metadata.shipping_line"},
                        "container_type": {"$last": "$metadata.container_type"},
                        "refrigerated": {"$last": "$metadata.refrigerated"},
                        "cargo_type": {"$last": "$metadata.cargo_type"},
                        "first_seen": {"$min": "$timestamp"},
                        "last_seen": {"$max": "$timestamp"},
                        "readings_count": {"$sum": 1},
                        "last_location": {"$last": "$location"},
                        "last_status": {"$last": "$status"},
                        "last_weight_kg": {"$last": "$weight_kg"},
                        "last_temperature_celsius": {"$last": "$temperature_celsius"},
                        "last_speed_knots": {"$last": "$speed_knots"}
                    }
                },
                {"$sort": {"last_seen": -1}},  # Sort by last seen descending
                {"$skip": (page - 1) * limit},
                {"$limit": limit}
            ]
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported location type: {location_type}")
        
        # Execute aggregation on TimeSeries collection and measure time
        import time
        start_time = time.time()
        try:
            # Add timeout to prevent hanging (30 seconds max)
            results = list(containers_timeseries.aggregate(pipeline, maxTimeMS=30000))
        except Exception as agg_error:
            import traceback
            error_trace = traceback.format_exc()
            print(f"TimeSeries aggregation error: {str(agg_error)}")
            print(f"Traceback: {error_trace}")
            print(f"Pipeline: {pipeline}")
            raise HTTPException(status_code=500, detail=f"TimeSeries aggregation failed: {str(agg_error)}")
        query_time = time.time() - start_time
        
        # Get total count (separate aggregation without skip/limit)
        # Rebuild count pipeline: copy all stages except pagination and final sort
        count_pipeline = []
        for stage in pipeline:
            stage_key = list(stage.keys())[0] if stage else None
            # Skip pagination stages
            if stage_key in ["$skip", "$limit"]:
                continue
            # For $group stage, replace with simpler grouping
            elif stage_key == "$group":
                count_pipeline.append({"$group": {"_id": "$metadata.container_id"}})
                break
            # For $sort after group, skip it (we'll add count instead)
            elif stage_key == "$sort" and any("$group" in str(s) for s in count_pipeline):
                continue
            else:
                count_pipeline.append(stage)
        
        # Add count stage
        count_pipeline.append({"$count": "total"})
        
        count_start_time = time.time()
        try:
            # Add timeout to prevent hanging (30 seconds max)
            count_result = list(containers_timeseries.aggregate(count_pipeline, maxTimeMS=30000))
            total = count_result[0]["total"] if count_result else len(results)
        except Exception as e:
            # Fallback: count distinct container IDs from results
            print(f"Count pipeline error: {e}")
            # Use a simpler approach - just count the grouped results
            container_ids = set(r.get("container_id") for r in results if r.get("container_id"))
            total = len(container_ids) if container_ids else len(results)
        count_time = time.time() - count_start_time
        total_query_time = query_time + count_time
        
        return {
            "location": serialize_doc({
                "name": location_name,
                "type": location.get("type"),
                "city": location.get("city"),
                "country": location.get("country"),
                "location_type": location_type,  # Include geometry type for UI (Point or Polygon)
                "geometry_type": location_type,
                "location": location_geo  # Include full geometry for map display
            }),
            "containers": serialize_doc(results),
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            },
            "collection_type": "timeseries",  # Indicate this is from TimeSeries collection
            "query_time_ms": round(total_query_time * 1000, 2)  # Query time in milliseconds
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = str(e)
        
        # Provide more specific error messages
        if "timeout" in error_msg.lower() or "maxTimeMS" in error_msg:
            raise HTTPException(
                status_code=504,
                detail="Query timeout. The search is taking too long. Try reducing the radius or date range."
            )
        elif "index" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="Database index error. Please contact support."
            )
        else:
            print(f"Error in TimeSeries container search: {error_msg}")
            print(f"Traceback: {error_trace}")
            raise HTTPException(
                status_code=500,
                detail=f"TimeSeries search error: {error_msg[:200]}"  # Limit error message length
            )


@app.get("/api/stats")
async def get_stats():
    """Get general statistics."""
    try:
        # Use aggregation instead of distinct() to avoid 16MB limit
        # Count distinct container IDs using aggregation
        container_count_pipeline = [
            {"$group": {"_id": "$metadata.container_id"}},
            {"$count": "total"}
        ]
        container_count_result = list(containers.aggregate(container_count_pipeline, maxTimeMS=30000))
        total_containers = container_count_result[0]["total"] if container_count_result else 0
        
        total_alerts = alerts.count_documents({})
        unacknowledged_alerts = alerts.count_documents({"acknowledged": False})
        total_locations = locations.count_documents({})
        
        return {
            "total_containers": total_containers,
            "total_alerts": total_alerts,
            "unacknowledged_alerts": unacknowledged_alerts,
            "total_locations": total_locations
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alert-generation/status")
async def get_alert_generation_status():
    """Get the status of alert generation."""
    global alert_generation_process
    is_running = False
    
    if alert_generation_process:
        # Check if process is still running
        poll_result = alert_generation_process.poll()
        if poll_result is None:
            is_running = True
        else:
            # Process has ended
            alert_generation_process = None
    
    return {
        "running": is_running,
        "process_id": alert_generation_process.pid if alert_generation_process else None
    }


@app.post("/api/alert-generation/start")
async def start_alert_generation():
    """Start the alert generation script."""
    global alert_generation_process
    
    # Check if already running
    if alert_generation_process:
        poll_result = alert_generation_process.poll()
        if poll_result is None:
            return {"success": False, "message": "Alert generation is already running"}
        else:
            # Process has ended, clean up
            alert_generation_process = None
    
    try:
        # Get the script path (go up from app/backend to root, then to generate_alerts.py)
        backend_dir = os.path.dirname(__file__)
        root_dir = os.path.dirname(os.path.dirname(backend_dir))
        script_path = os.path.join(root_dir, "generate_alerts.py")
        
        if not os.path.exists(script_path):
            return {
                "success": False,
                "message": f"Script not found at {script_path}"
            }
        
        # Start the process (redirect output to log file for debugging)
        log_file_path = "/tmp/alert_generation.log"
        # Open in append mode and keep reference
        log_file = open(log_file_path, "a", buffering=1)  # Line buffered
        log_file.write(f"\n{'='*60}\n")
        log_file.write(f"Alert generation started at {datetime.utcnow()}\n")
        log_file.write(f"Process will be started with PID tracking\n")
        log_file.write(f"{'='*60}\n")
        log_file.flush()
        
        # Use unbuffered output and ensure Python output is flushed
        alert_generation_process = subprocess.Popen(
            ["python3", "-u", script_path],  # -u flag for unbuffered output
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=root_dir,
            start_new_session=True,  # Start in new session to detach from parent
            env=dict(os.environ, PYTHONUNBUFFERED="1")  # Force unbuffered
        )
        
        # Write process info to log
        log_file.write(f"Process started with PID: {alert_generation_process.pid}\n")
        log_file.flush()
        
        # Store file handle in a way that won't be garbage collected
        # Note: We can't easily keep it open, but the process should keep writing
        
        return {
            "success": True,
            "message": "Alert generation started",
            "process_id": alert_generation_process.pid
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to start alert generation: {str(e)}"
        }


@app.post("/api/alert-generation/stop")
async def stop_alert_generation():
    """Stop the alert generation script."""
    global alert_generation_process
    
    if not alert_generation_process:
        return {"success": False, "message": "Alert generation is not running"}
    
    try:
        # Try graceful termination first
        alert_generation_process.terminate()
        
        # Wait a bit for graceful shutdown
        try:
            alert_generation_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't stop
            alert_generation_process.kill()
            alert_generation_process.wait()
        
        alert_generation_process = None
        return {"success": True, "message": "Alert generation stopped"}
    except Exception as e:
        # Clean up even if there's an error
        alert_generation_process = None
        return {
            "success": False,
            "message": f"Error stopping alert generation: {str(e)}"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


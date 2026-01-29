"""
FastAPI backend for Zim GeoFence application.
New version using zim_geofence database with real Zim data.
"""

from fastapi import FastAPI, HTTPException, Query, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import os
import io
import csv
import json
from bson import ObjectId

import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import (
    MONGODB_URI, DB_NAME, COLLECTIONS, USE_TIMESERIES,
    DEBUG, GEOFENCE_TYPES, EVENT_TYPES
)

app = FastAPI(
    title="Zim GeoFence API",
    version="2.0.0",
    description="Geofencing and IoT tracking for Zim shipping containers"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
print(f"Connecting to MongoDB: {MONGODB_URI[:50]}...")
client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000,
    socketTimeoutMS=300000,
    maxPoolSize=50,
)
db = client[DB_NAME]

# Collections
geofences = db[COLLECTIONS["geofences"]]
iot_events = db[COLLECTIONS["iot_events"]]
iot_events_ts = db[COLLECTIONS["iot_events_ts"]]
gate_events = db[COLLECTIONS["gate_events"]]
containers = db[COLLECTIONS["containers"]]

print(f"Connected to database: {DB_NAME}")
print(f"Using TimeSeries: {USE_TIMESERIES}")


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


# =============================================================================
# ROOT & HEALTH
# =============================================================================

@app.get("/")
async def root():
    return {
        "message": "Zim GeoFence API",
        "version": "2.0.0",
        "database": DB_NAME,
        "use_timeseries": USE_TIMESERIES
    }


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    try:
        client.admin.command('ping')
        return {"status": "healthy", "database": DB_NAME}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get database statistics."""
    try:
        stats = {
            "geofences": geofences.count_documents({}),
            "iot_events": iot_events.count_documents({}),
            "gate_events": gate_events.count_documents({}),
            "containers": containers.count_documents({}),
        }

        # Geofences by type
        pipeline = [
            {"$group": {"_id": "$properties.typeId", "count": {"$sum": 1}}}
        ]
        stats["geofences_by_type"] = {
            doc["_id"]: doc["count"]
            for doc in geofences.aggregate(pipeline)
        }

        # Recent events count (last 24h)
        yesterday = datetime.utcnow() - timedelta(hours=24)
        stats["events_last_24h"] = iot_events.count_documents({
            "EventTime": {"$gte": yesterday}
        })

        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GEOFENCES CRUD
# =============================================================================

@app.get("/api/geofences")
async def list_geofences(
    type_id: Optional[str] = Query(None, description="Filter by type (Terminal, Depot, Rail ramp)"),
    search: Optional[str] = Query(None, description="Search by name, description, or codes"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=2000)
):
    """List geofences with filtering and pagination."""
    try:
        query = {}

        if type_id:
            query["properties.typeId"] = type_id

        if search:
            query["$or"] = [
                {"properties.name": {"$regex": search, "$options": "i"}},
                {"properties.description": {"$regex": search, "$options": "i"}},
                {"properties.UNLOCode": {"$regex": search, "$options": "i"}},
                {"properties.SMDGCode": {"$regex": search, "$options": "i"}},
            ]

        total = geofences.count_documents(query)
        skip = (page - 1) * limit

        cursor = geofences.find(query).skip(skip).limit(limit).sort("properties.name", ASCENDING)
        results = list(cursor)

        return {
            "geofences": serialize_doc(results),
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/geofences/{geofence_id}")
async def get_geofence(geofence_id: str):
    """Get a single geofence by ID."""
    try:
        doc = geofences.find_one({"_id": ObjectId(geofence_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Geofence not found")
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/geofences/by-name/{name}")
async def get_geofence_by_name(name: str):
    """Get a geofence by name."""
    try:
        doc = geofences.find_one({"properties.name": name})
        if not doc:
            raise HTTPException(status_code=404, detail="Geofence not found")
        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/geofences")
async def create_geofence(geofence: dict = Body(...)):
    """
    Create a new geofence.

    Expected body:
    {
        "name": "USNYC-NEW",
        "description": "New York Terminal",
        "typeId": "Terminal",
        "UNLOCode": "USNYC",
        "SMDGCode": "NYT",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[lon, lat], [lon, lat], ...]]
        }
    }
    """
    try:
        # Validate required fields
        required = ["name", "typeId", "geometry"]
        for field in required:
            if field not in geofence:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        # Check name uniqueness
        existing = geofences.find_one({"properties.name": geofence["name"]})
        if existing:
            raise HTTPException(status_code=409, detail=f"Geofence with name '{geofence['name']}' already exists")

        # Validate geometry
        geometry = geofence["geometry"]
        if geometry.get("type") != "Polygon":
            raise HTTPException(status_code=400, detail="Geometry must be a Polygon")

        # Create document in GeoJSON format
        doc = {
            "type": "Feature",
            "properties": {
                "name": geofence["name"],
                "description": geofence.get("description", ""),
                "typeId": geofence["typeId"],
                "UNLOCode": geofence.get("UNLOCode", ""),
                "SMDGCode": geofence.get("SMDGCode", ""),
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            },
            "geometry": geometry
        }

        result = geofences.insert_one(doc)
        doc["_id"] = result.inserted_id

        return serialize_doc(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/geofences/{geofence_id}")
async def update_geofence(geofence_id: str, updates: dict = Body(...)):
    """
    Update a geofence.

    Can update: name, description, typeId, UNLOCode, SMDGCode, geometry
    """
    try:
        # Check exists
        existing = geofences.find_one({"_id": ObjectId(geofence_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Geofence not found")

        # Build update
        update_doc = {"$set": {"properties.updatedAt": datetime.utcnow()}}

        if "name" in updates:
            # Check name uniqueness
            other = geofences.find_one({
                "properties.name": updates["name"],
                "_id": {"$ne": ObjectId(geofence_id)}
            })
            if other:
                raise HTTPException(status_code=409, detail=f"Name '{updates['name']}' already in use")
            update_doc["$set"]["properties.name"] = updates["name"]

        if "description" in updates:
            update_doc["$set"]["properties.description"] = updates["description"]

        if "typeId" in updates:
            if updates["typeId"] not in GEOFENCE_TYPES:
                raise HTTPException(status_code=400, detail=f"Invalid typeId. Must be one of: {GEOFENCE_TYPES}")
            update_doc["$set"]["properties.typeId"] = updates["typeId"]

        if "UNLOCode" in updates:
            update_doc["$set"]["properties.UNLOCode"] = updates["UNLOCode"]

        if "SMDGCode" in updates:
            update_doc["$set"]["properties.SMDGCode"] = updates["SMDGCode"]

        if "geometry" in updates:
            if updates["geometry"].get("type") != "Polygon":
                raise HTTPException(status_code=400, detail="Geometry must be a Polygon")
            update_doc["$set"]["geometry"] = updates["geometry"]

        geofences.update_one({"_id": ObjectId(geofence_id)}, update_doc)

        # Return updated document
        updated = geofences.find_one({"_id": ObjectId(geofence_id)})
        return serialize_doc(updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/geofences/{geofence_id}")
async def delete_geofence(geofence_id: str):
    """Delete a geofence."""
    try:
        result = geofences.delete_one({"_id": ObjectId(geofence_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Geofence not found")
        return {"success": True, "deleted_id": geofence_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GEOFENCE IMPORT/EXPORT
# =============================================================================

@app.get("/api/geofences/export/csv")
async def export_geofences_csv(
    type_id: Optional[str] = Query(None, description="Filter by type")
):
    """Export geofences as CSV file."""
    try:
        query = {}
        if type_id:
            query["properties.typeId"] = type_id

        cursor = geofences.find(query).sort("properties.name", ASCENDING)

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "name", "description", "typeId", "UNLOCode", "SMDGCode", "geometry_wkt"
        ])

        # Data rows
        for doc in cursor:
            props = doc.get("properties", {})
            geometry = doc.get("geometry", {})

            # Convert geometry to WKT format
            coords = geometry.get("coordinates", [[]])
            if coords and coords[0]:
                wkt_coords = ", ".join([f"{p[0]} {p[1]}" for p in coords[0]])
                wkt = f"POLYGON(({wkt_coords}))"
            else:
                wkt = ""

            writer.writerow([
                props.get("name", ""),
                props.get("description", ""),
                props.get("typeId", ""),
                props.get("UNLOCode", ""),
                props.get("SMDGCode", ""),
                wkt
            ])

        output.seek(0)

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=geofences.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/geofences/export/geojson")
async def export_geofences_geojson(
    type_id: Optional[str] = Query(None, description="Filter by type")
):
    """Export geofences as GeoJSON file."""
    try:
        query = {}
        if type_id:
            query["properties.typeId"] = type_id

        cursor = geofences.find(query).sort("properties.name", ASCENDING)

        features = []
        for doc in cursor:
            feature = {
                "type": "Feature",
                "properties": doc.get("properties", {}),
                "geometry": doc.get("geometry", {})
            }
            # Remove MongoDB-specific fields from properties
            if "_id" in feature["properties"]:
                del feature["properties"]["_id"]
            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        output = json.dumps(geojson, indent=2, default=str)

        return StreamingResponse(
            io.BytesIO(output.encode('utf-8')),
            media_type="application/geo+json",
            headers={"Content-Disposition": "attachment; filename=geofences.geojson"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/geofences/import/csv")
async def import_geofences_csv(file: UploadFile = File(...)):
    """
    Import geofences from CSV file.

    Expected columns: name, description, typeId, UNLOCode, SMDGCode, geometry_wkt
    geometry_wkt should be WKT format: POLYGON((lon lat, lon lat, ...))
    """
    try:
        content = await file.read()
        text = content.decode('utf-8')

        reader = csv.DictReader(io.StringIO(text))

        imported = 0
        updated = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            try:
                name = row.get("name", "").strip()
                if not name:
                    errors.append(f"Row {row_num}: Missing name")
                    continue

                # Parse WKT geometry
                wkt = row.get("geometry_wkt", "").strip()
                geometry = None
                if wkt.startswith("POLYGON"):
                    # Extract coordinates from WKT
                    coords_str = wkt.replace("POLYGON((", "").replace("))", "")
                    coords = []
                    for point in coords_str.split(","):
                        parts = point.strip().split()
                        if len(parts) >= 2:
                            coords.append([float(parts[0]), float(parts[1])])

                    if coords:
                        geometry = {"type": "Polygon", "coordinates": [coords]}

                if not geometry:
                    errors.append(f"Row {row_num}: Invalid geometry for {name}")
                    continue

                # Create document
                doc = {
                    "type": "Feature",
                    "properties": {
                        "name": name,
                        "description": row.get("description", ""),
                        "typeId": row.get("typeId", "Depot"),
                        "UNLOCode": row.get("UNLOCode", ""),
                        "SMDGCode": row.get("SMDGCode", ""),
                        "updatedAt": datetime.utcnow(),
                    },
                    "geometry": geometry
                }

                # Upsert
                result = geofences.update_one(
                    {"properties.name": name},
                    {"$set": doc, "$setOnInsert": {"properties.createdAt": datetime.utcnow()}},
                    upsert=True
                )

                if result.upserted_id:
                    imported += 1
                else:
                    updated += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        return {
            "success": True,
            "imported": imported,
            "updated": updated,
            "errors": errors[:20]  # Limit error messages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# IOT EVENTS
# =============================================================================

@app.get("/api/iot-events")
async def list_iot_events(
    container_id: Optional[str] = Query(None, alias="assetname"),
    tracker_id: Optional[str] = Query(None, alias="TrackerID"),
    event_type: Optional[str] = Query(None, alias="EventType"),
    location: Optional[str] = Query(None, alias="EventLocation"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000)
):
    """List IoT events with filtering."""
    try:
        # Choose collection based on config
        collection = iot_events_ts if USE_TIMESERIES else iot_events

        query = {}

        if container_id:
            if USE_TIMESERIES:
                query["metadata.assetname"] = container_id
            else:
                query["assetname"] = container_id

        if tracker_id:
            if USE_TIMESERIES:
                query["metadata.TrackerID"] = tracker_id
            else:
                query["TrackerID"] = tracker_id

        if event_type:
            query["EventType"] = event_type

        if location:
            query["EventLocation"] = {"$regex": location, "$options": "i"}

        time_field = "timestamp" if USE_TIMESERIES else "EventTime"

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query[time_field] = {"$gte": start_dt}

        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if time_field in query:
                query[time_field]["$lte"] = end_dt
            else:
                query[time_field] = {"$lte": end_dt}

        total = collection.count_documents(query)
        skip = (page - 1) * limit

        cursor = collection.find(query).sort(time_field, DESCENDING).skip(skip).limit(limit)
        results = list(cursor)

        return {
            "events": serialize_doc(results),
            "collection_type": "timeseries" if USE_TIMESERIES else "regular",
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/iot-events/latest")
async def get_latest_iot_events(limit: int = Query(50, ge=1, le=500)):
    """Get the most recent IoT events (for live map)."""
    try:
        collection = iot_events_ts if USE_TIMESERIES else iot_events
        time_field = "timestamp" if USE_TIMESERIES else "EventTime"

        cursor = collection.find().sort(time_field, DESCENDING).limit(limit)
        results = list(cursor)

        return {"events": serialize_doc(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/iot-events/by-container/{container_id}")
async def get_container_events(
    container_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000)
):
    """Get all events for a specific container (for tracking map)."""
    try:
        collection = iot_events_ts if USE_TIMESERIES else iot_events

        if USE_TIMESERIES:
            query = {"metadata.assetname": container_id}
            time_field = "timestamp"
        else:
            query = {"assetname": container_id}
            time_field = "EventTime"

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query[time_field] = {"$gte": start_dt}

        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if time_field in query:
                query[time_field]["$lte"] = end_dt
            else:
                query[time_field] = {"$lte": end_dt}

        cursor = collection.find(query).sort(time_field, ASCENDING).limit(limit)
        results = list(cursor)

        return {
            "container_id": container_id,
            "events": serialize_doc(results),
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GATE EVENTS (Geofence Crossings)
# =============================================================================

@app.get("/api/gate-events")
async def list_gate_events(
    container_id: Optional[str] = Query(None),
    geofence_name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, description="Gate In or Gate Out"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000)
):
    """List gate events (geofence crossings)."""
    try:
        query = {}

        if container_id:
            query["assetname"] = container_id

        if geofence_name:
            query["geofence_name"] = {"$regex": geofence_name, "$options": "i"}

        if event_type:
            query["EventType"] = event_type

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query["EventTime"] = {"$gte": start_dt}

        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if "EventTime" in query:
                query["EventTime"]["$lte"] = end_dt
            else:
                query["EventTime"] = {"$lte": end_dt}

        total = gate_events.count_documents(query)
        skip = (page - 1) * limit

        cursor = gate_events.find(query).sort("EventTime", DESCENDING).skip(skip).limit(limit)
        results = list(cursor)

        return {
            "events": serialize_doc(results),
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# CONTAINERS
# =============================================================================

@app.get("/api/containers")
async def list_containers(
    state: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000)
):
    """List all containers being tracked."""
    try:
        query = {}
        if state:
            query["state"] = state

        total = containers.count_documents(query)
        skip = (page - 1) * limit

        cursor = containers.find(query).skip(skip).limit(limit)
        results = list(cursor)

        return {
            "containers": serialize_doc(results),
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/containers/{container_id}")
async def get_container(container_id: str):
    """Get container details."""
    try:
        doc = containers.find_one({"container_id": container_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Container not found")
        return serialize_doc(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/containers/positions/latest")
async def get_container_positions():
    """Get latest position of all containers (for live map)."""
    try:
        cursor = containers.find(
            {},
            {"container_id": 1, "tracker_id": 1, "latitude": 1, "longitude": 1,
             "state": 1, "is_moving": 1, "current_geofence": 1}
        )
        results = list(cursor)
        return {"containers": serialize_doc(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GEOSPATIAL QUERIES
# =============================================================================

@app.get("/api/geofences/at-point")
async def get_geofences_at_point(
    lon: float = Query(..., description="Longitude"),
    lat: float = Query(..., description="Latitude")
):
    """Find all geofences containing a point."""
    try:
        results = geofences.find({
            "geometry": {
                "$geoIntersects": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                }
            }
        })
        return {"geofences": serialize_doc(list(results))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/iot-events/in-geofence/{geofence_name}")
async def get_events_in_geofence(
    geofence_name: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get IoT events that occurred within a specific geofence."""
    try:
        # Get geofence
        geofence = geofences.find_one({"properties.name": geofence_name})
        if not geofence:
            raise HTTPException(status_code=404, detail="Geofence not found")

        geometry = geofence.get("geometry")

        collection = iot_events_ts if USE_TIMESERIES else iot_events
        time_field = "timestamp" if USE_TIMESERIES else "EventTime"

        query = {
            "location": {
                "$geoWithin": {
                    "$geometry": geometry
                }
            }
        }

        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query[time_field] = {"$gte": start_dt}

        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if time_field in query:
                query[time_field]["$lte"] = end_dt
            else:
                query[time_field] = {"$lte": end_dt}

        cursor = collection.find(query).sort(time_field, DESCENDING).limit(limit)
        results = list(cursor)

        return {
            "geofence": serialize_doc(geofence),
            "events": serialize_doc(results),
            "count": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# REFERENCE DATA
# =============================================================================

@app.get("/api/reference/geofence-types")
async def get_geofence_types():
    """Get available geofence types."""
    return {"types": GEOFENCE_TYPES}


@app.get("/api/reference/event-types")
async def get_event_types():
    """Get available event types."""
    return {"types": EVENT_TYPES}


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

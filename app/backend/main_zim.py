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
    DEBUG, GEOFENCE_TYPES, EVENT_TYPES, IOT_PROVIDERS,
    USER_ROLES, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS,
    EXTERNAL_WEBHOOKS
)
import hashlib
import secrets
import httpx
from typing import Annotated
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt as pyjwt

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
clusters = db[COLLECTIONS["clusters"]]  # Geofence clusters (groups)
iot_events = db[COLLECTIONS["iot_events"]]
iot_events_ts = db[COLLECTIONS["iot_events_ts"]]
gate_events = db[COLLECTIONS["gate_events"]]
containers = db[COLLECTIONS["containers"]]

# New collections for auth, webhooks, notifications
users = db["users"]
webhooks = db["webhooks"]  # Registered webhooks for API In/Out
notifications = db["notifications"]  # Alert notifications
api_keys = db["api_keys"]  # API keys for external systems

# Security
security = HTTPBearer(auto_error=False)

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
# AUTHENTICATION HELPERS
# =============================================================================

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode())
    return f"{salt}:{hash_obj.hexdigest()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against stored hash."""
    try:
        salt, hash_value = stored_hash.split(":")
        hash_obj = hashlib.sha256((password + salt).encode())
        return hash_obj.hexdigest() == hash_value
    except:
        return False


def create_token(user_id: str, role: str) -> str:
    """Create a JWT token."""
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: Optional[str] = Header(None)
) -> Optional[dict]:
    """Get current user from JWT token or API key."""
    # Try JWT token first
    if credentials:
        payload = decode_token(credentials.credentials)
        if payload:
            user = users.find_one({"_id": ObjectId(payload["user_id"])})
            if user:
                return {"user": serialize_doc(user), "role": payload["role"]}

    # Try API key
    if x_api_key:
        api_key_doc = api_keys.find_one({"key": x_api_key, "active": True})
        if api_key_doc:
            return {"api_key": serialize_doc(api_key_doc), "role": api_key_doc.get("role", "viewer")}

    return None


def require_role(required_role: str):
    """Dependency to require a specific role."""
    async def check_role(current_user: dict = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        user_role = current_user.get("role", "viewer")
        role_permissions = USER_ROLES.get(user_role, {})
        required_permissions = USER_ROLES.get(required_role, {})
        # Check if user has at least the required permissions
        for perm, required in required_permissions.items():
            if required and not role_permissions.get(perm, False):
                raise HTTPException(status_code=403, detail=f"Insufficient permissions. Required: {required_role}")
        return current_user
    return check_role


async def send_webhook(webhook_url: str, data: dict) -> bool:
    """Send data to a webhook URL."""
    if not webhook_url:
        return False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=data, timeout=10.0)
            return response.status_code in (200, 201, 202)
    except Exception as e:
        print(f"Webhook error: {e}")
        return False


async def notify_external_systems(event_type: str, data: dict):
    """Notify external systems of geofence changes (API Out)."""
    # Get active webhooks for this event type
    active_webhooks = list(webhooks.find({
        "active": True,
        "events": {"$in": [event_type, "all"]}
    }))

    for webhook in active_webhooks:
        await send_webhook(webhook.get("url"), {
            "event": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })

    # Also notify configured external systems
    if event_type in ["geofence_created", "geofence_updated", "geofence_deleted"]:
        for provider, url in EXTERNAL_WEBHOOKS.items():
            if url and provider in ["hoopo", "orbcom"]:
                await send_webhook(url, {
                    "event": event_type,
                    "data": data,
                    "source": "zim_geofence",
                    "timestamp": datetime.utcnow().isoformat()
                })


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
            "clusters": clusters.count_documents({}),
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

        # Map last update date (most recent geofence update)
        last_updated_doc = geofences.find_one(
            {"properties.updatedAt": {"$exists": True}},
            sort=[("properties.updatedAt", DESCENDING)]
        )
        if last_updated_doc and last_updated_doc.get("properties", {}).get("updatedAt"):
            stats["map_last_updated"] = last_updated_doc["properties"]["updatedAt"].isoformat()
        else:
            stats["map_last_updated"] = None

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

        # Validate clusterId if provided
        cluster_id = geofence.get("clusterId")
        if cluster_id:
            cluster_doc = clusters.find_one({"_id": ObjectId(cluster_id)})
            if not cluster_doc:
                raise HTTPException(status_code=400, detail=f"Cluster with ID '{cluster_id}' not found")

        # Validate parentId if provided (for nested polygons)
        parent_id = geofence.get("parentId")
        if parent_id:
            parent_doc = geofences.find_one({"_id": ObjectId(parent_id)})
            if not parent_doc:
                raise HTTPException(status_code=400, detail=f"Parent geofence with ID '{parent_id}' not found")

        # Create document in GeoJSON format
        doc = {
            "type": "Feature",
            "properties": {
                "name": geofence["name"],
                "description": geofence.get("description", ""),
                "typeId": geofence["typeId"],
                "UNLOCode": geofence.get("UNLOCode", ""),
                "SMDGCode": geofence.get("SMDGCode", ""),
                "clusterId": cluster_id,  # Optional: belongs to cluster
                "parentId": parent_id,    # Optional: nested inside parent geofence
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

        if "clusterId" in updates:
            cluster_id = updates["clusterId"]
            if cluster_id:
                cluster_doc = clusters.find_one({"_id": ObjectId(cluster_id)})
                if not cluster_doc:
                    raise HTTPException(status_code=400, detail=f"Cluster with ID '{cluster_id}' not found")
            update_doc["$set"]["properties.clusterId"] = cluster_id

        if "parentId" in updates:
            parent_id = updates["parentId"]
            if parent_id:
                # Prevent self-reference
                if parent_id == geofence_id:
                    raise HTTPException(status_code=400, detail="Geofence cannot be its own parent")
                parent_doc = geofences.find_one({"_id": ObjectId(parent_id)})
                if not parent_doc:
                    raise HTTPException(status_code=400, detail=f"Parent geofence with ID '{parent_id}' not found")
            update_doc["$set"]["properties.parentId"] = parent_id

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
# CLUSTERS (Geofence Groups)
# =============================================================================

@app.get("/api/clusters")
async def list_clusters():
    """List all clusters."""
    try:
        cursor = clusters.find().sort("name", ASCENDING)
        result = []
        for doc in cursor:
            # Count geofences in this cluster
            count = geofences.count_documents({"properties.clusterId": str(doc["_id"])})
            doc["geofenceCount"] = count
            result.append(serialize_doc(doc))
        return {"clusters": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/clusters/{cluster_id}")
async def get_cluster(cluster_id: str):
    """Get a cluster with its geofences."""
    try:
        doc = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Cluster not found")

        # Get geofences in this cluster
        gfs = list(geofences.find({"properties.clusterId": cluster_id}))

        result = serialize_doc(doc)
        result["geofences"] = [serialize_doc(gf) for gf in gfs]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clusters")
async def create_cluster(cluster: dict = Body(...)):
    """
    Create a new cluster.

    Expected body:
    {
        "name": "Port of Rotterdam",
        "description": "All terminals in Rotterdam port",
        "color": "#FF5722"  // Optional: display color
    }
    """
    try:
        if "name" not in cluster:
            raise HTTPException(status_code=400, detail="Missing required field: name")

        # Check name uniqueness
        existing = clusters.find_one({"name": cluster["name"]})
        if existing:
            raise HTTPException(status_code=409, detail=f"Cluster with name '{cluster['name']}' already exists")

        doc = {
            "name": cluster["name"],
            "description": cluster.get("description", ""),
            "color": cluster.get("color", "#1a237e"),
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
        }

        result = clusters.insert_one(doc)
        doc["_id"] = result.inserted_id
        return serialize_doc(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/clusters/{cluster_id}")
async def update_cluster(cluster_id: str, updates: dict = Body(...)):
    """Update a cluster."""
    try:
        existing = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Cluster not found")

        update_doc = {"$set": {"updatedAt": datetime.utcnow()}}

        if "name" in updates:
            other = clusters.find_one({
                "name": updates["name"],
                "_id": {"$ne": ObjectId(cluster_id)}
            })
            if other:
                raise HTTPException(status_code=409, detail=f"Name '{updates['name']}' already in use")
            update_doc["$set"]["name"] = updates["name"]

        if "description" in updates:
            update_doc["$set"]["description"] = updates["description"]

        if "color" in updates:
            update_doc["$set"]["color"] = updates["color"]

        clusters.update_one({"_id": ObjectId(cluster_id)}, update_doc)
        updated = clusters.find_one({"_id": ObjectId(cluster_id)})
        return serialize_doc(updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/clusters/{cluster_id}")
async def delete_cluster(cluster_id: str):
    """Delete a cluster. Geofences in the cluster will be unassigned."""
    try:
        result = clusters.delete_one({"_id": ObjectId(cluster_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Cluster not found")

        # Unassign geofences from this cluster
        geofences.update_many(
            {"properties.clusterId": cluster_id},
            {"$set": {"properties.clusterId": None}}
        )

        return {"success": True, "deleted_id": cluster_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clusters/{cluster_id}/geofences")
async def add_geofences_to_cluster(cluster_id: str, body: dict = Body(...)):
    """
    Add geofences to a cluster.

    Expected body:
    {
        "geofenceIds": ["id1", "id2", ...]
    }
    """
    try:
        cluster_doc = clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster_doc:
            raise HTTPException(status_code=404, detail="Cluster not found")

        geofence_ids = body.get("geofenceIds", [])
        if not geofence_ids:
            raise HTTPException(status_code=400, detail="geofenceIds is required")

        updated = 0
        for gf_id in geofence_ids:
            result = geofences.update_one(
                {"_id": ObjectId(gf_id)},
                {"$set": {"properties.clusterId": cluster_id, "properties.updatedAt": datetime.utcnow()}}
            )
            if result.modified_count > 0:
                updated += 1

        return {"success": True, "updated": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/clusters/{cluster_id}/geofences/{geofence_id}")
async def remove_geofence_from_cluster(cluster_id: str, geofence_id: str):
    """Remove a geofence from a cluster."""
    try:
        result = geofences.update_one(
            {"_id": ObjectId(geofence_id), "properties.clusterId": cluster_id},
            {"$set": {"properties.clusterId": None, "properties.updatedAt": datetime.utcnow()}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Geofence not found in this cluster")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# NESTED GEOFENCES (Parent-Child Relationships)
# =============================================================================

@app.get("/api/geofences/{geofence_id}/children")
async def get_geofence_children(geofence_id: str):
    """Get all child geofences nested inside this geofence."""
    try:
        parent = geofences.find_one({"_id": ObjectId(geofence_id)})
        if not parent:
            raise HTTPException(status_code=404, detail="Geofence not found")

        children = list(geofences.find({"properties.parentId": geofence_id}))
        return {
            "parent": serialize_doc(parent),
            "children": [serialize_doc(c) for c in children]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/geofences/{geofence_id}/hierarchy")
async def get_geofence_hierarchy(geofence_id: str):
    """Get the full hierarchy for a geofence (ancestors and descendants)."""
    try:
        geofence = geofences.find_one({"_id": ObjectId(geofence_id)})
        if not geofence:
            raise HTTPException(status_code=404, detail="Geofence not found")

        # Get ancestors (walk up the tree)
        ancestors = []
        current = geofence
        while current.get("properties", {}).get("parentId"):
            parent_id = current["properties"]["parentId"]
            parent = geofences.find_one({"_id": ObjectId(parent_id)})
            if parent:
                ancestors.append(serialize_doc(parent))
                current = parent
            else:
                break

        # Get direct children
        children = list(geofences.find({"properties.parentId": geofence_id}))

        return {
            "geofence": serialize_doc(geofence),
            "ancestors": ancestors,
            "children": [serialize_doc(c) for c in children]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/geofences/{geofence_id}/parent")
async def set_geofence_parent(geofence_id: str, body: dict = Body(...)):
    """
    Set or clear the parent of a geofence.

    Expected body:
    {
        "parentId": "parent_geofence_id"  // or null to clear
    }
    """
    try:
        geofence = geofences.find_one({"_id": ObjectId(geofence_id)})
        if not geofence:
            raise HTTPException(status_code=404, detail="Geofence not found")

        parent_id = body.get("parentId")

        if parent_id:
            # Prevent self-reference
            if parent_id == geofence_id:
                raise HTTPException(status_code=400, detail="Geofence cannot be its own parent")

            # Check parent exists
            parent = geofences.find_one({"_id": ObjectId(parent_id)})
            if not parent:
                raise HTTPException(status_code=400, detail="Parent geofence not found")

            # Prevent circular references
            current = parent
            while current.get("properties", {}).get("parentId"):
                if current["properties"]["parentId"] == geofence_id:
                    raise HTTPException(status_code=400, detail="Circular reference detected")
                current = geofences.find_one({"_id": ObjectId(current["properties"]["parentId"])})
                if not current:
                    break

        geofences.update_one(
            {"_id": ObjectId(geofence_id)},
            {"$set": {"properties.parentId": parent_id, "properties.updatedAt": datetime.utcnow()}}
        )

        updated = geofences.find_one({"_id": ObjectId(geofence_id)})
        return serialize_doc(updated)
    except HTTPException:
        raise
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


@app.get("/api/reference/iot-providers")
async def get_iot_providers():
    """Get available IOT providers."""
    return {"providers": IOT_PROVIDERS}


@app.get("/api/reference/user-roles")
async def get_user_roles():
    """Get available user roles."""
    return {"roles": list(USER_ROLES.keys())}


# =============================================================================
# AUTHENTICATION
# =============================================================================

@app.post("/api/auth/register")
async def register_user(body: dict = Body(...)):
    """
    Register a new user.

    Expected body:
    {
        "username": "user@example.com",
        "password": "securepassword",
        "name": "John Doe",
        "role": "viewer"  // Optional, defaults to viewer
    }
    """
    try:
        username = body.get("username")
        password = body.get("password")
        name = body.get("name", "")
        role = body.get("role", "viewer")

        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")

        if role not in USER_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {list(USER_ROLES.keys())}")

        # Check if user exists
        if users.find_one({"username": username}):
            raise HTTPException(status_code=409, detail="Username already exists")

        # Create user
        user_doc = {
            "username": username,
            "password_hash": hash_password(password),
            "name": name,
            "role": role,
            "active": True,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow(),
        }

        result = users.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id

        # Generate token
        token = create_token(str(result.inserted_id), role)

        return {
            "user": serialize_doc({k: v for k, v in user_doc.items() if k != "password_hash"}),
            "token": token
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/login")
async def login_user(body: dict = Body(...)):
    """
    Login and get a JWT token.

    Expected body:
    {
        "username": "user@example.com",
        "password": "securepassword"
    }
    """
    try:
        username = body.get("username")
        password = body.get("password")

        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")

        user = users.find_one({"username": username, "active": True})
        if not user or not verify_password(password, user.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_token(str(user["_id"]), user.get("role", "viewer"))

        return {
            "user": serialize_doc({k: v for k, v in user.items() if k != "password_hash"}),
            "token": token
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user info from token."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user


@app.get("/api/users")
async def list_users(current_user: dict = Depends(require_role("admin"))):
    """List all users (admin only)."""
    try:
        cursor = users.find({}, {"password_hash": 0})
        return {"users": [serialize_doc(u) for u in cursor]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/users/{user_id}/role")
async def update_user_role(user_id: str, body: dict = Body(...), current_user: dict = Depends(require_role("admin"))):
    """Update a user's role (admin only)."""
    try:
        role = body.get("role")
        if role not in USER_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {list(USER_ROLES.keys())}")

        result = users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"role": role, "updatedAt": datetime.utcnow()}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# API KEYS (for external systems)
# =============================================================================

@app.post("/api/api-keys")
async def create_api_key(body: dict = Body(...), current_user: dict = Depends(require_role("admin"))):
    """
    Create an API key for external system access.

    Expected body:
    {
        "name": "Hoopo Integration",
        "role": "editor",
        "description": "API key for Hoopo webhook"
    }
    """
    try:
        name = body.get("name")
        role = body.get("role", "viewer")
        description = body.get("description", "")

        if not name:
            raise HTTPException(status_code=400, detail="Name required")

        if role not in USER_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role")

        key = secrets.token_urlsafe(32)

        doc = {
            "name": name,
            "key": key,
            "role": role,
            "description": description,
            "active": True,
            "createdAt": datetime.utcnow(),
            "createdBy": current_user.get("user", {}).get("_id")
        }

        result = api_keys.insert_one(doc)
        doc["_id"] = result.inserted_id

        return serialize_doc(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/api-keys")
async def list_api_keys(current_user: dict = Depends(require_role("admin"))):
    """List all API keys (admin only). Key values are masked."""
    try:
        cursor = api_keys.find({})
        result = []
        for doc in cursor:
            doc["key"] = doc["key"][:8] + "..." if doc.get("key") else ""
            result.append(serialize_doc(doc))
        return {"api_keys": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/api-keys/{key_id}")
async def revoke_api_key(key_id: str, current_user: dict = Depends(require_role("admin"))):
    """Revoke an API key."""
    try:
        result = api_keys.update_one(
            {"_id": ObjectId(key_id)},
            {"$set": {"active": False}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WEBHOOKS (API In/Out)
# =============================================================================

@app.post("/api/webhooks")
async def create_webhook(body: dict = Body(...), current_user: dict = Depends(require_role("admin"))):
    """
    Register a webhook for receiving geofence updates (API Out).

    Expected body:
    {
        "name": "My System Webhook",
        "url": "https://example.com/webhook",
        "events": ["geofence_created", "geofence_updated", "geofence_deleted", "alert"],
        "secret": "optional-secret-for-validation"
    }
    """
    try:
        name = body.get("name")
        url = body.get("url")
        events = body.get("events", ["all"])
        secret = body.get("secret", "")

        if not name or not url:
            raise HTTPException(status_code=400, detail="Name and URL required")

        doc = {
            "name": name,
            "url": url,
            "events": events,
            "secret": secret,
            "active": True,
            "createdAt": datetime.utcnow(),
            "createdBy": current_user.get("user", {}).get("_id")
        }

        result = webhooks.insert_one(doc)
        doc["_id"] = result.inserted_id

        return serialize_doc(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/webhooks")
async def list_webhooks(current_user: dict = Depends(require_role("admin"))):
    """List all registered webhooks."""
    try:
        cursor = webhooks.find({})
        return {"webhooks": [serialize_doc(w) for w in cursor]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, current_user: dict = Depends(require_role("admin"))):
    """Delete a webhook."""
    try:
        result = webhooks.delete_one({"_id": ObjectId(webhook_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/webhooks/receive")
async def receive_webhook(body: dict = Body(...), x_api_key: Optional[str] = Header(None)):
    """
    Receive geofence updates from external systems (API In).
    Used by Hoopo, Orbcom, ZIM-Lake/Fabric to push updates.

    Expected body:
    {
        "action": "create" | "update" | "delete",
        "geofence": {
            "name": "...",
            "typeId": "...",
            "geometry": {...},
            ...
        },
        "source": "hoopo" | "orbcom" | "zim-lake"
    }
    """
    try:
        # Validate API key
        if x_api_key:
            key_doc = api_keys.find_one({"key": x_api_key, "active": True})
            if not key_doc:
                raise HTTPException(status_code=401, detail="Invalid API key")
        else:
            raise HTTPException(status_code=401, detail="API key required")

        action = body.get("action")
        geofence_data = body.get("geofence", {})
        source = body.get("source", "external")

        if action not in ["create", "update", "delete"]:
            raise HTTPException(status_code=400, detail="Invalid action")

        if action == "create":
            # Create new geofence
            if not geofence_data.get("name") or not geofence_data.get("geometry"):
                raise HTTPException(status_code=400, detail="Name and geometry required")

            doc = {
                "type": "Feature",
                "properties": {
                    "name": geofence_data["name"],
                    "description": geofence_data.get("description", ""),
                    "typeId": geofence_data.get("typeId", "Depot"),
                    "UNLOCode": geofence_data.get("UNLOCode", ""),
                    "SMDGCode": geofence_data.get("SMDGCode", ""),
                    "provider": source,
                    "createdAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow(),
                },
                "geometry": geofence_data["geometry"]
            }
            result = geofences.insert_one(doc)
            return {"success": True, "id": str(result.inserted_id), "action": "created"}

        elif action == "update":
            name = geofence_data.get("name")
            if not name:
                raise HTTPException(status_code=400, detail="Name required for update")

            update_fields = {"properties.updatedAt": datetime.utcnow(), "properties.provider": source}
            if geofence_data.get("description"):
                update_fields["properties.description"] = geofence_data["description"]
            if geofence_data.get("typeId"):
                update_fields["properties.typeId"] = geofence_data["typeId"]
            if geofence_data.get("geometry"):
                update_fields["geometry"] = geofence_data["geometry"]

            result = geofences.update_one(
                {"properties.name": name},
                {"$set": update_fields}
            )
            return {"success": True, "modified": result.modified_count, "action": "updated"}

        elif action == "delete":
            name = geofence_data.get("name")
            if not name:
                raise HTTPException(status_code=400, detail="Name required for delete")

            result = geofences.delete_one({"properties.name": name})
            return {"success": True, "deleted": result.deleted_count, "action": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# NOTIFICATIONS
# =============================================================================

@app.post("/api/notifications")
async def create_notification(body: dict = Body(...)):
    """
    Create a notification (typically called when an alert is triggered).

    Expected body:
    {
        "type": "gate_in" | "gate_out" | "alert",
        "title": "Container entered geofence",
        "message": "MSCU1234567 entered Port of Rotterdam",
        "containerId": "MSCU1234567",
        "geofenceName": "Port of Rotterdam",
        "severity": "info" | "warning" | "critical"
    }
    """
    try:
        doc = {
            "type": body.get("type", "info"),
            "title": body.get("title", ""),
            "message": body.get("message", ""),
            "containerId": body.get("containerId"),
            "geofenceName": body.get("geofenceName"),
            "severity": body.get("severity", "info"),
            "read": False,
            "createdAt": datetime.utcnow(),
        }

        result = notifications.insert_one(doc)
        doc["_id"] = result.inserted_id

        # Send to MYZIM if configured
        myzim_url = EXTERNAL_WEBHOOKS.get("myzim")
        if myzim_url:
            await send_webhook(myzim_url, serialize_doc(doc))

        # Notify registered webhooks
        await notify_external_systems("alert", serialize_doc(doc))

        return serialize_doc(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=500)
):
    """List recent notifications."""
    try:
        query = {}
        if unread_only:
            query["read"] = False

        cursor = notifications.find(query).sort("createdAt", DESCENDING).limit(limit)
        return {"notifications": [serialize_doc(n) for n in cursor]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark a notification as read."""
    try:
        result = notifications.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"read": True}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/notifications/read-all")
async def mark_all_notifications_read():
    """Mark all notifications as read."""
    try:
        result = notifications.update_many(
            {"read": False},
            {"$set": {"read": True}}
        )
        return {"success": True, "updated": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

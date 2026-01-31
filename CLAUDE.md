# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MongoDB GeoSpatial Demo for Zim shipping, showcasing geofencing with container IoT tracking. Uses real Zim geofences (1,154 terminals, depots, rail ramps), TimeSeries collections, and generates realistic IoT events matching Zim's actual data format. The project includes a Python simulator for generating realistic shipping events and a full-stack web application (FastAPI + React) for visualization and management.

## CRITICAL Safety Rules

**MANDATORY: All `rm` commands require explicit user approval before execution.**

- NEVER run any `rm`, `rm -r`, `rm -rf`, or similar deletion commands without first asking the user for confirmation
- Always show the exact files/directories that will be deleted and wait for explicit "yes" approval
- This applies to ALL delete operations via bash, including `rmdir`, `unlink`, and any command that removes files or directories
- No exceptions, even for temporary files or build artifacts

## Key Databases

- `zim_geofence` - **Production**: Real Zim geofence data (1,153 terminals, depots, rail ramps) with generated IoT events
- `geofence` - **Legacy**: Original demo database with synthetic locations (kept for reference, not actively used)

## Development Commands

### Setup Dependencies
```bash
# Python dependencies (root and backend)
pip install -r requirements.txt
pip install -r app/backend/requirements.txt

# Frontend dependencies
cd app/frontend && npm install && cd ../..
```

### Running the Application (Full Stack)

**Terminal 1 - Backend (FastAPI on port 8000):**
```bash
cd app/backend
python main_zim.py              # Use main_zim.py for Zim API (newer)
# python main.py               # Alternative: Use main.py for original demo API
```

**Terminal 2 - Frontend (React/Vite on port 3000):**
```bash
cd app/frontend
npm run dev
```

### Simulator (for generating test data)
```bash
# 1. Import real Zim geofences from GeoJSON (one-time setup)
python3 simulator/import_geofences.py

# 2. Run container simulator (generates realistic IoT events)
python3 simulator/simulator.py -n 50 -s 3600

# Options:
#   -n, --num-containers  Number of containers to simulate (default: 50)
#   -s, --speed           Simulation speed multiplier (default: 60)
#   --start-date          Start date ISO format (default: current time)
```

### Utility Scripts (data generation and management)

**Initial Setup:**
```bash
# Generate synthetic location data (ports, terminals, facilities)
python3 generate_locations.py geofence locations 300000

# Create optimized MongoDB indexes
python3 create_indexes.py

# Generate container tracking data (choose one):
python3 generate_containers.py geofence containers 1000000 7        # TimeSeries
python3 generate_containers.py geofence containers_regular 1000000 7  # Regular collection

# Quick test setup (minimal data)
python3 seed_local_data.py
```

**Monitoring and Queries:**
```bash
# Monitor new container insertions and generate alerts
python3 monitor_containers.py

# Query containers at specific locations
python3 find_containers_at_location.py
python3 check_container_location.py

# Check for location-based anomalies
python3 detect_potential_locations.py
```

**Data Conversion:**
```bash
# Convert existing container data to TimeSeries format
python3 ConvertTimeSeries.py
```

### Frontend Development
```bash
cd app/frontend

npm run dev       # Start dev server (http://localhost:3000)
npm run build     # Production build
npm run preview   # Preview production build
```

## Architecture

### Directory Structure

```
simulator/                        # Container shipping simulator
├── simulator.py                  # Main orchestrator: orchestrates simulation workflow
├── config.py                     # Configuration constants (speeds, event frequencies)
├── import_geofences.py           # One-time import: loads Zim geofences from GeoJSON
├── models/
│   ├── container.py              # Container state machine (in transit, docked, etc.)
│   └── vessel.py                 # Vessel model (used for ocean routes)
└── core/
    ├── database.py               # MongoDB handler: dual-writes to iot_events + iot_events_ts
    ├── geofence_checker.py       # Geospatial: checks if container is within geofence polygon
    ├── route_generator.py        # Route planning: great circle ocean routes, land routes
    └── event_generator.py        # Event generation: creates realistic IoT event payloads

app/backend/                      # FastAPI REST API
├── main_zim.py                   # PRIMARY: Zim API with geofence CRUD, events, containers
├── main.py                       # Alternative: Original demo API (legacy)
├── config.py                     # Backend configuration and MongoDB connection
└── requirements.txt              # Python dependencies (FastAPI, uvicorn, pymongo, pydantic)

app/frontend/                     # React + Vite web application
├── src/
│   ├── components/
│   │   ├── LiveMap.jsx           # Real-time map showing geofences + container locations
│   │   ├── GeofenceManager.jsx   # Geofence CRUD + interactive polygon drawing
│   │   ├── EventsGrid.jsx        # Table view of IoT events and gate entry/exit events
│   │   ├── ContainerTracker.jsx  # Track individual container movement over time
│   │   ├── AlertsGrid.jsx        # Display and manage system alerts
│   │   ├── LocationSearch.jsx    # Autocomplete location search (uses Atlas Search)
│   │   ├── LocationMap.jsx       # Map visualization for selected location
│   │   └── Admin.jsx             # Admin interface
│   └── services/api.js           # Axios API client for all backend endpoints
├── package.json                  # npm dependencies (React, Vite, Leaflet, Axios)
└── vite.config.js                # Vite build configuration

Root-level utility scripts/       # Data generation and management
├── generate_locations.py         # Generate synthetic port/terminal/facility data
├── generate_containers.py        # Generate container tracking data (TimeSeries or regular)
├── generate_alerts.py            # Generate system alerts
├── create_indexes.py             # Create optimized geospatial + metadata indexes
├── monitor_containers.py         # Change stream monitor for real-time alerts
├── find_containers_at_location.py # Query containers within locations
├── detect_potential_locations.py # Anomaly detection for shipping routes
├── seed_local_data.py            # Quick seed with minimal data for local testing
└── ConvertTimeSeries.py          # Convert regular collection to TimeSeries format

Zim Data/                         # Customer-provided data files
├── Geofences.geojson             # 1,154 real Zim geofence polygons (terminals, depots, ramps)
├── Sample for geofencing review.xlsx # Example IoT event output format
└── Zim Requirement.md            # Customer business requirements
```

### Data Flow

1. **Simulator** → generates IoT events → writes to MongoDB
2. **MongoDB** → dual-write to `iot_events` + `iot_events_ts` (for performance comparison)
3. **Backend API** → queries collections, serves REST endpoints
4. **Frontend** → displays real-time data on interactive maps and grids

## MongoDB Setup

### Environment Configuration

Create a `.env` file in the project root with one of these options:

**Option 1: Local MongoDB (for development)**
```bash
DEBUG=true
# Uses mongodb://localhost:27017 by default
```

**Option 2: MongoDB Atlas (cloud)**
```bash
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

### Collections in `zim_geofence` Database

| Collection | Type | Purpose | Indexes |
|------------|------|---------|---------|
| `geofences` | Regular | Zim terminals, depots, rail ramps (1,153 polygons) | `2dsphere` on `geometry` |
| `iot_events` | Regular | IoT events (default query target if not using TimeSeries) | `2dsphere` on `location`, compound on `TrackerID` + `EventTime` |
| `iot_events_ts` | TimeSeries | Same events in TimeSeries format (optimized for time queries) | Automatic (TimeSeries) |
| `gate_events` | Regular | Geofence entry/exit events (derived from IoT events) | Compound on `container_id` + `timestamp` |
| `containers` | Regular | Container metadata and current state | Index on `container_id` |
| `vessels` | Regular | Vessel information used for ocean route planning | Index on `vessel_id` |

### Data Generation Order

When setting up, **run scripts in this order**:

1. `python3 simulator/import_geofences.py` - Imports Zim geofences (one-time)
2. `python3 generate_locations.py geofence locations 300000` - Optional: synthetic locations
3. `python3 create_indexes.py` - Create MongoDB indexes
4. `python3 generate_containers.py` or `python3 simulator/simulator.py` - Generate IoT events

### USE_TIMESERIES Configuration

In `app/backend/config.py`, toggle which collection to query:
- **true** → queries faster `iot_events_ts` (TimeSeries collection)
- **false** → queries `iot_events` (regular collection)

## Data Formats

### IoT Event (matches Zim's production format)
```json
{
  "TrackerID": "A0000669",
  "assetname": "ZIMU3170479",
  "AssetId": 35758,
  "EventTime": "2024-12-31T15:49:39",
  "ReportTime": "2024-12-31T16:01:14",
  "EventLocation": "MXVER-DCO",
  "EventLocationCountry": "MX",
  "Lat": 19.225322,
  "Lon": -96.219475,
  "EventType": "Motion Stop",
  "location": { "type": "Point", "coordinates": [-96.219475, 19.225322] }
}
```

**Event Types:**
- `In Motion` / `Motion Stop` - Vehicle movement state changes
- `Location Update` - Periodic GPS ping (no movement change)
- `Door Opened` / `Door Closed` - Container access events
- `Gate In` / `Gate Out` - Geofence entry/exit (derived from polygon queries)

### Geofence (from Zim data, stored as GeoJSON Polygon)
```json
{
  "name": "USSAV-TGC",
  "typeId": "Terminal",
  "UNLOCode": "USSAV",
  "SMDGCode": "SAVANNAH",
  "description": "Port of Savannah, Georgia Terminal",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-81.1, 32.1], [-81.2, 32.1], [-81.2, 32.0], [-81.1, 32.0], [-81.1, 32.1]]]
  }
}
```

### Alert (generated when container enters geofence)
```json
{
  "container_id": "ZIMU3170479",
  "geofence_name": "USSAV-TGC",
  "geofence_type": "Terminal",
  "timestamp": "2024-12-31T16:05:00",
  "event_type": "Gate In",
  "acknowledged": false,
  "created_at": "2024-12-31T16:05:00"
}
```

## API Endpoints (main_zim.py)

**Geofence Management:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/geofences` | GET | List all geofences (with optional filters) |
| `/api/geofences` | POST | Create new geofence |
| `/api/geofences/{id}` | PUT | Update geofence geometry or properties |
| `/api/geofences/{id}` | DELETE | Delete geofence |
| `/api/geofences/export/csv` | GET | Export all geofences as CSV |
| `/api/geofences/export/geojson` | GET | Export all geofences as GeoJSON |
| `/api/geofences/import/csv` | POST | Bulk import geofences from CSV |

**IoT Events:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/iot-events` | GET | List IoT events (paginated, with filters) |
| `/api/iot-events/latest` | GET | Get latest events for live map |

**Gate Events:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/gate-events` | GET | List geofence entry/exit events |

**Container Tracking:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/containers` | GET | List all containers |
| `/api/containers/positions/latest` | GET | Get latest position for each container (for live map) |

**Access the interactive API documentation:** http://localhost:8000/docs (when backend is running)

## Key Architectural Decisions

1. **Dual-write pattern**: All IoT events written to both `iot_events` (regular) and `iot_events_ts` (TimeSeries) for performance testing
2. **Configurable collection**: `USE_TIMESERIES` toggle in backend config determines which collection queries use
3. **Gate events separation**: Geofence crossings stored in dedicated `gate_events` collection for fast alerting without querying all IoT events
4. **Great circle routes**: Ocean routes use realistic geodesic paths, not straight lines
5. **Event vs. Report time**: `EventTime` (when container recorded) vs `ReportTime` (when transmitted) simulates real IoT delays
6. **Geofence checker**: Uses MongoDB `$geoIntersects` operator for polygon containment queries

## Technology Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, Python 3.7+, PyMongo, Pydantic |
| **Frontend** | React 18.2, Vite 5, Leaflet (mapping), React Router, Axios |
| **Database** | MongoDB 5.0+, TimeSeries collections, Atlas Search (optional) |
| **Deployment** | Uvicorn (backend), npm dev server / static build (frontend) |

## Common Development Tasks

### Adding a New API Endpoint
1. Define the route in `app/backend/main_zim.py`
2. Add corresponding method to MongoDB service class if needed
3. Update frontend API client in `app/frontend/src/services/api.js`
4. Add new component if needed in `app/frontend/src/components/`
5. Update this documentation

### Modifying IoT Event Schema
1. Update event payload in `simulator/core/event_generator.py`
2. Ensure MongoDB indexes reflect new fields: `python3 create_indexes.py`
3. Update the IoT Event Format section above
4. Update backend parsing in `app/backend/main_zim.py`

### Testing Geofence Queries
```bash
python3 check_container_location.py    # Check if container in geofence
python3 find_containers_at_location.py # Find all containers in location
```

### Running the Simulator with Custom Parameters
```bash
# Simulate 100 containers at 1000x speed for 1 hour of simulated time
python3 simulator/simulator.py -n 100 -s 1000

# Start simulation from a specific date
python3 simulator/simulator.py -n 50 --start-date "2024-01-01T00:00:00"
```

### Toggling Between Collection Types
Edit `app/backend/config.py` and change `USE_TIMESERIES`:
- `True` → queries optimized `iot_events_ts` (faster for time-range queries)
- `False` → queries regular `iot_events` (slower but more flexible)

## Troubleshooting

### Backend won't start
**Error: ModuleNotFoundError: No module named 'app'**
- Solution: Run from project root with `python main_zim.py` (not `cd app/backend`)
- Or use: `python3 -m app.backend.main_zim`

**Error: MongoDB connection failed**
- Check `.env` exists with `DEBUG=true` or valid `MONGODB_URI`
- Verify MongoDB running locally: `mongosh --eval 'db.adminCommand("ping")'`
- For Atlas: ensure your IP is whitelisted in Network Access

### Frontend won't start
**Error: Port 3000 already in use**
- This is normal; Vite uses next available port (3001, 3002, etc.)
- Check terminal output for actual URL

**Cannot connect to backend**
- Ensure backend is running on http://localhost:8000
- Check browser console for specific error messages

### Simulator not generating events
- Verify MongoDB is running and connected
- Check geofences imported: `db.zim_geofence.geofences.countDocuments()` should be 1,153
- Ensure vessels exist: `db.zim_geofence.vessels.countDocuments()` should be > 0

### Slow queries
- Run `python3 create_indexes.py` to ensure all indexes exist
- Check `USE_TIMESERIES` is set correctly for your collection type
- For large datasets, add query pagination parameters (`skip`, `limit`)

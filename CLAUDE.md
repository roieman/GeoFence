# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MongoDB GeoSpatial Demo for Zim shipping, showcasing geofencing with container IoT tracking. Uses real Zim geofences (1,153 terminals, depots, rail ramps), TimeSeries collections, and generates realistic IoT events matching Zim's actual data format. The project includes a Python simulator for generating realistic shipping events and a full-stack web application (FastAPI + React) for visualization and management.

**Key Features:**
- Ocean chokepoint routing (Suez, Panama, Malacca, Gibraltar, etc.)
- Rail routing support for US/CA/GB (30% of eligible journeys)
- Zim-branded frontend with official logo and colors
- Real-time container tracking with gate events

## CRITICAL Safety Rules

**MANDATORY: All `rm` commands require explicit user approval before execution.**

- NEVER run any `rm`, `rm -r`, `rm -rf`, or similar deletion commands without first asking the user for confirmation
- Always show the exact files/directories that will be deleted and wait for explicit "yes" approval
- This applies to ALL delete operations via bash, including `rmdir`, `unlink`, and any command that removes files or directories
- No exceptions, even for temporary files or build artifacts

## Quick Start

### Option 1: Automated Setup (Recommended)
```bash
./setup.sh                           # Creates venv, installs deps, configures env

# Terminal 1 - Backend
source venv/bin/activate
cd app/backend && python main_zim.py

# Terminal 2 - Frontend
cd app/frontend && npm run dev
```

### Option 2: Docker Setup
```bash
docker-compose up -d                 # Starts MongoDB, backend, frontend
docker-compose exec backend python simulator/import_geofences.py
```

### Option 3: Manual Setup
See detailed instructions below.

## Key Databases

- `zim_geofence` - **Production**: Real Zim geofence data (1,153 terminals, depots, rail ramps) with generated IoT events
- `geofence` - **Legacy**: Original demo database with synthetic locations (kept for reference, not actively used)

## Development Commands

### Setup Dependencies
```bash
# Automated (recommended)
./setup.sh

# Manual
pip install -r requirements.txt
pip install -r app/backend/requirements.txt
cd app/frontend && npm install && cd ../..
```

### Running the Application (Full Stack)

**Terminal 1 - Backend (FastAPI on port 8000):**
```bash
source venv/bin/activate
cd app/backend
python main_zim.py
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
#   -s, --speed           Simulation speed multiplier (default: 60, use 3600 for faster demo)
#   --start-date          Start date ISO format (default: current time)
```

**Simulator Features:**
- Routes through real shipping chokepoints (Suez, Panama, Malacca, etc.)
- 30% of US/CA/GB journeys use rail ramps (78 available)
- Ocean route validation to avoid land masses
- Realistic IoT events matching Zim's format

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
GeoFence/
├── setup.sh                          # Automated setup script
├── docker-compose.yml                # Docker deployment configuration
├── Dockerfile.backend                # Backend container image
├── .env.example                      # Environment configuration template
├── README.md                         # Project overview and quick start
│
├── simulator/                        # Container shipping simulator
│   ├── simulator.py                  # Main orchestrator
│   ├── config.py                     # Configuration (speeds, rail probability)
│   ├── import_geofences.py           # Imports Zim geofences from GeoJSON
│   ├── data/
│   │   ├── chokepoints.py            # Ocean chokepoints (Suez, Panama, etc.)
│   │   └── water_regions.py          # Water region validation
│   ├── models/
│   │   ├── container.py              # Container state machine (incl. rail states)
│   │   └── vessel.py                 # Vessel model for ocean routes
│   └── core/
│       ├── database.py               # MongoDB handler (dual-write)
│       ├── geofence_checker.py       # Geospatial polygon checks
│       ├── route_generator.py        # Chokepoint routing, rail routing
│       └── event_generator.py        # IoT event payloads
│
├── app/
│   ├── backend/                      # FastAPI REST API
│   │   ├── main_zim.py               # Main API (geofences, events, containers)
│   │   ├── config.py                 # MongoDB connection config
│   │   └── requirements.txt          # Python dependencies
│   │
│   └── frontend/                     # React + Vite web application
│       ├── Dockerfile.frontend       # Frontend container image
│       ├── public/
│       │   └── zim-logo.png          # Official Zim logo
│       ├── src/
│       │   ├── App.jsx               # Main app with navigation
│       │   ├── App.css               # Zim-branded styles (gold/navy)
│       │   ├── components/
│       │   │   ├── LiveMap.jsx       # Real-time map with geofences
│       │   │   ├── GeofenceManager.jsx # Geofence CRUD + polygon drawing
│       │   │   ├── EventsGrid.jsx    # IoT event log
│       │   │   ├── ContainerTracker.jsx # Individual container tracking
│       │   │   └── Admin.jsx         # Admin interface
│       │   └── services/api.js       # Axios API client
│       └── package.json              # npm dependencies
│
├── Root-level utility scripts/
│   ├── generate_locations.py         # Generate synthetic locations
│   ├── generate_containers.py        # Generate container data
│   ├── generate_alerts.py            # Generate alerts
│   ├── create_indexes.py             # Create MongoDB indexes
│   ├── monitor_containers.py         # Change stream monitor
│   ├── find_containers_at_location.py
│   ├── check_container_location.py
│   ├── detect_potential_locations.py
│   ├── seed_local_data.py
│   └── ConvertTimeSeries.py
│
├── Zim Data/                         # Customer-provided data files
│   ├── Geofences.geojson             # 1,153 real Zim geofence polygons
│   └── Sample for geofencing review.xlsx
│
└── Older Data/                       # Archived/legacy files (not used)
    ├── main.py                       # Original demo API (superseded)
    └── (Atlas Search utilities)      # Optional Atlas Search helpers
```

### Data Flow

1. **Simulator** → generates IoT events → writes to MongoDB
2. **MongoDB** → dual-write to `iot_events` + `iot_events_ts` (for performance comparison)
3. **Backend API** → queries collections, serves REST endpoints
4. **Frontend** → displays real-time data on interactive maps and grids

### Simulator Routing

**Ocean Routes:**
- Routes pass through real shipping chokepoints based on origin/destination regions
- Example: Shanghai → Hamburg goes through Malacca, Singapore, Bab el-Mandeb, Suez, Gibraltar
- Water region validation ensures waypoints stay in ocean

**Rail Routes (US/CA/GB only):**
- 30% of eligible journeys use rail ramps
- Container states: depot → rail ramp → rail transit → terminal
- 78 rail ramps available in Zim data

## MongoDB Setup

### Environment Configuration

Create a `.env` file in the project root (or run `./setup.sh`):

```bash
# Local MongoDB
MONGODB_URI=mongodb://localhost:27017
DB_NAME=zim_geofence
DEBUG=true

# Or MongoDB Atlas
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
```

### Collections in `zim_geofence` Database

| Collection | Type | Purpose | Indexes |
|------------|------|---------|---------|
| `geofences` | Regular | Zim terminals, depots, rail ramps (1,153 polygons) | `2dsphere` on `geometry` |
| `iot_events` | Regular | IoT events (default query target) | `2dsphere` on `location`, compound on `TrackerID` + `EventTime` |
| `iot_events_ts` | TimeSeries | Same events optimized for time queries | Automatic (TimeSeries) |
| `gate_events` | Regular | Geofence entry/exit events | Compound on `container_id` + `timestamp` |
| `containers` | Regular | Container metadata and current state | Index on `container_id` |
| `vessels` | Regular | Vessel information for ocean routes | Index on `vessel_id` |

### Data Generation Order

1. `python3 simulator/import_geofences.py` - Import Zim geofences (one-time)
2. `python3 create_indexes.py` - Create MongoDB indexes
3. `python3 simulator/simulator.py -n 50 -s 3600` - Generate IoT events

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
- `Location Update` - Periodic GPS ping
- `Door Opened` / `Door Closed` - Container access events
- `Gate In` / `Gate Out` - Geofence entry/exit
- `In Transit by Rail` / `Loaded on Rail` / `Unloaded from Rail` - Rail events

### Geofence (from Zim data)
```json
{
  "name": "USSAV-TGC",
  "typeId": "Terminal",
  "UNLOCode": "USSAV",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-81.1, 32.1], [-81.2, 32.1], [-81.2, 32.0], [-81.1, 32.0], [-81.1, 32.1]]]
  }
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
| `/api/containers/positions/latest` | GET | Get latest position for each container |

**API Documentation:** http://localhost:8000/docs

## Frontend Branding

The frontend uses Zim's official branding:
- **Primary Gold:** `#FFD100`
- **Navy Blue:** `#1C2340`
- **Logo:** `public/zim-logo.png`

Key styling in `App.css`:
- Navigation: Navy background, gold active states
- Buttons: Gold primary, navy secondary
- Tables: Navy headers with gold accents
- Badges: Terminal (navy/gold), Depot (green), Rail Ramp (gold)

## Key Architectural Decisions

1. **Dual-write pattern**: All IoT events written to both `iot_events` (regular) and `iot_events_ts` (TimeSeries)
2. **Chokepoint routing**: Ocean routes pass through real shipping lanes (Suez, Panama, etc.)
3. **Rail routing**: 30% of US/CA/GB inland journeys use rail ramps
4. **Gate events separation**: Geofence crossings in dedicated collection for fast alerting
5. **Water validation**: Ocean waypoints validated against water region bounding boxes

## Technology Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, Python 3.7+, PyMongo, Pydantic |
| **Frontend** | React 18, Vite 5, Leaflet, Axios |
| **Database** | MongoDB 5.0+, TimeSeries collections |
| **Styling** | Custom CSS with Zim branding |
| **Deployment** | Docker, docker-compose, or manual |

## Troubleshooting

### Backend won't start
**Error: ModuleNotFoundError**
- Run from project root: `cd app/backend && python main_zim.py`
- Or activate venv: `source venv/bin/activate`

**Error: MongoDB connection failed**
- Check `.env` exists with valid `MONGODB_URI`
- Verify MongoDB running: `mongosh --eval 'db.adminCommand("ping")'`

### Frontend won't start
**Port 3000 in use** - Vite uses next available port (check terminal output)

### Simulator not generating events
- Check geofences imported: `db.zim_geofence.geofences.countDocuments()` should be 1,153
- Ensure MongoDB is running and connected

### Docker issues
```bash
docker-compose logs backend   # Check backend logs
docker-compose logs mongodb   # Check MongoDB logs
docker-compose down -v        # Reset and start fresh
```

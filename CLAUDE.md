# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MongoDB GeoSpatial Demo for Zim shipping, showcasing geofencing with container IoT tracking. Uses real Zim geofences (1,154 terminals, depots, rail ramps), TimeSeries collections, and generates realistic IoT events matching Zim's actual data format.

## Databases

- `zim_geofence` - **NEW**: Production database with real Zim data
- `geofence` - **OLD**: Original demo database (kept for reference)

## Commands

### Simulator (NEW)
```bash
# Import Zim geofences from GeoJSON
python3 simulator/import_geofences.py

# Run the container simulator
python3 simulator/simulator.py -n 50 -s 3600   # 50 containers, 3600x speed

# Options:
#   -n, --num-containers  Number of containers (default: 50)
#   -s, --speed           Simulation speed multiplier (default: 60)
#   --start-date          Start date ISO format (default: now)
```

### Backend (FastAPI) - NEW Zim API
```bash
cd app/backend
pip install -r requirements.txt
python main_zim.py                # NEW: Zim API on http://localhost:8000
# python main.py                  # OLD: Original demo API
```

### Frontend (React/Vite)
```bash
cd app/frontend
npm install
npm run dev                       # Runs on http://localhost:3000
```

## Architecture

```
simulator/                        # NEW: Container shipping simulator
├── config.py                     # Configuration and constants
├── import_geofences.py           # Import Zim geofences from GeoJSON
├── simulator.py                  # Main orchestrator
├── models/
│   ├── container.py              # Container state machine
│   └── vessel.py                 # Vessel model
└── core/
    ├── database.py               # MongoDB handler (writes to both collections)
    ├── geofence_checker.py       # Polygon intersection using $geoIntersects
    ├── route_generator.py        # Great circle ocean routes, land routes
    └── event_generator.py        # IoT event generation

app/                              # Web application
├── backend/
│   ├── main_zim.py               # NEW: Zim API (geofence CRUD, IoT events, etc.)
│   ├── config.py                 # Backend configuration
│   └── main.py                   # OLD: Original demo API
└── frontend/
    └── src/
        ├── components/
        │   ├── LiveMap.jsx       # Real-time IoT map with geofences
        │   ├── GeofenceManager.jsx  # Geofence CRUD + polygon drawing
        │   ├── EventsGrid.jsx    # IoT & Gate events grid
        │   └── ContainerTracker.jsx  # Track individual container
        └── services/api.js       # API client for all endpoints

Zim Data/                         # Real Zim data files
├── Geofences.geojson             # 1,154 real geofence polygons
├── Sample for geofencing review.xlsx  # Example IoT event output
└── Zim Requirenment.md           # Customer requirements
```

### Collections (database: `zim_geofence`)

| Collection | Type | Purpose |
|------------|------|---------|
| `geofences` | Regular | Zim terminals, depots, rail ramps (1,153 polygons) |
| `iot_events` | Regular | IoT events (default query target) |
| `iot_events_ts` | TimeSeries | Same events in TimeSeries format |
| `gate_events` | Regular | Geofence entry/exit events |
| `containers` | Regular | Container metadata and state |
| `vessels` | Regular | Vessel information |

### IoT Event Format (matches Zim's format)
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

### Event Types
- `In Motion` / `Motion Stop` - Vehicle movement state
- `Location Update` - Periodic GPS ping
- `Door Opened` / `Door Closed` - Container access
- `Gate In` / `Gate Out` - Geofence crossing (derived)

### Geofence Properties
- `name` - Unique ID like `USSAV-TGC`, `AUBNE-THP`
- `typeId` - `Terminal`, `Depot`, or `Rail ramp`
- `UNLOCode` - UN location code
- `SMDGCode` - SMDG terminal code
- `description` - Full location description

## API Endpoints (main_zim.py)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/geofences` | GET | List geofences with filters |
| `/api/geofences` | POST | Create new geofence |
| `/api/geofences/{id}` | PUT | Update geofence |
| `/api/geofences/{id}` | DELETE | Delete geofence |
| `/api/geofences/export/csv` | GET | Export as CSV |
| `/api/geofences/export/geojson` | GET | Export as GeoJSON |
| `/api/geofences/import/csv` | POST | Import from CSV |
| `/api/iot-events` | GET | List IoT events |
| `/api/iot-events/latest` | GET | Latest events (for live map) |
| `/api/gate-events` | GET | List geofence crossings |
| `/api/containers` | GET | List containers |
| `/api/containers/positions/latest` | GET | Container positions (for live map) |

## Key Design Decisions

1. **Dual-write to both collections**: All IoT events are written to both `iot_events` (regular) and `iot_events_ts` (TimeSeries) for performance comparison
2. **USE_TIMESERIES config**: Toggle which collection the app queries
3. **Gate events separated**: Geofence crossings stored in dedicated collection for fast alerting
4. **Great circle routes**: Ocean routes follow realistic shipping lanes
5. **Event/Report time distinction**: Simulates IoT transmission delay

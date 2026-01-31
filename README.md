# ZIM GeoFence - Container Tracking System

A geofencing and container tracking demo for ZIM Shipping, showcasing MongoDB's geospatial capabilities with real Zim terminal data.

![ZIM Logo](app/frontend/public/zim-logo.png)

## Features

- **1,153 Real Zim Geofences** - Terminals, depots, and rail ramps worldwide
- **Realistic Container Simulation** - IoT events matching Zim's actual data format
- **Ocean Chokepoint Routing** - Routes through Suez, Panama, Malacca, etc.
- **Rail Routing Support** - 30% of US/CA/UK journeys use rail ramps
- **Real-time Tracking** - Live map with container positions
- **Gate Events** - Automatic geofence entry/exit detection
- **TimeSeries Collections** - Optimized for time-range queries

## Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/roieman/GeoFence.git
cd GeoFence

# Run setup script
./setup.sh

# Start backend (Terminal 1)
source venv/bin/activate
cd app/backend && python main_zim.py

# Start frontend (Terminal 2)
cd app/frontend && npm run dev
```

Then open **http://localhost:3000** in your browser.

### Option 2: Docker Setup

```bash
# Clone and start with Docker
git clone https://github.com/roieman/GeoFence.git
cd GeoFence
docker-compose up -d

# Import geofence data
docker-compose exec backend python simulator/import_geofences.py
```

Open **http://localhost:3000** in your browser.

### Option 3: Manual Setup

See [DEMO_SETUP_INSTRUCTIONS.md](DEMO_SETUP_INSTRUCTIONS.md) for detailed step-by-step instructions.

## Prerequisites

- **Python 3.7+**
- **Node.js 16+**
- **MongoDB 5.0+** (local or Atlas)

## Running the Simulator

Generate realistic container tracking data:

```bash
source venv/bin/activate
python simulator/simulator.py -n 50 -s 3600
```

Options:
- `-n, --num-containers`: Number of containers (default: 50)
- `-s, --speed`: Simulation speed multiplier (default: 60, use 3600 for faster demo)

## Project Structure

```
GeoFence/
├── app/
│   ├── backend/           # FastAPI REST API
│   │   └── main_zim.py    # Main API (Zim-specific)
│   └── frontend/          # React + Vite web app
│       └── src/components/
├── simulator/             # Container shipping simulator
│   ├── simulator.py       # Main orchestrator
│   ├── data/              # Chokepoints & water regions
│   └── core/              # Route generation, events
├── Zim Data/              # Customer geofence data
│   └── Geofences.geojson  # 1,153 real Zim geofences
├── setup.sh               # Automated setup script
├── docker-compose.yml     # Docker deployment
└── CLAUDE.md              # Detailed developer guide
```

## Web Application Pages

| Page | Description |
|------|-------------|
| **Live Map** | Real-time container positions with geofence overlays |
| **Geofences** | Manage terminals, depots, rail ramps (CRUD + export) |
| **Events** | IoT event log with filters |
| **Track Container** | Individual container journey tracking |
| **Admin** | System administration |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/geofences` | GET | List all geofences |
| `/api/geofences` | POST | Create geofence |
| `/api/iot-events` | GET | List IoT events (paginated) |
| `/api/iot-events/latest` | GET | Latest events for live map |
| `/api/gate-events` | GET | Geofence entry/exit events |
| `/api/containers/positions/latest` | GET | Latest container positions |

Full API docs: **http://localhost:8000/docs**

## Data Format

### IoT Event (Zim Format)
```json
{
  "TrackerID": "A0000669",
  "assetname": "ZIMU3170479",
  "EventTime": "2024-12-31T15:49:39",
  "EventType": "Motion Stop",
  "Lat": 19.225322,
  "Lon": -96.219475,
  "EventLocation": "MXVER-DCO"
}
```

### Geofence
```json
{
  "name": "USSAV-TGC",
  "typeId": "Terminal",
  "UNLOCode": "USSAV",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[...], ...]]
  }
}
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Local MongoDB
MONGODB_URI=mongodb://localhost:27017
DB_NAME=zim_geofence
DEBUG=true

# Or MongoDB Atlas
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
```

## Documentation

- [DEMO_SETUP_INSTRUCTIONS.md](DEMO_SETUP_INSTRUCTIONS.md) - Detailed setup guide
- [CLAUDE.md](CLAUDE.md) - Comprehensive developer guide
- [ALERT_SYSTEM.md](ALERT_SYSTEM.md) - Alert system documentation
- [AGGREGATION_EXAMPLES.md](AGGREGATION_EXAMPLES.md) - Geospatial query examples

## Technologies

| Layer | Stack |
|-------|-------|
| Backend | FastAPI, Python 3.11, PyMongo |
| Frontend | React 18, Vite 5, Leaflet |
| Database | MongoDB 7.0, TimeSeries Collections |
| Styling | Custom CSS with Zim branding |

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

# MongoDB GeoSpatial Demo - GeoFence

A comprehensive demo application showcasing MongoDB's geospatial capabilities with a full-stack web interface for tracking shipping containers, monitoring locations, and generating real-time alerts.

## Overview

This project demonstrates MongoDB's geospatial capabilities with:
- **300,000+ locations** (ports, train terminals, industrial facilities) with Point and Polygon geometries
- **TimeSeries collection** for container tracking with periodic location readings
- **Real-time alert system** using MongoDB Change Streams
- **Full-stack web application** with React frontend and FastAPI backend
- **Atlas Search integration** for location autocomplete

## Features

### Data Generation
- Generate large-scale location data (ports, terminals, factories, warehouses)
- Generate TimeSeries container data with realistic shipping routes
- Support for both regular and TimeSeries collections

### Web Application
- **Container Tracker**: Track individual container movement on an interactive map
- **Alerts Grid**: View and filter system alerts with real-time updates
- **Location Search**: 
  - Search containers by location with autocomplete
  - Compare performance between Regular and TimeSeries collections
  - View query execution times
  - Display results on interactive maps

### Geospatial Capabilities
- Point-based location queries with radius
- Polygon-based location queries
- Geospatial aggregation pipelines
- Real-time geofence monitoring

## Architecture

```
GeoFence/
├── app/
│   ├── backend/          # FastAPI backend
│   │   ├── main.py        # API endpoints
│   │   └── requirements.txt
│   └── frontend/          # React frontend
│       ├── src/
│       │   ├── components/
│       │   └── services/
│       └── package.json
├── generate_locations.py  # Location data generator
├── generate_containers.py # Container data generator
├── monitor_containers.py  # Change stream monitor
└── requirements.txt       # Python dependencies
```

## Prerequisites

- Python 3.7+
- Node.js 16+ and npm
- MongoDB 5.0+ (for TimeSeries collections support)
- MongoDB Atlas account (for Atlas Search features)

## Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd GeoFence
```

### 2. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt
pip install -r app/backend/requirements.txt

# Create .env file with MongoDB connection string
echo "MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority" > .env
```

### 3. Frontend Setup

```bash
cd app/frontend
npm install
```

## Quick Start

### 1. Generate Location Data

```bash
# Generate 300,000 locations (ports, terminals, facilities)
python generate_locations.py geofence locations 300000

# Create optimized indexes
python create_indexes.py
```

### 2. Generate Container Data

```bash
# Generate TimeSeries container data
python generate_containers.py geofence containers 1000000 7

# Or generate regular collection data
python generate_containers.py geofence containers_regular 1000000 7
```

### 3. Set Up Atlas Search (Optional)

```bash
cd app/backend
python create_atlas_search_index.py
# Follow instructions to create the "default" search index
```

### 4. Start the Application

**Backend:**
```bash
cd app/backend
python main.py
# Backend runs on http://localhost:8000
```

**Frontend:**
```bash
cd app/frontend
npm run dev
# Frontend runs on http://localhost:3000
```

### 5. Start Alert Monitor (Optional)

```bash
python monitor_containers.py
# Monitors new container insertions and creates alerts
```

## Usage

### Web Application

1. **Container Tracker** (`/`)
   - Enter a container ID to track its movement
   - View route on interactive map
   - Filter by date range

2. **Alerts Grid** (`/alerts`)
   - View all system alerts
   - Filter by container ID, location, date range
   - Acknowledge alerts

3. **Location Search** (`/location`)
   - Search locations by name, city, or country (autocomplete)
   - Select location and search for containers
   - Compare Regular vs TimeSeries collection performance
   - View query execution times
   - Display results on map

### Data Generation Scripts

#### Generate Locations

```bash
python generate_locations.py [database] [collection] [num_facilities]
```

**Example:**
```bash
python generate_locations.py geofence locations 300000
```

**Features:**
- Creates ~20 major ports worldwide
- Creates ~15 major train terminals
- Generates 300,000+ industrial facilities
- 70% weighted distribution, 30% uniform
- ~25% Polygon geometries, 75% Point geometries
- Automatic 2dsphere index creation

#### Generate Containers

```bash
python generate_containers.py [database] [collection] [num_containers] [days]
```

**Example:**
```bash
# TimeSeries collection
python generate_containers.py geofence containers 1000000 7

# Regular collection
python generate_containers.py geofence containers_regular 1000000 7
```

**Features:**
- Creates TimeSeries or regular collection
- Generates readings every 15 minutes
- Realistic shipping routes between ports
- Container metadata (ID, shipping line, type, etc.)
- Automatic index creation

## API Endpoints

### Container Tracking
- `GET /api/containers/{container_id}/track` - Track container movement

### Alerts
- `GET /api/alerts` - Get all alerts (with filters)
- `POST /api/alerts/{alert_id}/acknowledge` - Acknowledge alert

### Locations
- `GET /api/locations` - Search locations (with autocomplete)
- `GET /api/locations/static` - Get 10 static locations
- `GET /api/locations/{location_name}/containers` - Get containers at location (Regular)
- `GET /api/locations/{location_name}/containers/timeseries` - Get containers at location (TimeSeries)

### Statistics
- `GET /api/stats` - Get system statistics

## Data Structure

### Locations Collection

```json
{
  "name": "Port of Shanghai",
  "type": "port",
  "city": "Shanghai",
  "country": "China",
  "location": {
    "type": "Point",
    "coordinates": [121.4737, 31.2304]
  },
  "capacity": 25000
}
```

### Containers Collection (TimeSeries)

```json
{
  "metadata": {
    "container_id": "ABCD1234567",
    "shipping_line": "Maersk",
    "container_type": "refrigerated",
    "refrigerated": true
  },
  "timestamp": ISODate("2024-01-01T12:00:00Z"),
  "location": {
    "type": "Point",
    "coordinates": [-118.2642, 33.7420]
  },
  "weight_kg": 15000,
  "temperature_celsius": -18.5,
  "speed_knots": 22.3,
  "status": "in_transit"
}
```

### Alerts Collection

```json
{
  "container_id": "ABCD1234567",
  "location_name": "Port of Shanghai",
  "location_id": ObjectId("..."),
  "timestamp": ISODate("2024-01-01T12:00:00Z"),
  "container_location": {
    "type": "Point",
    "coordinates": [121.4737, 31.2304]
  },
  "acknowledged": false,
  "created_at": ISODate("2024-01-01T12:00:00Z")
}
```

## Geospatial Queries

### Find Containers at Location

See `find_containers_at_location.py` and `AGGREGATION_EXAMPLES.md` for detailed examples.

**Point Location (with radius):**
```javascript
{
  $geoNear: {
    near: { type: "Point", coordinates: [lon, lat] },
    distanceField: "distance",
    maxDistance: 10000, // meters
    spherical: true,
    key: "location" // Required for TimeSeries
  }
}
```

**Polygon Location:**
```javascript
{
  location: {
    $geoWithin: {
      $geometry: polygonGeometry
    }
  }
}
```

## Alert System

The alert system uses MongoDB Change Streams to monitor new container insertions and check if they're within location polygons.

**Start Monitor:**
```bash
python monitor_containers.py
```

See `ALERT_SYSTEM.md` for detailed documentation.

## Performance

- **Query Time Display**: Both Regular and TimeSeries searches display execution time
- **Timeout**: Frontend API timeout set to 5 minutes for long-running queries
- **Indexes**: Automatic creation of geospatial and metadata indexes
- **Batch Processing**: Data generation uses batch inserts for efficiency

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```bash
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

### Atlas Search Setup

1. Create a search index named "default" in MongoDB Atlas
2. Configure autocomplete on `name`, `city`, and `country` fields
3. See `app/backend/ATLAS_SEARCH_SETUP.md` for details

## Documentation

- `AGGREGATION_EXAMPLES.md` - Geospatial aggregation examples
- `ALERT_SYSTEM.md` - Alert system documentation
- `app/backend/ATLAS_SEARCH_SETUP.md` - Atlas Search setup guide

## Technologies

- **Backend**: FastAPI, Python, PyMongo
- **Frontend**: React, Vite, Leaflet, Axios
- **Database**: MongoDB (Atlas or self-hosted)
- **Search**: MongoDB Atlas Search

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

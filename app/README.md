# GeoFence Web Application

A web application for tracking shipping containers and monitoring geospatial alerts.

## Features

1. **Container Tracker**: Track a specific container and visualize its movement on a map
2. **Alerts Grid**: View and filter all alerts with various filtering options
3. **Location Search**: Search for containers that passed through a specific location within a time period

## Project Structure

```
app/
├── backend/          # FastAPI backend
│   ├── main.py      # API server
│   └── requirements.txt
└── frontend/         # React frontend
    ├── src/
    │   ├── components/
    │   │   ├── ContainerTracker.jsx
    │   │   ├── AlertsGrid.jsx
    │   │   └── LocationSearch.jsx
    │   ├── services/
    │   │   └── api.js
    │   ├── App.jsx
    │   └── main.jsx
    ├── package.json
    └── vite.config.js
```

## Setup

### Backend Setup

1. Navigate to backend directory:
```bash
cd app/backend
```

2. Create virtual environment (optional but recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Ensure `.env` file exists in the project root with `MONGODB_URI` set

5. Run the backend server:
```bash
python main.py
# Or with uvicorn directly:
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd app/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## API Endpoints

### Container Tracking
- `GET /api/containers/{container_id}/track` - Get container movement history
  - Query params: `start_date`, `end_date` (optional)

### Alerts
- `GET /api/alerts` - Get alerts with filtering
  - Query params: `page`, `limit`, `container_id`, `shipping_line`, `location_name`, `acknowledged`, `start_date`, `end_date`
- `POST /api/alerts/{alert_id}/acknowledge` - Acknowledge an alert

### Locations
- `GET /api/locations` - Get list of locations
  - Query params: `search`, `location_type`
- `GET /api/locations/{location_name}/containers` - Get containers at a location
  - Query params: `start_date`, `end_date`, `radius_meters`, `page`, `limit`

### Statistics
- `GET /api/stats` - Get general statistics

## Usage

### Track a Container

1. Navigate to the "Track Container" page
2. Enter a container ID (e.g., from your containers collection)
3. Optionally set start and end dates
4. Click "Track Container"
5. View the container's movement path on the map with markers showing each reading

### View Alerts

1. Navigate to the "Alerts" page
2. Use the filter options to search for specific alerts:
   - Container ID
   - Shipping Line
   - Location Name
   - Acknowledged status
   - Date range
3. Click "Search" to apply filters
4. Acknowledge alerts by clicking the "Acknowledge" button

### Search Containers by Location

1. Navigate to the "Location Search" page
2. Select a location from the dropdown
3. Optionally set a time period (start and end dates)
4. Set the search radius in meters
5. Click "Search Containers"
6. View the list of containers that passed through the location

## Development

### Backend Development

The backend uses FastAPI with automatic API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Frontend Development

The frontend uses Vite for fast development:
- Hot module replacement enabled
- Proxy configured for API calls to backend

## Production Build

### Frontend

```bash
cd app/frontend
npm run build
```

The built files will be in `app/frontend/dist/`

### Backend

The backend can be deployed using any ASGI server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

For production, consider using:
- Gunicorn with uvicorn workers
- Docker containerization
- Environment-specific configuration

## Technologies

- **Backend**: FastAPI, PyMongo, Uvicorn
- **Frontend**: React, React Router, Leaflet (maps), Axios, Vite
- **Maps**: OpenStreetMap tiles via Leaflet


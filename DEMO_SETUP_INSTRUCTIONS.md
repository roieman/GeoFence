# GeoFence Demo - Setup Instructions

This guide will walk you through setting up and running the GeoFence demo application step by step.

## Prerequisites

Before starting, ensure you have the following installed:

- **Python 3.7+** (check with `python3 --version`)
- **Node.js 16+** and **npm** (check with `node --version` and `npm --version`)
- **MongoDB** (local installation or MongoDB Atlas account)
  - For local MongoDB: Ensure MongoDB is running on `localhost:27017`
  - For MongoDB Atlas: Have your connection string ready

## Step 1: Install Dependencies

### 1.1 Install Python Dependencies

```bash
# From the project root directory
pip install -r requirements.txt
pip install -r app/backend/requirements.txt
```

**Note:** You may want to use a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r app/backend/requirements.txt
```

### 1.2 Install Frontend Dependencies

```bash
cd app/frontend
npm install
cd ../..
```

## Step 2: Configure Environment

Create a `.env` file in the project root directory:

### Option A: Local MongoDB (Recommended for Demo)

```bash
# Create .env file
echo "DEBUG=true" > .env
```

This will use `mongodb://localhost:27017` automatically.

**Important:** Make sure MongoDB is running locally:
```bash
# Test MongoDB connection
mongosh --eval 'db.adminCommand("ping")'
```

### Option B: MongoDB Atlas (Cloud)

```bash
# Create .env file
echo "MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority" > .env
```

Replace `username`, `password`, and `cluster` with your actual Atlas credentials.

## Step 3: Generate Data (IN ORDER)

**⚠️ IMPORTANT: Run these scripts in the exact order shown below.**

### 3.1 Generate Locations Data

This creates the location database (ports, terminals, facilities):

```bash
# Generate 300,000 locations
python3 generate_locations.py geofence locations 300000
```

**What this does:**
- Creates ~20 major ports worldwide
- Creates ~15 major train terminals
- Generates 300,000+ industrial facilities
- Creates geospatial indexes automatically

**Expected time:** 5-15 minutes depending on your system

**Expected output:**
```
Creating locations collection...
✓ Created 300000 locations
✓ Created 2dsphere index
```

### 3.2 Create Database Indexes

This optimizes database queries:

```bash
python3 create_indexes.py
```

**Expected output:**
```
✓ Created indexes successfully
```

### 3.3 Generate Container Data

This creates the container tracking data. You have two options:

#### Option A: TimeSeries Collection (Recommended)

```bash
# Generate 1,000,000 container readings over 7 days
python3 generate_containers.py geofence containers 1000000 7
```

#### Option B: Regular Collection

```bash
# Generate 1,000,000 container readings over 7 days
python3 generate_containers.py geofence containers_regular 1000000 7
```

**What this does:**
- Creates container tracking data with location readings every 15 minutes
- Generates realistic shipping routes between ports
- Creates container metadata (ID, shipping line, type, etc.)
- Creates geospatial and metadata indexes

**Expected time:** 10-30 minutes depending on your system and data size

**Expected output:**
```
Generating containers...
Progress: 100000/1000000...
Progress: 200000/1000000...
...
✓ Created 1000000 container readings
✓ Created indexes
```

### 3.4 (Optional) Quick Seed for Testing

If you want a smaller dataset for quick testing, you can use the seed script instead:

```bash
# This creates 10 locations and 1000 containers (much faster)
python3 seed_local_data.py
```

**Note:** This is only for quick testing. For the full demo, use the full data generation scripts above.

## Step 4: Start the Application Services

**⚠️ IMPORTANT: Start services in this order - Backend first, then Frontend.**

### 4.1 Start Backend Service

Open a **new terminal window** and run:

```bash
# Navigate to project root
cd /path/to/GeoFence

# Start backend (from project root, not backend directory)
python3 -m app.backend.main
```

**Expected output:**
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Backend is now running on:** http://localhost:8000

**API Documentation:** http://localhost:8000/docs

**Keep this terminal window open!**

### 4.2 Start Frontend Service

Open **another new terminal window** and run:

```bash
# Navigate to frontend directory
cd /path/to/GeoFence/app/frontend

# Start frontend
npm run dev
```

**Expected output:**
```
  VITE v5.x.x  ready in XXX ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: use --host to expose
```

**Frontend is now running on:** http://localhost:3000

**Note:** If port 3000 is in use, Vite will automatically use the next available port (3001, 3002, etc.). Check the terminal output for the actual URL.

**Keep this terminal window open!**

## Step 5: Verify Everything is Working

### 5.1 Test Backend API

Open a browser or use curl:

```bash
# Test the stats endpoint
curl http://localhost:8000/api/stats
```

**Expected response:**
```json
{
  "total_containers": 1000000,
  "total_alerts": 0,
  "unacknowledged_alerts": 0,
  "total_locations": 300000
}
```

### 5.2 Test Frontend

1. Open your browser and navigate to: **http://localhost:3000**
2. You should see the GeoFence application interface
3. Try navigating to different pages:
   - Container Tracker
   - Alerts Grid
   - Location Search

### 5.3 Verify Data is Loaded

In the frontend:
- Go to **Location Search** page
- You should see locations in the dropdown
- Try searching for a location like "Port of Shanghai"
- The search should return results

## Step 6: (Optional) Start Alert Monitor

If you want to monitor containers and generate alerts in real-time:

Open **another terminal window** and run:

```bash
cd /path/to/GeoFence
python3 monitor_containers.py
```

This will monitor new container insertions and create alerts when containers enter location boundaries.

## Troubleshooting

### Backend won't start

**Error: "ModuleNotFoundError: No module named 'app'"**
- **Solution:** Make sure you're running from the project root, not the backend directory
- Use: `python3 -m app.backend.main` (from project root)

**Error: "MongoDB connection failed"**
- **Solution:** 
  - Check if MongoDB is running: `mongosh --eval 'db.adminCommand("ping")'`
  - Verify your `.env` file has `DEBUG=true` for local MongoDB
  - Or verify your `MONGODB_URI` is correct for Atlas

### Frontend won't start

**Error: "Port 3000 is in use"**
- **Solution:** This is normal - Vite will use the next available port. Check the terminal output for the actual URL (e.g., http://localhost:3001)

**Error: "Cannot connect to backend"**
- **Solution:** 
  - Make sure the backend is running first
  - Check that backend is on port 8000
  - Check browser console for specific error messages

### Data generation issues

**Error: "Connection timeout"**
- **Solution:** 
  - Verify MongoDB is running and accessible
  - Check your `.env` configuration
  - For large datasets, this may take time - be patient

**Error: "Collection already exists"**
- **Solution:** The scripts will skip existing data. If you want to regenerate:
  ```bash
  # Connect to MongoDB and drop collections
  mongosh
  use geofence
  db.locations.drop()
  db.containers.drop()
  db.containers_regular.drop()
  ```

## Quick Reference

### Service URLs

- **Frontend:** http://localhost:3000 (or next available port)
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### Data Generation Commands (Quick Reference)

```bash
# 1. Generate locations
python3 generate_locations.py geofence locations 300000

# 2. Create indexes
python3 create_indexes.py

# 3. Generate containers (TimeSeries)
python3 generate_containers.py geofence containers 1000000 7

# OR generate containers (Regular)
python3 generate_containers.py geofence containers_regular 1000000 7
```

### Service Start Commands (Quick Reference)

```bash
# Terminal 1: Backend
cd /path/to/GeoFence
python3 -m app.backend.main

# Terminal 2: Frontend
cd /path/to/GeoFence/app/frontend
npm run dev

# Terminal 3 (Optional): Alert Monitor
cd /path/to/GeoFence
python3 monitor_containers.py
```

## Summary Checklist

- [ ] Python dependencies installed
- [ ] Node.js dependencies installed
- [ ] `.env` file created and configured
- [ ] MongoDB running and accessible
- [ ] Locations data generated (300,000 locations)
- [ ] Database indexes created
- [ ] Container data generated (1,000,000 readings)
- [ ] Backend service running on port 8000
- [ ] Frontend service running (check port in terminal)
- [ ] Can access frontend in browser
- [ ] Can see data in the application

## Need Help?

If you encounter issues:
1. Check the terminal output for error messages
2. Verify MongoDB is running and accessible
3. Check that all dependencies are installed
4. Ensure you're running commands from the correct directories
5. Review the troubleshooting section above

---

**You're all set!** The GeoFence demo application should now be running and ready to use.


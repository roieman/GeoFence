# Container Location Alert System

This system monitors container insertions and creates alerts when a container's location is within any location's polygon (like a port or facility).

## Overview

When a new container document is inserted into the `containers` collection, the system:
1. Checks if the container's location (Point) is within any location's polygon
2. If found, creates an alert document in the `alerts` collection

## Files

### 1. `monitor_containers.py`
Real-time monitoring using MongoDB Change Streams. Monitors the containers collection and automatically creates alerts.

### 2. `check_container_location.py`
Helper function that can be called after inserting a container document.

## Usage

### Option 1: Real-time Monitoring (Change Streams)

Start the monitor to watch for new container insertions:

```bash
python3 monitor_containers.py
```

The monitor will:
- Watch for new insertions in the containers collection
- Check each new container against location polygons
- Automatically create alerts when matches are found

**Stop monitoring**: Press `Ctrl+C`

### Option 2: Check After Insertion

Use the helper function in your code:

```python
from check_container_location import check_and_create_alert
import pymongo
from dotenv import load_dotenv
import os

load_dotenv()
client = pymongo.MongoClient(os.getenv("MONGODB_URI"))
db = client["geofence"]
containers = db["containers"]

# Insert a new container
new_container = {
    "metadata": {
        "container_id": "ABCD1234567",
        "shipping_line": "Maersk",
        "container_type": "standard",
        "refrigerated": False,
        "cargo_type": "electronics"
    },
    "timestamp": datetime.utcnow(),
    "location": {
        "type": "Point",
        "coordinates": [121.4737, 31.2304]  # Near Port of Shanghai
    },
    "status": "in_transit",
    "weight_kg": 15000
}

result = containers.insert_one(new_container)
container_doc = containers.find_one({"_id": result.inserted_id})

# Check and create alert
alert_id = check_and_create_alert(container_doc)
if alert_id:
    print(f"Alert created: {alert_id}")
```

### Option 3: Check Specific Container

Check an existing container:

```bash
python3 monitor_containers.py --check ABCD1234567
```

## Alert Document Structure

```json
{
  "_id": ObjectId("..."),
  "alert_type": "container_in_location",
  "timestamp": ISODate("2025-11-25T..."),
  "container": {
    "container_id": "ABCD1234567",
    "shipping_line": "Maersk",
    "container_type": "standard",
    "refrigerated": false,
    "cargo_type": "electronics",
    "location": {
      "type": "Point",
      "coordinates": [121.4737, 31.2304]
    },
    "status": "in_transit",
    "weight_kg": 15000,
    "temperature_celsius": null,
    "timestamp": ISODate("2025-11-25T...")
  },
  "location": {
    "name": "Port of Shanghai",
    "type": "port",
    "city": "Shanghai",
    "country": "China",
    "location": {
      "type": "Polygon",
      "coordinates": [[...]]
    }
  },
  "severity": "info",
  "acknowledged": false,
  "created_at": ISODate("2025-11-25T...")
}
```

## How It Works

### Geospatial Query

The system uses MongoDB's `$geoWithin` operator to check if a container's Point is within a location's Polygon:

```javascript
// Query to find locations that contain the container point
db.locations.find({
  "location": {
    "$geoWithin": {
      "$geometry": container_location  // The container's Point geometry
    }
  },
  "location.type": "Polygon"  // Only check against polygons
})
```

### Change Streams

MongoDB Change Streams provide real-time notifications of data changes:

```python
with containers.watch([{"$match": {"operationType": "insert"}}]) as stream:
    for change in stream:
        if change["operationType"] == "insert":
            container_doc = change["fullDocument"]
            # Process the new container
```

## Indexes

The alerts collection automatically creates these indexes:
- `timestamp` - For time-based queries
- `container.container_id` - For finding alerts by container
- `location.name` - For finding alerts by location
- `acknowledged` - For filtering unacknowledged alerts
- `container.location` (2dsphere) - For geospatial queries on container locations

## Querying Alerts

### Find all alerts for a specific container

```javascript
db.alerts.find({
  "container.container_id": "ABCD1234567"
}).sort({ timestamp: -1 })
```

### Find all unacknowledged alerts

```javascript
db.alerts.find({
  acknowledged: false
}).sort({ timestamp: -1 })
```

### Find alerts for a specific location

```javascript
db.alerts.find({
  "location.name": "Port of Shanghai"
}).sort({ timestamp: -1 })
```

### Find alerts in a time range

```javascript
db.alerts.find({
  timestamp: {
    $gte: ISODate("2025-11-01"),
    $lte: ISODate("2025-11-30")
  }
}).sort({ timestamp: -1 })
```

### Acknowledge an alert

```javascript
db.alerts.updateOne(
  { _id: ObjectId("...") },
  { $set: { acknowledged: true, acknowledged_at: new Date() } }
)
```

## Performance Considerations

1. **Indexes**: Ensure locations collection has a 2dsphere index on `location`
2. **Polygon Filtering**: The query only checks against locations with Polygon geometry (not Points)
3. **Change Streams**: Use appropriate resume tokens for production deployments
4. **Batch Processing**: For bulk inserts, consider processing in batches rather than one-by-one

## Error Handling

The monitor includes error handling and will:
- Continue monitoring even if one container fails to process
- Print warnings for containers without location data
- Close connections properly on exit

## Production Deployment

For production, consider:
1. Using MongoDB Atlas Triggers (serverless functions)
2. Adding retry logic for failed alert creations
3. Implementing alert deduplication (avoid duplicate alerts for same container/location)
4. Adding alert severity levels based on location type or container status
5. Sending notifications (email, webhooks, etc.) when alerts are created


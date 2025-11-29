# Aggregation Pipeline Examples for GeoSpatial Queries

## Finding Containers That Passed Through a Specific Location

### Example: Find all containers that passed through Port of Shanghai

```javascript
// Step 1: Get the location coordinates (from locations collection)
var location = db.locations.findOne({ name: "Port of Shanghai" });
var coordinates = location.location.coordinates; // [lon, lat]

// Step 2: Aggregation pipeline to find containers
db.containers.aggregate([
  // Stage 1: $geoNear - Find containers within radius
  // NOTE: For TimeSeries collections, you MUST specify the 'key' option
  {
    $geoNear: {
      near: {
        type: "Point",
        coordinates: [121.4737, 31.2304]  // [longitude, latitude]
      },
      distanceField: "distance",  // Distance in meters
      maxDistance: 10000,  // 10km radius
      spherical: true,
      key: "location"  // REQUIRED for TimeSeries collections
    }
  },
  
  // Stage 2: Group by container ID to get unique containers
  {
    $group: {
      _id: "$metadata.container_id",
      container_id: { $first: "$metadata.container_id" },
      shipping_line: { $first: "$metadata.shipping_line" },
      container_type: { $first: "$metadata.container_type" },
      refrigerated: { $first: "$metadata.refrigerated" },
      cargo_type: { $first: "$metadata.cargo_type" },
      first_seen: { $min: "$timestamp" },
      last_seen: { $max: "$timestamp" },
      min_distance: { $min: "$distance" },
      readings_count: { $sum: 1 }
    }
  },
  
  // Stage 3: Sort by first seen time
  {
    $sort: { first_seen: 1 }
  },
  
  // Stage 4: Add computed fields
  {
    $addFields: {
      time_at_location: {
        $subtract: ["$last_seen", "$first_seen"]
      }
    }
  }
])
```

### Key Points:

1. **$geoNear must be the first stage** in the aggregation pipeline
2. **For TimeSeries collections**, you must specify `key: "location"` in the `$geoNear` stage
3. **distanceField** adds a field with the distance in meters from the center point
4. **maxDistance** limits results to containers within the specified radius
5. **spherical: true** uses spherical geometry (required for Earth distances)

## Alternative: Using $match with $near (Simpler but less flexible)

```javascript
db.containers.aggregate([
  {
    $match: {
      location: {
        $near: {
          $geometry: {
            type: "Point",
            coordinates: [121.4737, 31.2304]
          },
          $maxDistance: 10000  // 10km in meters
        }
      }
    }
  },
  {
    $group: {
      _id: "$metadata.container_id",
      container_id: { $first: "$metadata.container_id" },
      first_seen: { $min: "$timestamp" },
      last_seen: { $max: "$timestamp" },
      readings_count: { $sum: 1 }
    }
  }
])
```

## Finding Containers Within Multiple Locations

### Using $lookup to join with locations collection

```javascript
db.containers.aggregate([
  // Stage 1: Lookup locations
  {
    $lookup: {
      from: "locations",
      let: { container_location: "$location" },
      pipeline: [
        {
          $match: {
            $expr: {
              $geoWithin: {
                $geometry: "$$container_location",
                $geometry: "$location"
              }
            }
          }
        }
      ],
      as: "nearby_locations"
    }
  },
  
  // Stage 2: Filter containers that are near any location
  {
    $match: {
      nearby_locations: { $ne: [] }
    }
  },
  
  // Stage 3: Group by container and location
  {
    $unwind: "$nearby_locations"
  },
  {
    $group: {
      _id: {
        container_id: "$metadata.container_id",
        location_name: "$nearby_locations.name"
      },
      container_id: { $first: "$metadata.container_id" },
      location_name: { $first: "$nearby_locations.name" },
      first_seen: { $min: "$timestamp" },
      last_seen: { $max: "$timestamp" }
    }
  }
])
```

## Finding Containers Near a Location with Additional Filters

```javascript
db.containers.aggregate([
  {
    $geoNear: {
      near: {
        type: "Point",
        coordinates: [121.4737, 31.2304]
      },
      distanceField: "distance",
      maxDistance: 10000,
      spherical: true,
      key: "location",
      // Add additional query filters
      query: {
        "metadata.refrigerated": true,  // Only refrigerated containers
        "metadata.shipping_line": "Maersk",  // Specific shipping line
        timestamp: {
          $gte: ISODate("2025-11-01"),
          $lte: ISODate("2025-11-30")
        }
      }
    }
  },
  {
    $group: {
      _id: "$metadata.container_id",
      container_id: { $first: "$metadata.container_id" },
      shipping_line: { $first: "$metadata.shipping_line" },
      first_seen: { $min: "$timestamp" },
      last_seen: { $max: "$timestamp" },
      min_distance: { $min: "$distance" },
      readings_count: { $sum: 1 }
    }
  }
])
```

## Finding Containers That Passed Through Multiple Locations

```javascript
// Find containers that passed through both Port of Shanghai and Port of Los Angeles
var shanghai = db.locations.findOne({ name: "Port of Shanghai" });
var losAngeles = db.locations.findOne({ name: "Port of Los Angeles" });

// Get containers near Shanghai
var containersAtShanghai = db.containers.aggregate([
  {
    $geoNear: {
      near: {
        type: "Point",
        coordinates: shanghai.location.coordinates
      },
      distanceField: "distance",
      maxDistance: 10000,
      spherical: true,
      key: "location"
    }
  },
  {
    $group: {
      _id: "$metadata.container_id"
    }
  }
]).toArray();

var containerIds = containersAtShanghai.map(c => c._id);

// Find which of those containers also passed through Los Angeles
db.containers.aggregate([
  {
    $match: {
      "metadata.container_id": { $in: containerIds }
    }
  },
  {
    $geoNear: {
      near: {
        type: "Point",
        coordinates: losAngeles.location.coordinates
      },
      distanceField: "distance",
      maxDistance: 10000,
      spherical: true,
      key: "location"
    }
  },
  {
    $group: {
      _id: "$metadata.container_id",
      container_id: { $first: "$metadata.container_id" },
      shipping_line: { $first: "$metadata.shipping_line" }
    }
  }
])
```

## Performance Tips

1. **Indexes**: Ensure you have a 2dsphere index on the `location` field
   ```javascript
   db.containers.createIndex({ location: "2dsphere" })
   ```

2. **TimeSeries Collections**: The `key: "location"` option is required for `$geoNear` on TimeSeries collections

3. **Radius**: Use appropriate radius values - larger radii will be slower

4. **Filter Early**: Add filters in the `query` option of `$geoNear` to reduce data processed

5. **Limit Results**: Add `$limit` stage if you only need a subset of results

## Python Example

See `find_containers_at_location.py` for a complete Python implementation.


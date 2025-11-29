import React, { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Circle, Polygon, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix for default marker icons in React-Leaflet
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

function LocationMap({ location, containers, radiusMeters, onClose }) {
  const mapRef = useRef(null)

  // Get center point for map
  const getMapCenter = () => {
    if (location?.location?.type === "Point") {
      const [lon, lat] = location.location.coordinates
      return [lat, lon]
    } else if (location?.location?.type === "Polygon") {
      // Get center of polygon (approximate - use first coordinate)
      const coords = location.location.coordinates[0]
      if (coords && coords.length > 0) {
        const [lon, lat] = coords[0]
        return [lat, lon]
      }
    }
    // Default center
    return [51.9225, 4.4772] // Rotterdam
  }

  // Get bounds for map to fit all containers
  const getBounds = () => {
    const points = []
    
    // Add location center/points
    if (location?.location?.type === "Point") {
      const [lon, lat] = location.location.coordinates
      points.push([lat, lon])
    } else if (location?.location?.type === "Polygon") {
      const coords = location.location.coordinates[0]
      coords.forEach(([lon, lat]) => {
        points.push([lat, lon])
      })
    }
    
    // Add container locations
    containers.forEach(container => {
      if (container.last_location?.coordinates) {
        const [lon, lat] = container.last_location.coordinates
        points.push([lat, lon])
      }
    })
    
    if (points.length > 0) {
      return L.latLngBounds(points)
    }
    return null
  }

  useEffect(() => {
    if (mapRef.current) {
      const bounds = getBounds()
      if (bounds) {
        // Use setTimeout to ensure map is fully rendered
        setTimeout(() => {
          if (mapRef.current) {
            mapRef.current.fitBounds(bounds, { padding: [50, 50] })
          }
        }, 100)
      }
    }
  }, [containers, location])

  const renderLocationGeometry = () => {
    if (location?.location?.type === "Point") {
      const [lon, lat] = location.location.coordinates
      return (
        <Circle
          center={[lat, lon]}
          radius={radiusMeters}
          pathOptions={{
            color: '#3388ff',
            fillColor: '#3388ff',
            fillOpacity: 0.2,
            weight: 2
          }}
        >
          <Popup>
            <div>
              <strong>{location.name}</strong>
              <br />
              Type: {location.type}
              <br />
              Search Radius: {radiusMeters.toLocaleString()} meters
            </div>
          </Popup>
        </Circle>
      )
    } else if (location?.location?.type === "Polygon") {
      const coords = location.location.coordinates[0].map(([lon, lat]) => [lat, lon])
      return (
        <Polygon
          positions={coords}
          pathOptions={{
            color: '#3388ff',
            fillColor: '#3388ff',
            fillOpacity: 0.2,
            weight: 2
          }}
        >
          <Popup>
            <div>
              <strong>{location.name}</strong>
              <br />
              Type: {location.type}
              <br />
              Geometry: Polygon
            </div>
          </Popup>
        </Polygon>
      )
    }
    return null
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.5)',
      zIndex: 2000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: '8px',
        width: '90%',
        height: '90%',
        maxWidth: '1400px',
        maxHeight: '900px',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
      }}>
            <div style={{
              padding: '20px',
              borderBottom: '1px solid #ddd',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <h2 style={{ margin: 0 }}>Location Map: {location?.name}</h2>
                <p style={{ margin: '5px 0 0 0', color: '#666' }}>
                  Showing {containers.length} containers at this location
                  {location?.location?.type === "Point" && ` (within ${radiusMeters.toLocaleString()}m radius)`}
                  {location?.location?.type === "Polygon" && " (within polygon boundaries)"}
                </p>
              </div>
              <button
                className="btn btn-secondary"
                onClick={onClose}
                style={{ fontSize: '16px', padding: '10px 20px' }}
              >
                Close
              </button>
            </div>
        <div style={{ flex: 1, position: 'relative' }}>
          <MapContainer
            center={getMapCenter()}
            zoom={location?.location?.type === "Point" ? 12 : 10}
            style={{ height: '100%', width: '100%' }}
            ref={mapRef}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            
            {/* Render location geometry (circle for Point, polygon for Polygon) */}
            {renderLocationGeometry()}
            
            {/* Render container markers */}
            {containers.map((container, idx) => {
              if (!container.last_location?.coordinates) return null
              const [lon, lat] = container.last_location.coordinates
              
              return (
                <Marker
                  key={container.container_id || idx}
                  position={[lat, lon]}
                  icon={L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                  })}
                >
                  <Popup>
                    <div>
                      <strong>Container: {container.container_id}</strong>
                      <br />
                      Shipping Line: {container.shipping_line || 'N/A'}
                      <br />
                      Type: {container.container_type || 'N/A'}
                      <br />
                      Status: {container.last_status || 'N/A'}
                      <br />
                      Last Seen: {container.last_seen ? new Date(container.last_seen).toLocaleString() : 'N/A'}
                      {container.min_distance && (
                        <>
                          <br />
                          Distance: {Math.round(container.min_distance)}m
                        </>
                      )}
                    </div>
                  </Popup>
                </Marker>
              )
            })}
          </MapContainer>
        </div>
      </div>
    </div>
  )
}

export default LocationMap


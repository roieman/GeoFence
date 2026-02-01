import React, { useState, useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Polygon, Popup, useMap, FeatureGroup, CircleMarker } from 'react-leaflet'
import { geofencesAPI, referenceAPI, clustersAPI } from '../services/api'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet-draw/dist/leaflet.draw.css'
import 'leaflet-draw'

const GEOFENCE_COLORS = {
  'Terminal': '#2196F3',
  'Depot': '#4CAF50',
  'Rail ramp': '#FF9800',
}

// Colors for nested polygons (children shown with dashed lines)
const NESTED_STYLES = {
  parent: { weight: 3, dashArray: null, fillOpacity: 0.3 },
  child: { weight: 2, dashArray: '5, 5', fillOpacity: 0.5 }
}

// Component to fit map to selected geofence
function FitToGeofence({ geofence }) {
  const map = useMap()

  useEffect(() => {
    if (geofence && geofence.geometry && geofence.geometry.coordinates) {
      const coords = geofence.geometry.coordinates[0]
      if (coords && coords.length > 0) {
        const bounds = coords.map(c => [c[1], c[0]])
        map.fitBounds(bounds, { padding: [50, 50] })
      }
    }
  }, [geofence, map])

  return null
}

// Component to fit map to all geofences
function FitToAll({ geofences, trigger }) {
  const map = useMap()

  useEffect(() => {
    if (trigger && geofences && geofences.length > 0) {
      const allCoords = []
      geofences.forEach(gf => {
        if (gf.geometry && gf.geometry.coordinates && gf.geometry.coordinates[0]) {
          gf.geometry.coordinates[0].forEach(c => {
            allCoords.push([c[1], c[0]])
          })
        }
      })
      if (allCoords.length > 0) {
        map.fitBounds(allCoords, { padding: [20, 20] })
      }
    }
  }, [trigger, geofences, map])

  return null
}

// Calculate centroid of polygon
function getCentroid(geometry) {
  if (!geometry || !geometry.coordinates || !geometry.coordinates[0]) return null
  const coords = geometry.coordinates[0]
  let latSum = 0, lngSum = 0
  coords.forEach(c => {
    lngSum += c[0]
    latSum += c[1]
  })
  return [latSum / coords.length, lngSum / coords.length]
}

// Drawing control component
function DrawControl({ onCreated }) {
  const map = useMap()
  const drawControlRef = useRef(null)
  const featureGroupRef = useRef(null)

  useEffect(() => {
    // Create a feature group to store drawn items
    featureGroupRef.current = new L.FeatureGroup()
    map.addLayer(featureGroupRef.current)

    // Create draw control
    drawControlRef.current = new L.Control.Draw({
      position: 'topright',
      draw: {
        polygon: {
          allowIntersection: false,
          shapeOptions: {
            color: '#2196F3',
            weight: 2
          }
        },
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
        rectangle: false
      },
      edit: {
        featureGroup: featureGroupRef.current,
        remove: false,
        edit: false
      }
    })

    map.addControl(drawControlRef.current)

    // Handle draw created event
    const handleDrawCreated = (e) => {
      const layer = e.layer
      const coords = layer.getLatLngs()[0].map(ll => [ll.lng, ll.lat])
      coords.push(coords[0]) // Close the polygon

      // Clear the drawn layer (we'll save to DB instead)
      featureGroupRef.current.clearLayers()

      onCreated(coords)
    }

    map.on(L.Draw.Event.CREATED, handleDrawCreated)

    return () => {
      map.off(L.Draw.Event.CREATED, handleDrawCreated)
      if (drawControlRef.current) {
        map.removeControl(drawControlRef.current)
      }
      if (featureGroupRef.current) {
        map.removeLayer(featureGroupRef.current)
      }
    }
  }, [map, onCreated])

  return null
}

function GeofenceManager() {
  const [geofences, setGeofences] = useState([])
  const [selectedGeofence, setSelectedGeofence] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({ type_id: '', search: '', cluster_id: '' })
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0 })
  const [mapGeofences, setMapGeofences] = useState([]) // Geofences for map (all matching current filter)
  const [geofenceTypes, setGeofenceTypes] = useState([])
  const [showEditModal, setShowEditModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [newGeofenceCoords, setNewGeofenceCoords] = useState(null)
  const [fitAllTrigger, setFitAllTrigger] = useState(0)

  // Clusters state
  const [clusters, setClusters] = useState([])
  const [showClusterModal, setShowClusterModal] = useState(false)
  const [clusterForm, setClusterForm] = useState({ name: '', description: '', color: '#1a237e' })
  const [editingCluster, setEditingCluster] = useState(null)

  // Tab state for switching between Geofences and Clusters views
  const [activeTab, setActiveTab] = useState('geofences')

  // Load geofence types
  useEffect(() => {
    referenceAPI.geofenceTypes()
      .then(res => setGeofenceTypes(res.data.types))
      .catch(err => console.error('Failed to load geofence types:', err))
  }, [])

  // Load clusters
  useEffect(() => {
    loadClusters()
  }, [])

  const loadClusters = async () => {
    try {
      const response = await clustersAPI.list()
      setClusters(response.data.clusters || [])
    } catch (err) {
      console.error('Failed to load clusters:', err)
    }
  }

  // Load geofences when filters change
  useEffect(() => {
    loadGeofences()
    loadMapGeofences()
  }, [filters])

  // Load table page when page changes
  useEffect(() => {
    loadGeofences()
  }, [pagination.page])

  const loadMapGeofences = async () => {
    try {
      // Load ALL geofences matching current filter (for map display)
      const params = { limit: 2000 }
      if (filters.type_id) params.type_id = filters.type_id
      if (filters.search) params.search = filters.search

      const response = await geofencesAPI.list(params)
      setMapGeofences(response.data.geofences || [])
    } catch (err) {
      console.error('Failed to load map geofences:', err)
    }
  }

  const loadGeofences = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {
        page: pagination.page,
        limit: pagination.limit,
      }
      if (filters.type_id) params.type_id = filters.type_id
      if (filters.search) params.search = filters.search

      const response = await geofencesAPI.list(params)
      setGeofences(response.data.geofences || [])
      setPagination(prev => ({ ...prev, ...response.data.pagination }))
    } catch (err) {
      console.error('Failed to load geofences:', err)
      setError(err.message || 'Failed to load geofences')
    } finally {
      setLoading(false)
    }
  }

  const handleResetFilters = () => {
    setFilters({ type_id: '', search: '', cluster_id: '' })
    setPagination(prev => ({ ...prev, page: 1 }))
  }

  const handleFilterChange = (e) => {
    const { name, value } = e.target
    setFilters(prev => ({ ...prev, [name]: value }))
    setPagination(prev => ({ ...prev, page: 1 }))
  }

  const handleGeofenceClick = (geofence) => {
    setSelectedGeofence(geofence)
  }

  const handleEdit = (geofence) => {
    setEditForm({
      _id: geofence._id,
      name: geofence.properties.name,
      description: geofence.properties.description || '',
      typeId: geofence.properties.typeId,
      UNLOCode: geofence.properties.UNLOCode || '',
      SMDGCode: geofence.properties.SMDGCode || '',
      clusterId: geofence.properties.clusterId || '',
      parentId: geofence.properties.parentId || '',
    })
    setShowEditModal(true)
  }

  const handleSaveEdit = async () => {
    try {
      await geofencesAPI.update(editForm._id, {
        name: editForm.name,
        description: editForm.description,
        typeId: editForm.typeId,
        UNLOCode: editForm.UNLOCode,
        SMDGCode: editForm.SMDGCode,
        clusterId: editForm.clusterId || null,
        parentId: editForm.parentId || null,
      })
      setShowEditModal(false)
      loadGeofences()
      loadMapGeofences()
    } catch (err) {
      alert('Failed to update geofence: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleDelete = async (geofence) => {
    if (!window.confirm(`Delete geofence "${geofence.properties.name}"?`)) return
    try {
      await geofencesAPI.delete(geofence._id)
      loadGeofences()
      loadMapGeofences()
      setSelectedGeofence(null)
    } catch (err) {
      alert('Failed to delete geofence: ' + (err.response?.data?.detail || err.message))
    }
  }

  // Cluster management functions
  const handleCreateCluster = () => {
    setClusterForm({ name: '', description: '', color: '#1a237e' })
    setEditingCluster(null)
    setShowClusterModal(true)
  }

  const handleEditCluster = (cluster) => {
    setClusterForm({
      name: cluster.name,
      description: cluster.description || '',
      color: cluster.color || '#1a237e'
    })
    setEditingCluster(cluster)
    setShowClusterModal(true)
  }

  const handleSaveCluster = async () => {
    try {
      if (editingCluster) {
        await clustersAPI.update(editingCluster._id, clusterForm)
      } else {
        await clustersAPI.create(clusterForm)
      }
      setShowClusterModal(false)
      loadClusters()
    } catch (err) {
      alert('Failed to save cluster: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleDeleteCluster = async (cluster) => {
    if (!window.confirm(`Delete cluster "${cluster.name}"? Geofences will be unassigned.`)) return
    try {
      await clustersAPI.delete(cluster._id)
      loadClusters()
      loadGeofences()
      loadMapGeofences()
    } catch (err) {
      alert('Failed to delete cluster: ' + (err.response?.data?.detail || err.message))
    }
  }

  // Get parent geofence name for display
  const getParentName = (parentId) => {
    if (!parentId) return null
    const parent = mapGeofences.find(g => g._id === parentId)
    return parent?.properties?.name || parentId
  }

  // Get cluster name for display
  const getClusterName = (clusterId) => {
    if (!clusterId) return null
    const cluster = clusters.find(c => c._id === clusterId)
    return cluster?.name || clusterId
  }

  // Check if geofence has children (is a parent)
  const hasChildren = (geofenceId) => {
    return mapGeofences.some(g => g.properties?.parentId === geofenceId)
  }

  const handleExportCSV = async () => {
    try {
      const response = await geofencesAPI.exportCSV(filters.type_id)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'geofences.csv')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Export failed: ' + err.message)
    }
  }

  const handleExportGeoJSON = async () => {
    try {
      const response = await geofencesAPI.exportGeoJSON(filters.type_id)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'geofences.geojson')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Export failed: ' + err.message)
    }
  }

  const handleImportCSV = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      const response = await geofencesAPI.importCSV(file)
      alert(`Imported: ${response.data.imported}, Updated: ${response.data.updated}`)
      loadGeofences()
    } catch (err) {
      alert('Import failed: ' + (err.response?.data?.detail || err.message))
    }
    e.target.value = ''
  }

  // Handle polygon drawn on map
  const handlePolygonCreated = (coords) => {
    setNewGeofenceCoords(coords)
    setEditForm({
      name: '',
      description: '',
      typeId: 'Depot',
      UNLOCode: '',
      SMDGCode: '',
    })
    setShowCreateModal(true)
  }

  const handleSaveNewGeofence = async () => {
    if (!editForm.name) {
      alert('Please enter a name for the geofence')
      return
    }

    try {
      await geofencesAPI.create({
        name: editForm.name,
        description: editForm.description,
        typeId: editForm.typeId,
        UNLOCode: editForm.UNLOCode,
        SMDGCode: editForm.SMDGCode,
        geometry: {
          type: 'Polygon',
          coordinates: [newGeofenceCoords]
        }
      })
      setShowCreateModal(false)
      setNewGeofenceCoords(null)
      loadGeofences()
      loadMapGeofences()
    } catch (err) {
      alert('Failed to create geofence: ' + (err.response?.data?.detail || err.message))
    }
  }

  const getPolygonCoords = (geometry) => {
    if (!geometry || !geometry.coordinates || !geometry.coordinates[0]) return []
    return geometry.coordinates[0].map(coord => [coord[1], coord[0]]) // [lat, lng]
  }

  return (
    <div className="geofence-manager">
      <div className="page-header">
        <h2>Geofence Management</h2>
        <div className="header-actions">
          <button onClick={handleExportCSV} className="btn btn-secondary">
            Export CSV
          </button>
          <button onClick={handleExportGeoJSON} className="btn btn-secondary">
            Export GeoJSON
          </button>
          <label className="btn btn-primary">
            Import CSV
            <input type="file" accept=".csv" onChange={handleImportCSV} hidden />
          </label>
        </div>
      </div>

      {/* Tabs for Geofences vs Clusters */}
      <div className="tab-buttons" style={{ marginBottom: '1rem' }}>
        <button
          className={`tab-btn ${activeTab === 'geofences' ? 'active' : ''}`}
          onClick={() => setActiveTab('geofences')}
        >
          Geofences ({pagination.total})
        </button>
        <button
          className={`tab-btn ${activeTab === 'clusters' ? 'active' : ''}`}
          onClick={() => setActiveTab('clusters')}
        >
          Clusters ({clusters.length})
        </button>
      </div>

      {/* Instructions */}
      <div className="info-banner">
        <strong>Tip:</strong> Click the polygon icon (pentagon) in the top-right of the map to draw a new geofence.
        Click "Fit to All" to zoom to see all geofences. Use Clusters to group related geofences. Set Parent to nest polygons.
        <button
          onClick={() => setFitAllTrigger(t => t + 1)}
          className="btn btn-small btn-primary"
          style={{ marginLeft: '1rem' }}
        >
          Fit to All
        </button>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <input
          type="text"
          name="search"
          placeholder="Search by name, code..."
          value={filters.search}
          onChange={handleFilterChange}
          className="filter-input"
        />
        <select
          name="type_id"
          value={filters.type_id}
          onChange={handleFilterChange}
          className="filter-select"
        >
          <option value="">All Types</option>
          {geofenceTypes.map(type => (
            <option key={type} value={type}>{type}</option>
          ))}
        </select>
        <select
          name="cluster_id"
          value={filters.cluster_id}
          onChange={handleFilterChange}
          className="filter-select"
        >
          <option value="">All Clusters</option>
          {clusters.map(cluster => (
            <option key={cluster._id} value={cluster._id}>{cluster.name}</option>
          ))}
        </select>
        {(filters.search || filters.type_id || filters.cluster_id) && (
          <button onClick={handleResetFilters} className="btn btn-secondary btn-small">
            Reset
          </button>
        )}
        <div className="results-count">
          <strong>{pagination.total}</strong> geofences in table &bull; <strong>{mapGeofences.length}</strong> on map
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="map-container" style={{ height: '500px' }}>
        <MapContainer
          center={[20, 0]}
          zoom={2}
          style={{ height: '100%', width: '100%' }}
          maxBounds={[[-90, -180], [90, 180]]}
          maxBoundsViscosity={1.0}
          minZoom={2}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            noWrap={true}
          />

          <DrawControl onCreated={handlePolygonCreated} />

          {selectedGeofence && <FitToGeofence geofence={selectedGeofence} />}
          <FitToAll geofences={mapGeofences} trigger={fitAllTrigger} />

          {/* Geofence markers (visible at low zoom) - show ALL geofences */}
          {mapGeofences.map(gf => {
            const centroid = getCentroid(gf.geometry)
            if (!centroid) return null
            return (
              <CircleMarker
                key={`marker-${gf._id}`}
                center={centroid}
                radius={6}
                pathOptions={{
                  color: GEOFENCE_COLORS[gf.properties?.typeId] || '#666',
                  fillColor: GEOFENCE_COLORS[gf.properties?.typeId] || '#666',
                  fillOpacity: 0.8,
                  weight: 1
                }}
                eventHandlers={{
                  click: () => handleGeofenceClick(gf)
                }}
              />
            )
          })}

          {/* Geofence polygons - show ALL geofences */}
          {mapGeofences.map(gf => {
            const coords = getPolygonCoords(gf.geometry)
            if (coords.length === 0) return null

            // Determine if this is a child (nested) geofence
            const isChild = !!gf.properties?.parentId
            const isParent = hasChildren(gf._id)
            const nestedStyle = isChild ? NESTED_STYLES.child : NESTED_STYLES.parent

            return (
              <Polygon
                key={gf._id}
                positions={coords}
                pathOptions={{
                  color: GEOFENCE_COLORS[gf.properties?.typeId] || '#666',
                  fillOpacity: selectedGeofence?._id === gf._id ? 0.6 : nestedStyle.fillOpacity,
                  weight: selectedGeofence?._id === gf._id ? 4 : nestedStyle.weight,
                  dashArray: isChild ? nestedStyle.dashArray : null
                }}
                eventHandlers={{
                  click: () => handleGeofenceClick(gf)
                }}
              >
                <Popup>
                  <div className="geofence-popup">
                    <h4>{gf.properties?.name}</h4>
                    <p><strong>Type:</strong> {gf.properties?.typeId}</p>
                    {gf.properties?.clusterId && (
                      <p><strong>Cluster:</strong> {getClusterName(gf.properties.clusterId)}</p>
                    )}
                    {gf.properties?.parentId && (
                      <p><strong>Parent:</strong> {getParentName(gf.properties.parentId)}</p>
                    )}
                    {isParent && (
                      <p><strong>Has nested children</strong></p>
                    )}
                    <p><strong>Description:</strong> {gf.properties?.description || 'N/A'}</p>
                    <p><strong>UNLO:</strong> {gf.properties?.UNLOCode || 'N/A'}</p>
                    <p><strong>SMDG:</strong> {gf.properties?.SMDGCode || 'N/A'}</p>
                    <div className="popup-actions">
                      <button onClick={() => handleEdit(gf)} className="btn btn-small">
                        Edit
                      </button>
                      <button onClick={() => handleDelete(gf)} className="btn btn-small btn-danger">
                        Delete
                      </button>
                    </div>
                  </div>
                </Popup>
              </Polygon>
            )
          })}
        </MapContainer>
      </div>

      {/* Geofence list - only show when geofences tab is active */}
      {activeTab === 'geofences' && (
        <div className="geofence-list">
          <h3>Geofences ({pagination.total})</h3>
          {loading ? (
            <div className="loading">Loading...</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Cluster</th>
                  <th>Parent</th>
                  <th>UNLO Code</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {geofences.map(gf => (
                  <tr
                    key={gf._id}
                    className={selectedGeofence?._id === gf._id ? 'selected' : ''}
                    onClick={() => handleGeofenceClick(gf)}
                  >
                    <td>
                      {gf.properties?.name}
                      {hasChildren(gf._id) && <span title="Has nested children" style={{ marginLeft: '0.5rem', color: '#1a237e' }}>&#9660;</span>}
                    </td>
                    <td>
                      <span className={`type-badge type-${gf.properties?.typeId?.toLowerCase().replace(' ', '-')}`}>
                        {gf.properties?.typeId}
                      </span>
                    </td>
                    <td>{getClusterName(gf.properties?.clusterId) || '-'}</td>
                    <td>{getParentName(gf.properties?.parentId) || '-'}</td>
                    <td>{gf.properties?.UNLOCode || '-'}</td>
                    <td>
                      <button onClick={(e) => { e.stopPropagation(); handleEdit(gf) }} className="btn btn-small">
                        Edit
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(gf) }} className="btn btn-small btn-danger">
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

        {/* Pagination */}
        {pagination.pages > 1 && (
          <div className="pagination">
            <button
              disabled={pagination.page <= 1}
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
            >
              Previous
            </button>
            <span>Page {pagination.page} of {pagination.pages}</span>
            <button
              disabled={pagination.page >= pagination.pages}
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
            >
              Next
            </button>
          </div>
        )}
        </div>
      )}

      {/* Clusters list - only show when clusters tab is active */}
      {activeTab === 'clusters' && (
        <div className="clusters-list">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3>Clusters ({clusters.length})</h3>
            <button onClick={handleCreateCluster} className="btn btn-primary">
              + New Cluster
            </button>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Color</th>
                <th>Geofences</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {clusters.map(cluster => (
                <tr key={cluster._id}>
                  <td><strong>{cluster.name}</strong></td>
                  <td>{cluster.description || '-'}</td>
                  <td>
                    <span
                      style={{
                        display: 'inline-block',
                        width: '20px',
                        height: '20px',
                        backgroundColor: cluster.color || '#1a237e',
                        borderRadius: '4px'
                      }}
                    />
                  </td>
                  <td>{cluster.geofenceCount || 0}</td>
                  <td>
                    <button onClick={() => handleEditCluster(cluster)} className="btn btn-small">
                      Edit
                    </button>
                    <button onClick={() => handleDeleteCluster(cluster)} className="btn btn-small btn-danger">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {clusters.length === 0 && (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', color: '#666' }}>
                    No clusters yet. Create one to group related geofences.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Edit Geofence</h3>
            <form onSubmit={(e) => { e.preventDefault(); handleSaveEdit() }}>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label>Type *</label>
                <select
                  value={editForm.typeId}
                  onChange={(e) => setEditForm(prev => ({ ...prev, typeId: e.target.value }))}
                  required
                >
                  {geofenceTypes.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>UNLO Code</label>
                  <input
                    type="text"
                    value={editForm.UNLOCode}
                    onChange={(e) => setEditForm(prev => ({ ...prev, UNLOCode: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label>SMDG Code</label>
                  <input
                    type="text"
                    value={editForm.SMDGCode}
                    onChange={(e) => setEditForm(prev => ({ ...prev, SMDGCode: e.target.value }))}
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Cluster (Group)</label>
                  <select
                    value={editForm.clusterId || ''}
                    onChange={(e) => setEditForm(prev => ({ ...prev, clusterId: e.target.value }))}
                  >
                    <option value="">None</option>
                    {clusters.map(cluster => (
                      <option key={cluster._id} value={cluster._id}>{cluster.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Parent (Nested Inside)</label>
                  <select
                    value={editForm.parentId || ''}
                    onChange={(e) => setEditForm(prev => ({ ...prev, parentId: e.target.value }))}
                  >
                    <option value="">None (Top Level)</option>
                    {mapGeofences
                      .filter(gf => gf._id !== editForm._id) // Can't be parent of itself
                      .map(gf => (
                        <option key={gf._id} value={gf._id}>{gf.properties?.name}</option>
                      ))}
                  </select>
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowEditModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Create New Geofence</h3>
            <form onSubmit={(e) => { e.preventDefault(); handleSaveNewGeofence() }}>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., USNYC-NEW"
                  required
                />
              </div>
              <div className="form-group">
                <label>Type *</label>
                <select
                  value={editForm.typeId}
                  onChange={(e) => setEditForm(prev => ({ ...prev, typeId: e.target.value }))}
                  required
                >
                  {geofenceTypes.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="e.g., USA, NEW YORK, New Terminal"
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>UNLO Code</label>
                  <input
                    type="text"
                    value={editForm.UNLOCode}
                    onChange={(e) => setEditForm(prev => ({ ...prev, UNLOCode: e.target.value }))}
                    placeholder="e.g., USNYC"
                  />
                </div>
                <div className="form-group">
                  <label>SMDG Code</label>
                  <input
                    type="text"
                    value={editForm.SMDGCode}
                    onChange={(e) => setEditForm(prev => ({ ...prev, SMDGCode: e.target.value }))}
                  />
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => { setShowCreateModal(false); setNewGeofenceCoords(null) }} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create Geofence
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cluster Modal */}
      {showClusterModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>{editingCluster ? 'Edit Cluster' : 'Create New Cluster'}</h3>
            <form onSubmit={(e) => { e.preventDefault(); handleSaveCluster() }}>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={clusterForm.name}
                  onChange={(e) => setClusterForm(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., Port of Rotterdam"
                  required
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={clusterForm.description}
                  onChange={(e) => setClusterForm(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="e.g., All terminals in Rotterdam port area"
                />
              </div>
              <div className="form-group">
                <label>Color</label>
                <input
                  type="color"
                  value={clusterForm.color}
                  onChange={(e) => setClusterForm(prev => ({ ...prev, color: e.target.value }))}
                  style={{ width: '60px', height: '36px', padding: '2px' }}
                />
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowClusterModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingCluster ? 'Save' : 'Create Cluster'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default GeofenceManager

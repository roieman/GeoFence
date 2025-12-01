import React, { useState, useEffect, useCallback, useRef } from 'react'
import { locationsAPI } from '../services/api'
import { format } from 'date-fns'
import LocationMap from './LocationMap'

function LocationSearch() {
  const [searchText, setSearchText] = useState('')
  const [autocompleteResults, setAutocompleteResults] = useState([])
  const [selectedLocation, setSelectedLocation] = useState(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [radius, setRadius] = useState(10000)
  const [containers, setContainers] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingLocations, setLoadingLocations] = useState(false)
  const [showAutocomplete, setShowAutocomplete] = useState(false)
  const [pagination, setPagination] = useState({ page: 1, limit: 100, total: 0, pages: 0 })
  const [showMap, setShowMap] = useState(false)
  const [locationData, setLocationData] = useState(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [collectionType, setCollectionType] = useState('regular')
  const [queryTime, setQueryTime] = useState(null)
  const [error, setError] = useState(null)
  
  // Refs for cleanup and request management
  const autocompleteRef = useRef(null)
  const searchTimeoutRef = useRef(null)
  const abortControllerRef = useRef(null)
  const locationSearchAbortRef = useRef(null)
  const pendingRequestRef = useRef(null)

  // Cleanup function
  const cleanup = useCallback(() => {
    // Cancel any pending requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    if (locationSearchAbortRef.current) {
      locationSearchAbortRef.current.abort()
      locationSearchAbortRef.current = null
    }
    // Clear timeouts
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
      searchTimeoutRef.current = null
    }
    // Clear pending request flag
    pendingRequestRef.current = null
  }, [])

  const loadInitialLocations = useCallback(async () => {
    // Cancel any pending location search
    if (locationSearchAbortRef.current) {
      locationSearchAbortRef.current.abort()
    }
    
    locationSearchAbortRef.current = new AbortController()
    const signal = locationSearchAbortRef.current.signal
    
    setLoadingLocations(true)
    setError(null)
    
    try {
      const response = await locationsAPI.getAll(null, null, 10)
      
      // Check if request was aborted
      if (signal.aborted) return
      
      const locations = response.data?.locations || []
      setAutocompleteResults(locations)
      if (locations.length > 0) {
        setShowAutocomplete(true)
      }
    } catch (err) {
      // Don't set error if request was aborted
      if (err.name === 'AbortError' || signal.aborted) {
        return
      }
      console.error('Failed to load initial locations:', err)
      setError('Failed to load locations. Please try again.')
      setAutocompleteResults([])
      setShowAutocomplete(false)
    } finally {
      if (!signal.aborted) {
        setLoadingLocations(false)
      }
      locationSearchAbortRef.current = null
    }
  }, [])

  // Load initial locations on mount
  useEffect(() => {
    loadInitialLocations()
    
    // Cleanup on unmount
    return () => {
      cleanup()
    }
  }, [loadInitialLocations, cleanup])

  // Close autocomplete when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (autocompleteRef.current && !autocompleteRef.current.contains(event.target)) {
        setShowAutocomplete(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const searchLocations = useCallback(async (query) => {
    if (!query || query.length < 3) {
      if (query.length === 0) {
        loadInitialLocations()
      }
      return
    }

    // Cancel any pending location search
    if (locationSearchAbortRef.current) {
      locationSearchAbortRef.current.abort()
    }
    
    locationSearchAbortRef.current = new AbortController()
    const signal = locationSearchAbortRef.current.signal

    setLoadingLocations(true)
    setError(null)
    
    try {
      const response = await locationsAPI.getAll(query, null, 10)
      
      // Check if request was aborted
      if (signal.aborted) return
      
      const locations = response.data?.locations || []
      setAutocompleteResults(locations)
      setShowAutocomplete(true)
    } catch (err) {
      // Don't set error if request was aborted
      if (err.name === 'AbortError' || signal.aborted) {
        return
      }
      console.error('Failed to search locations:', err)
      setError('Failed to search locations. Please try again.')
      setAutocompleteResults([])
    } finally {
      if (!signal.aborted) {
        setLoadingLocations(false)
      }
      locationSearchAbortRef.current = null
    }
  }, [loadInitialLocations])

  const handleSearchTextChange = (e) => {
    const value = e.target.value
    setSearchText(value)
    setError(null)
    
    // Clear selected location when typing
    if (value !== selectedLocation?.name) {
      setSelectedLocation(null)
      setContainers([])
      setHasSearched(false)
    }

    // Clear previous timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    // If 3+ characters, debounce the search
    if (value.length >= 3) {
      searchTimeoutRef.current = setTimeout(() => {
        searchLocations(value)
      }, 300)
    } else if (value.length === 0) {
      // If empty, show initial locations
      loadInitialLocations()
      setShowAutocomplete(true)
    } else {
      // Less than 3 characters, hide autocomplete
      setShowAutocomplete(false)
      setAutocompleteResults([])
    }
  }

  const handleLocationSelect = (location) => {
    setSelectedLocation(location)
    setSearchText(location.name)
    setShowAutocomplete(false)
    setContainers([])
    setHasSearched(false)
    setError(null)
  }

  const isPolygon = selectedLocation?.location?.type === "Polygon"

  const handleSearch = useCallback(async (page = 1) => {
    if (!selectedLocation) {
      setError('Please select a location first')
      return
    }
    
    // Cancel any pending search
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    
    // Prevent duplicate requests
    if (pendingRequestRef.current) {
      console.log('Search already in progress, skipping duplicate request')
      return
    }
    
    abortControllerRef.current = new AbortController()
    const signal = abortControllerRef.current.signal
    pendingRequestRef.current = true
    
    const locationName = selectedLocation.name
    setCollectionType('regular')
    setLoading(true)
    setError(null)
    
    try {
      const params = {
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        radius_meters: radius,
        page,
        limit: pagination.limit
      }
      
      const apiCall = locationsAPI.getContainers(
        locationName,
        params.start_date,
        params.end_date,
        params.radius_meters,
        params.page,
        params.limit
      )
      
      const response = await apiCall
      
      // Check if request was aborted
      if (signal.aborted) return
      
      // Validate response
      if (!response || !response.data) {
        throw new Error('Invalid response from server')
      }
      
      setContainers(response.data.containers || [])
      setPagination(response.data.pagination || { page: 1, limit: 100, total: 0, pages: 0 })
      setHasSearched(true)
      
      if (response.data.query_time_ms !== undefined) {
        setQueryTime(response.data.query_time_ms)
      } else {
        setQueryTime(null)
      }
      
      setLocationData(response.data.location)
      
      if (response.data.location?.geometry_type && selectedLocation) {
        setSelectedLocation(prev => ({
          ...prev,
          location: {
            ...prev?.location,
            type: response.data.location.geometry_type
          }
        }))
      }
    } catch (err) {
      // Don't set error if request was aborted
      if (err.name === 'AbortError' || signal.aborted) {
        return
      }
      
      console.error('Failed to search containers:', err)
      
      // Provide user-friendly error messages
      let errorMessage = 'Failed to search containers'
      if (err.response?.status === 404) {
        errorMessage = 'Location not found'
      } else if (err.response?.status === 400) {
        errorMessage = err.response?.data?.detail || 'Invalid search parameters'
      } else if (err.response?.status === 500) {
        errorMessage = 'Server error. Please try again later.'
      } else if (err.message === 'Network Error' || err.code === 'ECONNABORTED') {
        errorMessage = 'Request timed out. The search may be taking too long. Please try with a smaller radius or date range.'
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail
      }
      
      setError(errorMessage)
      setContainers([])
      setHasSearched(true)
    } finally {
      if (!signal.aborted) {
        setLoading(false)
      }
      abortControllerRef.current = null
      pendingRequestRef.current = null
    }
  }, [selectedLocation, startDate, endDate, radius, pagination.limit])

  const handlePageChange = useCallback((newPage) => {
    handleSearch(newPage)
  }, [handleSearch])

  const handleClear = useCallback(() => {
    cleanup()
    setSearchText('')
    setSelectedLocation(null)
    setStartDate('')
    setEndDate('')
    setRadius(10000)
    setContainers([])
    setHasSearched(false)
    setLocationData(null)
    setShowAutocomplete(false)
    setCollectionType('regular')
    setQueryTime(null)
    setError(null)
    loadInitialLocations()
  }, [cleanup, loadInitialLocations])

  const getLocationDisplayName = (location) => {
    const city = location.city || 'N/A'
    const country = location.country || 'N/A'
    return `${location.name} (${location.type}) - ${city}, ${country}`
  }

  return (
    <div>
      <div className="card">
        <h2>Search Containers by Location</h2>
        <p style={{ color: '#666', marginBottom: '1rem' }}>
          Search for a location by name, city, or country. Type at least 3 characters to see autocomplete suggestions.
        </p>
        
        {/* Error message display */}
        {error && (
          <div style={{
            padding: '12px',
            backgroundColor: '#fee',
            border: '1px solid #fcc',
            borderRadius: '4px',
            marginBottom: '1rem',
            color: '#c33',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              style={{
                background: 'none',
                border: 'none',
                color: '#c33',
                cursor: 'pointer',
                fontSize: '18px',
                padding: '0 8px'
              }}
              title="Dismiss error"
            >
              ×
            </button>
          </div>
        )}
        
        <div className="form-group" style={{ position: 'relative' }} ref={autocompleteRef}>
          <label className="form-label">Location</label>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <input
              type="text"
              className="input"
              value={searchText}
              onChange={handleSearchTextChange}
              onFocus={() => {
                if (autocompleteResults.length > 0) {
                  setShowAutocomplete(true)
                } else if (searchText.length === 0) {
                  loadInitialLocations()
                }
              }}
              placeholder="Type to search locations..."
              disabled={loadingLocations || loading}
              style={{ flex: 1, paddingRight: searchText ? '40px' : '10px' }}
            />
            {searchText && (
              <button
                type="button"
                onClick={() => {
                  cleanup()
                  setSearchText('')
                  setSelectedLocation(null)
                  setShowAutocomplete(false)
                  setContainers([])
                  setHasSearched(false)
                  setError(null)
                  loadInitialLocations()
                }}
                disabled={loadingLocations || loading}
                style={{
                  position: 'absolute',
                  right: '8px',
                  background: 'none',
                  border: 'none',
                  cursor: loadingLocations || loading ? 'not-allowed' : 'pointer',
                  fontSize: '18px',
                  color: '#999',
                  padding: '0',
                  width: '24px',
                  height: '24px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                title="Clear location"
              >
                ×
              </button>
            )}
          </div>
          {loadingLocations && (
            <div style={{ marginTop: '0.5rem', color: '#666', fontSize: '0.9em' }}>
              Searching...
            </div>
          )}
          {showAutocomplete && autocompleteResults.length > 0 && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              backgroundColor: 'white',
              border: '1px solid #ddd',
              borderRadius: '4px',
              maxHeight: '300px',
              overflowY: 'auto',
              zIndex: 1000,
              boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
              marginTop: '4px'
            }}>
              {autocompleteResults.map((loc) => (
                <div
                  key={loc._id || loc.name}
                  onClick={() => handleLocationSelect(loc)}
                  style={{
                    padding: '10px 15px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #f0f0f0',
                    transition: 'background-color 0.2s'
                  }}
                  onMouseEnter={(e) => e.target.style.backgroundColor = '#f5f5f5'}
                  onMouseLeave={(e) => e.target.style.backgroundColor = 'white'}
                >
                  <div style={{ fontWeight: 'bold' }}>{loc.name}</div>
                  <div style={{ fontSize: '0.9em', color: '#666' }}>
                    {loc.type} - {loc.city || 'N/A'}, {loc.country || 'N/A'}
                  </div>
                </div>
              ))}
            </div>
          )}
          {!loadingLocations && searchText.length > 0 && searchText.length < 3 && (
            <div style={{ marginTop: '0.5rem', color: '#666', fontSize: '0.9em' }}>
              Type at least 3 characters to search
            </div>
          )}
          {!loadingLocations && !showAutocomplete && autocompleteResults.length === 0 && searchText.length === 0 && (
            <div style={{ marginTop: '0.5rem', color: '#999', fontSize: '0.9em' }}>
              Click in the field to see initial locations, or type to search
            </div>
          )}
        </div>
        {selectedLocation && (
          <div style={{ 
            padding: '10px', 
            backgroundColor: '#e7f3ff', 
            borderRadius: '4px', 
            marginBottom: '1rem' 
          }}>
            <strong>Selected:</strong> {getLocationDisplayName(selectedLocation)}
            <br />
            <span style={{ fontSize: '0.9em', color: '#666' }}>
              Location Type: {selectedLocation.location?.type || 'Unknown'}
              {selectedLocation.location?.type === "Polygon" && " (searching within polygon boundaries)"}
              {selectedLocation.location?.type === "Point" && ` (searching within ${radius}m radius)`}
            </span>
          </div>
        )}
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Start Date (optional)</label>
            <input
              type="datetime-local"
              className="input"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              disabled={loading}
            />
          </div>
          <div className="form-group">
            <label className="form-label">End Date (optional)</label>
            <input
              type="datetime-local"
              className="input"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">
            Search Radius (meters)
            {isPolygon && <span style={{ color: '#999', fontSize: '0.9em', marginLeft: '0.5rem' }}>
              (disabled for polygon locations)
            </span>}
          </label>
          <input
            type="number"
            className="input"
            value={radius}
            onChange={(e) => setRadius(parseInt(e.target.value) || 10000)}
            min="0"
            step="1000"
            disabled={isPolygon || loading}
            style={{
              backgroundColor: isPolygon ? '#f5f5f5' : 'white',
              cursor: isPolygon ? 'not-allowed' : 'text'
            }}
          />
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button 
            className="btn btn-primary" 
            onClick={() => handleSearch(1)} 
            disabled={loading || !selectedLocation || loadingLocations}
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
          <button 
            className="btn btn-secondary" 
            onClick={handleClear}
            disabled={loading}
          >
            Clear Filters
          </button>
          {containers.length > 0 && (
            <button 
              className="btn btn-secondary" 
              onClick={() => setShowMap(true)}
              disabled={loading}
            >
              View on Map
            </button>
          )}
        </div>
      </div>

      {hasSearched && !loading && containers.length === 0 && !error && (
        <div className="card">
          <div style={{ 
            padding: '2rem', 
            textAlign: 'center',
            color: '#666'
          }}>
            <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>
              <strong>No containers found</strong>
            </p>
            <p style={{ margin: 0 }}>
              No containers were found at this location within the specified criteria.
              {selectedLocation?.location?.type === "Point" && (
                <span> Try increasing the search radius or adjusting the date range.</span>
              )}
              {selectedLocation?.location?.type === "Polygon" && (
                <span> Try adjusting the date range.</span>
              )}
            </p>
            {queryTime !== null && (
              <p style={{ marginTop: '1rem', fontSize: '0.9em', color: '#999' }}>
                Query executed in <strong>{queryTime}ms</strong>
              </p>
            )}
          </div>
        </div>
      )}

      {loading && (
        <div className="card">
          <div style={{ 
            padding: '2rem', 
            textAlign: 'center',
            color: '#666'
          }}>
            <p>Searching for containers...</p>
            <p style={{ fontSize: '0.9em', color: '#999', marginTop: '0.5rem' }}>
              This may take a few moments. Please wait.
            </p>
          </div>
        </div>
      )}

      {containers.length > 0 && !loading && (
        <div className="card">
          <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p style={{ margin: 0 }}>Found {pagination.total} containers</p>
              {queryTime !== null && (
                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9em', color: '#666' }}>
                  Query time: <strong style={{ color: '#1976d2' }}>{queryTime}ms</strong>
                </p>
              )}
            </div>
            <div>
              <button
                className="btn btn-secondary"
                onClick={() => handlePageChange(pagination.page - 1)}
                disabled={pagination.page === 1 || loading}
              >
                Previous
              </button>
              <span style={{ margin: '0 1rem' }}>
                Page {pagination.page} of {pagination.pages}
              </span>
              <button
                className="btn btn-secondary"
                onClick={() => handlePageChange(pagination.page + 1)}
                disabled={pagination.page >= pagination.pages || loading}
              >
                Next
              </button>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Container ID</th>
                <th>Shipping Line</th>
                <th>Type</th>
                <th>Refrigerated</th>
                <th>Cargo Type</th>
                <th>First Seen</th>
                <th>Last Seen</th>
                <th>Readings</th>
                <th>Distance (m)</th>
              </tr>
            </thead>
            <tbody>
              {containers.map((container) => (
                <tr key={container.container_id}>
                  <td>{container.container_id}</td>
                  <td>{container.shipping_line || 'N/A'}</td>
                  <td>{container.container_type || 'N/A'}</td>
                  <td>{container.refrigerated ? 'Yes' : 'No'}</td>
                  <td>{container.cargo_type || 'N/A'}</td>
                  <td>
                    {container.first_seen
                      ? format(new Date(container.first_seen), 'PPpp')
                      : 'N/A'}
                  </td>
                  <td>
                    {container.last_seen
                      ? format(new Date(container.last_seen), 'PPpp')
                      : 'N/A'}
                  </td>
                  <td>{container.readings_count || 0}</td>
                  <td>{container.min_distance ? Math.round(container.min_distance) : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showMap && locationData && selectedLocation && (
        <LocationMap
          location={{
            ...selectedLocation,
            location: selectedLocation.location || locationData.location
          }}
          containers={containers}
          radiusMeters={radius}
          onClose={() => setShowMap(false)}
        />
      )}
    </div>
  )
}

export default LocationSearch

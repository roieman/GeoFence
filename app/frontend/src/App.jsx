import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import LiveMap from './components/LiveMap'
import GeofenceManager from './components/GeofenceManager'
import EventsGrid from './components/EventsGrid'
import ContainerTracker from './components/ContainerTracker'
import Admin from './components/Admin'
import { statsAPI } from './services/api'
import './App.css'

function Navigation() {
  const location = useLocation()
  const [stats, setStats] = useState({})

  useEffect(() => {
    statsAPI.get()
      .then(res => setStats(res.data))
      .catch(err => console.error('Failed to load stats:', err))
  }, [location.pathname])

  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="nav-brand">
          <img src="/zim-logo.png" alt="ZIM" className="nav-logo-img" />
          <div className="nav-logo-text">
            <h1 className="nav-logo">GeoFence</h1>
            <span className="nav-subtitle">Container Tracking System</span>
          </div>
        </div>
        <div className="nav-links">
          <Link
            to="/"
            className={location.pathname === '/' ? 'nav-link active' : 'nav-link'}
          >
            <span className="nav-icon">🗺️</span>
            Live Map
          </Link>
          <Link
            to="/geofences"
            className={location.pathname === '/geofences' ? 'nav-link active' : 'nav-link'}
          >
            <span className="nav-icon">📍</span>
            Geofences
            {stats.geofences && <span className="nav-badge">{stats.geofences}</span>}
          </Link>
          <Link
            to="/events"
            className={location.pathname === '/events' ? 'nav-link active' : 'nav-link'}
          >
            <span className="nav-icon">📊</span>
            Events
            {stats.iot_events && <span className="nav-badge">{stats.iot_events}</span>}
          </Link>
          <Link
            to="/track"
            className={location.pathname === '/track' ? 'nav-link active' : 'nav-link'}
          >
            <span className="nav-icon">🚚</span>
            Track Container
          </Link>
          <Link
            to="/admin"
            className={location.pathname === '/admin' ? 'nav-link active' : 'nav-link'}
          >
            <span className="nav-icon">⚙️</span>
            Admin
          </Link>
        </div>
        <div className="nav-stats">
          {stats.containers && (
            <span className="nav-stat" title="Active containers">
              📦 {stats.containers}
            </span>
          )}
          {stats.gate_events && (
            <span className="nav-stat" title="Gate events">
              🚪 {stats.gate_events}
            </span>
          )}
          {stats.map_last_updated && (
            <span className="nav-stat" title="Map last updated">
              🕐 {new Date(stats.map_last_updated).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>
    </nav>
  )
}

function App() {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<LiveMap />} />
            <Route path="/geofences" element={<GeofenceManager />} />
            <Route path="/events" element={<EventsGrid />} />
            <Route path="/track" element={<ContainerTracker />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App

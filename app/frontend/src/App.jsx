import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import ContainerTracker from './components/ContainerTracker'
import AlertsGrid from './components/AlertsGrid'
import LocationSearch from './components/LocationSearch'
import './App.css'

function Navigation() {
  const location = useLocation()
  
  return (
    <nav className="navbar">
      <div className="nav-container">
        <h1 className="nav-logo">GeoFence</h1>
        <div className="nav-links">
          <Link 
            to="/" 
            className={location.pathname === '/' ? 'nav-link active' : 'nav-link'}
          >
            Track Container
          </Link>
          <Link 
            to="/alerts" 
            className={location.pathname === '/alerts' ? 'nav-link active' : 'nav-link'}
          >
            Alerts
          </Link>
          <Link 
            to="/location" 
            className={location.pathname === '/location' ? 'nav-link active' : 'nav-link'}
          >
            Location Search
          </Link>
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
        <div className="container">
          <Routes>
            <Route path="/" element={<ContainerTracker />} />
            <Route path="/alerts" element={<AlertsGrid />} />
            <Route path="/location" element={<LocationSearch />} />
          </Routes>
        </div>
      </div>
    </Router>
  )
}

export default App


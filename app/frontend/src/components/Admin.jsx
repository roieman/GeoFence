import React, { useState, useEffect } from 'react'
import { authAPI, apiKeysAPI, webhooksAPI, notificationsAPI, referenceAPI } from '../services/api'

function Admin() {
  const [activeTab, setActiveTab] = useState('users')
  const [users, setUsers] = useState([])
  const [apiKeys, setApiKeys] = useState([])
  const [webhooks, setWebhooks] = useState([])
  const [notifications, setNotifications] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Modals
  const [showUserModal, setShowUserModal] = useState(false)
  const [showApiKeyModal, setShowApiKeyModal] = useState(false)
  const [showWebhookModal, setShowWebhookModal] = useState(false)

  // Forms
  const [userForm, setUserForm] = useState({ username: '', password: '', name: '', role: 'viewer' })
  const [apiKeyForm, setApiKeyForm] = useState({ name: '', role: 'viewer', description: '' })
  const [webhookForm, setWebhookForm] = useState({ name: '', url: '', events: 'all' })

  useEffect(() => {
    referenceAPI.userRoles().then(res => setRoles(res.data.roles)).catch(() => {})
    loadData()
  }, [activeTab])

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      if (activeTab === 'users') {
        const res = await authAPI.listUsers()
        setUsers(res.data.users || [])
      } else if (activeTab === 'apiKeys') {
        const res = await apiKeysAPI.list()
        setApiKeys(res.data.api_keys || [])
      } else if (activeTab === 'webhooks') {
        const res = await webhooksAPI.list()
        setWebhooks(res.data.webhooks || [])
      } else if (activeTab === 'notifications') {
        const res = await notificationsAPI.list(false, 100)
        setNotifications(res.data.notifications || [])
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Authentication required. Please login as admin.')
      } else if (err.response?.status === 403) {
        setError('Admin access required.')
      } else {
        setError(err.message || 'Failed to load data')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCreateUser = async () => {
    try {
      await authAPI.register(userForm.username, userForm.password, userForm.name, userForm.role)
      setShowUserModal(false)
      setUserForm({ username: '', password: '', name: '', role: 'viewer' })
      loadData()
    } catch (err) {
      alert('Failed to create user: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleCreateApiKey = async () => {
    try {
      const res = await apiKeysAPI.create(apiKeyForm.name, apiKeyForm.role, apiKeyForm.description)
      alert(`API Key created! Key: ${res.data.key}\n\nSave this key - it won't be shown again.`)
      setShowApiKeyModal(false)
      setApiKeyForm({ name: '', role: 'viewer', description: '' })
      loadData()
    } catch (err) {
      alert('Failed to create API key: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleRevokeApiKey = async (keyId) => {
    if (!window.confirm('Revoke this API key?')) return
    try {
      await apiKeysAPI.revoke(keyId)
      loadData()
    } catch (err) {
      alert('Failed to revoke: ' + err.message)
    }
  }

  const handleCreateWebhook = async () => {
    try {
      const events = webhookForm.events.split(',').map(e => e.trim())
      await webhooksAPI.create(webhookForm.name, webhookForm.url, events)
      setShowWebhookModal(false)
      setWebhookForm({ name: '', url: '', events: 'all' })
      loadData()
    } catch (err) {
      alert('Failed to create webhook: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleDeleteWebhook = async (webhookId) => {
    if (!window.confirm('Delete this webhook?')) return
    try {
      await webhooksAPI.delete(webhookId)
      loadData()
    } catch (err) {
      alert('Failed to delete: ' + err.message)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await notificationsAPI.markAllRead()
      loadData()
    } catch (err) {
      alert('Failed: ' + err.message)
    }
  }

  return (
    <div className="admin-page">
      <div className="page-header">
        <h2>Administration</h2>
      </div>

      {/* Tabs */}
      <div className="tab-buttons" style={{ marginBottom: '1rem' }}>
        <button className={`tab-btn ${activeTab === 'users' ? 'active' : ''}`} onClick={() => setActiveTab('users')}>
          Users
        </button>
        <button className={`tab-btn ${activeTab === 'apiKeys' ? 'active' : ''}`} onClick={() => setActiveTab('apiKeys')}>
          API Keys
        </button>
        <button className={`tab-btn ${activeTab === 'webhooks' ? 'active' : ''}`} onClick={() => setActiveTab('webhooks')}>
          Webhooks
        </button>
        <button className={`tab-btn ${activeTab === 'notifications' ? 'active' : ''}`} onClick={() => setActiveTab('notifications')}>
          Notifications
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Users Tab */}
      {activeTab === 'users' && (
        <div>
          <div style={{ marginBottom: '1rem' }}>
            <button onClick={() => setShowUserModal(true)} className="btn btn-primary">+ Add User</button>
          </div>
          {loading ? <div className="loading">Loading...</div> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Created</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user._id}>
                    <td>{user.username}</td>
                    <td>{user.name || '-'}</td>
                    <td><span className="type-badge">{user.role}</span></td>
                    <td>{user.createdAt ? new Date(user.createdAt).toLocaleDateString() : '-'}</td>
                    <td>{user.active ? '✅ Active' : '❌ Inactive'}</td>
                  </tr>
                ))}
                {users.length === 0 && <tr><td colSpan="5" style={{ textAlign: 'center' }}>No users found</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* API Keys Tab */}
      {activeTab === 'apiKeys' && (
        <div>
          <div style={{ marginBottom: '1rem' }}>
            <button onClick={() => setShowApiKeyModal(true)} className="btn btn-primary">+ Create API Key</button>
          </div>
          {loading ? <div className="loading">Loading...</div> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Key (masked)</th>
                  <th>Role</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {apiKeys.map(key => (
                  <tr key={key._id}>
                    <td>{key.name}</td>
                    <td><code>{key.key}</code></td>
                    <td><span className="type-badge">{key.role}</span></td>
                    <td>{key.createdAt ? new Date(key.createdAt).toLocaleDateString() : '-'}</td>
                    <td>
                      {key.active ? (
                        <button onClick={() => handleRevokeApiKey(key._id)} className="btn btn-small btn-danger">Revoke</button>
                      ) : (
                        <span style={{ color: '#999' }}>Revoked</span>
                      )}
                    </td>
                  </tr>
                ))}
                {apiKeys.length === 0 && <tr><td colSpan="5" style={{ textAlign: 'center' }}>No API keys</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Webhooks Tab */}
      {activeTab === 'webhooks' && (
        <div>
          <div style={{ marginBottom: '1rem' }}>
            <button onClick={() => setShowWebhookModal(true)} className="btn btn-primary">+ Register Webhook</button>
          </div>
          <div className="info-banner">
            <strong>API Out:</strong> Webhooks receive notifications when geofences are created, updated, or deleted.
          </div>
          {loading ? <div className="loading">Loading...</div> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>URL</th>
                  <th>Events</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {webhooks.map(wh => (
                  <tr key={wh._id}>
                    <td>{wh.name}</td>
                    <td><code style={{ fontSize: '0.8rem' }}>{wh.url}</code></td>
                    <td>{(wh.events || []).join(', ')}</td>
                    <td>
                      <button onClick={() => handleDeleteWebhook(wh._id)} className="btn btn-small btn-danger">Delete</button>
                    </td>
                  </tr>
                ))}
                {webhooks.length === 0 && <tr><td colSpan="4" style={{ textAlign: 'center' }}>No webhooks registered</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div>
          <div style={{ marginBottom: '1rem' }}>
            <button onClick={handleMarkAllRead} className="btn btn-secondary">Mark All Read</button>
          </div>
          {loading ? <div className="loading">Loading...</div> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Title</th>
                  <th>Message</th>
                  <th>Time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {notifications.map(n => (
                  <tr key={n._id} style={{ backgroundColor: n.read ? 'transparent' : '#e3f2fd' }}>
                    <td><span className={`type-badge type-${n.type}`}>{n.type}</span></td>
                    <td>{n.title}</td>
                    <td>{n.message}</td>
                    <td>{n.createdAt ? new Date(n.createdAt).toLocaleString() : '-'}</td>
                    <td>{n.read ? '✓ Read' : '● Unread'}</td>
                  </tr>
                ))}
                {notifications.length === 0 && <tr><td colSpan="5" style={{ textAlign: 'center' }}>No notifications</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Create User Modal */}
      {showUserModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Create User</h3>
            <form onSubmit={(e) => { e.preventDefault(); handleCreateUser() }}>
              <div className="form-group">
                <label>Username (email) *</label>
                <input type="email" value={userForm.username} onChange={(e) => setUserForm(prev => ({ ...prev, username: e.target.value }))} required />
              </div>
              <div className="form-group">
                <label>Password *</label>
                <input type="password" value={userForm.password} onChange={(e) => setUserForm(prev => ({ ...prev, password: e.target.value }))} required />
              </div>
              <div className="form-group">
                <label>Name</label>
                <input type="text" value={userForm.name} onChange={(e) => setUserForm(prev => ({ ...prev, name: e.target.value }))} />
              </div>
              <div className="form-group">
                <label>Role</label>
                <select value={userForm.role} onChange={(e) => setUserForm(prev => ({ ...prev, role: e.target.value }))}>
                  {roles.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowUserModal(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create API Key Modal */}
      {showApiKeyModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Create API Key</h3>
            <form onSubmit={(e) => { e.preventDefault(); handleCreateApiKey() }}>
              <div className="form-group">
                <label>Name *</label>
                <input type="text" value={apiKeyForm.name} onChange={(e) => setApiKeyForm(prev => ({ ...prev, name: e.target.value }))} placeholder="e.g., Hoopo Integration" required />
              </div>
              <div className="form-group">
                <label>Role (permissions)</label>
                <select value={apiKeyForm.role} onChange={(e) => setApiKeyForm(prev => ({ ...prev, role: e.target.value }))}>
                  {roles.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea value={apiKeyForm.description} onChange={(e) => setApiKeyForm(prev => ({ ...prev, description: e.target.value }))} placeholder="What is this key used for?" />
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowApiKeyModal(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Webhook Modal */}
      {showWebhookModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Register Webhook</h3>
            <form onSubmit={(e) => { e.preventDefault(); handleCreateWebhook() }}>
              <div className="form-group">
                <label>Name *</label>
                <input type="text" value={webhookForm.name} onChange={(e) => setWebhookForm(prev => ({ ...prev, name: e.target.value }))} placeholder="e.g., My System" required />
              </div>
              <div className="form-group">
                <label>URL *</label>
                <input type="url" value={webhookForm.url} onChange={(e) => setWebhookForm(prev => ({ ...prev, url: e.target.value }))} placeholder="https://example.com/webhook" required />
              </div>
              <div className="form-group">
                <label>Events (comma separated)</label>
                <input type="text" value={webhookForm.events} onChange={(e) => setWebhookForm(prev => ({ ...prev, events: e.target.value }))} placeholder="all, geofence_created, geofence_updated, geofence_deleted, alert" />
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowWebhookModal(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Register</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default Admin

/**
 * API utility functions to communicate with FastAPI backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function apiCall(method, endpoint, data = null) {
  const url = `${API_BASE_URL}${endpoint}`

  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  }

  if (data && (method === 'POST' || method === 'PUT')) {
    options.body = JSON.stringify(data)
  }

  try {
    const response = await fetch(url, options)

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`API Error: ${response.status} - ${error}`)
    }

    return await response.json()
  } catch (error) {
    console.error(`API call failed: ${method} ${endpoint}`, error)
    throw error
  }
}

export async function healthCheck() {
  try {
    const response = await apiCall('GET', '/api/health')
    return response
  } catch (error) {
    console.error('Health check failed:', error)
    return { status: 'error' }
  }
}

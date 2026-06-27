import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function ImportRepository() {
  const [url, setUrl] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    
    if (!url.startsWith('https://github.com/')) {
      setError('Please provide a valid GitHub URL (must start with https://github.com/).')
      return
    }

    setIsLoading(true)
    try {
      const res = await fetch('/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      })
      
      const data = await res.json()
      
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to import repository.')
      }

      // Success
      navigate('/repository')
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-gray-900">Import Repository</h1>
      
      <div className="bg-white rounded-lg shadow-md border border-gray-100 p-6">
        {error && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-md border border-red-200">
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Repository URL (Python only for MVP)</label>
            <input 
              type="text" 
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/username/repo" 
              className="w-full border border-gray-300 rounded-md p-2 focus:ring-blue-500 focus:border-blue-500"
              disabled={isLoading}
            />
          </div>
          <div className="pt-4 flex items-center">
            <button 
              type="submit" 
              disabled={isLoading}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center"
            >
              {isLoading ? 'Importing...' : 'Import'}
            </button>
            <Link to="/" className="ml-4 text-gray-600 hover:text-gray-900">Cancel</Link>
          </div>
        </form>
      </div>
    </div>
  )
}

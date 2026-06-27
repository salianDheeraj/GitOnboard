import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function Repository() {
  const [repos, setRepos] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  const fetchRepos = async () => {
    try {
      const res = await fetch('/api/repos')
      const data = await res.json()
      setRepos(data.repositories || [])
    } catch (err) {
      console.error("Failed to fetch repos", err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchRepos()
  }, [])

  const handleDelete = async (repoName) => {
    if (!window.confirm(`Are you sure you want to delete ${repoName}?`)) return
    
    try {
      const res = await fetch(`/api/repos/${repoName}`, { method: 'DELETE' })
      if (res.ok) {
        fetchRepos() // Refresh the list
      } else {
        alert("Failed to delete repository.")
      }
    } catch (err) {
      console.error("Failed to delete repo", err)
      alert("Error deleting repository.")
    }
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Repositories</h1>
        <Link to="/import" className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">Import New</Link>
      </div>
      
      {isLoading ? (
        <div className="text-center text-gray-500 mt-10">Loading repositories...</div>
      ) : repos.length === 0 ? (
        <div className="bg-white rounded-lg shadow-md border border-gray-100 p-8 text-center text-gray-500">
          <p>No repositories found. Import one to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {repos.map(repo => (
            <div key={repo} className="bg-white rounded-lg shadow-md border border-gray-100 p-6 flex flex-col justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-2 truncate" title={repo}>{repo}</h2>
                <p className="text-sm text-gray-500 mb-4">Saved locally in backend file system.</p>
              </div>
              <div className="flex justify-between items-center mt-4 pt-4 border-t border-gray-100">
                <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded-full">Cloned</span>
                <button 
                  onClick={() => handleDelete(repo)}
                  className="text-red-600 hover:text-red-800 text-sm font-medium"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

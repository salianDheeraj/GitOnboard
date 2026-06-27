import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function Dashboard() {
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
        fetchRepos()
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
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <Link to="/import" className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">Import Repository</Link>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-500 mt-10">Loading Dashboard...</div>
      ) : repos.length === 0 ? (
        <div className="bg-white rounded-lg shadow-md border border-gray-100 p-8 text-center text-gray-500">
          <p className="mb-4">Welcome to the Repository Intelligence Platform MVP.</p>
          <p>No repositories imported yet. Import one to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {repos.map(repo => (
            <div key={repo.project_name} className="bg-white rounded-lg shadow-md border border-gray-100 flex flex-col justify-between hover:shadow-lg transition-shadow duration-200">
              <Link to={`/repository/${repo.project_name}`} className="p-6 block flex-grow">
                <div className="flex justify-between items-start mb-4">
                  <h2 className="text-xl font-bold text-blue-600 truncate" title={repo.project_name}>{repo.project_name}</h2>
                  <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-full font-medium">{repo.language}</span>
                </div>
                
                <div className="space-y-2 mb-4">
                  <div>
                    <p className="text-xs text-gray-500 font-semibold uppercase">Path</p>
                    <p className="text-sm text-gray-700 font-mono truncate" title={repo.repository_path}>{repo.repository_path}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 font-semibold uppercase">Imported At</p>
                    <p className="text-sm text-gray-700">{new Date(repo.import_time).toLocaleString()}</p>
                  </div>
                </div>
              </Link>
              
              <div className="flex justify-end items-center px-6 py-4 border-t border-gray-100">
                <button 
                  onClick={(e) => {
                    e.preventDefault();
                    handleDelete(repo.project_name);
                  }}
                  className="text-red-500 hover:text-red-700 text-sm font-medium transition-colors"
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


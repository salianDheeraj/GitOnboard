import React, { useState, useEffect } from 'react'

export default function RepositoryHealth({ repoName }) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch(`/api/repos/${repoName}/health/scores`)
        if (!res.ok) throw new Error("Failed to fetch health scores.")
        const json = await res.json()
        setData(json)
      } catch (err) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    fetchHealth()
  }, [repoName])

  if (isLoading) return <div className="text-gray-500 text-center py-10">Loading health data...</div>
  if (error) return <div className="text-red-500 bg-red-50 p-4 rounded-md">Error: {error}</div>
  if (!data) return <div className="text-gray-500">No health data available.</div>

  const getStatusColor = (status) => {
    switch (status) {
      case 'Excellent': return 'bg-green-100 text-green-800 border-green-200'
      case 'Good': return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'Fair': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'Needs Work': return 'bg-red-100 text-red-800 border-red-200'
      default: return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  return (
    <div className="space-y-6 max-h-full overflow-y-auto pr-2">
      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Overall Health Score</h2>
          <p className="text-gray-500 mt-1">Computed deterministically from repository metrics and findings.</p>
        </div>
        <div className="text-right flex items-center gap-4">
          <div className={`px-4 py-2 rounded-full border font-bold ${getStatusColor(data.status)}`}>
            {data.status}
          </div>
          <div className="text-5xl font-black text-gray-900">
            {data.health_score}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(data.categories || {}).map(([catName, catData]) => (
          <div key={catName} className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
            <div className="flex justify-between items-center mb-2 border-b pb-2">
              <h3 className="text-lg font-bold text-gray-800">{catName}</h3>
              <div className="text-xl font-black text-blue-600">{catData.score.toFixed(1)}</div>
            </div>
            <p className="text-sm text-gray-500 uppercase tracking-wider mb-2 font-semibold">Weight: {(catData.weight * 100).toFixed(0)}%</p>
            <p className="text-gray-700 text-sm">{catData.explanation}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

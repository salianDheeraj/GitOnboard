import React, { useState, useEffect } from 'react'

export default function RepositoryAnalysis({ repoName }) {
  const [findings, setFindings] = useState([])
  const [smells, setSmells] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all') // all, deadcode, smells

  useEffect(() => {
    const fetchAnalysis = async () => {
      try {
        const [resFindings, resSmells] = await Promise.all([
          fetch(`/api/repos/${repoName}/health/findings`),
          fetch(`/api/repos/${repoName}/health/smells`)
        ])
        
        if (!resFindings.ok || !resSmells.ok) {
          throw new Error("Failed to fetch analysis data.")
        }
        
        const jsonFindings = await resFindings.json()
        const jsonSmells = await resSmells.json()
        
        setFindings(jsonFindings.findings || [])
        setSmells(jsonSmells.smells || [])
      } catch (err) {
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }
    fetchAnalysis()
  }, [repoName])

  if (isLoading) return <div className="text-gray-500 text-center py-10">Running analysis...</div>
  if (error) return <div className="text-red-500 bg-red-50 p-4 rounded-md">Error: {error}</div>

  const deadCode = findings.filter(f => f.title.includes('Unused') || f.title.includes('Unreachable'))
  
  let displayedItems = []
  if (filter === 'all') displayedItems = [...findings, ...smells]
  else if (filter === 'deadcode') displayedItems = deadCode
  else if (filter === 'smells') displayedItems = smells

  const getSeverityBadge = (severity) => {
    const sevStr = String(severity).toLowerCase()
    if (sevStr.includes('critical')) return <span className="bg-red-100 text-red-800 text-xs font-bold px-2 py-1 rounded border border-red-200">CRITICAL</span>
    if (sevStr.includes('error')) return <span className="bg-orange-100 text-orange-800 text-xs font-bold px-2 py-1 rounded border border-orange-200">ERROR</span>
    return <span className="bg-yellow-100 text-yellow-800 text-xs font-bold px-2 py-1 rounded border border-yellow-200">WARNING</span>
  }

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="flex space-x-2 bg-gray-50 p-2 rounded-lg border border-gray-200">
        <button 
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${filter === 'all' ? 'bg-white shadow border border-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          All Findings ({findings.length + smells.length})
        </button>
        <button 
          onClick={() => setFilter('deadcode')}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${filter === 'deadcode' ? 'bg-white shadow border border-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          Dead Code ({deadCode.length})
        </button>
        <button 
          onClick={() => setFilter('smells')}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${filter === 'smells' ? 'bg-white shadow border border-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          Architecture Smells ({smells.length})
        </button>
      </div>

      <div className="flex-grow overflow-y-auto space-y-3 pr-2">
        {displayedItems.length === 0 ? (
          <div className="text-gray-500 text-center py-10 italic">No findings to display for this category. Great job!</div>
        ) : (
          displayedItems.map((item, idx) => (
            <div key={idx} className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm flex flex-col space-y-2 hover:border-blue-300 transition-colors">
              <div className="flex items-start justify-between">
                <h3 className="text-lg font-bold text-gray-900">{item.title || item.type}</h3>
                {getSeverityBadge(item.severity)}
              </div>
              <p className="text-sm text-gray-700">{item.description}</p>
              
              {item.file_path && (
                <div className="mt-2 text-xs font-mono text-gray-500 bg-gray-50 p-2 rounded border border-gray-100 inline-block w-fit">
                  {item.file_path}
                </div>
              )}
              {item.members && (
                <div className="mt-2 text-xs font-mono text-gray-500 bg-gray-50 p-2 rounded border border-gray-100">
                  <span className="font-bold uppercase text-gray-400 mr-2">Cycle Members:</span>
                  {item.members.join(' → ')}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

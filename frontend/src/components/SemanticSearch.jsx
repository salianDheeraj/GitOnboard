import React, { useState, useEffect } from 'react';

export default function SemanticSearch({ repoName }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  
  // Status states: 'checking', 'building', 'updating', 'ready'
  const [indexState, setIndexState] = useState('checking');
  const [indexMessage, setIndexMessage] = useState("");
  
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState(null);

  // Auto-trigger semantic indexing when the component mounts
  useEffect(() => {
    let isMounted = true;
    
    const buildIndex = async () => {
      setError(null);
      
      try {
        // Step 1: Check if index exists to show appropriate UI
        const statusRes = await fetch(`/api/repos/${repoName}/semantic-status`);
        if (!statusRes.ok) throw new Error("Failed to check index status");
        const statusData = await statusRes.json();
        
        if (isMounted) {
          if (statusData.has_index) {
            setIndexState('updating');
            setIndexMessage("Checking for changed files to incrementally update the semantic index...");
          } else {
            setIndexState('building');
            setIndexMessage("Building the semantic index for the first time. This may take a moment.");
          }
        }
        
        // Step 2: Trigger the actual indexing/update process
        const res = await fetch(`/api/repos/${repoName}/semantic-index`, {
          method: 'POST'
        });
        
        if (!res.ok) {
          throw new Error("Failed to build semantic index");
        }
        
        const data = await res.json();
        
        if (isMounted) {
          if (data.status === "up to date") {
            setIndexMessage("Repository already indexed. Semantic index up to date.");
          } else if (data.status === "indexed") {
            setIndexMessage(`Building semantic index complete. Processed ${data.processed} files.`);
          } else if (data.status === "updated") {
            setIndexMessage(`Updating changed files complete. Processed ${data.processed} files, removed ${data.deleted} deleted files.`);
          }
          
          setIndexState('ready');
          
          // Clear the success message after 4 seconds
          setTimeout(() => {
            if (isMounted) setIndexMessage("");
          }, 4000);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message);
          setIndexState('ready');
        }
      }
    };
    
    buildIndex();
    
    return () => {
      isMounted = false;
    };
  }, [repoName]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setIsSearching(true);
    setError(null);
    setHasSearched(true);
    
    try {
      const res = await fetch(`/api/repos/${repoName}/semantic-search?q=${encodeURIComponent(query)}`);
      if (!res.ok) {
        throw new Error("Failed to perform semantic search");
      }
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSearching(false);
    }
  };

  if (indexState === 'checking' || indexState === 'building' || indexState === 'updating') {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-500 bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <svg className="animate-spin h-10 w-10 text-purple-500 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p className="font-semibold text-lg">
          {indexState === 'checking' && "Checking Index Status..."}
          {indexState === 'building' && "Building Semantic Index"}
          {indexState === 'updating' && "Updating Changed Files"}
        </p>
        <p className="text-sm mt-2 max-w-sm text-center">{indexMessage}</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-purple-50/30 rounded-lg shadow-sm border border-purple-100 overflow-hidden relative">
      
      {/* Status Toast */}
      {indexMessage && (
        <div className="absolute top-4 right-4 z-50 bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded shadow-sm text-sm font-medium animate-fade-in-down">
          <div className="flex items-center gap-2">
            <span className="text-green-500">✓</span>
            {indexMessage}
          </div>
        </div>
      )}
      
      {/* Search Header */}
      <div className="p-6 bg-white border-b border-purple-100 shadow-sm z-10">
        <h2 className="text-xl font-bold text-gray-800 mb-2 flex items-center gap-2">
          <span className="text-2xl">✨</span> Semantic Search
        </h2>
        <p className="text-sm text-gray-500 mb-4">Search by concepts and natural language instead of exact keywords.</p>
        
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="relative flex-grow">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <span className="text-purple-400 font-bold font-mono">?</span>
            </div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="block w-full pl-10 pr-3 py-3 border border-purple-200 rounded-md leading-5 bg-white placeholder-gray-400 focus:outline-none focus:placeholder-gray-300 focus:ring-1 focus:ring-purple-500 focus:border-purple-500 sm:text-sm transition duration-150 ease-in-out shadow-inner"
              placeholder="e.g. 'handle user login' or 'JWT authentication'"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !query.trim()}
            className="inline-flex items-center px-6 py-3 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:bg-purple-400 transition duration-150 ease-in-out"
          >
            {isSearching ? 'Searching...' : 'Ask AI'}
          </button>
        </form>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>
      
      {/* Search Results */}
      <div className="flex-grow overflow-y-auto p-6 relative">
        {/* Background Graphic */}
        <div className="absolute inset-0 pointer-events-none flex items-center justify-center opacity-[0.03]">
          <svg className="w-96 h-96" viewBox="0 0 100 100" fill="currentColor">
            <path d="M50 0L60.9789 39.0211L100 50L60.9789 60.9789L50 100L39.0211 60.9789L0 50L39.0211 39.0211L50 0Z" />
          </svg>
        </div>

        {!hasSearched ? (
          <div className="text-center py-12 relative z-10">
            <div className="mx-auto h-12 w-12 text-purple-200 text-5xl mb-4">🧠</div>
            <h3 className="mt-2 text-sm font-medium text-gray-900">Semantic AI Search</h3>
            <p className="mt-1 text-sm text-gray-500">Enter a concept to discover related code using embeddings.</p>
          </div>
        ) : results.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200 relative z-10">
            <h3 className="mt-2 text-sm font-medium text-gray-900">No results found</h3>
            <p className="mt-1 text-sm text-gray-500">Try rephrasing your concept.</p>
          </div>
        ) : (
          <div className="space-y-4 relative z-10">
            <h3 className="text-sm font-medium text-gray-500">Found {results.length} semantic matche{results.length === 1 ? '' : 's'}</h3>
            <ul className="space-y-3">
              {results.map((result, idx) => (
                <li key={idx} className="bg-white px-4 py-4 sm:px-6 rounded-lg shadow-sm border border-purple-100 hover:border-purple-300 transition duration-150 ease-in-out relative overflow-hidden group">
                  {/* Confidence Bar */}
                  <div className="absolute bottom-0 left-0 h-1 bg-purple-500" style={{ width: `${Math.max(10, 100 - (result.distance * 50))}%` }}></div>
                  
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-purple-700 truncate font-mono">
                      {result.file_path}
                    </p>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 uppercase tracking-wide">
                      {result.match_type}
                    </span>
                  </div>
                  <div className="mt-2">
                    <p className="text-base text-gray-800 font-bold font-mono">
                      {result.match_name}()
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

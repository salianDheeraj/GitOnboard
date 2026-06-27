import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

export default function RepositorySummary({ repoName }) {
  const [summary, setSummary] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isOutdated, setIsOutdated] = useState(false);
  const [error, setError] = useState(null);

  const fetchSummary = async () => {
    try {
      const res = await fetch(`/api/repos/${repoName}/summary`);
      if (!res.ok) throw new Error("Failed to fetch summary");
      const data = await res.json();
      setSummary(data.summary);
      setIsOutdated(data.outdated);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [repoName]);

  const generateSummary = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const res = await fetch(`/api/repos/${repoName}/summary/generate`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error("Failed to generate summary");
      const data = await res.json();
      setSummary(data.summary);
      setIsOutdated(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  if (isGenerating) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-white rounded-lg p-12">
        <svg className="animate-spin h-12 w-12 text-blue-500 mb-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <h3 className="text-xl font-semibold text-gray-800">Generating AI Summary...</h3>
        <p className="text-gray-500 mt-2 text-center max-w-md">
          The local LLM is analyzing the repository metadata to create a comprehensive overview. This process happens entirely offline and may take a few moments.
        </p>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-white rounded-lg p-12 border border-gray-100">
        <div className="text-6xl mb-4">🤖</div>
        <h3 className="text-xl font-semibold text-gray-800 mb-2">No Summary Available</h3>
        <p className="text-gray-500 mb-6 text-center max-w-md">
          Generate an AI-powered summary of the repository structure, languages, modules, and dependencies using local Ollama.
        </p>
        <button
          onClick={generateSummary}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md shadow-sm transition-colors flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
          Generate Summary
        </button>
        {error && <p className="text-red-500 mt-4 text-sm">{error}</p>}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white rounded-lg shadow-sm border border-gray-200 relative overflow-hidden">
      {/* Header bar */}
      <div className="flex justify-between items-center p-6 border-b border-gray-100 bg-gray-50/50">
        <div className="flex items-center gap-3">
          <span className="text-2xl">📝</span>
          <h2 className="text-xl font-bold text-gray-800">Repository Overview</h2>
          {isOutdated && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
              Outdated
            </span>
          )}
        </div>
        
        <button
          onClick={generateSummary}
          className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-md shadow-sm transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
          {isOutdated ? "Update Summary" : "Regenerate"}
        </button>
      </div>
      
      {/* Markdown Content */}
      <div className="flex-grow overflow-y-auto p-8 prose prose-blue max-w-none">
        <ReactMarkdown>{summary}</ReactMarkdown>
      </div>
    </div>
  );
}

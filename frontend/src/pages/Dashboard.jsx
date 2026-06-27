import React from 'react'
import { Link } from 'react-router-dom'

export default function Dashboard() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-6 text-gray-900">Dashboard</h1>
      <p className="text-gray-600 mb-8">Welcome to the Repository Intelligence Platform MVP.</p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-6 bg-white rounded-lg shadow-md border border-gray-100">
          <h2 className="text-xl font-semibold mb-2">Import a Repository</h2>
          <p className="text-gray-500 mb-4">Start analyzing a new Python repository.</p>
          <Link to="/import" className="text-blue-600 hover:text-blue-800 font-medium">Go to Import &rarr;</Link>
        </div>
        <div className="p-6 bg-white rounded-lg shadow-md border border-gray-100">
          <h2 className="text-xl font-semibold mb-2">View Repositories</h2>
          <p className="text-gray-500 mb-4">Explore your previously imported repositories.</p>
          <Link to="/repository" className="text-blue-600 hover:text-blue-800 font-medium">Go to Repositories &rarr;</Link>
        </div>
      </div>
    </div>
  )
}

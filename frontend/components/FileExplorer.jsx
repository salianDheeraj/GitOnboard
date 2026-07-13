"use client";

import React, { useState } from 'react';

const TreeNode = ({ node, onFileClick, selectedPath }) => {
  const [isOpen, setIsOpen] = useState(true);

  if (node.type === "file") {
    const isPython = node.name.endsWith('.py');
    const isSelected = selectedPath === node.path;
    
    return (
      <div 
        className={`py-1 flex items-center text-sm rounded px-2 mt-1 ${isPython ? 'cursor-pointer hover:bg-blue-50' : 'text-gray-500'} ${isSelected ? 'bg-blue-100 font-medium text-blue-800' : 'text-gray-600'}`}
        onClick={() => isPython && onFileClick(node.path)}
      >
        <span className={`mr-2 ${isPython ? 'text-blue-500' : 'text-gray-400'}`}>📄</span>
        <span className="truncate" title={node.name}>{node.name}</span>
      </div>
    );
  }

  return (
    <div className="mt-1">
      <div 
        className="py-1 px-2 flex items-center text-sm font-semibold text-gray-800 cursor-pointer hover:bg-gray-100 rounded"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="mr-2">{isOpen ? "📂" : "📁"}</span>
        <span className="truncate" title={node.name}>{node.name}</span>
      </div>
      {isOpen && node.children && node.children.length > 0 && (
        <div className="ml-4 pl-4 border-l-2 border-gray-200">
          {node.children.map((child, idx) => (
            <TreeNode key={idx} node={child} onFileClick={onFileClick} selectedPath={selectedPath} />
          ))}
        </div>
      )}
    </div>
  );
};

export default function FileExplorer({ hierarchy, onFileClick, selectedFile }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 flex-grow overflow-auto flex flex-col h-full">
      <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4 px-2 border-b pb-2 flex-shrink-0">Repository Explorer</h2>
      <div className="flex-grow overflow-y-auto">
        {hierarchy ? (
          <TreeNode node={hierarchy} onFileClick={onFileClick} selectedPath={selectedFile} />
        ) : (
          <div className="text-gray-400 text-sm">No files found.</div>
        )}
      </div>
    </div>
  );
}

"use client";

import React, { useState } from 'react';
import { PythonIcon, JavascriptIcon, TypescriptIcon, ReactIcon, JavaIcon } from './common/LanguageIcons';
import { ChevronRight, ChevronDown, Folder, FolderOpen } from 'lucide-react';

const getFileMeta = (filename) => {
  const ext = filename.split('.').pop().toLowerCase();
  switch (ext) {
    case 'py': return { isSupported: true, color: 'text-blue-500', bg: 'bg-blue-50', activeBg: 'bg-blue-100', activeText: 'text-blue-800', Icon: PythonIcon };
    case 'js': return { isSupported: true, color: 'text-yellow-500', bg: 'bg-yellow-50', activeBg: 'bg-yellow-100', activeText: 'text-yellow-800', Icon: JavascriptIcon };
    case 'ts': return { isSupported: true, color: 'text-blue-600', bg: 'bg-blue-50', activeBg: 'bg-blue-100', activeText: 'text-blue-800', Icon: TypescriptIcon };
    case 'jsx': 
    case 'tsx': return { isSupported: true, color: 'text-cyan-500', bg: 'bg-cyan-50', activeBg: 'bg-cyan-100', activeText: 'text-cyan-800', Icon: ReactIcon };
    case 'java': return { isSupported: true, color: 'text-red-500', bg: 'bg-red-50', activeBg: 'bg-red-100', activeText: 'text-red-800', Icon: JavaIcon };
    default: return { isSupported: false, color: 'text-gray-400', bg: 'bg-gray-50', activeBg: 'bg-gray-200', activeText: 'text-gray-800', Icon: null };
  }
};

const TreeNode = ({ node, onFileClick, selectedPath, isRoot = false }) => {
  const [isOpen, setIsOpen] = useState(isRoot);

  if (node.type === "file") {
    const meta = getFileMeta(node.name);
    const isSelected = selectedPath === node.path;
    
    return (
      <div 
        className={`py-1 flex items-center text-sm rounded px-2 mt-1 ${meta.isSupported ? `cursor-pointer hover:${meta.bg}` : 'text-gray-500'} ${isSelected ? `${meta.activeBg} font-medium ${meta.activeText}` : 'text-gray-600'}`}
        onClick={() => meta.isSupported && onFileClick(node.path)}
      >
        <span className={`mr-2 flex items-center justify-center w-4 h-4 ${meta.color}`}>
          {meta.Icon ? <meta.Icon className="w-4 h-4" /> : "📄"}
        </span>
        <span className="truncate" title={node.name}>{node.name}</span>
      </div>
    );
  }

  return (
    <div className="mt-1">
      <div 
        className="py-1 px-2 flex items-center text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100 rounded"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="mr-1 text-gray-400">
          {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </span>
        <span className="mr-2 text-blue-400">
          {isOpen ? <FolderOpen className="w-4 h-4" /> : <Folder className="w-4 h-4" />}
        </span>
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
          <TreeNode node={hierarchy} onFileClick={onFileClick} selectedPath={selectedFile} isRoot={true} />
        ) : (
          <div className="text-gray-400 text-sm">No files found.</div>
        )}
      </div>
    </div>
  );
}

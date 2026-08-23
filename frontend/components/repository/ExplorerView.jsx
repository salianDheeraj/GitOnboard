"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { Folder, RotateCcw, RefreshCw } from 'lucide-react';
import { TreeNode } from '@/components/workspace/FileTree';
import { getRepositoryStructure } from '@/services/repositoryApi';
import { sanitizeFileTree, toggleExpandedPath } from '@/utils/fileTree';
import CodeDetailsViewer from '@/components/CodeDetailsViewer';
import { repositoryService } from '@/services/repository';

export default function ExplorerView({ repoName }) {
  const [treeHierarchy, setTreeHierarchy] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedPaths, setExpandedPaths] = useState(new Set(['']));

  const [selectedFile, setSelectedFile] = useState(null);
  const [astData, setAstData] = useState(null);
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState(null);

  const [selectedFunction, setSelectedFunction] = useState(null);
  const [selectedClass, setSelectedClass] = useState(null);

  const loadStructure = useCallback(() => {
    if (!repoName) return;
    setIsLoading(true);
    getRepositoryStructure(repoName).then((tree) => {
      setTreeHierarchy(sanitizeFileTree(tree));
      setIsLoading(false);
    });
  }, [repoName]);

  useEffect(() => {
    loadStructure();
  }, [loadStructure]);

  const toggleExpand = useCallback((path) => {
    setExpandedPaths((prev) => toggleExpandedPath(prev, path));
  }, []);

  const handleFileClick = async (filePath) => {
    setSelectedFile(filePath);
    setIsParsing(true);
    setParseError(null);
    setAstData(null);
    setSelectedFunction(null);
    setSelectedClass(null);

    try {
      const json = await repositoryService.parseFile(repoName, filePath);
      setAstData(json);
    } catch (err) {
      setParseError(err.message);
    } finally {
      setIsParsing(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 h-full">
      <div className="lg:col-span-4 flex flex-col overflow-hidden bg-workspace-surface rounded-xl shadow-sm border border-workspace-border text-workspace-text">
        <div className="h-9 px-3 border-b border-workspace-border flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-workspace-text-muted flex-shrink-0">
          <div className="flex items-center gap-1.5">
            <Folder className="w-4 h-4 text-workspace-accent" />
            <span className="truncate">Repository Explorer</span>
          </div>
          <button
            onClick={loadStructure}
            className="hover:text-workspace-text transition-colors p-0.5 rounded"
            title="Refresh Structure"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto py-1 text-xs">
          {isLoading ? (
            <div className="p-3 text-xs text-workspace-text-muted font-mono flex items-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-workspace-accent" />
              <span>Loading tree...</span>
            </div>
          ) : treeHierarchy ? (
            <TreeNode
              node={treeHierarchy}
              activeFile={selectedFile || ""}
              onSelectFile={handleFileClick}
              expandedPaths={expandedPaths}
              onToggle={toggleExpand}
            />
          ) : (
            <div className="p-3 text-xs text-workspace-text-muted italic">No files found.</div>
          )}
        </div>
      </div>
      <div className="lg:col-span-8 flex flex-col overflow-hidden bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
        <CodeDetailsViewer
          selectedFile={selectedFile}
          isParsing={isParsing}
          parseError={parseError}
          astData={astData}
          selectedFunction={selectedFunction}
          setSelectedFunction={setSelectedFunction}
          selectedClass={selectedClass}
          setSelectedClass={setSelectedClass}
        />
      </div>
    </div>
  );
}

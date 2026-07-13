"use client";

import React, { useState, useEffect } from 'react';
import FileExplorer from '@/components/FileExplorer';
import CodeDetailsViewer from '@/components/CodeDetailsViewer';
import { repositoryService } from '@/services/repository';

export default function ExplorerView({ repoName }) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [astData, setAstData] = useState(null);
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState(null);
  
  const [selectedFunction, setSelectedFunction] = useState(null);
  const [selectedClass, setSelectedClass] = useState(null);

  useEffect(() => {
    if (!repoName) return;
    
    const fetchScanData = async () => {
      try {
        const json = await repositoryService.scan(repoName);
        setData(json);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchScanData();
  }, [repoName]);

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

  if (isLoading) {
    return <div className="p-8 flex justify-center items-center h-full text-slate-500">Loading explorer...</div>;
  }

  if (error) {
    return <div className="p-8 text-red-600 bg-red-50 m-4 rounded-lg">Error: {error}</div>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 h-full">
      <div className="lg:col-span-4 flex flex-col overflow-hidden bg-white rounded-xl shadow-sm border border-slate-200">
        <FileExplorer 
          hierarchy={data?.hierarchy} 
          onFileClick={handleFileClick} 
          selectedFile={selectedFile} 
        />
      </div>
      <div className="lg:col-span-8 flex flex-col overflow-hidden bg-white rounded-xl shadow-sm border border-slate-200">
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

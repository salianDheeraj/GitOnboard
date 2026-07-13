"use client";

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { repositoryService } from '@/services/repository';
import RepositoryOverview from '@/components/repository/RepositoryOverview';

export default function RepositoryOverviewPage() {
  const params = useParams();
  const repoName = params.repoName;
  
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!repoName) return;
    
    const fetchScanData = async () => {
      try {
        const json = await repositoryService.scan(repoName);
        setData(json);
      } catch (err) {
        setError((err as any).message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchScanData();
  }, [repoName]);

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading overview...</div>;
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 text-red-600 p-4 rounded-md border border-red-100">Error: {error}</div>
      </div>
    );
  }

  return <RepositoryOverview repoName={repoName} data={data} />;
}

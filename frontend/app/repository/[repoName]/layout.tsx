import React from 'react';
import { Sidebar } from '@/components/layout/Sidebar';

export default async function RepositoryLayout(props: any) {
  const params = await props.params;
  const repoName = params.repoName;

  return (
    <div className="flex w-full h-full">
      <Sidebar repoName={repoName} />
      <main className="flex-1 overflow-y-auto bg-slate-50 relative">
        {props.children}
      </main>
    </div>
  );
}

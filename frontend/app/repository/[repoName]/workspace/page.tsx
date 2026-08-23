"use client";

import React from "react";
import { useParams } from "next/navigation";
import { WorkspaceLayout } from "@/components/workspace/WorkspaceLayout";
import { useResolveRepoName } from "@/hooks/useResolveRepoName";

export default function RepoWorkspacePage() {
  const params = useParams();
  const rawRepoName = (params?.repoName as string) || "";
  const repoName = decodeURIComponent(rawRepoName);
  const { repoName: resolvedRepo, isLoading } = useResolveRepoName(repoName || null);

  if (isLoading) {
    return (
      <div className="h-screen w-screen bg-workspace-bg text-workspace-text flex items-center justify-center font-mono text-sm">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-workspace-accent border-t-transparent rounded-full animate-spin" />
          <span>Resolving repository context...</span>
        </div>
      </div>
    );
  }

  return <WorkspaceLayout initialRepoName={resolvedRepo || "default"} />;
}

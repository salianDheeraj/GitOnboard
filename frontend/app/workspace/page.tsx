"use client";

import React, { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useResolveRepoName } from "@/hooks/useResolveRepoName";

// Legacy entry point — redirects to the canonical workspace route,
// /repository/{repoName}/workspace, which keeps repo context in the URL.
function RedirectToCanonicalWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryRepo = searchParams.get("repo");
  const { isLoading: authLoading, isAuthenticated } = useAuth();
  const { repoName, isLoading: repoLoading } = useResolveRepoName(queryRepo);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace("/");
      return;
    }
    if (repoLoading || !repoName) return;
    router.replace(`/repository/${encodeURIComponent(repoName)}/workspace`);
  }, [authLoading, isAuthenticated, repoLoading, repoName, router]);

  return (
    <div className="h-screen w-screen bg-workspace-bg text-workspace-text flex items-center justify-center font-mono text-sm">
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 border-2 border-workspace-accent border-t-transparent rounded-full animate-spin" />
        <span>Redirecting to workspace...</span>
      </div>
    </div>
  );
}

export default function RootWorkspacePage() {
  return (
    <Suspense
      fallback={
        <div className="h-screen w-screen bg-workspace-bg text-workspace-text flex items-center justify-center font-mono text-sm">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 border-2 border-workspace-accent border-t-transparent rounded-full animate-spin" />
            <span>Loading workspace...</span>
          </div>
        </div>
      }
    >
      <RedirectToCanonicalWorkspace />
    </Suspense>
  );
}

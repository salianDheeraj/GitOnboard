"use client";

import { useEffect, useState } from "react";

/**
 * Resolves the repository to open in the workspace: uses `explicitRepoName`
 * when given (e.g. from a route param or query string), otherwise fetches
 * the user's registered repositories and falls back to the first one, or
 * "default" if none are registered.
 */
export function useResolveRepoName(explicitRepoName?: string | null) {
  const [repoName, setRepoName] = useState<string | null>(explicitRepoName || null);
  const [isLoading, setIsLoading] = useState<boolean>(!explicitRepoName);

  // Sync state to a changed explicitRepoName (e.g. navigating between repos)
  // during render rather than in an effect, avoiding a redundant extra pass.
  const [prevExplicit, setPrevExplicit] = useState(explicitRepoName);
  if (explicitRepoName !== prevExplicit) {
    setPrevExplicit(explicitRepoName);
    if (explicitRepoName) {
      setRepoName(explicitRepoName);
      setIsLoading(false);
    } else {
      setIsLoading(true);
    }
  }

  useEffect(() => {
    if (explicitRepoName) return;

    let cancelled = false;

    async function resolveFirstRepo() {
      try {
        const res = await fetch("/api/repos");
        if (res.ok) {
          const data = await res.json();
          const repoList = Array.isArray(data) ? data : data?.repositories || [];
          if (repoList.length > 0) {
            const first = repoList[0];
            const firstRepo =
              first.project_name ||
              first.name ||
              (first.url ? first.url.split("/").pop().replace(".git", "") : "default");
            if (!cancelled) {
              setRepoName(firstRepo);
              setIsLoading(false);
            }
            return;
          }
        }
      } catch (err) {
        console.warn("Failed to fetch repositories:", err);
      }
      if (!cancelled) {
        setRepoName("default");
        setIsLoading(false);
      }
    }

    resolveFirstRepo();
    return () => {
      cancelled = true;
    };
  }, [explicitRepoName]);

  return { repoName, isLoading };
}

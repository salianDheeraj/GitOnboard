import { useState, useEffect } from 'react';

export function useTaskStatus(repoName, taskName, intervalMs = 2000) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    if (!repoName) return;

    let isMounted = true;
    
    const fetchStatus = async () => {
      try {
        const res = await fetch(`/api/repos/${repoName}/tasks`);
        if (!res.ok) return;
        const tasks = await res.json();
        if (isMounted) {
          setStatus(tasks[taskName] || null);
        }
      } catch (err) {
        console.error("Failed to fetch task status", err);
      }
    };

    // Initial fetch
    fetchStatus();

    // Poll interval
    const intervalId = setInterval(fetchStatus, intervalMs);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [repoName, taskName, intervalMs]);

  return status;
}

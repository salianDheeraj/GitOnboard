"use client";

import { useState, useEffect, useRef } from 'react';

export function useTaskStatus(repoName, taskName) {
  const [status, setStatus] = useState(null);
  const esRef = useRef(null);

  useEffect(() => {
    if (!repoName) return;

    // Close any existing connection before opening a new one
    if (esRef.current) {
      esRef.current.close();
    }

    const es = new EventSource(`/api/repos/${repoName}/tasks/stream`);
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const tasks = JSON.parse(event.data);
        if (taskName in tasks) {
          setStatus(tasks[taskName]);
        }
      } catch {
        // Ignore malformed events
      }
    };

    es.onerror = () => {
      // Browser auto-reconnects on error — no action needed
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [repoName, taskName]);

  return status;
}

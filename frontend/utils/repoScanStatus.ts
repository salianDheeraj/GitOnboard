// Shared with dashboard/page.tsx and repository/[repoName]/page.tsx, which
// both render a progress bar for an in-flight repository import/analysis job.
export const REPO_SCAN_STATUS_PROGRESS: Record<string, number> = {
  Queued: 10,
  Downloading: 30,
  Analyzing: 60,
  Saving: 90,
  Completed: 100,
  Failed: 0,
};

export function getRepoScanProgress(status: string | null | undefined): number {
  if (!status) return REPO_SCAN_STATUS_PROGRESS.Queued;
  return REPO_SCAN_STATUS_PROGRESS[status] ?? REPO_SCAN_STATUS_PROGRESS.Queued;
}

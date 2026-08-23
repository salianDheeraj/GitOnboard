"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  ChevronDown,
  Search,
  Bell,
  Check,
  GitBranch,
  Play,
  RefreshCw,
  Folder,
  FolderTree,
  Terminal,
  Keyboard,
  HeartPulse,
  User as UserIcon,
} from "lucide-react";
import { RunState } from "@/types/workspace";
import { Button } from "@/components/common/Button";
import { useAuth } from "@/context/AuthContext";

const HEALTH_STATUS_STYLE: Record<string, string> = {
  Excellent: "text-emerald-400",
  Good: "text-emerald-400",
  Fair: "text-amber-400",
  "Needs Work": "text-rose-400",
  Analyzing: "text-workspace-text-muted",
};

interface HeaderGlobalProps {
  runState?: RunState;
  onRunVerification?: () => void;
  isFileExplorerOpen?: boolean;
  onToggleFileExplorer?: () => void;
  isTerminalOpen?: boolean;
  onToggleTerminal?: () => void;
  isAIAgentOpen?: boolean;
  onToggleAIAgent?: () => void;
  onOpenShortcuts?: () => void;
  onSelectFile?: (filePath: string) => void;
}

export function HeaderGlobal({
  runState,
  onRunVerification,
  isFileExplorerOpen = true,
  onToggleFileExplorer,
  isTerminalOpen = true,
  onToggleTerminal,
  isAIAgentOpen = true,
  onToggleAIAgent,
  onOpenShortcuts,
  onSelectFile,
}: HeaderGlobalProps) {
  const router = useRouter();
  const currentRepo = runState?.repoId || "default";
  const { user } = useAuth();
  const hasUnresolvedDefects = Boolean(runState?.report && !runState.report.passed && (runState.report.defects?.length || 0) > 0);

  const [repositories, setRepositories] = useState<Array<{ id: number | string; name: string; branch: string }>>([]);
  const [selectedProject, setSelectedProject] = useState<string>(currentRepo);
  const [selectedBranch, setSelectedBranch] = useState<string>(runState?.branch || "main");
  const [isProjectDropdownOpen, setIsProjectDropdownOpen] = useState(false);

  // Repo Health Chip — reuses the same /health/scores endpoint RepositoryOverview
  // fetches on the dashboard side, so the IDE header reflects the same status.
  const [healthStatus, setHealthStatus] = useState<string | null>(null);
  const [healthScore, setHealthScore] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;
    setHealthStatus(null);
    setHealthScore(null);
    fetch(`/api/repos/${encodeURIComponent(currentRepo)}/health/scores`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data) return;
        setHealthStatus(data.status || null);
        setHealthScore(typeof data.health_score === "number" ? data.health_score : null);
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, [currentRepo]);

  // Search Bar state (⌘ K)
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Array<{ name: string; type: string; file_path: string }>>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);

  // Fetch registered repositories from GET /api/repos on mount
  useEffect(() => {
    async function fetchRepos() {
      try {
        const res = await fetch("/api/repos");
        if (res.ok) {
          const data = await res.json();
          const repoList = (data.repositories || data || []).map((r: any) => ({
            id: r.id || r.name,
            name: r.project_name || r.name || (r.url ? r.url.split("/").pop().replace(".git", "") : "default"),
            branch: r.branch || r.default_branch || "main",
          }));
          if (repoList.length > 0) {
            setRepositories(repoList);
            const found = repoList.find((r: any) => r.name === currentRepo);
            if (found) {
              setSelectedBranch(found.branch);
            }
          }
        }
      } catch (err) {
        console.warn("Failed to fetch registered repositories:", err);
      }
    }
    fetchRepos();
  }, [currentRepo]);

  // Handle switching projects
  const handleSelectProject = (projName: string) => {
    setSelectedProject(projName);
    setIsProjectDropdownOpen(false);
    router.push(`/repository/${encodeURIComponent(projName)}/workspace`);
  };

  // Perform live symbol / semantic search on input
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setSearchResults([]);
      setShowSearchDropdown(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      setShowSearchDropdown(true);
      try {
        const res = await fetch(`/api/repos/${encodeURIComponent(currentRepo)}/symbols`);
        if (res.ok) {
          const data = await res.json();
          const allSymbols = data.symbols || [];
          const q = searchQuery.toLowerCase();
          const filtered = allSymbols
            .filter((s: any) => (s.name || "").toLowerCase().includes(q) || (s.file_path || "").toLowerCase().includes(q))
            .slice(0, 8);
          setSearchResults(filtered);
        }
      } catch (err) {
        console.warn("Symbol search error:", err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, currentRepo]);

  return (
    <header className="h-12 bg-workspace-surface border-b border-workspace-border px-4 flex items-center justify-between select-none z-20 flex-shrink-0">
      {/* Left Section: Platform Brand + Contextual Dropdowns */}
      <div className="flex items-center gap-3">
        {/* Brand / Logo */}
        <Link href="/dashboard" className="flex items-center gap-2 group mr-2">
          <div className="w-7 h-7 rounded-lg bg-workspace-accent flex items-center justify-center shadow-md shadow-workspace-accent/30 group-hover:scale-105 transition-transform">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-sm text-workspace-text tracking-wide">
            GitOnboard
          </span>
        </Link>

        {/* Project Selector Dropdown */}
        <div className="relative">
          <button
            onClick={() => setIsProjectDropdownOpen(!isProjectDropdownOpen)}
            className="flex items-center gap-2 bg-workspace-bg border border-workspace-border hover:border-workspace-accent/50 px-2.5 py-1 rounded text-xs transition-colors font-medium text-workspace-text"
          >
            <Folder className="w-4 h-4 text-workspace-accent" />
            <span className="truncate max-w-[140px] font-mono">{selectedProject}</span>
            <ChevronDown className="w-3 h-3 text-workspace-text-muted" />
          </button>

          {isProjectDropdownOpen && (
            <div className="absolute top-full left-0 mt-1 w-56 bg-workspace-surface border border-workspace-border rounded-md shadow-2xl py-1 z-50 text-xs">
              <div className="px-3 py-1 text-[10px] uppercase font-semibold text-workspace-text-muted tracking-wider">
                Select Project
              </div>
              {repositories.map((repo) => (
                <button
                  key={repo.id}
                  onClick={() => handleSelectProject(repo.name)}
                  className="w-full text-left px-3 py-1.5 hover:bg-workspace-surface-raised flex items-center justify-between transition-colors font-mono"
                >
                  <span className="truncate">{repo.name}</span>
                  {repo.name === selectedProject && <Check className="w-3 h-3 text-workspace-accent" />}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Active Git Branch (read-only until branch switching is real) */}
        <div
          className="flex items-center gap-2 bg-workspace-bg border border-workspace-border px-2.5 py-1 rounded text-xs font-mono text-workspace-text-muted"
          title="Active Git Branch"
        >
          <GitBranch className="w-4 h-4 text-workspace-accent" />
          <span className="truncate max-w-[100px]">{selectedBranch}</span>
        </div>

        {/* Repo Health Chip — same health/scores data the dashboard overview shows */}
        {healthStatus && (
          <div
            className="hidden lg:flex items-center gap-1.5 bg-workspace-bg border border-workspace-border px-2.5 py-1 rounded text-xs font-mono"
            title={`Repository health: ${healthStatus}${healthScore !== null ? ` (${Math.round(healthScore)}/100)` : ""}`}
          >
            <HeartPulse className={`w-4 h-4 ${HEALTH_STATUS_STYLE[healthStatus] || "text-workspace-text-muted"}`} />
            <span className={HEALTH_STATUS_STYLE[healthStatus] || "text-workspace-text-muted"}>{healthStatus}</span>
          </div>
        )}
      </div>

      {/* Middle Section: Centralized Semantic / Symbol Search Bar */}
      <div className="flex-1 max-w-md mx-4 relative">
        <div className="relative flex items-center">
          <Search className="w-4 h-4 absolute left-3 text-workspace-text-muted pointer-events-none" />
          <input
            id="global-search-input"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => {
              if (searchResults.length > 0) setShowSearchDropdown(true);
            }}
            placeholder="Search files, symbols, AST entities (Ctrl+K)..."
            className="w-full bg-workspace-bg border border-workspace-border rounded-md py-1 pl-9 pr-12 text-xs text-workspace-text placeholder-workspace-text-muted focus:outline-none focus:border-workspace-accent focus:ring-1 focus:ring-workspace-accent/30 transition-all font-mono"
          />
          <span className="absolute right-2.5 text-[10px] font-mono text-workspace-text-muted bg-workspace-surface border border-workspace-border px-1.5 py-0.5 rounded pointer-events-none">
            Ctrl+K
          </span>
        </div>

        {/* Live Symbol Search Results Dropdown */}
        {showSearchDropdown && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-workspace-surface border border-workspace-border rounded-md shadow-2xl py-1 z-50 text-xs max-h-60 overflow-y-auto">
            {isSearching ? (
              <div className="p-2.5 text-workspace-text-muted text-xs font-mono flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-workspace-accent" />
                <span>Searching symbols...</span>
              </div>
            ) : searchResults.length > 0 ? (
              searchResults.map((sym, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    if (sym.file_path && onSelectFile) onSelectFile(sym.file_path);
                    setShowSearchDropdown(false);
                    setSearchQuery("");
                  }}
                  className="px-3 py-1.5 hover:bg-workspace-surface-raised cursor-pointer flex items-center justify-between font-mono"
                >
                  <div className="flex items-center gap-2 truncate">
                    <span className="text-workspace-accent font-semibold">{sym.name}</span>
                    <span className="text-[10px] text-workspace-text-muted truncate">{sym.file_path}</span>
                  </div>
                  <span className="text-[9px] uppercase px-1 rounded bg-workspace-border text-workspace-text-muted">
                    {sym.type || "symbol"}
                  </span>
                </div>
              ))
            ) : (
              <div className="p-2.5 text-workspace-text-muted text-xs italic">No symbols found for "{searchQuery}"</div>
            )}
          </div>
        )}
      </div>

      {/* Right Section: View Ribbon + Run Verification & Actions */}
      <div className="flex items-center gap-2.5">
        {/* Top View Access Ribbon */}
        <div className="flex items-center gap-1 bg-workspace-bg border border-workspace-border p-0.5 rounded-lg">
          <button
            onClick={onToggleFileExplorer}
            className={`px-2 py-1 rounded flex items-center gap-1.5 text-xs font-medium transition-all ${
              isFileExplorerOpen
                ? "bg-workspace-accent/30 text-workspace-accent border border-workspace-accent/40 shadow-sm"
                : "text-workspace-text-muted hover:text-workspace-text hover:bg-workspace-surface-raised"
            }`}
            title="Toggle File Explorer (Ctrl+B)"
            aria-label="Toggle File Explorer"
            aria-pressed={isFileExplorerOpen}
          >
            <FolderTree className="w-4 h-4" />
            <span className="hidden xl:inline text-[11px]">Explorer</span>
          </button>

          <button
            onClick={onToggleTerminal}
            className={`px-2 py-1 rounded flex items-center gap-1.5 text-xs font-medium transition-all ${
              isTerminalOpen
                ? "bg-workspace-accent/30 text-workspace-accent border border-workspace-accent/40 shadow-sm"
                : "text-workspace-text-muted hover:text-workspace-text hover:bg-workspace-surface-raised"
            }`}
            title="Toggle Terminal & Tests (Ctrl+` or Ctrl+J)"
            aria-label="Toggle Terminal"
            aria-pressed={isTerminalOpen}
          >
            <Terminal className="w-4 h-4" />
            <span className="hidden xl:inline text-[11px]">Terminal</span>
          </button>

          <button
            onClick={onToggleAIAgent}
            className={`px-2 py-1 rounded flex items-center gap-1.5 text-xs font-medium transition-all ${
              isAIAgentOpen
                ? "bg-workspace-accent/30 text-workspace-accent border border-workspace-accent/40 shadow-sm"
                : "text-workspace-text-muted hover:text-workspace-text hover:bg-workspace-surface-raised"
            }`}
            title="Toggle AI Agent Panel (Ctrl+L or Ctrl+I)"
            aria-label="Toggle AI Agent Panel"
            aria-pressed={isAIAgentOpen}
          >
            <Sparkles className="w-4 h-4" />
            <span className="hidden xl:inline text-[11px]">AI Agent</span>
          </button>

          <div className="h-3 w-[1px] bg-workspace-border mx-0.5" />

          <button
            onClick={onOpenShortcuts}
            className="p-1 rounded text-workspace-text-muted hover:text-workspace-accent hover:bg-workspace-surface-raised transition-colors"
            title="Keyboard Shortcuts & Commands (? or Ctrl+Shift+P)"
            aria-label="Keyboard Shortcuts & Commands"
          >
            <Keyboard className="w-4 h-4" />
          </button>
        </div>

        {/* Primary Action: Run Verification */}
        <Button
          variant="primary"
          size="sm"
          onClick={onRunVerification}
          disabled={runState?.isLoading}
          aria-label="Run Verification"
          icon={
            runState?.isLoading ? (
              <RefreshCw className="w-4 h-4 animate-spin text-white/80" />
            ) : (
              <Play className="w-4 h-4 fill-current" />
            )
          }
          className="shadow-md workspace:shadow-workspace-accent/30"
        >
          <span className="hidden sm:inline">Run Verification</span>
        </Button>

        <button
          onClick={() => {
            if (!isTerminalOpen) onToggleTerminal?.();
          }}
          className="p-1.5 text-workspace-text-muted hover:text-workspace-text hover:bg-workspace-surface-raised rounded transition-colors relative"
          title={
            hasUnresolvedDefects
              ? `${runState?.report?.defects?.length || 0} unresolved defect(s) — open Terminal → Problems`
              : "No unresolved defects"
          }
          aria-label={
            hasUnresolvedDefects
              ? `Notifications: ${runState?.report?.defects?.length || 0} unresolved defect(s)`
              : "Notifications: no unresolved defects"
          }
        >
          <Bell className="w-4 h-4" />
          {hasUnresolvedDefects && (
            <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-rose-500 rounded-full"></span>
          )}
        </button>

        {/* Profile Avatar — same auth-derived identity as the dashboard Header */}
        <div className="relative pl-1 border-l border-workspace-border">
          <div
            className="w-7 h-7 rounded-full bg-workspace-surface-raised text-workspace-text font-semibold text-xs flex items-center justify-center ring-1 ring-workspace-border overflow-hidden shadow-sm"
            title={user?.username || "Not signed in"}
          >
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt={user.username} className="w-full h-full object-cover" />
            ) : user?.username ? (
              user.username.charAt(0).toUpperCase()
            ) : (
              <UserIcon className="w-4 h-4 text-workspace-text-muted" />
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

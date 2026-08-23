"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  FolderTree,
  Network,
  Search,
  Sparkles,
  GitMerge,
  Menu,
  X,
} from 'lucide-react';

const navItems = [
  { id: 'overview', label: 'Dashboard', icon: LayoutDashboard, path: '' },
  { id: 'workspace', label: 'AI Workspace IDE', icon: Sparkles, path: '/workspace' },
  { id: 'trace', label: 'Feature Tracing', icon: GitMerge, path: '/trace' },
  { id: 'explorer', label: 'File Explorer', icon: FolderTree, path: '/explorer' },
  { id: 'architecture', label: 'Architecture', icon: Network, path: '/architecture' },
  { id: 'search', label: 'Search', icon: Search, path: '/search' },
  { id: 'summary', label: 'AI Summary', icon: Sparkles, path: '/summary' },
];

function NavLinks({ repoName, pathname, onNavigate }) {
  return (
    <nav className="space-y-1 px-3">
      {navItems.map((item) => {
        const itemPath = item.id === 'workspace'
          ? `/repository/${encodeURIComponent(repoName || '')}/workspace`
          : item.path === ''
            ? `/repository/${repoName}`
            : `/repository/${repoName}${item.path}`;

        const isActive = item.id === 'workspace'
          ? pathname === '/workspace' || pathname?.includes('/workspace')
          : item.path === ''
            ? pathname === `/repository/${repoName}`
            : pathname.startsWith(`/repository/${repoName}${item.path}`);

        return (
          <Link
            key={item.id}
            href={itemPath}
            onClick={onNavigate}
            className={`
              flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group
              ${isActive
                ? 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'}
            `}
          >
            <item.icon
              className={`flex-shrink-0 mr-3 h-5 w-5 ${isActive ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 dark:text-slate-500 group-hover:text-slate-500 dark:group-hover:text-slate-300'}`}
            />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Sidebar({ repoName }) {
  const pathname = usePathname();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <>
      {/* Desktop sidebar */}
      <div className="w-64 border-r border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 flex-col h-full hidden md:flex transition-colors">
        <div className="flex-grow py-6 overflow-y-auto overflow-x-hidden">
          <NavLinks repoName={repoName} pathname={pathname} />
        </div>
      </div>

      {/* Mobile hamburger trigger — repository navigation is otherwise
          unreachable below the md breakpoint since the sidebar above is
          hidden entirely there. */}
      <button
        type="button"
        onClick={() => setIsMobileOpen(true)}
        aria-label="Open repository navigation"
        aria-expanded={isMobileOpen}
        className="md:hidden fixed top-20 left-4 z-40 p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 shadow-md"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Mobile drawer */}
      {isMobileOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-slate-900/50 dark:bg-slate-950/70"
            onClick={() => setIsMobileOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] bg-slate-50 dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shadow-xl">
            <div className="flex items-center justify-between px-4 h-16 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
              <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">Repository Navigation</span>
              <button
                type="button"
                onClick={() => setIsMobileOpen(false)}
                aria-label="Close repository navigation"
                className="p-1.5 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-grow py-6 overflow-y-auto overflow-x-hidden">
              <NavLinks repoName={repoName} pathname={pathname} onNavigate={() => setIsMobileOpen(false)} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

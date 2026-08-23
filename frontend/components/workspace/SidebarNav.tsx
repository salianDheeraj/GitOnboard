"use client";

import React from "react";
import { FolderTree, Terminal, Sparkles, Keyboard } from "lucide-react";

interface SidebarNavProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isFileExplorerOpen: boolean;
  setIsFileExplorerOpen: (open: boolean) => void;
  isTerminalOpen?: boolean;
  onToggleTerminal?: () => void;
  isAIAgentOpen?: boolean;
  onToggleAIAgent?: () => void;
  onOpenShortcuts?: () => void;
}

export function SidebarNav({
  activeTab,
  setActiveTab,
  isFileExplorerOpen,
  setIsFileExplorerOpen,
  isTerminalOpen,
  onToggleTerminal,
  isAIAgentOpen,
  onToggleAIAgent,
  onOpenShortcuts,
}: SidebarNavProps) {
  const topNavItems = [
    { id: "projects", icon: FolderTree, label: "Explorer (Ctrl+B)", isPanelToggle: true, isOpen: isFileExplorerOpen },
    { id: "terminal", icon: Terminal, label: "Terminal & Tests (Ctrl+`)", isPanelToggle: true, isOpen: isTerminalOpen },
    { id: "agent", icon: Sparkles, label: "AI Agent Chat (Ctrl+L)", isPanelToggle: true, isOpen: isAIAgentOpen },
  ];

  const bottomNavItems = [
    { id: "shortcuts", icon: Keyboard, label: "Keyboard Shortcuts (?)", isPanelToggle: false, isOpen: false },
  ];

  const handleItemClick = (id: string) => {
    setActiveTab(id);
    if (id === "projects") {
      setIsFileExplorerOpen(!isFileExplorerOpen);
    } else if (id === "terminal" && onToggleTerminal) {
      onToggleTerminal();
    } else if (id === "agent" && onToggleAIAgent) {
      onToggleAIAgent();
    } else if (id === "shortcuts" && onOpenShortcuts) {
      onOpenShortcuts();
    }
  };

  return (
    <aside className="w-12 bg-workspace-bg border-r border-workspace-border flex flex-col justify-between items-center py-2 flex-shrink-0 select-none z-10">
      {/* Top Nav Group */}
      <div className="flex flex-col gap-1 w-full items-center">
        {topNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id || (item.isPanelToggle && item.isOpen);
          return (
            <button
              key={item.id}
              onClick={() => handleItemClick(item.id)}
              title={item.label}
              aria-label={item.label}
              aria-pressed={item.isPanelToggle ? Boolean(item.isOpen) : undefined}
              className={`relative w-9 h-9 rounded-lg flex items-center justify-center transition-all group ${
                isActive
                  ? "bg-workspace-accent/20 text-workspace-accent font-semibold shadow-sm"
                  : "text-workspace-text-muted hover:text-workspace-text hover:bg-workspace-surface"
              }`}
            >
              {/* Accent Left Highlight Bar for Active State */}
              {isActive && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-workspace-accent rounded-r-md shadow-sm shadow-workspace-accent/50" />
              )}
              <Icon className={`w-5 h-5 transition-transform group-hover:scale-105 ${isActive ? "text-workspace-accent" : ""}`} />
            </button>
          );
        })}
      </div>

      {/* Bottom Nav Group */}
      <div className="flex flex-col gap-1 w-full items-center pt-2 border-t border-workspace-border/60">
        {bottomNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => handleItemClick(item.id)}
              title={item.label}
              aria-label={item.label}
              aria-pressed={item.isPanelToggle ? Boolean(item.isOpen) : undefined}
              className={`relative w-9 h-9 rounded-lg flex items-center justify-center transition-all group ${
                isActive
                  ? "bg-workspace-accent/20 text-workspace-accent font-semibold shadow-sm"
                  : "text-workspace-text-muted hover:text-workspace-text hover:bg-workspace-surface"
              }`}
            >
              {isActive && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-workspace-accent rounded-r-md shadow-sm shadow-workspace-accent/50" />
              )}
              <Icon className="w-5 h-5 transition-transform group-hover:scale-105" />
            </button>
          );
        })}
      </div>
    </aside>
  );
}


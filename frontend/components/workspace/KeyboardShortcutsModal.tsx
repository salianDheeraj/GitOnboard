"use client";

import React from "react";
import { X, Keyboard, Sparkles, Terminal, FolderTree, Play, Search } from "lucide-react";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/common/Button";

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsModal({ isOpen, onClose }: KeyboardShortcutsModalProps) {
  const shortcuts = [
    {
      category: "Panels & Views",
      items: [
        {
          label: "Toggle File Explorer",
          keys: ["Ctrl", "B"],
          macKeys: ["⌘", "B"],
          icon: FolderTree,
          desc: "Show or hide the repository file tree",
        },
        {
          label: "Toggle Terminal & Tests",
          keys: ["Ctrl", "`"],
          altKeys: ["Ctrl", "J"],
          macKeys: ["⌘", "`"],
          icon: Terminal,
          desc: "Open or close the worktree sandbox terminal & test output",
        },
        {
          label: "Toggle AI Agent Chat",
          keys: ["Ctrl", "L"],
          altKeys: ["Ctrl", "I"],
          macKeys: ["⌘", "L"],
          icon: Sparkles,
          desc: "Open or close the autonomous verification agent panel",
        },
      ],
    },
    {
      category: "Navigation & Actions",
      items: [
        {
          label: "Search Symbols & Files",
          keys: ["Ctrl", "K"],
          macKeys: ["⌘", "K"],
          icon: Search,
          desc: "Focus search bar for fast symbol & AST lookup",
        },
        {
          label: "Run Verification Pipeline",
          keys: ["Ctrl", "Enter"],
          macKeys: ["⌘", "Enter"],
          icon: Play,
          desc: "Start contract synthesis & sandboxed verification",
        },
        {
          label: "Keyboard Shortcuts Guide",
          keys: ["?"],
          altKeys: ["Ctrl", "Shift", "P"],
          macKeys: ["⌘", "Shift", "P"],
          icon: Keyboard,
          desc: "Show this cheat sheet modal",
        },
        {
          label: "Close Overlays & Modals",
          keys: ["Esc"],
          macKeys: ["Esc"],
          icon: X,
          desc: "Dismiss active dropdowns and dialogs",
        },
      ],
    },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      variant="dark"
      title="Keyboard Shortcuts & Access Ribbon"
      titleIcon={
        <div className="p-1.5 rounded-lg bg-workspace-accent/20 text-workspace-accent border border-workspace-accent/30">
          <Keyboard className="w-4 h-4" />
        </div>
      }
    >
      <div className="space-y-5 -m-6 p-5 max-h-[70vh] overflow-y-auto scrollbar-thin">
        {shortcuts.map((section, sIdx) => (
          <div key={sIdx} className="space-y-2.5">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-workspace-accent font-mono">
              {section.category}
            </div>
            <div className="space-y-1.5">
              {section.items.map((item, iIdx) => {
                const Icon = item.icon;
                return (
                  <div
                    key={iIdx}
                    className="flex items-center justify-between p-2 rounded-lg bg-workspace-bg/50 border border-workspace-border/40 hover:border-workspace-accent/30 transition-colors"
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon className="w-4 h-4 text-workspace-accent/80 flex-shrink-0" />
                      <div>
                        <div className="text-xs font-medium text-workspace-text">{item.label}</div>
                        <div className="text-[10px] text-workspace-text-muted">{item.desc}</div>
                      </div>
                    </div>

                    {/* Shortcut Badges */}
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <div className="flex items-center gap-1">
                        {item.keys.map((k, kIdx) => (
                          <kbd
                            key={kIdx}
                            className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-workspace-surface-raised text-workspace-accent border border-workspace-border rounded shadow-sm"
                          >
                            {k}
                          </kbd>
                        ))}
                      </div>
                      {item.altKeys && (
                        <>
                          <span className="text-[10px] text-workspace-text-muted">or</span>
                          <div className="flex items-center gap-1">
                            {item.altKeys.map((k, kIdx) => (
                              <kbd
                                key={kIdx}
                                className="px-1.5 py-0.5 text-[10px] font-mono text-workspace-text-muted bg-workspace-surface-raised/80 border border-workspace-border rounded"
                              >
                                {k}
                              </kbd>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        <div className="flex items-center justify-between text-[11px] text-workspace-text-muted pt-1">
          <span>Tip: You can also use the top ribbon icons anytime</span>
          <Button variant="primary" size="sm" onClick={onClose}>
            Got it
          </Button>
        </div>
      </div>
    </Modal>
  );
}

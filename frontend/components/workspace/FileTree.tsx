"use client";

import React from "react";
import {
  ChevronDown,
  ChevronRight,
  FileCode,
  FileText,
  FileJson,
  File,
  Lock,
  GitBranch,
  Folder,
  FolderOpen,
  Settings,
  Globe,
  Palette,
  Database,
  Terminal,
} from "lucide-react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FileTreeNode } from "@/services/repositoryApi";
import { FlatTreeRow } from "@/utils/fileTree";

/**
 * Returns a file-type specific icon based on extension.
 */
export function renderFileIcon(fileName: string) {
  const lower = fileName.toLowerCase();

  // Python
  if (lower.endsWith(".py") || lower.endsWith(".pyw") || lower.endsWith(".ipynb")) {
    return <FileCode className="w-4 h-4 text-blue-400 flex-shrink-0" />;
  }
  // TypeScript
  if (lower.endsWith(".tsx") || lower.endsWith(".ts") || lower.endsWith(".mts")) {
    return <FileCode className="w-4 h-4 text-cyan-400 flex-shrink-0" />;
  }
  // JavaScript
  if (lower.endsWith(".jsx") || lower.endsWith(".js") || lower.endsWith(".mjs") || lower.endsWith(".cjs")) {
    return <FileCode className="w-4 h-4 text-amber-300 flex-shrink-0" />;
  }
  // JSON / Data
  if (lower.endsWith(".json") || lower.endsWith(".jsonc")) {
    return <FileJson className="w-4 h-4 text-amber-400 flex-shrink-0" />;
  }
  // Markdown / Docs / Text
  if (lower.endsWith(".md") || lower.endsWith(".mdx") || lower.endsWith(".txt") || lower.endsWith(".rst")) {
    return <FileText className="w-4 h-4 text-sky-400 flex-shrink-0" />;
  }
  // Config / TOML / YAML / INI
  if (lower.endsWith(".toml") || lower.endsWith(".yaml") || lower.endsWith(".yml") || lower.endsWith(".ini") || lower.endsWith(".cfg")) {
    return <Settings className="w-4 h-4 text-purple-400 flex-shrink-0" />;
  }
  // Web / HTML / SVG
  if (lower.endsWith(".html") || lower.endsWith(".htm") || lower.endsWith(".svg")) {
    return <Globe className="w-4 h-4 text-orange-400 flex-shrink-0" />;
  }
  // Styles / CSS / SCSS
  if (lower.endsWith(".css") || lower.endsWith(".scss") || lower.endsWith(".sass") || lower.endsWith(".less")) {
    return <Palette className="w-4 h-4 text-pink-400 flex-shrink-0" />;
  }
  // Database / SQL
  if (lower.endsWith(".sql") || lower.endsWith(".db") || lower.endsWith(".sqlite")) {
    return <Database className="w-4 h-4 text-emerald-400 flex-shrink-0" />;
  }
  // Shell / Script
  if (lower.endsWith(".sh") || lower.endsWith(".bash") || lower.endsWith(".zsh") || lower.endsWith(".ps1") || lower.endsWith(".bat")) {
    return <Terminal className="w-4 h-4 text-emerald-400 flex-shrink-0" />;
  }
  // Git / Env / Security
  if (lower.startsWith(".env")) {
    return <Lock className="w-4 h-4 text-emerald-400 flex-shrink-0" />;
  }
  if (lower.startsWith(".git") || lower.endsWith(".lock")) {
    return <GitBranch className="w-4 h-4 text-orange-400 flex-shrink-0" />;
  }

  // Generic Document
  return <File className="w-4 h-4 text-workspace-text-muted flex-shrink-0" />;
}

interface TreeRowContentProps {
  node: FileTreeNode;
  depth: number;
  isOpen: boolean;
  isActive: boolean;
  onToggle: (path: string) => void;
  onSelectFile: (path: string) => void;
}

/**
 * Single-row presentation, shared by the plain recursive tree (small trees)
 * and the virtualized flat-list tree (large trees) so both render pixel-identical rows.
 */
function TreeRowContent({ node, depth, isOpen, isActive, onToggle, onSelectFile }: TreeRowContentProps) {
  const isDirectory = node.type === "directory";

  if (isDirectory) {
    return (
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggle(node.path);
        }}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        className="w-full py-1 px-1.5 flex items-center gap-1.5 hover:bg-workspace-surface-raised text-workspace-text transition-colors text-[11px] font-medium select-none group"
      >
        <span className="w-4 h-4 flex items-center justify-center text-workspace-text-muted group-hover:text-workspace-text">
          {isOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </span>
        {isOpen ? (
          <FolderOpen className="w-4 h-4 text-workspace-accent flex-shrink-0" />
        ) : (
          <Folder className="w-4 h-4 text-workspace-accent flex-shrink-0" />
        )}
        <span className="truncate">{node.name}</span>
      </button>
    );
  }

  // File Node (No chevron, clicking opens in editor)
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onSelectFile(node.path);
      }}
      style={{ paddingLeft: `${depth * 12 + 22}px` }}
      className={`w-full py-1 px-1.5 flex items-center gap-2 transition-colors text-[11px] font-mono select-none ${
        isActive
          ? "bg-workspace-accent/25 text-workspace-text font-semibold border-l-2 border-workspace-accent shadow-sm"
          : "hover:bg-workspace-surface-raised text-workspace-text-muted hover:text-workspace-text"
      }`}
      title={node.path || node.name}
    >
      {renderFileIcon(node.name)}
      <span className="truncate">{node.name}</span>
    </button>
  );
}

/**
 * Recursive file-tree row. Expansion state lives entirely in the caller
 * (`expandedPaths` + `onToggle`) — this component never tracks its own open/
 * closed state, so selecting a file never touches which folders are expanded.
 *
 * Used for small trees (see FileExplorerPanel's virtualization threshold).
 * For large trees, use `VirtualizedTreeList` instead — same rows, windowed.
 */
export function TreeNode({
  node,
  activeFile,
  onSelectFile,
  expandedPaths,
  onToggle,
  depth = 0,
}: {
  node: FileTreeNode;
  activeFile: string;
  onSelectFile: (path: string) => void;
  expandedPaths: Set<string>;
  onToggle: (path: string) => void;
  depth?: number;
}) {
  const isDirectory = node.type === "directory";
  const isOpen = expandedPaths.has(node.path);
  const isActive = activeFile === node.path;

  return (
    <div>
      <TreeRowContent
        node={node}
        depth={depth}
        isOpen={isOpen}
        isActive={isActive}
        onToggle={onToggle}
        onSelectFile={onSelectFile}
      />

      {isDirectory && isOpen && node.children && (
        <div>
          {node.children.map((child, idx) => (
            <TreeNode
              key={`${child.path || node.path}-${child.name}-${idx}`}
              node={child}
              activeFile={activeFile}
              onSelectFile={onSelectFile}
              expandedPaths={expandedPaths}
              onToggle={onToggle}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface VirtualizedTreeListProps {
  rows: FlatTreeRow[];
  activeFile: string;
  onSelectFile: (path: string) => void;
  expandedPaths: Set<string>;
  onToggle: (path: string) => void;
  scrollElementRef: React.RefObject<HTMLElement | null>;
}

/**
 * Windowed rendering of the already-flattened visible row list, for trees
 * large enough that mounting every row would be expensive. Only the rows
 * currently in (or near) the scroll viewport are actually in the DOM.
 */
export function VirtualizedTreeList({
  rows,
  activeFile,
  onSelectFile,
  expandedPaths,
  onToggle,
  scrollElementRef,
}: VirtualizedTreeListProps) {
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollElementRef.current,
    estimateSize: () => 26,
    overscan: 12,
  });

  const virtualItems = virtualizer.getVirtualItems();

  return (
    <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
      {virtualItems.map((virtualRow) => {
        const row = rows[virtualRow.index];
        if (!row) return null;
        const { node, depth } = row;
        return (
          <div
            key={`${node.path || ""}-${node.name}-${virtualRow.index}`}
            ref={virtualizer.measureElement}
            data-index={virtualRow.index}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <TreeRowContent
              node={node}
              depth={depth}
              isOpen={expandedPaths.has(node.path)}
              isActive={activeFile === node.path}
              onToggle={onToggle}
              onSelectFile={onSelectFile}
            />
          </div>
        );
      })}
    </div>
  );
}

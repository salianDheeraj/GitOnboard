"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  FilePlus,
  FolderPlus,
  RotateCcw,
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
  Code2,
  Box,
  Layers,
  RefreshCw,
  Settings,
  Globe,
  Palette,
  Database,
  Terminal,
} from "lucide-react";
import { RunState } from "@/types/workspace";
import {
  FileTreeNode,
  SymbolItem,
  getRepositoryStructure,
  getFileSymbols,
} from "@/services/repositoryApi";
import { sanitizeFileTree, toggleExpandedPath, mergeAncestorPaths } from "@/utils/fileTree";

interface FileExplorerPanelProps {
  activeFile: string;
  onSelectFile: (filePath: string) => void;
  isOpen: boolean;
  onClose: () => void;
  runState?: RunState;
  width?: number;
}

/**
 * Returns a file-type specific icon based on extension.
 */
function renderFileIcon(fileName: string) {
  const lower = fileName.toLowerCase();

  // Python
  if (lower.endsWith(".py") || lower.endsWith(".pyw") || lower.endsWith(".ipynb")) {
    return <FileCode className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />;
  }
  // TypeScript
  if (lower.endsWith(".tsx") || lower.endsWith(".ts") || lower.endsWith(".mts")) {
    return <FileCode className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />;
  }
  // JavaScript
  if (lower.endsWith(".jsx") || lower.endsWith(".js") || lower.endsWith(".mjs") || lower.endsWith(".cjs")) {
    return <FileCode className="w-3.5 h-3.5 text-amber-300 flex-shrink-0" />;
  }
  // JSON / Data
  if (lower.endsWith(".json") || lower.endsWith(".jsonc")) {
    return <FileJson className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />;
  }
  // Markdown / Docs / Text
  if (lower.endsWith(".md") || lower.endsWith(".mdx") || lower.endsWith(".txt") || lower.endsWith(".rst")) {
    return <FileText className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" />;
  }
  // Config / TOML / YAML / INI
  if (lower.endsWith(".toml") || lower.endsWith(".yaml") || lower.endsWith(".yml") || lower.endsWith(".ini") || lower.endsWith(".cfg")) {
    return <Settings className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />;
  }
  // Web / HTML / SVG
  if (lower.endsWith(".html") || lower.endsWith(".htm") || lower.endsWith(".svg")) {
    return <Globe className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />;
  }
  // Styles / CSS / SCSS
  if (lower.endsWith(".css") || lower.endsWith(".scss") || lower.endsWith(".sass") || lower.endsWith(".less")) {
    return <Palette className="w-3.5 h-3.5 text-pink-400 flex-shrink-0" />;
  }
  // Database / SQL
  if (lower.endsWith(".sql") || lower.endsWith(".db") || lower.endsWith(".sqlite")) {
    return <Database className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />;
  }
  // Shell / Script
  if (lower.endsWith(".sh") || lower.endsWith(".bash") || lower.endsWith(".zsh") || lower.endsWith(".ps1") || lower.endsWith(".bat")) {
    return <Terminal className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />;
  }
  // Git / Env / Security
  if (lower.startsWith(".env")) {
    return <Lock className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />;
  }
  if (lower.startsWith(".git") || lower.endsWith(".lock")) {
    return <GitBranch className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />;
  }

  // Generic Document
  return <File className="w-3.5 h-3.5 text-[#8B949E] flex-shrink-0" />;
}

// Recursive Tree Node Component
function TreeNode({
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

  if (isDirectory) {
    return (
      <div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggle(node.path);
          }}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          className="w-full py-1 px-1.5 flex items-center gap-1.5 hover:bg-[#1E222A] text-[#E6EDF3] transition-colors text-[11px] font-medium select-none group"
        >
          <span className="w-3.5 h-3.5 flex items-center justify-center text-[#8B949E] group-hover:text-[#E6EDF3]">
            {isOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </span>
          {isOpen ? (
            <FolderOpen className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
          ) : (
            <Folder className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
          )}
          <span className="truncate">{node.name}</span>
        </button>

        {isOpen && node.children && (
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

  // File Node (No chevron, clicking opens in editor)
  const isActive = activeFile === node.path;
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onSelectFile(node.path);
      }}
      style={{ paddingLeft: `${depth * 12 + 22}px` }}
      className={`w-full py-1 px-1.5 flex items-center gap-2 transition-colors text-[11px] font-mono select-none ${
        isActive
          ? "bg-purple-600/25 text-purple-200 font-semibold border-l-2 border-purple-400 shadow-sm"
          : "hover:bg-[#1E222A] text-[#8B949E] hover:text-[#E6EDF3]"
      }`}
      title={node.path || node.name}
    >
      {renderFileIcon(node.name)}
      <span className="truncate">{node.name}</span>
    </button>
  );
}

export function FileExplorerPanel({
  activeFile,
  onSelectFile,
  isOpen,
  onClose,
  runState,
  width = 240,
}: FileExplorerPanelProps) {
  const repoName = runState?.repoId || "my-project";

  const [treeHierarchy, setTreeHierarchy] = useState<FileTreeNode | null>(null);
  const [symbols, setSymbols] = useState<SymbolItem[]>([]);
  const [loadingStructure, setLoadingStructure] = useState(true);
  const [isOutlineExpanded, setIsOutlineExpanded] = useState(true);

  // Which directory paths are expanded in the tree ("" = the repository root,
  // which starts open so top-level folders/files are visible). This is the
  // single source of truth for expansion — selecting a file never touches it,
  // except to reveal the ancestors of a file selected from outside the tree
  // (see the effect below).
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set([""]));

  // Tracks whether the in-flight activeFile change was triggered by a click
  // inside this tree (in which case expansion must be left alone) versus an
  // external caller like search/AI navigation (which may need ancestors revealed).
  const internalSelectionRef = useRef(false);

  const toggleExpand = useCallback((path: string) => {
    setExpandedPaths((prev) => toggleExpandedPath(prev, path));
  }, []);

  const handleTreeSelectFile = useCallback(
    (path: string) => {
      internalSelectionRef.current = true;
      onSelectFile(path);
    },
    [onSelectFile]
  );

  // Reveal only the ancestors of a file selected from outside the explorer
  // (e.g. search/symbol/AI navigation). Clicks originating in the tree itself
  // are flagged via internalSelectionRef and skip this entirely.
  useEffect(() => {
    if (!activeFile) return;
    if (internalSelectionRef.current) {
      internalSelectionRef.current = false;
      return;
    }
    setExpandedPaths((prev) => mergeAncestorPaths(prev, activeFile));
  }, [activeFile]);

  // Fetch real directory structure on mount or repo change. Selecting a file
  // must NOT re-trigger this — it previously depended on `activeFile`, which
  // forced a refetch (and the loading-state remount below) on every click,
  // wiping out expansion state.
  useEffect(() => {
    let isMounted = true;
    setLoadingStructure(true);
    setTreeHierarchy(null);
    setExpandedPaths(new Set([""]));

    getRepositoryStructure(repoName)
      .then((tree) => {
        if (isMounted) {
          setTreeHierarchy(sanitizeFileTree(tree));
          setLoadingStructure(false);
        }
      })
      .catch(() => {
        if (isMounted) setLoadingStructure(false);
      });

    return () => {
      isMounted = false;
    };
  }, [repoName]);

  // Fetch real AST symbols for active file
  useEffect(() => {
    if (!activeFile) {
      setSymbols([]);
      return;
    }

    let isMounted = true;
    getFileSymbols(repoName, activeFile).then((data) => {
      if (isMounted) {
        setSymbols(data);
      }
    });

    return () => {
      isMounted = false;
    };
  }, [repoName, activeFile]);

  if (!isOpen) return null;

  return (
    <div
      style={{ width: `${width}px` }}
      className="bg-[#14181E] border-r border-[#2F343A] flex flex-col h-full select-none flex-shrink-0 text-[#E6EDF3]"
    >
      {/* Top Header */}
      <div className="h-9 px-3 border-b border-[#2F343A] flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-[#8B949E] flex-shrink-0">
        <div className="flex items-center gap-1.5">
          <Folder className="w-3.5 h-3.5 text-purple-400" />
          <span className="truncate">{repoName}</span>
        </div>
        <div className="flex items-center gap-1 text-[#8B949E]">
          <button
            onClick={() => {
              setLoadingStructure(true);
              getRepositoryStructure(repoName).then((t) => {
                setTreeHierarchy(sanitizeFileTree(t));
                setLoadingStructure(false);
              });
            }}
            className="hover:text-[#E6EDF3] transition-colors p-0.5 rounded"
            title="Refresh Structure"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Recursive File Tree Area */}
      <div className="flex-1 overflow-y-auto py-1 text-xs scrollbar-thin">
        {loadingStructure ? (
          <div className="p-3 text-xs text-[#8B949E] font-mono flex items-center gap-2">
            <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-400" />
            <span>Loading tree...</span>
          </div>
        ) : treeHierarchy ? (
          <TreeNode
            node={treeHierarchy}
            activeFile={activeFile}
            onSelectFile={handleTreeSelectFile}
            expandedPaths={expandedPaths}
            onToggle={toggleExpand}
          />
        ) : (
          <div className="p-3 text-xs text-[#8B949E] italic">No directory structure found.</div>
        )}
      </div>

      {/* Real AST Symbols / OUTLINE Panel */}
      <div className="border-t border-[#2F343A] text-xs flex-shrink-0">
        <button
          onClick={() => setIsOutlineExpanded(!isOutlineExpanded)}
          className="w-full px-3 py-1.5 flex items-center justify-between hover:bg-[#1E222A] font-semibold text-[#8B949E] transition-colors"
        >
          <span className="flex items-center gap-1.5 uppercase tracking-wider text-[10px]">
            <Code2 className="w-3.5 h-3.5 text-purple-400" />
            OUTLINE / SYMBOLS ({symbols.length})
          </span>
          {isOutlineExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>

        {isOutlineExpanded && (
          <div className="px-2 py-1 text-[11px] font-mono text-[#8B949E] bg-[#0A0D10]/80 border-t border-[#2F343A]/50 max-h-40 overflow-y-auto space-y-1 scrollbar-thin">
            {symbols.length > 0 ? (
              symbols.map((sym, idx) => (
                <div key={idx} className="flex items-center gap-1.5 py-0.5 px-1 hover:bg-[#1E222A] rounded cursor-pointer">
                  {sym.type === "class" ? (
                    <Box className="w-3 h-3 text-amber-400 flex-shrink-0" />
                  ) : sym.type === "import" ? (
                    <Layers className="w-3 h-3 text-sky-400 flex-shrink-0" />
                  ) : (
                    <Code2 className="w-3 h-3 text-purple-400 flex-shrink-0" />
                  )}
                  <span className="text-[#E6EDF3] truncate">{sym.name}</span>
                  {sym.line_number && <span className="text-[9px] text-[#8B949E] ml-auto">:{sym.line_number}</span>}
                </div>
              ))
            ) : (
              <div className="italic text-[10px] text-[#8B949E] p-1">No symbols extracted for active file.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

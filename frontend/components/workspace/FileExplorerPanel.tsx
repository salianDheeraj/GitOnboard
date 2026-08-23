"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Folder,
  Code2,
  Box,
  Layers,
  RefreshCw,
} from "lucide-react";
import { RunState } from "@/types/workspace";
import {
  FileTreeNode,
  SymbolItem,
  getRepositoryStructure,
  getFileSymbols,
} from "@/services/repositoryApi";
import { sanitizeFileTree, toggleExpandedPath, mergeAncestorPaths, flattenVisibleTree } from "@/utils/fileTree";
import { TreeNode, VirtualizedTreeList } from "./FileTree";
import { Button } from "@/components/common/Button";

// Above this many currently-visible rows, switch from a plain recursive
// render to a windowed one — mounting a few thousand DOM nodes for a large,
// fully-expanded monorepo tree is the actual cost, not the tree itself.
const VIRTUALIZATION_THRESHOLD = 300;

interface FileExplorerPanelProps {
  activeFile: string;
  onSelectFile: (filePath: string) => void;
  isOpen: boolean;
  onClose: () => void;
  runState?: RunState;
  width?: number;
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

  const treeScrollRef = useRef<HTMLDivElement | null>(null);

  const flatRows = useMemo(
    () => (treeHierarchy ? flattenVisibleTree(treeHierarchy, expandedPaths) : []),
    [treeHierarchy, expandedPaths]
  );
  const shouldVirtualize = flatRows.length > VIRTUALIZATION_THRESHOLD;

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
      className="bg-workspace-surface border-r border-workspace-border flex flex-col h-full select-none flex-shrink-0 text-workspace-text"
    >
      {/* Top Header */}
      <div className="h-9 px-3 border-b border-workspace-border flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-workspace-text-muted flex-shrink-0">
        <div className="flex items-center gap-1.5">
          <Folder className="w-4 h-4 text-workspace-accent" />
          <span className="truncate">{repoName}</span>
        </div>
        <div className="flex items-center gap-1 text-workspace-text-muted">
          <Button
            variant="ghost"
            size="icon"
            className="!p-1"
            onClick={() => {
              setLoadingStructure(true);
              getRepositoryStructure(repoName).then((t) => {
                setTreeHierarchy(sanitizeFileTree(t));
                setLoadingStructure(false);
              });
            }}
            title="Refresh Structure"
            aria-label="Refresh Structure"
          >
            <RotateCcw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Main File Tree Area — recursive for small trees, windowed above
          VIRTUALIZATION_THRESHOLD visible rows */}
      <div ref={treeScrollRef} className="flex-1 overflow-y-auto py-1 text-xs scrollbar-thin">
        {loadingStructure ? (
          <div className="p-3 text-xs text-workspace-text-muted font-mono flex items-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-workspace-accent" />
            <span>Loading tree...</span>
          </div>
        ) : treeHierarchy ? (
          shouldVirtualize ? (
            <VirtualizedTreeList
              rows={flatRows}
              activeFile={activeFile}
              onSelectFile={handleTreeSelectFile}
              expandedPaths={expandedPaths}
              onToggle={toggleExpand}
              scrollElementRef={treeScrollRef}
            />
          ) : (
            <TreeNode
              node={treeHierarchy}
              activeFile={activeFile}
              onSelectFile={handleTreeSelectFile}
              expandedPaths={expandedPaths}
              onToggle={toggleExpand}
            />
          )
        ) : (
          <div className="p-3 text-xs text-workspace-text-muted italic">No directory structure found.</div>
        )}
      </div>

      {/* Real AST Symbols / OUTLINE Panel */}
      <div className="border-t border-workspace-border text-xs flex-shrink-0">
        <Button
          variant="ghost"
          onClick={() => setIsOutlineExpanded(!isOutlineExpanded)}
          className="!w-full !justify-between !rounded-none px-3 py-1.5 font-semibold text-workspace-text-muted"
          icon={<Code2 className="w-4 h-4 text-workspace-accent" />}
          iconRight={isOutlineExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        >
          <span className="uppercase tracking-wider text-[10px]">OUTLINE / SYMBOLS ({symbols.length})</span>
        </Button>

        {isOutlineExpanded && (
          <div className="px-2 py-1 text-[11px] font-mono text-workspace-text-muted bg-workspace-bg/80 border-t border-workspace-border/50 max-h-40 overflow-y-auto space-y-1 scrollbar-thin">
            {symbols.length > 0 ? (
              symbols.map((sym, idx) => (
                <div key={idx} className="flex items-center gap-1.5 py-0.5 px-1 hover:bg-workspace-surface-raised rounded cursor-pointer">
                  {sym.type === "class" ? (
                    <Box className="w-3 h-3 text-amber-400 flex-shrink-0" />
                  ) : sym.type === "import" ? (
                    <Layers className="w-3 h-3 text-sky-400 flex-shrink-0" />
                  ) : (
                    <Code2 className="w-3 h-3 text-workspace-accent flex-shrink-0" />
                  )}
                  <span className="text-workspace-text truncate">{sym.name}</span>
                  {sym.line_number && <span className="text-[9px] text-workspace-text-muted ml-auto">:{sym.line_number}</span>}
                </div>
              ))
            ) : (
              <div className="italic text-[10px] text-workspace-text-muted p-1">No symbols extracted for active file.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

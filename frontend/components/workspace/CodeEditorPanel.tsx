"use client";

import React, { useState, useEffect, useRef } from "react";
import Editor, { DiffEditor, OnMount, loader } from "@monaco-editor/react";
import {
  FileCode,
  X,
  ChevronRight,
  Code2,
  FileDiff,
  AlertTriangle,
  Save,
  RefreshCw,
  Check,
} from "lucide-react";
import { RunState } from "@/types/workspace";
import { getFileContent, saveFileContent } from "@/services/repositoryApi";
import { Button } from "@/components/common/Button";

interface CodeEditorPanelProps {
  activeFile: string;
  onSelectFile: (filePath: string) => void;
  openTabs: string[];
  onCloseTab: (filePath: string) => void;
  runState?: RunState;
  editorMode?: "source" | "diff";
  onSetEditorMode?: (mode: "source" | "diff") => void;
}

export function CodeEditorPanel({
  activeFile,
  onSelectFile,
  openTabs,
  onCloseTab,
  runState,
  editorMode: externalEditorMode,
  onSetEditorMode,
}: CodeEditorPanelProps) {
  const repoName = runState?.repoId || "my-project";

  const [internalEditorMode, setInternalEditorMode] = useState<"source" | "diff">("source");
  const editorMode = externalEditorMode || internalEditorMode;

  const setEditorMode = (mode: "source" | "diff") => {
    setInternalEditorMode(mode);
    if (onSetEditorMode) onSetEditorMode(mode);
  };

  const [fileContent, setFileContent] = useState<string>("");
  const [loadingFile, setLoadingFile] = useState<boolean>(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  const editorRef = useRef<any>(null);

  // Auto-detect language for Monaco
  const getLanguage = (path: string) => {
    if (!path) return "plaintext";
    const lower = path.toLowerCase();
    if (lower.endsWith(".tsx") || lower.endsWith(".ts")) return "typescript";
    if (lower.endsWith(".jsx") || lower.endsWith(".js")) return "javascript";
    if (lower.endsWith(".py")) return "python";
    if (lower.endsWith(".json")) return "json";
    if (lower.endsWith(".css")) return "css";
    if (lower.endsWith(".html")) return "html";
    if (lower.endsWith(".md")) return "markdown";
    if (lower.endsWith(".toml") || lower.endsWith(".yaml") || lower.endsWith(".yml")) return "yaml";
    return "plaintext";
  };

  const getFileBasename = (path: string) => {
    if (!path) return "";
    const parts = path.split("/");
    return parts[parts.length - 1];
  };

  // Fetch file content with race condition cancellation guard
  const fetchActiveFile = () => {
    if (!activeFile) {
      setFileContent("");
      setLoadingFile(false);
      setFileError(null);
      return;
    }

    if (activeFile === "implementation_plan.md" || activeFile.endsWith("plan.md")) {
      const planMarkdown = localStorage.getItem("gitonboard_active_plan_markdown") || "# Implementation Plan\n\nPlan is being synthesized...";
      setFileContent(planMarkdown);
      setLoadingFile(false);
      setFileError(null);
      return;
    }

    setLoadingFile(true);
    setFileError(null);
    setSaveSuccess(false);

    getFileContent(repoName, activeFile)
      .then((res) => {
        setFileContent(res.content || "");
        setLoadingFile(false);
      })
      .catch((err: any) => {
        setFileContent("");
        setFileError(err?.message || "Failed to load file content from storage");
        setLoadingFile(false);
      });
  };

  useEffect(() => {
    if (!activeFile) {
      setFileContent("");
      setLoadingFile(false);
      setFileError(null);
      return;
    }

    if (activeFile === "implementation_plan.md" || activeFile.endsWith("plan.md")) {
      const planMarkdown = localStorage.getItem("gitonboard_active_plan_markdown") || "# Implementation Plan\n\nPlan is being synthesized...";
      setFileContent(planMarkdown);
      setLoadingFile(false);
      setFileError(null);
      return;
    }

    let isCurrent = true;
    setLoadingFile(true);
    setFileError(null);
    setSaveSuccess(false);

    getFileContent(repoName, activeFile)
      .then((res) => {
        if (!isCurrent) return;
        setFileContent(res.content || "");
        setLoadingFile(false);
      })
      .catch((err: any) => {
        if (!isCurrent) return;
        setFileContent("");
        setFileError(err?.message || "Failed to load file content from storage");
        setLoadingFile(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [repoName, activeFile]);

  // Handle Save Action (Ctrl+S or Save Button)
  const handleSave = async () => {
    if (!activeFile || isSaving || fileError) return;

    const currentCode = editorRef.current ? editorRef.current.getValue() : fileContent;
    setIsSaving(true);

    const success = await saveFileContent(repoName, activeFile, currentCode);
    setIsSaving(false);

    if (success) {
      setFileContent(currentCode);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    }
  };

  // Set Monaco markers for defects
  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    // Save shortcut listener
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      handleSave();
    });

    const defects = runState?.report?.defects || [];
    if (!defects.length) return;

    const markers = defects
      .filter((d) => !d.file_path || d.file_path.includes(getFileBasename(activeFile)))
      .map((d) => ({
        startLineNumber: d.line_number || 1,
        startColumn: 1,
        endLineNumber: (d.line_number || 1) + 1,
        endColumn: 100,
        message: `[${d.category}] ${d.description}`,
        severity:
          d.severity === "CRITICAL" || d.severity === "HIGH"
            ? monaco.MarkerSeverity.Error
            : monaco.MarkerSeverity.Warning,
      }));

    if (markers.length) {
      const model = editor.getModel();
      if (model) {
        monaco.editor.setModelMarkers(model, "gitonboard_verifier", markers);
      }
    }
  };

  const patchedCode = runState?.rawDiff || fileContent;

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-workspace-bg text-workspace-text border-b border-workspace-border">
      {/* Top Control Bar */}
      <div className="h-9 bg-workspace-surface border-b border-workspace-border flex items-center justify-between px-2 select-none flex-shrink-0">
        {/* Open Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none max-w-[65%]">
          {openTabs.length > 0 ? (
            openTabs.map((tabPath) => {
              const isActive = tabPath === activeFile;
              const basename = getFileBasename(tabPath);
              return (
                <div
                  key={tabPath}
                  onClick={() => onSelectFile(tabPath)}
                  className={`h-7 px-2.5 rounded-t flex items-center gap-2 text-xs font-mono border-t border-x cursor-pointer transition-colors ${
                    isActive
                      ? "bg-workspace-bg border-workspace-border text-workspace-accent font-medium"
                      : "bg-workspace-surface border-transparent text-workspace-text-muted hover:text-workspace-text hover:bg-workspace-surface-raised"
                  }`}
                >
                  <FileCode className="w-4 h-4 text-workspace-accent" />
                  <span>{basename}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onCloseTab(tabPath);
                    }}
                    className="hover:text-white p-0.5 rounded text-workspace-text-muted"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              );
            })
          ) : (
            <div className="text-[11px] text-workspace-text-muted italic px-2">No files open</div>
          )}
        </div>

        {/* Right Actions: Save Button & Mode Switcher */}
        <div className="flex items-center gap-2">
          {/* Save Button */}
          <Button
            variant={saveSuccess ? "primary" : "soft"}
            size="sm"
            onClick={handleSave}
            disabled={!activeFile || isSaving || Boolean(fileError)}
            className={saveSuccess ? "!bg-emerald-950 !text-emerald-300 !border !border-emerald-500/40" : ""}
            icon={
              isSaving ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : saveSuccess ? (
                <Check className="w-3 h-3 text-emerald-400" />
              ) : (
                <Save className="w-3 h-3" />
              )
            }
            title="Save File (Ctrl+S)"
          >
            {saveSuccess ? "Saved" : "Save"}
          </Button>

          {/* Mode Switcher: [ Source Code ] vs [ Agent Diff ] */}
          <div className="flex items-center gap-1 bg-workspace-bg border border-workspace-border p-0.5 rounded-lg text-xs font-mono">
            <button
              onClick={() => setEditorMode("source")}
              className={`px-2 py-0.5 rounded flex items-center gap-1 transition-all ${
                editorMode === "source"
                  ? "bg-workspace-accent/30 text-workspace-accent font-semibold border border-workspace-accent/40 shadow-sm"
                  : "text-workspace-text-muted hover:text-workspace-text"
              }`}
            >
              <Code2 className="w-4 h-4" />
              <span>Source Code</span>
            </button>

            <button
              onClick={() => setEditorMode("diff")}
              className={`px-2 py-0.5 rounded flex items-center gap-1 transition-all ${
                editorMode === "diff"
                  ? "bg-workspace-accent/30 text-workspace-accent font-semibold border border-workspace-accent/40 shadow-sm"
                  : "text-workspace-text-muted hover:text-workspace-text"
              }`}
            >
              <FileDiff className="w-4 h-4" />
              <span>Agent Diff</span>
            </button>
          </div>
        </div>
      </div>

      {/* Breadcrumb Path Bar */}
      <div className="h-6 bg-workspace-bg border-b border-workspace-border/60 px-3 flex items-center gap-1 text-[11px] text-workspace-text-muted font-mono select-none flex-shrink-0">
        <span>{repoName}</span>
        <ChevronRight className="w-3 h-3 text-workspace-border" />
        {activeFile ? (
          <>
            <span>{activeFile.split("/").slice(0, -1).join("/") || "."}</span>
            <ChevronRight className="w-3 h-3 text-workspace-border" />
            <span className="text-workspace-accent font-semibold">{getFileBasename(activeFile)}</span>
          </>
        ) : (
          <span className="text-workspace-text-muted italic">(No active file)</span>
        )}

        {runState?.report?.defects && runState.report.defects.length > 0 && (
          <div className="ml-auto flex items-center gap-1 text-rose-400 bg-rose-950/40 px-2 py-0.5 rounded border border-rose-500/30">
            <AlertTriangle className="w-3 h-3" />
            <span>{runState.report.defects.length} defect(s) flagged</span>
          </div>
        )}
      </div>

      {/* Monaco Editor / Loading Skeleton / Empty State / Explicit Error Card */}
      <div className="flex-1 min-h-0 relative bg-workspace-bg">
        {!activeFile ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-workspace-bg text-workspace-text-muted text-xs font-mono p-6 select-none">
            <div className="w-12 h-12 rounded-xl bg-workspace-surface border border-workspace-border flex items-center justify-center mb-3 text-workspace-accent">
              <FileCode className="w-6 h-6" />
            </div>
            <div className="text-sm font-semibold text-workspace-text mb-1">No File Selected</div>
            <div className="text-xs text-workspace-text-muted max-w-sm text-center">
              Select a file from the repository explorer on the left or search symbols (⌘K) to open code in Monaco.
            </div>
          </div>
        ) : loadingFile ? (
          <div className="absolute inset-0 flex items-center justify-center bg-workspace-bg text-workspace-text-muted text-xs font-mono">
            <div className="flex items-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-workspace-accent" />
              <span>Loading {getFileBasename(activeFile)}...</span>
            </div>
          </div>
        ) : fileError ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-workspace-bg text-rose-300 text-xs font-mono p-6">
            <div className="w-12 h-12 rounded-xl bg-rose-950/30 border border-rose-500/40 flex items-center justify-center mb-3 text-rose-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div className="text-sm font-semibold text-rose-200 mb-1">Failed to Load File</div>
            <div className="text-xs text-rose-400/90 max-w-md text-center mb-4 bg-workspace-surface p-3 rounded border border-rose-500/30">
              {fileError}
            </div>
            <Button
              variant="soft"
              size="sm"
              onClick={fetchActiveFile}
              icon={<RefreshCw className="w-4 h-4" />}
            >
              Retry Load
            </Button>
          </div>
        ) : editorMode === "diff" ? (
          <DiffEditor
            height="100%"
            language={getLanguage(activeFile)}
            original={fileContent}
            modified={patchedCode}
            theme="vs-dark"
            options={{
              readOnly: true,
              renderSideBySide: true,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              fontSize: 13,
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              automaticLayout: true,
            }}
          />
        ) : (
          <Editor
            height="100%"
            language={getLanguage(activeFile)}
            value={fileContent}
            theme="vs-dark"
            onMount={handleEditorDidMount}
            options={{
              readOnly: false,
              minimap: { enabled: true },
              scrollBeyondLastLine: false,
              fontSize: 13,
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              automaticLayout: true,
              lineNumbers: "on",
              glyphMargin: true,
            }}
          />
        )}
      </div>
    </div>
  );
}

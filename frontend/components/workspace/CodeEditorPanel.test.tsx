import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@monaco-editor/react", () => ({
  __esModule: true,
  default: ({ value }: { value?: string }) => <div data-testid="monaco-editor">{value}</div>,
  DiffEditor: ({ original }: { original?: string }) => <div data-testid="monaco-diff-editor">{original}</div>,
  loader: { config: vi.fn() },
}));

vi.mock("@/services/repositoryApi", () => ({
  getFileContent: vi.fn(),
  saveFileContent: vi.fn(),
}));

import { getFileContent } from "@/services/repositoryApi";
import { CodeEditorPanel } from "./CodeEditorPanel";
import type { RunState } from "@/types/workspace";

function makeRunState(repoId: string): RunState {
  return {
    runId: null,
    repoId,
    branch: "main",
    taskPrompt: "",
    contract: null,
    rawDiff: "",
    report: null,
    iteration: 0,
    isLoading: false,
    statusMessage: "",
  };
}

beforeEach(() => {
  vi.mocked(getFileContent).mockResolvedValue({ content: "hello world" });
});

describe("CodeEditorPanel", () => {
  it("shows the empty state and fetches nothing when no file is active", async () => {
    render(
      <CodeEditorPanel
        activeFile=""
        onSelectFile={() => {}}
        openTabs={[]}
        onCloseTab={() => {}}
        runState={makeRunState("repo-a")}
      />
    );

    expect(await screen.findByText("No File Selected")).toBeInTheDocument();
    expect(getFileContent).not.toHaveBeenCalled();
    expect(screen.queryByTestId("monaco-editor")).not.toBeInTheDocument();
  });

  it("loads and displays the selected file's content", async () => {
    render(
      <CodeEditorPanel
        activeFile="alpha/nested.ts"
        onSelectFile={() => {}}
        openTabs={["alpha/nested.ts"]}
        onCloseTab={() => {}}
        runState={makeRunState("repo-a")}
      />
    );

    await waitFor(() => expect(getFileContent).toHaveBeenCalledWith("repo-a", "alpha/nested.ts"));
    expect(await screen.findByTestId("monaco-editor")).toHaveTextContent("hello world");
    expect(screen.queryByText("No File Selected")).not.toBeInTheDocument();
  });

  it("does not resurrect a closed file when its in-flight load resolves late", async () => {
    let resolveLoad: (res: { content: string }) => void;
    vi.mocked(getFileContent).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveLoad = resolve;
      })
    );

    const { rerender } = render(
      <CodeEditorPanel
        activeFile="A.py"
        onSelectFile={() => {}}
        openTabs={["A.py"]}
        onCloseTab={() => {}}
        runState={makeRunState("repo-a")}
      />
    );

    await waitFor(() => expect(getFileContent).toHaveBeenCalledWith("repo-a", "A.py"));

    // Simulate the tab being closed before the request resolves: activeFile
    // clears and A.py leaves openTabs.
    rerender(
      <CodeEditorPanel
        activeFile=""
        onSelectFile={() => {}}
        openTabs={[]}
        onCloseTab={() => {}}
        runState={makeRunState("repo-a")}
      />
    );

    expect(await screen.findByText("No File Selected")).toBeInTheDocument();

    // Now let the stale request resolve — it must not repopulate the editor.
    resolveLoad!({ content: "hello world" });
    await Promise.resolve();
    await Promise.resolve();

    expect(screen.queryByTestId("monaco-editor")).not.toBeInTheDocument();
    expect(screen.getByText("No File Selected")).toBeInTheDocument();
  });
});

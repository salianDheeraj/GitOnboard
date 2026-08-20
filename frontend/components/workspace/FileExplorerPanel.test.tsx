import React, { useState } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { FileTreeNode } from "@/services/repositoryApi";
import type { RunState } from "@/types/workspace";

vi.mock("@/services/repositoryApi", () => ({
  getRepositoryStructure: vi.fn(),
  getFileSymbols: vi.fn().mockResolvedValue([]),
}));

import { getRepositoryStructure } from "@/services/repositoryApi";
import { FileExplorerPanel } from "./FileExplorerPanel";

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

// Generic fixture tree — deliberately uses no real-world repo/file names so the
// behavior under test can't accidentally depend on a specific project.
function makeFixtureTree(repoId: string): FileTreeNode {
  return {
    name: repoId,
    type: "directory",
    path: "",
    children: [
      {
        name: "alpha",
        type: "directory",
        path: "alpha",
        children: [{ name: "nested.ts", type: "file", path: "alpha/nested.ts" }],
      },
      {
        name: "beta",
        type: "directory",
        path: "beta",
        children: [{ name: "inner.ts", type: "file", path: "beta/inner.ts" }],
      },
      { name: "root-file.txt", type: "file", path: "root-file.txt" },
    ],
  };
}

// Test harness mirroring how the real app wires activeFile: the explorer's
// onSelectFile prop updates local state, and a separate "external" trigger
// simulates a file being opened from outside the tree (search/AI navigation)
// by calling the same onSelectFile prop directly.
function Harness({ initialActiveFile = "", repoId = "repo-a" }: { initialActiveFile?: string; repoId?: string }) {
  const [activeFile, setActiveFile] = useState(initialActiveFile);
  return (
    <div>
      <FileExplorerPanel
        activeFile={activeFile}
        onSelectFile={setActiveFile}
        isOpen={true}
        onClose={() => {}}
        runState={makeRunState(repoId)}
      />
      <button onClick={() => setActiveFile("beta/inner.ts")}>external-select-beta-inner</button>
      <div data-testid="active-file-probe">{activeFile}</div>
    </div>
  );
}

beforeEach(() => {
  vi.mocked(getRepositoryStructure).mockImplementation(async (repoId: string) => makeFixtureTree(repoId));
});

describe("FileExplorerPanel", () => {
  it("does not auto-select any file on load", async () => {
    const onSelectFile = vi.fn();
    render(
      <FileExplorerPanel
        activeFile=""
        onSelectFile={onSelectFile}
        isOpen={true}
        onClose={() => {}}
        runState={makeRunState("repo-a")}
      />
    );

    await screen.findByText("root-file.txt");
    expect(onSelectFile).not.toHaveBeenCalled();
  });

  it("renders folders collapsed by default", async () => {
    render(<Harness />);

    await screen.findByText("alpha");
    expect(screen.getByText("beta")).toBeInTheDocument();
    // Root-level file is visible, but nested files inside collapsed folders are not.
    expect(screen.getByText("root-file.txt")).toBeInTheDocument();
    expect(screen.queryByText("nested.ts")).not.toBeInTheDocument();
    expect(screen.queryByText("inner.ts")).not.toBeInTheDocument();
  });

  it("expanding one folder does not expand its sibling", async () => {
    render(<Harness />);
    await screen.findByText("alpha");

    fireEvent.click(screen.getByText("alpha"));

    expect(await screen.findByText("nested.ts")).toBeInTheDocument();
    expect(screen.queryByText("inner.ts")).not.toBeInTheDocument();
  });

  it("clicking a root-level file opens it without expanding any folder", async () => {
    render(<Harness />);
    await screen.findByText("root-file.txt");

    fireEvent.click(screen.getByText("root-file.txt"));

    await waitFor(() => expect(screen.getByTestId("active-file-probe")).toHaveTextContent("root-file.txt"));
    expect(screen.queryByText("nested.ts")).not.toBeInTheDocument();
    expect(screen.queryByText("inner.ts")).not.toBeInTheDocument();
  });

  it("selecting a file inside an expanded folder preserves existing expansion state", async () => {
    render(<Harness />);
    await screen.findByText("alpha");

    fireEvent.click(screen.getByText("alpha"));
    const nested = await screen.findByText("nested.ts");
    fireEvent.click(nested);

    await waitFor(() => expect(screen.getByTestId("active-file-probe")).toHaveTextContent("alpha/nested.ts"));
    // alpha remains expanded (its child is still rendered) and beta remains collapsed.
    expect(screen.getByText("nested.ts")).toBeInTheDocument();
    expect(screen.queryByText("inner.ts")).not.toBeInTheDocument();
  });

  it("collapsing a folder and then selecting a different root file keeps it collapsed", async () => {
    render(<Harness />);
    await screen.findByText("alpha");

    fireEvent.click(screen.getByText("alpha")); // expand
    await screen.findByText("nested.ts");
    fireEvent.click(screen.getByText("alpha")); // collapse again
    await waitFor(() => expect(screen.queryByText("nested.ts")).not.toBeInTheDocument());

    fireEvent.click(screen.getByText("root-file.txt"));

    await waitFor(() => expect(screen.getByTestId("active-file-probe")).toHaveTextContent("root-file.txt"));
    expect(screen.queryByText("nested.ts")).not.toBeInTheDocument();
  });

  it("opening a nested file from outside the tree expands only its ancestors", async () => {
    render(<Harness />);
    await screen.findByText("alpha");
    expect(screen.queryByText("inner.ts")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("external-select-beta-inner"));

    expect(await screen.findByText("inner.ts")).toBeInTheDocument();
    // alpha was never touched by this navigation, so it stays collapsed.
    expect(screen.queryByText("nested.ts")).not.toBeInTheDocument();
  });

  it("resets expansion state when switching repositories", async () => {
    const { rerender } = render(<Harness repoId="repo-a" />);
    await screen.findByText("alpha");

    fireEvent.click(screen.getByText("alpha"));
    await screen.findByText("nested.ts");

    rerender(<Harness repoId="repo-b" />);

    await waitFor(() => expect(getRepositoryStructure).toHaveBeenCalledWith("repo-b"));
    await screen.findByText("alpha");
    expect(screen.queryByText("nested.ts")).not.toBeInTheDocument();
  });
});

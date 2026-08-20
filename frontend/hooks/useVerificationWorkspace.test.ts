import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/services/verificationApi", () => ({
  submitPipelineTask: vi.fn(),
  executePipelineTask: vi.fn(),
  repairPipelineTask: vi.fn(),
}));

import { useVerificationWorkspace } from "./useVerificationWorkspace";

describe("useVerificationWorkspace tab/editor synchronization", () => {
  it("opens a file into tabs and makes it active", () => {
    const { result } = renderHook(() => useVerificationWorkspace("repo-a"));

    act(() => result.current.handleSelectFile("A.py"));

    expect(result.current.openTabs).toEqual(["A.py"]);
    expect(result.current.activeFile).toBe("A.py");
  });

  it("closing the only active tab clears the active file (no auto-reopen)", () => {
    const { result } = renderHook(() => useVerificationWorkspace("repo-a"));

    act(() => result.current.handleSelectFile("A.py"));
    act(() => result.current.handleCloseTab("A.py"));

    expect(result.current.openTabs).toEqual([]);
    expect(result.current.activeFile).toBe("");
  });

  it("closing the active tab among several activates a remaining tab, never the closed one", () => {
    const { result } = renderHook(() => useVerificationWorkspace("repo-a"));

    act(() => result.current.handleSelectFile("A.py"));
    act(() => result.current.handleSelectFile("B.py"));
    act(() => result.current.handleSelectFile("C.py"));
    // Active file is currently C.py; make B.py active instead.
    act(() => result.current.handleSelectFile("B.py"));

    act(() => result.current.handleCloseTab("B.py"));

    expect(result.current.openTabs).toEqual(["A.py", "C.py"]);
    expect(result.current.activeFile).not.toBe("B.py");
    expect(result.current.openTabs).toContain(result.current.activeFile);
  });

  it("closing a non-active tab leaves the active file untouched", () => {
    const { result } = renderHook(() => useVerificationWorkspace("repo-a"));

    act(() => result.current.handleSelectFile("A.py"));
    act(() => result.current.handleSelectFile("B.py"));
    act(() => result.current.handleSelectFile("C.py"));
    act(() => result.current.handleSelectFile("B.py"));

    act(() => result.current.handleCloseTab("A.py"));

    expect(result.current.openTabs).toEqual(["B.py", "C.py"]);
    expect(result.current.activeFile).toBe("B.py");
  });

  it("closing all tabs one by one ends with an empty, consistent state", () => {
    const { result } = renderHook(() => useVerificationWorkspace("repo-a"));

    act(() => result.current.handleSelectFile("A.py"));
    act(() => result.current.handleSelectFile("B.py"));

    act(() => result.current.handleCloseTab("A.py"));
    act(() => result.current.handleCloseTab("B.py"));

    expect(result.current.openTabs).toEqual([]);
    expect(result.current.activeFile).toBe("");
  });

  it("reopening a previously closed file works normally", () => {
    const { result } = renderHook(() => useVerificationWorkspace("repo-a"));

    act(() => result.current.handleSelectFile("A.py"));
    act(() => result.current.handleCloseTab("A.py"));
    act(() => result.current.handleSelectFile("A.py"));

    expect(result.current.openTabs).toEqual(["A.py"]);
    expect(result.current.activeFile).toBe("A.py");
  });

  it("switching repositories resets tabs and active file, without leaking state", () => {
    const { result, rerender } = renderHook(
      ({ repo }) => useVerificationWorkspace(repo),
      { initialProps: { repo: "repo-a" } }
    );

    act(() => result.current.handleSelectFile("A.py"));
    expect(result.current.activeFile).toBe("A.py");

    rerender({ repo: "repo-b" });

    expect(result.current.openTabs).toEqual([]);
    expect(result.current.activeFile).toBe("");
  });
});

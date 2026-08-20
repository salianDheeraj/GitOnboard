import { describe, expect, it } from "vitest";
import { getAncestorDirPaths, mergeAncestorPaths, sanitizeFileTree, toggleExpandedPath } from "./fileTree";

describe("getAncestorDirPaths", () => {
  it("returns only the root for a top-level file", () => {
    expect(getAncestorDirPaths("readme.md")).toEqual([""]);
  });

  it("returns every intermediate directory for a nested file", () => {
    expect(getAncestorDirPaths("alpha/beta/gamma/file.ts")).toEqual([
      "",
      "alpha",
      "alpha/beta",
      "alpha/beta/gamma",
    ]);
  });
});

describe("toggleExpandedPath", () => {
  it("adds a collapsed path without touching others", () => {
    const prev = new Set(["", "existing"]);
    const next = toggleExpandedPath(prev, "alpha");
    expect(next.has("alpha")).toBe(true);
    expect(next.has("existing")).toBe(true);
    expect(prev.has("alpha")).toBe(false); // original untouched
  });

  it("removes an already-expanded path without touching others", () => {
    const prev = new Set(["", "alpha", "beta"]);
    const next = toggleExpandedPath(prev, "alpha");
    expect(next.has("alpha")).toBe(false);
    expect(next.has("beta")).toBe(true);
  });
});

describe("mergeAncestorPaths", () => {
  it("returns the same reference when all ancestors are already expanded", () => {
    const prev = new Set(["", "alpha", "alpha/beta"]);
    const next = mergeAncestorPaths(prev, "alpha/beta/file.ts");
    expect(next).toBe(prev);
  });

  it("adds only the missing ancestors, leaving unrelated expanded paths intact", () => {
    const prev = new Set(["", "unrelated"]);
    const next = mergeAncestorPaths(prev, "alpha/beta/file.ts");
    expect(next.has("alpha")).toBe(true);
    expect(next.has("alpha/beta")).toBe(true);
    expect(next.has("unrelated")).toBe(true);
    expect(next.has("alpha/beta/file.ts")).toBe(false); // the file itself is not a directory path
  });
});

describe("sanitizeFileTree", () => {
  it("strips AST symbol children from files and sorts directories before files", () => {
    const raw = {
      name: "root",
      type: "directory" as const,
      path: "",
      children: [
        { name: "file.ts", type: "file" as const, path: "file.ts", children: [{ name: "SomeClass", type: "class" as const, path: "" }] },
        { name: "zzz", type: "directory" as const, path: "zzz", children: [] },
        { name: "aaa", type: "directory" as const, path: "aaa", children: [] },
      ],
    };

    const cleaned = sanitizeFileTree(raw);
    expect(cleaned.children?.map((c) => c.name)).toEqual(["aaa", "zzz", "file.ts"]);

    const file = cleaned.children?.find((c) => c.name === "file.ts");
    expect(file).toEqual({ name: "file.ts", type: "file", path: "file.ts" });
  });
});

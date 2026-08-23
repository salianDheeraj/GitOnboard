import type { FileTreeNode } from "@/services/repositoryApi";

/**
 * Sanitizes the raw tree hierarchy to strictly separate real filesystem directories
 * and files, removing any nested AST code structures (classes/functions) from the file tree.
 */
export function sanitizeFileTree(node: FileTreeNode): FileTreeNode {
  if (node.type === "directory") {
    const validChildren = (node.children || [])
      .filter((child) => child.type === "directory" || child.type === "file" || child.name.includes("."))
      .map((child) => {
        // If node is a file, strip any AST symbol children
        if (child.type === "file" || (!child.type && child.name.includes("."))) {
          return {
            name: child.name,
            type: "file" as const,
            path: child.path,
          };
        }
        return sanitizeFileTree(child);
      })
      .sort((a, b) => {
        const aIsDir = a.type === "directory";
        const bIsDir = b.type === "directory";
        if (aIsDir && !bIsDir) return -1;
        if (!aIsDir && bIsDir) return 1;
        return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
      });

    return {
      ...node,
      type: "directory",
      children: validChildren,
    };
  }

  return {
    name: node.name,
    type: "file",
    path: node.path,
  };
}

/**
 * Computes the set of ancestor directory paths (including the root "") that
 * must be expanded for `filePath` to be visible in the tree.
 */
export function getAncestorDirPaths(filePath: string): string[] {
  const parts = filePath.split("/").filter(Boolean);
  const ancestors: string[] = [""];
  let acc = "";
  for (let i = 0; i < parts.length - 1; i++) {
    acc = acc ? `${acc}/${parts[i]}` : parts[i];
    ancestors.push(acc);
  }
  return ancestors;
}

/**
 * Returns a new Set with `path` toggled in/out of `prev`. Used for manual
 * folder expand/collapse — touches only the one path, never siblings.
 */
export function toggleExpandedPath(prev: Set<string>, path: string): Set<string> {
  const next = new Set(prev);
  if (next.has(path)) {
    next.delete(path);
  } else {
    next.add(path);
  }
  return next;
}

/**
 * Merges the ancestor directories of `filePath` into `prev`, returning `prev`
 * unchanged (same reference) if every ancestor is already expanded. Used to
 * reveal a file selected from outside the tree (search, AI navigation, etc.)
 * without expanding anything unrelated.
 */
export function mergeAncestorPaths(prev: Set<string>, filePath: string): Set<string> {
  const ancestors = getAncestorDirPaths(filePath);
  let changed = false;
  const next = new Set(prev);
  for (const ancestor of ancestors) {
    if (!next.has(ancestor)) {
      next.add(ancestor);
      changed = true;
    }
  }
  return changed ? next : prev;
}

export interface FlatTreeRow {
  node: FileTreeNode;
  depth: number;
}

/**
 * Flattens the tree into the exact ordered list of rows that would be
 * visible given `expandedPaths`, in the same pre-order a recursive renderer
 * would produce. Used to feed a windowed/virtualized list — the API returns
 * the full hierarchy up front (no per-directory paging), so this walk (and
 * the DOM node count it drives) is the only lever the frontend has for
 * keeping large trees cheap to render.
 */
export function flattenVisibleTree(root: FileTreeNode, expandedPaths: Set<string>): FlatTreeRow[] {
  const rows: FlatTreeRow[] = [];

  const walk = (node: FileTreeNode, depth: number) => {
    rows.push({ node, depth });
    if (node.type === "directory" && expandedPaths.has(node.path) && node.children) {
      for (const child of node.children) {
        walk(child, depth + 1);
      }
    }
  };

  walk(root, 0);
  return rows;
}

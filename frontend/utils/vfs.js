/**
 * Virtual File System for parsing flat file paths into a hierarchical tree.
 */

export class VFSNode {
  constructor(path, name, type) {
    this.path = path;
    this.name = name;
    this.type = type; // 'folder' | 'file'
    this.children = new Map();
    this.originalNodeId = null; // Set if type === 'file'
    
    // Metrics for heuristics
    this.totalDescendants = 0;
    this.internalEdgesCount = 0;
  }
}

/**
 * Builds a VFS tree from a list of flat nodes.
 * @param {Array} rawNodes - [{ id, full_path, ... }]
 * @returns {VFSNode} The root node of the tree.
 */
export const buildVFS = (rawNodes) => {
  const root = new VFSNode('/', 'root', 'folder');

  for (const node of rawNodes) {
    // Some paths might be "src/flask/app.py", we normalize to array of parts
    const pathParts = node.full_path.replace(/\\/g, '/').split('/').filter(p => p.length > 0);
    
    let current = root;
    let currentPath = '';

    for (let i = 0; i < pathParts.length; i++) {
      const part = pathParts[i];
      const isFile = (i === pathParts.length - 1);
      
      currentPath = currentPath === '' ? part : `${currentPath}/${part}`;
      
      if (!current.children.has(part)) {
        const type = isFile ? 'file' : 'folder';
        const vfsNode = new VFSNode(currentPath, part, type);
        current.children.set(part, vfsNode);
      }
      
      current = current.children.get(part);
      
      if (isFile) {
        current.originalNodeId = node.id;
      }
    }
  }

  // Pre-compute descendants count
  const computeDescendants = (node) => {
    if (node.type === 'file') return 1;
    let sum = 0;
    for (const child of node.children.values()) {
      sum += computeDescendants(child);
    }
    node.totalDescendants = sum;
    return sum;
  };
  computeDescendants(root);

  return root;
};

/**
 * Maps raw node IDs to their VFS paths for easy edge resolution.
 */
export const buildNodePathMap = (rawNodes) => {
  const map = new Map();
  for (const node of rawNodes) {
    const path = node.full_path.replace(/\\/g, '/').split('/').filter(p => p.length > 0).join('/');
    map.set(node.id, path);
  }
  return map;
};

/**
 * Calculates internal edge counts for each folder to determine visual complexity.
 */
export const calculateVisualComplexity = (root, rawEdges, nodePathMap) => {
  // Reset edge counts
  const resetEdges = (node) => {
    node.internalEdgesCount = 0;
    for (const child of node.children.values()) {
      resetEdges(child);
    }
  };
  resetEdges(root);
  
  // A helper to find the VFS node for a path
  const findVFSNode = (pathStr) => {
    const parts = pathStr.split('/');
    let current = root;
    for (const part of parts) {
      if (current.children.has(part)) {
        current = current.children.get(part);
      } else {
        return null;
      }
    }
    return current;
  };

  for (const edge of rawEdges) {
    const sourcePath = nodePathMap.get(edge.source);
    const targetPath = nodePathMap.get(edge.target);
    if (!sourcePath || !targetPath) continue;

    // Find the Lowest Common Ancestor (LCA) folder that contains this edge.
    // E.g., if source is a/b/c.py and target is a/b/d.py, LCA is a/b
    const sourceParts = sourcePath.split('/');
    const targetParts = targetPath.split('/');
    
    let lcaPath = '';
    let current = root;
    
    for (let i = 0; i < Math.min(sourceParts.length, targetParts.length); i++) {
      if (sourceParts[i] === targetParts[i]) {
        if (lcaPath === '') lcaPath = sourceParts[i];
        else lcaPath += `/${sourceParts[i]}`;
        
        current = current.children.get(sourceParts[i]);
      } else {
        break;
      }
    }
    
    // The LCA folder is where this internal edge exists.
    // We increment internalEdgesCount for this LCA and all its parents up to root.
    let ancestor = current;
    // But wait, the complexity of a folder includes ALL edges fully contained within it.
    // So increment LCA and all ancestors.
    const lcaParts = lcaPath.split('/');
    let climbNode = root;
    climbNode.internalEdgesCount++; // root always contains it
    
    for (const part of lcaParts) {
      if (!part) break;
      climbNode = climbNode.children.get(part);
      if (climbNode) climbNode.internalEdgesCount++;
    }
  }
};

/**
 * Determines which folders should be auto-expanded based on complexity heuristic.
 */
export const getAutoExpandedPaths = (root) => {
  const expanded = new Set();
  
  // Complexity heuristic threshold
  const COMPLEXITY_THRESHOLD = 10;
  
  const walk = (node) => {
    if (node.type === 'file') return;
    
    const complexity = node.totalDescendants + (node.internalEdgesCount * 1.5);
    
    if (complexity <= COMPLEXITY_THRESHOLD) {
      // Auto expand this node and its children (if they are folders)
      expanded.add(node.path);
      for (const child of node.children.values()) {
        walk(child); // Keep checking children
      }
    } else {
      // It's too complex to expand completely, but we might want to expand the root if it's the only thing.
      // E.g., if root has 1 child folder, we should expand the root so it's not just a single dot.
      if (node.path === 'root' || node === root) {
         expanded.add(node.path);
         for (const child of node.children.values()) walk(child);
      }
    }
  };
  
  // Always expand the artificial root if there is one
  expanded.add('root');
  
  // If the true repository has a top level wrapper (e.g. 'src'), expand it.
  if (root.children.size === 1) {
    const singleChild = Array.from(root.children.values())[0];
    if (singleChild.type === 'folder') {
      expanded.add(singleChild.path);
    }
  }

  walk(root);
  
  return expanded;
};

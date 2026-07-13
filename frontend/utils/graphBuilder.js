/**
 * Builds the visible React Flow graph from the VFS tree and expansion state.
 */

/**
 * Finds the highest visible node for a given file path.
 */
const getVisibleNode = (root, pathStr, expandedPaths) => {
  const parts = pathStr.split('/');
  let current = root;
  let visibleNode = root; // Should not really stay root unless root is collapsed (which it never is)
  
  if (!expandedPaths.has('root')) return root;
  
  for (const part of parts) {
    if (!current.children.has(part)) break;
    
    current = current.children.get(part);
    visibleNode = current;
    
    // If we hit a folder that is NOT expanded, this is the highest visible node
    if (current.type === 'folder' && !expandedPaths.has(current.path)) {
      break;
    }
  }
  
  return visibleNode;
};

/**
 * Traverses the VFS to collect all currently visible nodes.
 */
const collectVisibleNodes = (root, expandedPaths) => {
  const visible = [];
  
  const walk = (node) => {
    // We only process children if this node is expanded
    if (expandedPaths.has(node.path) || (node === root && expandedPaths.has('root'))) {
      for (const child of node.children.values()) {
        // Child is always visible if parent is expanded
        visible.push(child);
        if (child.type === 'folder' && expandedPaths.has(child.path)) {
          walk(child); // recurse to add its children as well
        }
      }
    }
  };
  
  walk(root);
  return visible;
};

/**
 * Generates React Flow nodes and edges based on the VFS and expansion state.
 */
export const buildVisibleGraph = (root, rawNodes, rawEdges, nodePathMap, expandedPaths, existingNodes = []) => {
  const visibleVFSNodes = collectVisibleNodes(root, expandedPaths);
  
  // Map existing node positions to preserve layout stability
  const positionMap = new Map();
  for (const n of existingNodes) {
    positionMap.set(n.id, n.position);
  }

  // Create React Flow Nodes
  const rfNodes = visibleVFSNodes.map(vfsNode => {
    // Generate a stable ID based on path
    const nodeId = vfsNode.type === 'file' ? vfsNode.originalNodeId : `folder-${vfsNode.path}`;
    
    return {
      id: nodeId,
      type: vfsNode.type === 'folder' ? 'folderNode' : 'custom',
      data: { 
        label: vfsNode.name,
        path: vfsNode.path,
        isExpanded: expandedPaths.has(vfsNode.path),
        descendants: vfsNode.totalDescendants
      },
      position: positionMap.get(nodeId) || { x: 0, y: 0 },
      // Mark as newly spawned if we don't have a position
      _isNew: !positionMap.has(nodeId),
      _vfsNode: vfsNode
    };
  });

  // Aggregate Edges
  const edgeAggregates = new Map();
  
  for (const edge of rawEdges) {
    const sourcePath = nodePathMap.get(edge.source);
    const targetPath = nodePathMap.get(edge.target);
    if (!sourcePath || !targetPath) continue;
    
    const visibleSource = getVisibleNode(root, sourcePath, expandedPaths);
    const visibleTarget = getVisibleNode(root, targetPath, expandedPaths);
    
    if (visibleSource && visibleTarget && visibleSource !== visibleTarget) {
      const sourceId = visibleSource.type === 'file' ? visibleSource.originalNodeId : `folder-${visibleSource.path}`;
      const targetId = visibleTarget.type === 'file' ? visibleTarget.originalNodeId : `folder-${visibleTarget.path}`;
      
      const edgeKey = `${sourceId}|${targetId}`;
      if (!edgeAggregates.has(edgeKey)) {
        edgeAggregates.set(edgeKey, {
          id: `edge-${edgeKey}`,
          source: sourceId,
          target: targetId,
          count: 0
        });
      }
      edgeAggregates.get(edgeKey).count++;
    }
  }

  const rfEdges = Array.from(edgeAggregates.values()).map(agg => ({
    id: agg.id,
    source: agg.source,
    type: agg.count > 1 ? 'aggregateEdge' : 'default',
    data: { count: agg.count },
    animated: false,
    style: { stroke: '#cbd5e1', strokeWidth: agg.count > 1 ? 2 : 1.5, opacity: 0.4 } // subdued by default
  }));
  
  // Add hierarchical edges to anchor the starbursts visually
  for (const vfsNode of visibleVFSNodes) {
    if (vfsNode.type === 'folder' && expandedPaths.has(vfsNode.path)) {
      const sourceId = `folder-${vfsNode.path}`;
      for (const child of vfsNode.children.values()) {
        const targetId = child.type === 'file' ? child.originalNodeId : `folder-${child.path}`;
        rfEdges.push({
          id: `hier-${sourceId}-${targetId}`,
          source: sourceId,
          target: targetId,
          type: 'default',
          animated: false,
          style: { stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '4 4', opacity: 0.3 },
          zIndex: -1,
          data: { isHierarchical: true }
        });
      }
    }
  }

  return { nodes: rfNodes, edges: rfEdges };
};

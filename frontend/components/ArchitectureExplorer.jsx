"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
  Panel
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

// --- Custom Node ---
const ArchitectureNode = ({ data, selected }) => {
  const isExpandable = data.has_children;
  const isExpanded = data.expanded;
  
  const iconMap = {
    repository: '📦',
    folder: '📁',
    file: '📄',
    class: '🧩',
    function: '⚡'
  };
  
  const bgMap = {
    repository: 'bg-gray-100',
    folder: 'bg-yellow-50',
    file: 'bg-blue-50',
    class: 'bg-purple-50',
    function: 'bg-green-50'
  };

  return (
    <div className={`px-3 py-2 shadow-sm rounded-md border-2 ${bgMap[data.type] || 'bg-white'} ${selected ? 'border-blue-500 shadow-md' : 'border-gray-300'} flex items-center gap-2 min-w-[150px]`}>
      <Handle type="target" position={Position.Top} className="opacity-0" />
      
      <span className="text-xl">{iconMap[data.type] || '📌'}</span>
      
      <div className="flex-grow flex flex-col">
        <span className="font-mono text-sm font-semibold text-gray-800 truncate max-w-[150px]" title={data.name}>
          {data.name}
        </span>
        <span className="text-xs text-gray-500 uppercase">{data.type}</span>
      </div>
      
      {isExpandable && (
        <button 
          onClick={(e) => {
            e.stopPropagation();
            data.onToggleExpand(data.id);
          }}
          className="w-6 h-6 flex items-center justify-center rounded-full bg-white border border-gray-300 hover:bg-gray-100 text-gray-600 font-bold"
        >
          {isExpanded ? '-' : '+'}
        </button>
      )}
      
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </div>
  );
};

const nodeTypes = {
  archNode: ArchitectureNode,
};

// --- Layout Algorithm ---
const getLayoutedElements = (nodes, edges, direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  dagreGraph.setGraph({ rankdir: direction, nodesep: 30, edgesep: 10, ranksep: 60 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 220, height: 60 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 220 / 2,
        y: nodeWithPosition.y - 60 / 2,
      },
    };
  });

  return { nodes: newNodes, edges };
};

export default function ArchitectureExplorer({ repoName }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  
  // Cache for lazily loaded children
  const childrenCache = useRef({});
  const rfInstance = useRef(null);

  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);

  useEffect(() => {
    nodesRef.current = nodes;
    edgesRef.current = edges;
  }, [nodes, edges]);

  const applyLayout = useCallback((currentNodes, currentEdges) => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(currentNodes, currentEdges);
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [setNodes, setEdges]);

  const fetchRoot = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`/api/repos/${repoName}/architecture?node_id=root`);
      if (!res.ok) throw new Error("Failed to fetch architecture.");
      const data = await res.json();
      
      const rootNode = {
        id: 'root',
        type: 'archNode',
        data: { id: 'root', name: repoName, type: 'repository', parent: null, has_children: true, expanded: true, onToggleExpand: handleToggleExpand },
        position: { x: 0, y: 0 },
      };
      
      childrenCache.current['root'] = data.nodes;
      
      const childNodes = data.nodes.map(n => ({
        id: n.id,
        type: 'archNode',
        data: { ...n, expanded: false, onToggleExpand: handleToggleExpand },
        position: { x: 0, y: 0 },
      }));
      
      const childEdges = data.nodes.map(n => ({
        id: `e-root-${n.id}`,
        source: 'root',
        target: n.id,
        type: 'smoothstep',
        style: { stroke: '#94a3b8', strokeWidth: 1.5 },
      }));
      
      applyLayout([rootNode, ...childNodes], childEdges);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [repoName, setNodes, setEdges, applyLayout]);

  // Initial Load
  useEffect(() => {
    fetchRoot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoName]);

  const handleToggleExpand = useCallback(async (nodeId) => {
    const currentNodes = nodesRef.current;
    const currentEdges = edgesRef.current;
    
    const nodeToToggle = currentNodes.find(n => n.id === nodeId);
    if (!nodeToToggle) return;
    
    const isExpanding = !nodeToToggle.data.expanded;
    
    if (isExpanding) {
      let childrenData = childrenCache.current[nodeId];
      
      if (!childrenData) {
        try {
          const res = await fetch(`/api/repos/${repoName}/architecture?node_id=${encodeURIComponent(nodeId)}`);
          if (!res.ok) throw new Error("Failed to load children");
          const data = await res.json();
          childrenData = data.nodes;
          childrenCache.current[nodeId] = childrenData;
        } catch (err) {
          console.error(err);
          return;
        }
      }
      
      const latestNodes = nodesRef.current;
      const latestEdges = edgesRef.current;
      
      const updatedNodes = latestNodes.map(n => n.id === nodeId ? { ...n, data: { ...n.data, expanded: true } } : n);
      
      const newChildNodes = (childrenData || []).map(n => ({
        id: n.id,
        type: 'archNode',
        data: { ...n, expanded: false, onToggleExpand: handleToggleExpand },
        position: { x: 0, y: 0 },
      }));
      
      const newChildEdges = (childrenData || []).map(n => ({
        id: `e-${nodeId}-${n.id}`,
        source: nodeId,
        target: n.id,
        type: 'smoothstep',
        style: { stroke: '#94a3b8', strokeWidth: 1.5 },
      }));
      
      const existingIds = new Set(updatedNodes.map(n => n.id));
      const filteredChildNodes = newChildNodes.filter(n => !existingIds.has(n.id));
      
      const combinedNodes = [...updatedNodes, ...filteredChildNodes];
      const combinedEdges = [...latestEdges, ...newChildEdges];
      
      applyLayout(combinedNodes, combinedEdges);
      
    } else {
      // Collapse
      const descendants = getDescendants(nodeId, currentEdges);
      const newNodes = currentNodes.filter(n => !descendants.has(n.id)).map(n => n.id === nodeId ? { ...n, data: { ...n.data, expanded: false } } : n);
      const newEdges = currentEdges.filter(e => !descendants.has(e.source) && !descendants.has(e.target));
      
      applyLayout(newNodes, newEdges);
    }
  }, [repoName, applyLayout]);

  const getDescendants = (nodeId, allEdges) => {
    const descendants = new Set();
    const stack = [nodeId];
    
    while (stack.length > 0) {
      const current = stack.pop();
      const children = allEdges.filter(e => e.source === current).map(e => e.target);
      children.forEach(child => {
        descendants.add(child);
        stack.push(child);
      });
    }
    
    return descendants;
  };

  const onNodeClick = useCallback((_, node) => {
    setSelectedNodeId(node.id);
  }, []);
  
  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  const selectedNodeData = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodes.find(n => n.id === selectedNodeId)?.data;
  }, [selectedNodeId, nodes]);

  if (isLoading) {
    return <div className="h-full flex items-center justify-center text-gray-500">Loading Architecture...</div>;
  }

  if (error) {
    return <div className="h-full p-4 text-red-600 bg-red-50">{error}</div>;
  }

  return (
    <div className="flex h-full w-full">
      {/* Sidebar for Metadata */}
      <div className="w-80 border-r border-gray-200 bg-gray-50 flex flex-col overflow-hidden">
        <div className="p-4 border-b border-gray-200 bg-white flex justify-between items-start">
          <div>
            <h2 className="text-lg font-bold text-gray-800">Architecture</h2>
            <p className="text-sm text-gray-500 mt-1">Hierarchical Repository View</p>
          </div>
          <button 
            onClick={fetchRoot}
            className="text-xs bg-gray-200 hover:bg-gray-300 text-gray-700 px-2 py-1 rounded"
            title="Reset to root view"
          >
            Reset
          </button>
        </div>
        
        <div className="flex-grow overflow-y-auto p-4">
          {!selectedNodeData ? (
            <div className="text-gray-500 text-sm italic text-center mt-10">
              Select a node to view its details.
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Name</h3>
                <div className="font-mono text-sm font-bold text-gray-900 break-all bg-white p-2 border border-gray-200 rounded">
                  {selectedNodeData.name}
                </div>
              </div>
              
              <div>
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Type</h3>
                <div className="text-sm text-gray-700 bg-white p-2 border border-gray-200 rounded uppercase font-semibold">
                  {selectedNodeData.type}
                </div>
              </div>
              
              <div>
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Path / ID</h3>
                <div className="text-sm text-gray-600 font-mono bg-gray-100 p-2 rounded break-all">
                  {selectedNodeData.id}
                </div>
              </div>
              
              <div>
                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Children</h3>
                <div className="text-sm text-gray-700">
                  {selectedNodeData.has_children ? 'Has children (can expand)' : 'Leaf node'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Graph Area */}
      <div className="flex-grow relative h-full">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          onInit={(instance) => { rfInstance.current = instance; instance.fitView(); }}
          fitView
          minZoom={0.05}
          maxZoom={2}
          nodesDraggable={false}
        >
          <Background color="#f3f4f6" gap={20} size={1} />
          <Controls />
          <MiniMap 
            nodeColor={(n) => n.id === selectedNodeId ? '#3b82f6' : '#e5e7eb'}
            maskColor="rgba(240, 240, 240, 0.6)" 
          />
        </ReactFlow>
      </div>
    </div>
  );
}

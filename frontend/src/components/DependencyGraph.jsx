import React, { useState, useEffect, useCallback } from 'react';
import ReactFlow, {
  Controls,
  Background,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';

// Simple circle layout function
const getCircleLayout = (nodes) => {
  const nodeCount = nodes.length;
  const radius = Math.max(300, nodeCount * 25);
  return nodes.map((node, i) => {
    const angle = (i / nodeCount) * 2 * Math.PI;
    return {
      ...node,
      position: {
        x: radius + radius * Math.cos(angle),
        y: radius + radius * Math.sin(angle)
      }
    };
  });
};

export default function DependencyGraph({ repoName }) {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchGraph = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/repos/${repoName}/dependencies`);
        if (!res.ok) {
          throw new Error("Failed to load dependency graph.");
        }
        const data = await res.json();
        
        // Convert to React Flow format
        const initialNodes = data.nodes.map(n => ({
          id: n.id,
          data: { label: n.full_path }, // Use full path for clarity
          position: { x: 0, y: 0 },
          style: {
            background: '#fff',
            border: '2px solid #2563eb',
            borderRadius: '4px',
            padding: '10px',
            fontSize: '12px',
            fontFamily: 'monospace'
          }
        }));
        
        const initialEdges = data.edges.map(e => ({
          id: e.id,
          source: e.source,
          target: e.target,
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#9ca3af' },
          style: { stroke: '#9ca3af', strokeWidth: 2 }
        }));

        setNodes(getCircleLayout(initialNodes));
        setEdges(initialEdges);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchGraph();
  }, [repoName]);

  const onNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );
  const onEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  if (isLoading) {
    return <div className="h-full flex items-center justify-center text-gray-500">Generating Dependency Graph...</div>;
  }

  if (error) {
    return <div className="h-full flex items-center justify-center text-red-500">{error}</div>;
  }

  if (nodes.length === 0) {
    return <div className="h-full flex items-center justify-center text-gray-400">No Python files found to analyze.</div>;
  }

  return (
    <div className="w-full h-full bg-gray-50 rounded-lg border border-gray-200 overflow-hidden relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        minZoom={0.1}
      >
        <Background color="#ccc" gap={16} />
        <Controls />
      </ReactFlow>
      <div className="absolute top-4 left-4 bg-white/80 p-2 rounded shadow text-xs font-semibold text-gray-700 pointer-events-none">
        {nodes.length} Files | {edges.length} Dependencies
      </div>
    </div>
  );
}

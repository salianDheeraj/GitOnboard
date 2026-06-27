import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import ReactFlow, {
  Controls,
  ControlButton,
  Background,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
  Panel,
  Handle,
  Position,
  getBezierPath,
  getStraightPath
} from 'reactflow';
import 'reactflow/dist/style.css';
import * as d3 from 'd3-force';

// Custom Node to place handles in the center so edges point exactly at the node
const CustomNode = ({ data }) => (
  <div style={{
    background: '#ffffff',
    border: '2px solid #6366f1',
    borderRadius: '24px',
    padding: '8px 16px',
    fontSize: '12px',
    fontWeight: '600',
    color: '#374151',
    fontFamily: 'sans-serif',
    boxShadow: '0 2px 4px -1px rgb(0 0 0 / 0.1)',
    minWidth: '50px',
    textAlign: 'center',
  }}>
    <Handle type="target" position={Position.Top} style={{ visibility: 'hidden', top: '50%' }} />
    <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden', top: '50%' }} />
    {data.label}
  </div>
);

const nodeTypes = {
  custom: CustomNode,
};

export default function DependencyGraph({ repoName }) {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Custom Control States
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  
  const containerRef = useRef(null);
  const rfInstance = useRef(null);
  const simulationRef = useRef(null);
  const initialNodesRef = useRef([]);

  useEffect(() => {
    let isMounted = true;
    
    const fetchGraph = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/repos/${repoName}/dependencies`);
        if (!res.ok) {
          throw new Error("Failed to load dependency graph.");
        }
        const data = await res.json();
        if (!isMounted) return;
        
        // Setup initial nodes
        const initialNodes = data.nodes.map(n => ({
          id: n.id,
          type: 'custom',
          data: { label: n.full_path.split('/').pop() }, 
          // Give them a random initial position
          x: Math.random() * 500 - 250, 
          y: Math.random() * 500 - 250 
        }));
        
        const initialEdges = data.edges.map(e => ({
          id: e.id,
          source: e.source,
          target: e.target,
          type: 'straight',
          animated: false,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#d1d5db', width: 15, height: 15 },
          style: { stroke: '#e5e7eb', strokeWidth: 1.5, opacity: 0.6 }
        }));

        const nodeIds = new Set(initialNodes.map(n => n.id));
        const simulationEdges = initialEdges
          .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
          .map(e => ({ ...e }));
        
        // Save to ref so drag handlers can access them
        initialNodesRef.current = initialNodes;

        // Setup D3 Force Simulation
        const simulation = d3.forceSimulation(initialNodes)
          .force('charge', d3.forceManyBody().strength(-400)) // Repel nodes
          .force('center', d3.forceCenter(0, 0)) 
          .force('collide', d3.forceCollide().radius(85)) // Larger collision radius to prevent pill overlaps
          .force('x', d3.forceX(0).strength(0.1)) 
          .force('y', d3.forceY(0).strength(0.1)) 
          .force('link', d3.forceLink(simulationEdges).id(d => d.id).distance(100));
          
        simulationRef.current = simulation;

        // Fast-forward the simulation so it appears stationary on load
        simulation.tick(300);

        // Map final D3 coordinates to React Flow positions
        const updateReactFlowNodes = () => {
          setNodes(initialNodes.map(n => ({
            id: n.id,
            type: 'custom',
            data: n.data,
            position: { x: isNaN(n.x) ? 0 : n.x, y: isNaN(n.y) ? 0 : n.y },
          })));
        };
        
        updateReactFlowNodes();
        setEdges(initialEdges);
        
        // Listen to live ticks for when the user drags a node and wakes up physics
        simulation.on('tick', () => {
          if (!isMounted) return;
          updateReactFlowNodes();
        });
        
        // Center view on the stationary graph
        setTimeout(() => {
          if (!isMounted || !rfInstance.current) return;
          rfInstance.current.fitView({ padding: 0.2, duration: 800 });
        }, 100);

      } catch (err) {
        if (isMounted) setError(err.message);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    fetchGraph();
    
    return () => {
      isMounted = false;
      if (simulationRef.current) simulationRef.current.stop();
    };
  }, [repoName]); 

  const onNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );
  const onEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  // Wire up React Flow Drag events to D3 physics
  const onNodeDragStart = useCallback((_, node) => {
    if (!simulationRef.current) return;
    const simNode = initialNodesRef.current.find(n => n.id === node.id);
    if (simNode) {
      simNode.fx = simNode.x;
      simNode.fy = simNode.y;
      simulationRef.current.alphaTarget(0.3).restart(); // Wake up physics
    }
  }, []);

  const onNodeDrag = useCallback((_, node) => {
    if (!simulationRef.current) return;
    const simNode = initialNodesRef.current.find(n => n.id === node.id);
    if (simNode) {
      // Pin the node to the mouse position
      simNode.fx = node.position.x;
      simNode.fy = node.position.y;
    }
  }, []);

  const onNodeDragStop = useCallback((_, node) => {
    if (!simulationRef.current) return;
    const simNode = initialNodesRef.current.find(n => n.id === node.id);
    if (simNode) {
      simNode.fx = null;
      simNode.fy = null;
      simulationRef.current.alphaTarget(0); // Let physics cool down and stabilize again
    }
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      if (containerRef.current) {
        containerRef.current.requestFullscreen().catch((err) => {
          console.error(`Error attempting to enable fullscreen mode: ${err.message}`);
        });
      }
    } else {
      document.exitFullscreen();
    }
  };

  const onNodeClick = useCallback((_, node) => {
    setSelectedNode(node.id);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Compute styles dynamically for selection effects
  const renderedEdges = useMemo(() => {
    return edges.map(e => {
      if (!selectedNode) {
        return {
          ...e,
          style: { stroke: '#cbd5e1', strokeWidth: 1.5, opacity: 0.8 },
          animated: false,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8', width: 20, height: 20 },
          zIndex: 0
        };
      }
      
      const isConnected = e.source === selectedNode || e.target === selectedNode;
      return {
        ...e,
        style: { 
          stroke: isConnected ? '#6366f1' : '#e2e8f0', // darker gray for non-connected
          strokeWidth: isConnected ? 3 : 1, 
          opacity: isConnected ? 1 : 0.3 // slightly higher opacity for non-connected
        },
        animated: isConnected,
        markerEnd: { type: MarkerType.ArrowClosed, color: isConnected ? '#6366f1' : '#e2e8f0', width: 20, height: 20 },
        zIndex: isConnected ? 10 : 0
      };
    });
  }, [edges, selectedNode]);

  if (isLoading) {
    return <div className="h-full flex items-center justify-center text-gray-500">Generating graph layout...</div>;
  }

  if (error) {
    return <div className="h-full flex items-center justify-center text-red-500">{error}</div>;
  }

  if (nodes.length === 0) {
    return <div className="h-full flex items-center justify-center text-gray-400">No Python files found to analyze.</div>;
  }

  return (
    <div 
      ref={containerRef}
      className="w-full h-full bg-white rounded-lg border border-gray-200 overflow-hidden relative"
    >
      <ReactFlow
        nodes={nodes}
        edges={renderedEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStart={onNodeDragStart}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onInit={(instance) => { rfInstance.current = instance; }}
        minZoom={0.05}
        maxZoom={2.5}
        nodesDraggable={true}
      >
        <Background color="#f3f4f6" gap={20} size={1} />
        
        {/* Integrated Controls */}
        <Controls showInteractive={false} showFitView={false} position="bottom-right">
          <ControlButton onClick={toggleFullscreen} title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}>
            {isFullscreen ? "↙️" : "↗️"}
          </ControlButton>
        </Controls>
        
        <Panel position="top-left" className="bg-white/90 shadow-sm border border-gray-100 px-3 py-1.5 rounded-full text-xs font-semibold text-gray-600 pointer-events-none">
          {nodes.length} Files | {edges.length} Dependencies
        </Panel>
      </ReactFlow>
    </div>
  );
}

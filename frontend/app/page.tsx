"use client";

import React, { useState, useEffect, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Node,
  Edge,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";

interface SymbolNode {
  id: string;
  name: string;
  symbol_type: string;
  file_id: string;
  line_start: number;
}

export default function TraceExecutionPage({
  params,
}: {
  params: { repoName: string };
}) {
  const [routeId, setRouteId] = useState("");
  const [executionPath, setExecutionPath] = useState<SymbolNode[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchTrace = async () => {
    if (!routeId) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/repo/${params.repoName}/trace/${routeId}`);
      const data = await res.json();
      if (data.execution_path) {
        setExecutionPath(data.execution_path);
      }
    } catch (err) {
      console.error("Failed to load trace", err);
    } finally {
      setLoading(false);
    }
  };

  // Construct React Flow Nodes & Edges dynamically from execution path
  const { nodes, edges } = useMemo(() => {
    const nodesList: Node[] = [];
    const edgesList: Edge[] = [];

    executionPath.forEach((sym, index) => {
      // 1. Position nodes sequentially in a vertical/horizontal pipeline layout
      nodesList.push({
        id: sym.id,
        data: {
          label: (
            <div className="p-2 text-left">
              <div className="font-bold text-sm text-blue-400">{sym.name}</div>
              <div className="text-xs text-gray-400">Type: {sym.symbol_type}</div>
              <div className="text-xs text-gray-500 font-mono truncate max-w-[180px]">
                {sym.file_id} L:{sym.line_start}
              </div>
            </div>
          ),
        },
        position: { x: index * 260, y: 100 },
        style: {
          background: "#1e293b",
          color: "#fff",
          border: "1px solid #3b82f6",
          borderRadius: "8px",
          width: 200,
        },
      });

      // 2. Connect step N -> step N+1 with animated edge
      if (index > 0) {
        const prevSym = executionPath[index - 1];
        edgesList.push({
          id: `edge-${prevSym.id}-${sym.id}`,
          source: prevSym.id,
          target: sym.id,
          animated: true,
          style: { stroke: "#60a5fa", strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#60a5fa",
          },
        });
      }
    });

    return { nodes: nodesList, edges: edgesList };
  }, [executionPath]);

  return (
    <div className="p-6 text-white min-h-screen bg-slate-900">
      <h1 className="text-2xl font-bold mb-4">
        ⚡ Execution Flow Simulator
      </h1>

      <div className="flex gap-4 mb-6">
        <input
          type="text"
          placeholder="Enter Route ID or Endpoint (e.g. route_login)"
          value={routeId}
          onChange={(e) => setRouteId(e.target.value)}
          className="px-4 py-2 bg-slate-800 border border-slate-700 rounded w-96 text-white"
        />
        <button
          onClick={fetchTrace}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded font-semibold transition"
        >
          {loading ? "Tracing..." : "Simulate Flow"}
        </button>
      </div>

      <div className="w-full h-[600px] border border-slate-800 rounded-lg bg-slate-950">
        {nodes.length > 0 ? (
          <ReactFlow nodes={nodes} edges={edges} fitView>
            <Background color="#334155" gap={16} />
            <Controls />
          </ReactFlow>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-500">
            Enter a route ID and click Simulate Flow to visualize the execution path.
          </div>
        )}
      </div>
    </div>
  );
}
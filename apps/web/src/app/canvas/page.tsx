"use client";

import {
  addEdge,
  Background,
  type Connection,
  Controls,
  type Edge,
  type Node,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./canvas.css";
import Link from "next/link";
import { useCallback, useRef, useState } from "react";

import { CodeView } from "@/components/canvas/CodeView";
import { ConfigPanel } from "@/components/canvas/ConfigPanel";
import { nodeTypes } from "@/components/canvas/nodes";
import { Palette } from "@/components/canvas/Palette";
import { Playground } from "@/components/canvas/Playground";
import { Button, buttonVariants } from "@/components/ui/button";
import { saveAgent } from "@/lib/api";
import {
  buildGraphSpec,
  type CalyprNodeType,
  DEFAULT_CONFIG,
  type NodeData,
} from "@/lib/graph";

function CanvasInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showPlayground, setShowPlayground] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const counter = useRef(0);
  const lastNodeId = useRef<string | null>(null);

  const addNode = useCallback(
    (type: CalyprNodeType) => {
      const index = ++counter.current;
      const id = `${type}-${index}`;
      const node: Node<NodeData> = {
        id,
        type,
        position: { x: 280, y: 30 + index * 130 },
        data: { config: { ...DEFAULT_CONFIG[type] } },
      };
      setNodes((nds) => [...nds, node]);
      if (lastNodeId.current && type !== "input") {
        const from = lastNodeId.current;
        setEdges((eds) =>
          addEdge({ id: `e-${from}-${id}`, source: from, target: id }, eds),
        );
      }
      lastNodeId.current = id;
      setSelectedId(id);
    },
    [setNodes, setEdges],
  );

  const onConnect = useCallback(
    (c: Connection) => setEdges((eds) => addEdge(c, eds)),
    [setEdges],
  );
  const onNodeClick = useCallback(
    (_: unknown, node: Node) => setSelectedId(node.id),
    [],
  );
  const updateConfig = useCallback(
    (config: Record<string, unknown>) =>
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedId ? { ...n, data: { ...n.data, config } } : n,
        ),
      ),
    [selectedId, setNodes],
  );

  const getGraph = useCallback(() => buildGraphSpec(nodes, edges), [nodes, edges]);

  const onSave = useCallback(async () => {
    try {
      const { id } = await saveAgent("Untitled Agent", getGraph());
      setSaveMsg(`Saved ${id.slice(0, 8)}`);
    } catch {
      setSaveMsg("Save failed");
    }
  }, [getGraph]);

  const selected = nodes.find((n) => n.id === selectedId) ?? null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">Agent Canvas</span>
          {saveMsg ? (
            <span className="text-xs text-muted-foreground" data-testid="save-msg">
              {saveMsg}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onSave} data-testid="save-agent">
            Save
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowCode((s) => !s)}
            data-testid="toggle-code"
          >
            {showCode ? "Hide code" : "Code"}
          </Button>
          <Button
            size="sm"
            onClick={() => setShowPlayground((s) => !s)}
            data-testid="toggle-playground"
          >
            {showPlayground ? "Hide" : "Playground"}
          </Button>
          <Link
            href="/dashboard"
            className={buttonVariants({ variant: "ghost", size: "sm" })}
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-48 shrink-0 border-r border-border p-3">
          <Palette onAdd={addNode} />
        </aside>

        <div className="relative flex-1" data-testid="canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={() => setSelectedId(null)}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>

        <aside className="w-72 shrink-0 overflow-auto border-l border-border p-3">
          <ConfigPanel node={selected} onChange={updateConfig} />
        </aside>

        {showCode ? (
          <aside
            className="w-96 shrink-0 border-l border-border"
            data-testid="code-panel"
          >
            <CodeView getGraph={getGraph} />
          </aside>
        ) : null}

        {showPlayground ? (
          <aside
            className="w-80 shrink-0 border-l border-border"
            data-testid="playground"
          >
            <Playground getGraph={getGraph} />
          </aside>
        ) : null}
      </div>
    </div>
  );
}

export default function CanvasPage() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}

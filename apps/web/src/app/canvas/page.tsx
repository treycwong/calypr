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
import { useCallback, useEffect, useRef, useState } from "react";

import { CodeView } from "@/components/canvas/CodeView";
import { ConfigPanel } from "@/components/canvas/ConfigPanel";
import { nodeTypes } from "@/components/canvas/nodes";
import { Palette } from "@/components/canvas/Palette";
import { Playground } from "@/components/canvas/Playground";
import { Button, buttonVariants } from "@/components/ui/button";
import { listTemplates, saveAgent, type Template } from "@/lib/api";
import {
  buildGraphSpec,
  type CalyprNodeType,
  DEFAULT_CONFIG,
  graphToCanvas,
  type NodeData,
  ROUTER_DEFAULT_BRANCH,
} from "@/lib/graph";

function CanvasInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showPlayground, setShowPlayground] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const counter = useRef(0);
  const lastNodeId = useRef<string | null>(null);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, []);

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
        // Edges leaving a Router need a branch name; auto-link uses its default branch.
        const label = from.startsWith("router-") ? ROUTER_DEFAULT_BRANCH : undefined;
        setEdges((eds) =>
          addEdge({ id: `e-${from}-${id}`, source: from, target: id, label }, eds),
        );
      }
      lastNodeId.current = id;
      setSelectedId(id);
    },
    [setNodes, setEdges],
  );

  // A connection dragged from a Router's named handle carries the branch name as the edge
  // label, which becomes the edge `condition` in the GraphSpec.
  const onConnect = useCallback(
    (c: Connection) =>
      setEdges((eds) =>
        addEdge({ ...c, label: c.sourceHandle ?? undefined }, eds),
      ),
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

  const loadTemplate = useCallback(
    (id: string) => {
      const tpl = templates.find((t) => t.id === id);
      if (!tpl) return;
      const canvas = graphToCanvas(tpl.graph);
      setNodes(canvas.nodes);
      setEdges(canvas.edges);
      counter.current = canvas.nodes.length;
      lastNodeId.current = canvas.nodes.at(-1)?.id ?? null;
      setSelectedId(null);
      setSaveMsg(`Loaded ${tpl.name}`);
    },
    [templates, setNodes, setEdges],
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
          <select
            data-testid="template-picker"
            aria-label="Start from a framework or template"
            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
            value=""
            onChange={(e) => {
              loadTemplate(e.target.value);
              e.target.value = "";
            }}
          >
            <option value="" disabled>
              Start from a framework or template…
            </option>
            <optgroup label="Frameworks">
              {templates
                .filter((t) => t.kind === "framework")
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
            </optgroup>
            <optgroup label="Templates">
              {templates
                .filter((t) => t.kind === "template")
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
            </optgroup>
          </select>
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

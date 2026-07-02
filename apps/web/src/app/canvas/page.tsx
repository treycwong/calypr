"use client";

import {
  addEdge,
  Background,
  type Connection,
  Controls,
  type Edge,
  MiniMap,
  type Node,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./canvas.css";
import {
  Blocks,
  LayoutTemplate,
  LogOut,
  type LucideIcon,
  Play,
  Sparkles,
  Square,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AssistantPanel } from "@/components/canvas/AssistantPanel";
import { CodeView } from "@/components/canvas/CodeView";
import { ConfigPanel } from "@/components/canvas/ConfigPanel";
import { nodeTypes } from "@/components/canvas/nodes";
import { Palette } from "@/components/canvas/Palette";
import { Playground } from "@/components/canvas/Playground";
import { TemplatesPanel } from "@/components/canvas/TemplatesPanel";
import { Button } from "@/components/ui/button";
import {
  createAgent,
  getAgent,
  listTemplates,
  type Template,
  updateAgent,
} from "@/lib/api";
import {
  buildGraphSpec,
  type CalyprNodeType,
  DEFAULT_CONFIG,
  graphToCanvas,
  type NodeData,
  ROUTER_DEFAULT_BRANCH,
} from "@/lib/graph";

function RailButton({
  icon: Icon,
  label,
  active,
  onClick,
  testid,
}: {
  icon: LucideIcon;
  label: string;
  active: boolean;
  onClick: () => void;
  testid: string;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      data-testid={testid}
      onClick={onClick}
      className={`flex h-9 w-9 items-center justify-center rounded-md transition ${
        active
          ? "bg-muted text-foreground"
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
      }`}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function CanvasInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showPlayground, setShowPlayground] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  // The single rail-driven left panel — one tab at a time (or null = closed). Clicking the
  // active tab again closes it (full-width canvas).
  const [activePanel, setActivePanel] = useState<
    "blocks" | "templates" | "ai" | null
  >("blocks");
  const togglePanel = (p: "blocks" | "templates" | "ai") =>
    setActivePanel((cur) => (cur === p ? null : p));
  // The persistent right panel switches between node Properties and generated Code.
  const [rightTab, setRightTab] = useState<"properties" | "code">("properties");
  // The saved agent this canvas is editing: id (null until first save) + its name. Save creates
  // once then updates in place, so re-saving never duplicates.
  const [agentId, setAgentId] = useState<string | null>(null);
  const [name, setName] = useState("Untitled Agent");
  const counter = useRef(0);
  const lastNodeId = useRef<string | null>(null);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, []);

  // Open an existing agent when arriving via /canvas?agent=<id> (from the dashboard), so Save
  // updates that agent rather than creating a new one.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("agent");
    if (!id) return;
    getAgent(id)
      .then((a) => {
        const canvas = graphToCanvas(a.graph);
        setNodes(canvas.nodes);
        setEdges(canvas.edges);
        counter.current = canvas.nodes.length;
        lastNodeId.current = canvas.nodes.at(-1)?.id ?? null;
        setAgentId(a.id);
        setName(a.name);
      })
      .catch(() => setSaveMsg("Couldn't load that agent"));
  }, [setNodes, setEdges]);

  const addNode = useCallback(
    (type: CalyprNodeType) => {
      const index = ++counter.current;
      const id = `${type}-${index}`;
      const node: Node<NodeData> = {
        id,
        type,
        // Flow left → right: each new block is placed to the right of the previous one.
        position: { x: 80 + index * 240, y: 300 },
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
  const onNodeClick = useCallback((_: unknown, node: Node) => {
    setSelectedId(node.id);
    setRightTab("properties"); // reveal the clicked node's properties
  }, []);
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
      // Loading a starter begins a fresh project: Save will create a new agent.
      setAgentId(null);
      setName(tpl.name);
      setSaveMsg(`Loaded ${tpl.name}`);
    },
    [templates, setNodes, setEdges],
  );

  const getGraph = useCallback(() => buildGraphSpec(nodes, edges), [nodes, edges]);

  const onSave = useCallback(async () => {
    setSaveMsg("Saving…");
    try {
      const agentName = name.trim() || "Untitled Agent";
      if (agentId) {
        await updateAgent(agentId, { name: agentName, graph: getGraph() });
      } else {
        const created = await createAgent(agentName, getGraph());
        setAgentId(created.id);
        // Reflect the saved agent in the URL so a refresh reopens it.
        window.history.replaceState(null, "", `/canvas?agent=${created.id}`);
      }
      setSaveMsg("Saved ✓");
    } catch {
      setSaveMsg("Save failed");
    }
  }, [agentId, name, getGraph]);

  const selected = nodes.find((n) => n.id === selectedId) ?? null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            aria-label="Back to dashboard"
            title="Back to dashboard"
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
          </Link>
          <input
            data-testid="agent-name"
            aria-label="Agent name"
            className="h-8 w-48 rounded-md bg-transparent px-2 text-sm font-medium outline-none hover:bg-muted focus:bg-muted"
            value={name}
            placeholder="Untitled Agent"
            onChange={(e) => setName(e.target.value)}
          />
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
            variant={showPlayground ? "outline" : "default"}
            onClick={() => setShowPlayground((s) => !s)}
            data-testid="toggle-playground"
          >
            {showPlayground ? (
              <Square className="h-4 w-4 fill-current" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {showPlayground ? "Stop" : "Try it"}
          </Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Slim icon rail: each tab drives the single left panel — one at a time. */}
        <aside className="flex w-11 shrink-0 flex-col items-center gap-1 border-r border-border py-2">
          <RailButton
            icon={Blocks}
            label="Blocks"
            active={activePanel === "blocks"}
            onClick={() => togglePanel("blocks")}
            testid="tab-blocks"
          />
          <RailButton
            icon={LayoutTemplate}
            label="Templates"
            active={activePanel === "templates"}
            onClick={() => togglePanel("templates")}
            testid="tab-templates"
          />
          <div className="my-1 h-px w-5 bg-border" />
          <RailButton
            icon={Sparkles}
            label="AI assistant"
            active={activePanel === "ai"}
            onClick={() => togglePanel("ai")}
            testid="toggle-assistant"
          />
        </aside>

        {/* The single rail-selected left panel. */}
        {activePanel === "blocks" || activePanel === "templates" ? (
          <aside className="w-52 shrink-0 overflow-auto border-r border-border p-3">
            {activePanel === "blocks" ? (
              <Palette onAdd={addNode} />
            ) : (
              <TemplatesPanel templates={templates} onLoad={loadTemplate} />
            )}
          </aside>
        ) : null}
        {activePanel === "ai" ? (
          <aside
            className="w-80 shrink-0 border-r border-border"
            data-testid="assistant"
          >
            <AssistantPanel />
          </aside>
        ) : null}

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
            <MiniMap
              pannable
              zoomable
              className="rounded-md border border-border"
              style={{ backgroundColor: "var(--card)" }}
              maskColor="rgb(2 6 23 / 0.6)"
              nodeColor="#22d3ee"
              nodeStrokeColor="#0e7490"
            />
          </ReactFlow>
        </div>

        {/* Right panel: Properties (selected node) or generated Code — replaced by the
            playground while it's running, rather than stacking alongside it. */}
        {showPlayground ? null : (
        <aside className="flex w-80 shrink-0 flex-col border-l border-border">
          <div className="flex gap-1 border-b border-border px-3 pt-2">
            <button
              type="button"
              data-testid="tab-properties"
              onClick={() => setRightTab("properties")}
              className={`-mb-px border-b-2 px-3 py-1.5 text-sm transition ${
                rightTab === "properties"
                  ? "border-cyan-400 text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Properties
            </button>
            <button
              type="button"
              data-testid="toggle-code"
              onClick={() => setRightTab("code")}
              className={`-mb-px border-b-2 px-3 py-1.5 text-sm transition ${
                rightTab === "code"
                  ? "border-cyan-400 text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              Code
            </button>
          </div>
          <div className="min-h-0 flex-1">
            {rightTab === "properties" ? (
              selected ? (
                <div className="h-full overflow-auto p-3" data-testid="config-panel">
                  <ConfigPanel node={selected} onChange={updateConfig} />
                </div>
              ) : (
                <div className="p-8 text-center text-sm text-muted-foreground">
                  Select a node to edit its properties.
                </div>
              )
            ) : (
              <div className="h-full" data-testid="code-panel">
                <CodeView getGraph={getGraph} />
              </div>
            )}
          </div>
        </aside>
        )}

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

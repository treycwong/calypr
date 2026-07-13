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
  type LucideIcon,
  Play,
  Redo2,
  Share2,
  Sparkles,
  Square,
  Undo2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import type { GraphSpec } from "@calypr/dsl";

import {
  AssistantPanel,
  type CanvasSnapshot,
} from "@/components/canvas/AssistantPanel";
import { CodeView } from "@/components/canvas/CodeView";
import { ConfigPanel } from "@/components/canvas/ConfigPanel";
import { nodeTypes } from "@/components/canvas/nodes";
import { Palette } from "@/components/canvas/Palette";
import { Playground } from "@/components/canvas/Playground";
import { TemplatesPanel } from "@/components/canvas/TemplatesPanel";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import {
  createAgent,
  createShare,
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
  const { toast } = useToast();
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
  // Undo/redo history: `past` holds prior canvases, `future` holds undone ones. `record()` is
  // called right before each mutation to snapshot the pre-change canvas (and clears the redo
  // stack, since a new edit forks history).
  const [past, setPast] = useState<CanvasSnapshot[]>([]);
  const [future, setFuture] = useState<CanvasSnapshot[]>([]);
  const record = useCallback(() => {
    setPast((p) => [...p.slice(-49), { nodes, edges, name }]);
    setFuture([]);
  }, [nodes, edges, name]);

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
      .catch(() => {
        setSaveMsg("Couldn't load that agent");
        toast("Couldn't load that agent.", "error");
      });
  }, [setNodes, setEdges, toast]);

  const addNode = useCallback(
    (type: CalyprNodeType) => {
      record();
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
    [record, setNodes, setEdges],
  );

  // A connection dragged from a Router's named handle carries the branch name as the edge
  // label, which becomes the edge `condition` in the GraphSpec.
  const onConnect = useCallback(
    (c: Connection) => {
      record();
      setEdges((eds) => addEdge({ ...c, label: c.sourceHandle ?? undefined }, eds));
    },
    [record, setEdges],
  );
  const onNodeClick = useCallback((_: unknown, node: Node) => {
    setSelectedId(node.id);
    setRightTab("properties"); // reveal the clicked node's properties
  }, []);
  const updateConfig = useCallback(
    (config: Record<string, unknown>) => {
      record();
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedId ? { ...n, data: { ...n.data, config } } : n,
        ),
      );
    },
    [record, selectedId, setNodes],
  );

  const loadTemplate = useCallback(
    (id: string) => {
      const tpl = templates.find((t) => t.id === id);
      if (!tpl) return;
      record();
      const canvas = graphToCanvas(tpl.graph);
      setNodes(canvas.nodes);
      setEdges(canvas.edges);
      counter.current = canvas.nodes.length;
      lastNodeId.current = canvas.nodes.at(-1)?.id ?? null;
      setSelectedId(null);
      // Applying a template only swaps the canvas nodes — it keeps the project's name and id,
      // so Save updates the same agent (it does not fork a new one or rename it).
      setSaveMsg(`Applied ${tpl.name}`);
    },
    [record, templates, setNodes, setEdges],
  );

  const getGraph = useCallback(
    () => buildGraphSpec(nodes, edges, name.trim() || "Untitled Agent"),
    [nodes, edges, name],
  );

  // --- AI assistant wiring ---------------------------------------------------
  // Refine context: the canvas is the source of truth, so hand-edits between prompts are
  // respected. Empty canvas → null (first prompt is a fresh generate, not a refine).
  const getCurrentGraph = useCallback(
    (): GraphSpec | null => (nodes.length ? buildGraphSpec(nodes, edges, name) : null),
    [nodes, edges, name],
  );
  const snapshotCanvas = useCallback(
    (): CanvasSnapshot => ({ nodes, edges, name }),
    [nodes, edges, name],
  );
  const restoreCanvas = useCallback(
    (snap: CanvasSnapshot) => {
      setNodes(snap.nodes);
      setEdges(snap.edges);
      setName(snap.name);
      setSelectedId(null);
    },
    [setNodes, setEdges],
  );

  // Undo/redo: move the current canvas onto the opposite stack, then restore the neighbour.
  const undo = useCallback(() => {
    if (!past.length) return;
    const prev = past[past.length - 1];
    setPast((p) => p.slice(0, -1));
    setFuture((f) => [...f, { nodes, edges, name }]);
    restoreCanvas(prev);
  }, [past, nodes, edges, name, restoreCanvas]);
  const redo = useCallback(() => {
    if (!future.length) return;
    const next = future[future.length - 1];
    setFuture((f) => f.slice(0, -1));
    setPast((p) => [...p, { nodes, edges, name }]);
    restoreCanvas(next);
  }, [future, nodes, edges, name, restoreCanvas]);

  // Snapshot before a drag (once per drag, not per pixel) and before a delete, so those are
  // undoable too. React Flow applies position/remove changes through onNodesChange.
  const onNodeDragStart = useCallback(() => record(), [record]);
  const handleNodesChange = useCallback<typeof onNodesChange>(
    (changes) => {
      if (changes.some((c) => c.type === "remove")) record();
      onNodesChange(changes);
    },
    [record, onNodesChange],
  );
  const handleEdgesChange = useCallback<typeof onEdgesChange>(
    (changes) => {
      if (changes.some((c) => c.type === "remove")) record();
      onEdgesChange(changes);
    },
    [record, onEdgesChange],
  );

  // Keyboard: ⌘/Ctrl+Z undo, ⌘/Ctrl+Shift+Z (or Ctrl+Y) redo — ignored while typing in a field.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "z") {
        if (!((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "y")) return;
      }
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      e.preventDefault();
      const redoCombo = e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey);
      if (redoCombo) redo();
      else undo();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo]);
  const applyAssistantGraph = useCallback(
    (spec: GraphSpec) => {
      record();
      const canvas = graphToCanvas(spec);
      setNodes(canvas.nodes);
      setEdges(canvas.edges);
      counter.current = canvas.nodes.length;
      lastNodeId.current = canvas.nodes.at(-1)?.id ?? null;
      setSelectedId(null);
      // Refining an open agent keeps its id/name (Save updates it); a fresh generate on an
      // unsaved canvas adopts the generated graph's name (Save then creates a new agent).
      if (!agentId) setName(spec.name || "Untitled Agent");
    },
    [record, agentId, setNodes, setEdges],
  );

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
      toast("Couldn't save your agent — please try again.", "error");
    }
  }, [agentId, name, getGraph, toast]);

  // Share: a popover under the Share button showing the /s/{token} link + a Copy button. The
  // link is minted once (lazily, when the popover first opens) and reused — it always runs the
  // agent's latest saved graph, so it stays valid across edits. Only offered once the agent has
  // an id (a share needs a persisted agent to run server-side).
  const [shareOpen, setShareOpen] = useState(false);
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const [shareError, setShareError] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const sharePanelRef = useRef<HTMLDivElement>(null);
  const shareUrl = shareToken ? `${window.location.origin}/s/${shareToken}` : "";

  const toggleShare = useCallback(async () => {
    if (!agentId) return;
    if (shareOpen) {
      setShareOpen(false);
      return;
    }
    setShareOpen(true);
    setShareCopied(false);
    if (!shareToken) {
      setShareBusy(true);
      setShareError(false);
      try {
        const { token } = await createShare(agentId);
        setShareToken(token);
      } catch {
        setShareError(true);
        toast("Couldn't create a share link — please try again.", "error");
      } finally {
        setShareBusy(false);
      }
    }
  }, [agentId, shareOpen, shareToken, toast]);

  const copyShareLink = useCallback(async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
    } catch {
      // clipboard blocked (e.g. insecure context) — the URL is visible to copy manually
    }
    setShareCopied(true);
  }, [shareUrl]);

  // Close the popover on an outside click.
  useEffect(() => {
    if (!shareOpen) return;
    const onDown = (e: MouseEvent) => {
      if (sharePanelRef.current && !sharePanelRef.current.contains(e.target as globalThis.Node)) {
        setShareOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [shareOpen]);

  const selected = nodes.find((n) => n.id === selectedId) ?? null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            aria-label="Calypr — back to dashboard"
            title="Back to dashboard"
            className="transition hover:opacity-90"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-cyan-400 to-cyan-600 text-sm font-bold text-black">
              C
            </span>
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
          <Button
            variant="ghost"
            size="icon"
            onClick={undo}
            disabled={past.length === 0}
            aria-label="Undo"
            title="Undo (⌘Z)"
            data-testid="undo"
          >
            <Undo2 className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={redo}
            disabled={future.length === 0}
            aria-label="Redo"
            title="Redo (⌘⇧Z)"
            data-testid="redo"
          >
            <Redo2 className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={onSave} data-testid="save-agent">
            Save
          </Button>
          {agentId ? (
            <div className="relative" ref={sharePanelRef}>
              <Button
                variant="outline"
                size="sm"
                onClick={toggleShare}
                data-testid="share-agent"
                title="Get a public link to test this agent"
              >
                <Share2 className="h-4 w-4" />
                Share
              </Button>
              {shareOpen ? (
                <div
                  className="absolute right-0 top-full z-50 mt-2 w-80 rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-md"
                  data-testid="share-panel"
                >
                  <p className="text-sm font-medium">Share this agent</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Anyone with the link can run it — they won&apos;t see your canvas.
                  </p>
                  {shareError ? (
                    <p className="mt-3 text-sm text-destructive" data-testid="share-error">
                      Couldn&apos;t create a link. Try again.
                    </p>
                  ) : (
                    <div className="mt-3 flex gap-2">
                      <input
                        readOnly
                        value={shareBusy ? "Creating link…" : shareUrl}
                        onFocus={(e) => e.currentTarget.select()}
                        aria-label="Share link"
                        data-testid="share-url"
                        className="h-8 min-w-0 flex-1 rounded-md border border-border bg-muted px-2 text-xs outline-none"
                      />
                      <Button
                        size="sm"
                        onClick={copyShareLink}
                        disabled={shareBusy || !shareToken}
                        data-testid="share-copy"
                      >
                        {shareCopied ? "Copied ✓" : "Copy"}
                      </Button>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}
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
            <AssistantPanel
              getCurrentGraph={getCurrentGraph}
              snapshot={snapshotCanvas}
              applyGraph={applyAssistantGraph}
              restore={restoreCanvas}
            />
          </aside>
        ) : null}

        <div className="relative flex-1" data-testid="canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={handleEdgesChange}
            onNodeDragStart={onNodeDragStart}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={() => setSelectedId(null)}
            nodeTypes={nodeTypes}
            fitView
          >
            {/* Subtle grey dots — visible as texture (Railway-style), not bright specks. */}
            <Background gap={22} size={1} color="#4a4a52" />
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
                <CodeView getGraph={getGraph} name={name} />
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

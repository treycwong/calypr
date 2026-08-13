"use client";

import {
  addEdge,
  Background,
  type Connection,
  type Edge,
  type Node,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  SelectionMode,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./canvas.css";
import {
  Blocks,
  Bookmark,
  BotMessageSquare,
  Cable,
  Images,
  LayoutTemplate,
  type LucideIcon,
  MessageSquare,
  PanelLeftClose,
  PanelRightClose,
  PanelRightOpen,
  Share2,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import type { GraphSpec } from "@calypr/dsl";

import { CalyprMark } from "@/components/brand/CalyprMark";
import {
  AssistantPanel,
  type CanvasSnapshot,
} from "@/components/canvas/AssistantPanel";
import { CanvasToolbar, type CanvasTool } from "@/components/canvas/CanvasToolbar";
import { CodeView } from "@/components/canvas/CodeView";
import { NODE_STYLE } from "@/components/canvas/node-style";
import { ConfigPanel } from "@/components/canvas/ConfigPanel";
import { nodeTypes } from "@/components/canvas/nodes";
import { PALETTE_DND_TYPE, Palette } from "@/components/canvas/Palette";
import { Playground } from "@/components/canvas/Playground";
import { SavedPromptsPanel } from "@/components/canvas/SavedPromptsPanel";
import { MediaTab } from "@/components/canvas/playground/MediaTab";
import { SettingsPanel } from "@/components/canvas/SettingsPanel";
import { TemplatesPanel } from "@/components/canvas/TemplatesPanel";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import {
  createAgent,
  createShare,
  getAgent,
  getWorkspace,
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
  type NodeStatus,
} from "@/lib/graph";

/** True when the keystroke belongs to a form control rather than the canvas. Every canvas hotkey
 *  checks this first — the bare V/H tool keys would otherwise be unusable in the AI assistant.
 *  `<select>` counts too: letters there jump to a matching option, and the config panel is full
 *  of them. */
function isTypingTarget(el: EventTarget | null) {
  const t = el as HTMLElement | null;
  if (!t) return false;
  return (
    t.tagName === "INPUT" ||
    t.tagName === "TEXTAREA" ||
    t.tagName === "SELECT" ||
    t.isContentEditable
  );
}

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
      // The active tab used to be a bare `bg-muted`, which barely separated from the rail on this
      // dark ground. The ring gives it an edge without introducing a second accent colour.
      className={`flex h-10 w-10 items-center justify-center rounded-lg transition ${
        active
          ? "bg-muted text-foreground ring-1 ring-border"
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
      }`}
    >
      <Icon className="h-5 w-5" />
    </button>
  );
}

/** Width of the rail-selected left panel, in pixels — must equal the `w-60` on the `<aside>`.
 *  The canvas reads it to cancel the sideways shift when the panel opens or closes. */
const LEFT_PANEL_PX = 240;

/** Panel titles live in the shell, not in the panels — see the header comment below. Keyed by
 *  the rail tab, and worded to match the rail's own tooltips. */
const PANEL_TITLES = {
  blocks: "Blocks",
  templates: "Templates",
  prompts: "Saved prompts",
  settings: "Connectors",
  ai: "AI assistant",
  media: "Media",
} as const;

function CanvasInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Arrow vs hand. Drives React Flow's drag props below, and the pane cursor via `canvas-pan`.
  const [tool, setTool] = useState<CanvasTool>("select");
  const { zoomIn, zoomOut, screenToFlowPosition, getViewport, setViewport } = useReactFlow();
  const [showPlayground, setShowPlayground] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const { toast } = useToast();
  const [templates, setTemplates] = useState<Template[]>([]);
  // The single rail-driven left panel — one tab at a time (or null = closed). Clicking the
  // active tab again closes it (full-width canvas).
  const [activePanel, setActivePanel] = useState<
    "blocks" | "templates" | "prompts" | "settings" | "ai" | "media" | null
  >("blocks");
  const togglePanel = (
    p: "blocks" | "templates" | "prompts" | "settings" | "ai" | "media",
  ) =>
    setActivePanel((cur) => (cur === p ? null : p));
  // Bumped whenever a run generates a file, so the Media panel refreshes without polling.
  const [mediaTick, setMediaTick] = useState(0);
  // The persistent right panel switches between node Properties and generated Code.
  const [rightTab, setRightTab] = useState<"properties" | "code">("properties");
  // Closed until something is selected. A node click opens it; a click on empty canvas puts it
  // away again. The header toggle is the way back to Code with nothing selected.
  const [rightOpen, setRightOpen] = useState(false);
  // Entitlement tier from the API (`free|beta|plus`); `free` until it loads, so a beta-only
  // surface never flashes for someone who isn't entitled to it.
  const [plan, setPlan] = useState("free");
  const [signedInAs, setSignedInAs] = useState<string | null>(null);
  // This cycle's credit allowance, shown in the header. `null` until it loads (and on any
  // failure), which renders nothing — an allowance we couldn't read must not display as "0 left".
  const [credits, setCredits] = useState<{
    allowance: number;
    remaining: number;
    used: number;
  } | null>(null);
  // The saved agent this canvas is editing: id (null until first save) + its name. Save creates
  // once then updates in place, so re-saving never duplicates.
  const [agentId, setAgentId] = useState<string | null>(null);
  // Whether `?agent=` has been resolved yet. History is scoped per project, so listing before
  // this is known would briefly show the wrong project's conversations.
  const [agentResolved, setAgentResolved] = useState(false);
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

  // Keep the graph visually still when the left panel opens or closes.
  //
  // The canvas is a flex child, so collapsing the panel widens it *leftwards* — its origin moves,
  // and with the viewport transform unchanged every node slides 240px across the screen. You hit
  // Hide panel to see more of the canvas and the canvas jumped out from under you. Compensating
  // the viewport by exactly the panel's width cancels the shift: the graph stays where your eyes
  // left it, and the extra room appears on the side you opened.
  //
  // `useLayoutEffect` so the correction lands in the same paint as the resize — an ordinary
  // effect shows one frame of the jump. Runs only on the *transition*, not on tab switches,
  // which keep the panel open and the width identical.
  const panelOpen = activePanel !== null;
  const wasPanelOpen = useRef(panelOpen);
  useLayoutEffect(() => {
    if (wasPanelOpen.current === panelOpen) return;
    wasPanelOpen.current = panelOpen;
    const vp = getViewport();
    setViewport({ ...vp, x: vp.x + (panelOpen ? -LEFT_PANEL_PX : LEFT_PANEL_PX) });
  }, [panelOpen, getViewport, setViewport]);

  // Name the browser tab after the project, so a window holding several agents is navigable by
  // its tabs.
  //
  // Neither obvious approach works alone. Route `metadata` is resolved on the server once per
  // navigation, so it can't follow a rename you type into the header. And a plain mount effect
  // gets overwritten: Next **streams** metadata, so the route's own `<title>` lands *after*
  // hydration — the title flicked to the project name and back. (Rendering a `<title>` from here
  // fares no better: React hoists it into `<head>`, but the browser reads the *first* title
  // element and the streamed one is already there.)
  //
  // So: assign `document.title`, which writes through to whichever element the browser is
  // reading, and keep watching `<head>` to re-assert it if the streamed metadata replaces it
  // later. The guard makes our own write a no-op, so the observer can't loop.
  useEffect(() => {
    const wanted = name.trim() ? `${name.trim()} · Calypr` : "Calypr";
    const apply = () => {
      if (document.title !== wanted) document.title = wanted;
    };
    apply();
    const observer = new MutationObserver(apply);
    observer.observe(document.head, { subtree: true, childList: true, characterData: true });
    return () => observer.disconnect();
  }, [name]);


  // The workspace's entitlement tier, for gating beta features (the round-trip Code editor), and
  // its credit balance for the header. Failure falls back to `free` — a gate that can't be read
  // stays shut.
  const refreshWorkspace = useCallback(() => {
    getWorkspace()
      .then((w) => {
        setPlan(w.plan);
        setSignedInAs(w.signed_in_as ?? null);
        setCredits(w.credits ?? null);
      })
      .catch(() => setPlan("free"));
  }, []);

  useEffect(() => {
    refreshWorkspace();
  }, [refreshWorkspace]);

  // Open an existing agent when arriving via /canvas?agent=<id> (from the dashboard), so Save
  // updates that agent rather than creating a new one.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("agent");
    // Both paths mark the scope resolved through a callback rather than synchronously in the
    // effect body — a sync setState here is a cascading render, and the lint rule is right.
    const resolved = () => setAgentResolved(true);
    // Nothing to fetch: a fresh canvas already knows its scope (no project).
    if (!id) {
      void Promise.resolve().then(resolved);
      return;
    }
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
      })
      // Resolved either way: a project that failed to load still has a known scope (none), and
      // leaving History waiting forever would be worse than showing it empty.
      .finally(resolved);
  }, [setNodes, setEdges, toast]);

  /** Put a block on the canvas. `position` comes from a drag-and-drop; without one the block is
   *  appended to the right of the last, which is what a click from the palette does.
   *
   *  **Nothing is wired automatically.** Adding a block used to also connect it to the previously
   *  added one, which was a guess that happened to be right for a straight chain and wrong for
   *  every branch — and once blocks can be dropped anywhere, "the previous one" stops meaning
   *  anything spatially. Connections are drawn by hand, from a node's handle. */
  const addNode = useCallback(
    (type: CalyprNodeType, position?: { x: number; y: number }) => {
      record();
      const index = ++counter.current;
      const id = `${type}-${index}`;
      const node: Node<NodeData> = {
        id,
        type,
        // Flow left → right: a clicked block lands to the right of the previous one.
        position: position ?? { x: 80 + index * 240, y: 300 },
        data: { config: { ...DEFAULT_CONFIG[type] } },
      };
      setNodes((nds) => [...nds, node]);
      lastNodeId.current = id;
      setSelectedId(id);
    },
    [record, setNodes],
  );

  // Drag-and-drop from the Blocks palette. The palette puts the block type on the dataTransfer
  // (see `PALETTE_DND_TYPE`); this turns the drop point into canvas coordinates so the block
  // lands exactly where it was released, at whatever pan and zoom the canvas is at.
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, []);
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const type = e.dataTransfer.getData(PALETTE_DND_TYPE) as CalyprNodeType;
      // Ignore anything that isn't one of ours — a file, a dragged link, a selection.
      if (!type || !(type in DEFAULT_CONFIG)) return;
      // The drop point is the pointer, and a node renders from its top-left corner, so offset by
      // roughly half a card to drop it under the cursor rather than beside it.
      const at = screenToFlowPosition({ x: e.clientX, y: e.clientY });
      addNode(type, { x: at.x - 84, y: at.y - 24 });
    },
    [screenToFlowPosition, addNode],
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
  // Clicking a node reveals its properties; clicking the empty canvas puts the panel away, so an
  // unselected canvas isn't 320px of "Select a node to edit its properties."
  const onNodeClick = useCallback((_: unknown, node: Node) => {
    setSelectedId(node.id);
    // Always lands on Properties: clicking a node *is* the request to see that node. (Only a
    // click on empty canvas leaves the Code tab alone — see `onPaneClick`, where there is no
    // such signal and closing mid-read would just be rude.)
    setRightTab("properties");
    setRightOpen(true);
  }, []);
  const onPaneClick = useCallback(() => {
    setSelectedId(null);
    // Code isn't about the selection, so deselecting must not close it mid-read.
    if (rightTab === "properties") setRightOpen(false);
  }, [rightTab]);
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

  // Every canvas hotkey, in one listener: V/H switch tool, ⌘/Ctrl+Z undoes, ⌘/Ctrl+Shift+Z (or
  // Ctrl+Y) redoes, +/− zoom. All ignored while typing in a field.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return;
      const mod = e.metaKey || e.ctrlKey;
      const key = e.key.toLowerCase();

      if (mod && (key === "z" || key === "y")) {
        e.preventDefault();
        if (key === "y" || e.shiftKey) redo();
        else undo();
        return;
      }
      // Zoom accepts the key with or without the modifier: "+" alone is the design-tool
      // convention, ⌘+ is the browser one (and needs preventDefault to stop page zoom).
      if (key === "+" || key === "=") {
        e.preventDefault();
        zoomIn({ duration: 150 });
        return;
      }
      if (key === "-" || key === "_") {
        e.preventDefault();
        zoomOut({ duration: 150 });
        return;
      }
      // Bare tool keys only — ⌘V is paste.
      if (mod || e.altKey) return;
      if (key === "v") setTool("select");
      else if (key === "h") setTool("pan");
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo, zoomIn, zoomOut]);
  // Replace the canvas with a graph produced elsewhere — the AI assistant, or the reverse
  // round-trip's "Apply to canvas". Records an undo point first, so either is reversible.
  const applyGraphToCanvas = useCallback(
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

  // --- Live run animation ----------------------------------------------------
  // Per-node run status, driven by node events streamed from the Playground. Kept out of the
  // canvas node state so it never persists into the saved graph or the undo history — it's
  // injected only into the decorated arrays handed to <ReactFlow> below.
  const [runStatus, setRunStatus] = useState<Record<string, NodeStatus>>({});
  const onNodeEvent = useCallback((nodeId: string, phase: "start" | "end") => {
    setRunStatus((prev) => {
      const next = { ...prev };
      if (phase === "start") {
        // The prior active node has finished once the next one begins.
        for (const k in next) if (next[k] === "active") next[k] = "done";
        next[nodeId] = "active";
      } else if (next[nodeId] === "active") {
        next[nodeId] = "done";
      }
      return next;
    });
  }, []);
  const onRunReset = useCallback((opts?: { error?: boolean }) => {
    if (opts?.error) {
      // Freeze the run where it stopped, flagging the node that was executing.
      setRunStatus((prev) => {
        const next = { ...prev };
        for (const k in next) if (next[k] === "active") next[k] = "error";
        return next;
      });
    } else {
      setRunStatus({});
    }
  }, []);

  // Overlay run status onto nodes, and animate/colour the connector feeding each running or
  // finished node. Untouched objects keep their identity so React Flow re-renders minimally.
  const decoratedNodes = useMemo(
    () =>
      nodes.map((n) =>
        runStatus[n.id] ? { ...n, data: { ...n.data, status: runStatus[n.id] } } : n,
      ),
    [nodes, runStatus],
  );
  // A wire takes the colour of the block it *leaves*, so you can trace what feeds what on a graph
  // too big to read label by label. Run state still wins: an active or finished edge is carrying
  // information about right now, which outranks where it came from. Those two states are CSS
  // classes, so the tint has to be withheld rather than overridden — an inline `stroke` would
  // beat the class and the run colour would never show.
  const edgeColor = useMemo(() => {
    const byId = new Map(nodes.map((n) => [n.id, n.type as CalyprNodeType | undefined]));
    return (source: string) => {
      const type = byId.get(source);
      return type ? NODE_STYLE[type]?.edge : undefined;
    };
  }, [nodes]);
  const decoratedEdges = useMemo(
    () =>
      edges.map((e) => {
        const s = runStatus[e.target];
        if (s === "active") return { ...e, animated: true, className: "edge-active" };
        if (s === "done") return { ...e, className: "edge-done" };
        const stroke = edgeColor(e.source);
        return stroke ? { ...e, style: { ...e.style, stroke, strokeWidth: 2 } } : e;
      }),
    [edges, runStatus, edgeColor],
  );

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            aria-label="Calypr — back to dashboard"
            title="Back to dashboard"
            className="rounded-md transition-colors"
          >
            {/* No chip behind the mark — it sits straight on the header. The only affordance is
                the hover wash, so it has to be visible enough to read as a target. */}
            <span className="flex h-7 w-7 items-center justify-center rounded-md text-foreground transition-colors hover:bg-white/10">
              <CalyprMark className="h-4 w-4" />
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
          {credits && credits.allowance > 0 ? (
            <Link
              href="/dashboard/settings"
              data-testid="nav-credits"
              // Same reason the Settings meter drops its denominator when the balance exceeds
              // the allowance: after a mid-month downgrade, "0 of 100 used" is a strange way to
              // describe holding 1,999.
              title={
                credits.remaining > credits.allowance
                  ? `${credits.remaining.toLocaleString()} credits left, carried from a previous plan (this plan grants ${credits.allowance.toLocaleString()} a month)`
                  : `${credits.used.toLocaleString()} of ${credits.allowance.toLocaleString()} credits used this cycle`
              }
              className={`rounded-md px-2 py-1 text-xs tabular-nums transition hover:bg-muted ${
                credits.remaining === 0 ? "text-destructive" : "text-muted-foreground"
              }`}
            >
              <span data-testid="nav-credits-remaining">
                {credits.remaining.toLocaleString()}
              </span>
              <span className="hidden sm:inline"> credits left</span>
            </Link>
          ) : null}
          {/* Undo/Redo used to sit here. They live in the canvas toolbar now — next to the tool
              and zoom controls they belong with, and within reach of the canvas you're editing. */}
          {/* The right panel now opens on a node click and closes on a canvas click, so this is
              the way back to it — and the only way to reach the Code tab with nothing selected. */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setRightOpen((o) => !o)}
            aria-label={rightOpen ? "Hide properties panel" : "Show properties panel"}
            aria-pressed={rightOpen}
            title={rightOpen ? "Hide properties panel" : "Show properties panel"}
            data-testid="toggle-right-panel"
          >
            {rightOpen ? (
              <PanelRightClose className="h-4 w-4" />
            ) : (
              <PanelRightOpen className="h-4 w-4" />
            )}
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
            // Outline when closed, so it sits level with Save and Share; solid white when the
            // playground is open. It used to be the other way round, which made Chat the loudest
            // thing in the header at exactly the moment it had nothing to do with.
            variant={showPlayground ? "default" : "outline"}
            onClick={() =>
              setShowPlayground((s) => {
                if (s) setRunStatus({}); // closing the playground clears any lingering run glow
                return !s;
              })
            }
            data-testid="toggle-playground"
          >
            {/* One label in both states. It used to read "Try it" / "Stop", but "Stop" here only
                ever closed the panel — and now that Send becomes a real Stop mid-generation,
                two different Stops on one screen meaning two different things is a trap. The
                open/closed state is carried by the button's variant instead. */}
            <MessageSquare className="h-4 w-4" />
            Chat
          </Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Slim icon rail: each tab drives the single left panel — one at a time. */}
        <aside className="flex w-13 shrink-0 flex-col items-center gap-1.5 border-r border-border py-2">
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
          <RailButton
            icon={Bookmark}
            label="Saved prompts"
            active={activePanel === "prompts"}
            onClick={() => togglePanel("prompts")}
            testid="tab-prompts"
          />
          <RailButton
            icon={Cable}
            label="Connectors"
            active={activePanel === "settings"}
            onClick={() => togglePanel("settings")}
            testid="tab-connectors"
          />
          <RailButton
            icon={BotMessageSquare}
            label="AI assistant"
            active={activePanel === "ai"}
            onClick={() => togglePanel("ai")}
            testid="toggle-assistant"
          />
          {/* Media sits with the workspace-level tools rather than in the Playground, because
              it is workspace-scoped: every file this workspace's runs have generated, not just
              the current conversation's. History stays in the Playground for the opposite
              reason — a transcript only means anything next to the chat it belongs to. */}
          <RailButton
            icon={Images}
            label="Media"
            active={activePanel === "media"}
            onClick={() => togglePanel("media")}
            testid="toggle-media"
          />
        </aside>

        {/* The single rail-selected left panel. One shell for every tab: the width used to be set
            per tab (w-52 / w-72 / w-80), so the canvas jumped sideways every time you switched
            rails. `w-60` (240px) is the shared width — narrow enough to leave the canvas the room,
            wide enough that the two-column tile grids and the Connectors rows still read.
            `LEFT_PANEL_PX` below must track it: the canvas compensates its viewport by exactly
            this many pixels when the panel opens or closes. */}
        {activePanel ? (
          <aside
            className="flex w-60 shrink-0 flex-col border-r border-border"
            data-testid={
              activePanel === "ai"
                ? "assistant"
                : activePanel === "media"
                  ? "media-panel"
                  : undefined
            }
          >
            {/* One header for every tab, so the title and the hide button share a baseline and
                the panels stop each styling their own. h-11 matches the Playground header on the
                far side of the canvas — the two are level when both are open. */}
            <div className="flex h-11 shrink-0 items-center justify-between gap-2 border-b border-border px-3">
              <span className="truncate text-xs font-medium tracking-wide uppercase">
                {PANEL_TITLES[activePanel]}
              </span>
              <button
                type="button"
                onClick={() => setActivePanel(null)}
                title="Hide panel"
                aria-label="Hide panel"
                data-testid="hide-panel"
                className="-mr-1 shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            </div>
            {/* `min-h-0` so the panels that scroll internally (chat, media) size to the shell
                instead of growing past it. The chat panels bring their own padding because
                their scroll region has to run edge to edge. */}
            <div
              className={`min-h-0 flex-1 ${
                activePanel === "blocks" ||
                activePanel === "templates" ||
                activePanel === "prompts" ||
                activePanel === "settings"
                  ? "rail-scroll overflow-auto p-3"
                  : ""
              }`}
            >
              {activePanel === "blocks" ? <Palette onAdd={addNode} /> : null}
              {activePanel === "templates" ? (
                <TemplatesPanel templates={templates} onLoad={loadTemplate} />
              ) : null}
              {activePanel === "prompts" ? <SavedPromptsPanel /> : null}
              {activePanel === "settings" ? <SettingsPanel /> : null}
              {/* `mediaTick` refetches when a run generates a file while this panel is open. */}
              {activePanel === "media" ? <MediaTab refreshKey={mediaTick} /> : null}
              {activePanel === "ai" ? (
                <AssistantPanel
                  getCurrentGraph={getCurrentGraph}
                  snapshot={snapshotCanvas}
                  applyGraph={applyGraphToCanvas}
                  restore={restoreCanvas}
                />
              ) : null}
            </div>
          </aside>
        ) : null}

        <div className="relative flex-1" data-testid="canvas">
          <ReactFlow
            nodes={decoratedNodes}
            edges={decoratedEdges}
            onNodesChange={handleNodesChange}
            onEdgesChange={handleEdgesChange}
            onNodeDragStart={onNodeDragStart}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            fitView
            // Tool-driven pointer behaviour. Arrow: left-drag marquees, nodes drag. Hand:
            // left-drag pans and nodes are pinned, so you can't shove a node while repositioning
            // the view. Holding Space pans in either mode (React Flow's default
            // `panActivationKeyCode`), which is the escape hatch for a one-off pan.
            panOnDrag={tool === "pan"}
            selectionOnDrag={tool === "select"}
            selectionMode={SelectionMode.Partial}
            nodesDraggable={tool === "select"}
            // Figma/weavy scrolling: the wheel moves the canvas, ⌘/ctrl+wheel and pinch zoom
            // (`zoomOnPinch` defaults on, and React Flow routes ctrl+wheel through it).
            panOnScroll
            zoomOnScroll={false}
            className={tool === "pan" ? "canvas-pan" : undefined}
            // Same call the template mini-maps already make — the badge is chrome we don't want
            // sitting over the canvas corner.
            proOptions={{ hideAttribution: true }}
          >
            {/* Subtle grey dots — visible as texture (Railway-style), not bright specks. */}
            <Background gap={22} size={1} color="#4a4a52" />
            {/* Replaces React Flow's stock <Controls /> and <MiniMap />: one horizontal bar
                carrying the tool switch, history and zoom. Centred on the bottom edge rather than
                cornered, so it stays equidistant from both side panels as they open and close. */}
            <Panel position="bottom-center">
              <CanvasToolbar
                tool={tool}
                onToolChange={setTool}
                canUndo={past.length > 0}
                canRedo={future.length > 0}
                onUndo={undo}
                onRedo={redo}
              />
            </Panel>
          </ReactFlow>
        </div>

        {/* Right panel: Properties (selected node) or generated Code — replaced by the
            playground while it's running, rather than stacking alongside it. */}
        {showPlayground || !rightOpen ? null : (
        <aside className="flex w-80 shrink-0 flex-col border-l border-border" data-testid="right-panel">
          <div className="flex gap-1 border-b border-border px-3 pt-2">
            <button
              type="button"
              data-testid="tab-properties"
              onClick={() => setRightTab("properties")}
              className={`-mb-px border-b-2 px-3 py-1.5 text-sm transition ${
                rightTab === "properties"
                  ? "border-foreground text-foreground"
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
                  ? "border-foreground text-foreground"
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
                <CodeView
                  getGraph={getGraph}
                  name={name}
                  applyGraph={applyGraphToCanvas}
                  plan={plan}
                  email={signedInAs}
                />
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
            <Playground
              getGraph={getGraph}
              agentId={agentId ?? undefined}
              scopeReady={agentResolved}
              onAssetGenerated={() => setMediaTick((n) => n + 1)}
              onNodeEvent={onNodeEvent}
              onRunReset={onRunReset}
              onRunFinished={refreshWorkspace}
            />
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

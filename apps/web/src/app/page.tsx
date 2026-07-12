import {
  ArrowRight,
  Boxes,
  Code2,
  GitBranch,
  Play,
  ShieldCheck,
  Sparkles,
  Star,
  Workflow,
} from "lucide-react";
import Link from "next/link";

import { HeroAscii } from "@/components/landing/HeroAscii";
import { buttonVariants } from "@/components/ui/button";

// ── small building blocks ───────────────────────────────────────────────────

function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden className="text-foreground">
        <line x1="5" y1="5" x2="5" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
        <line x1="5" y1="5" x2="15" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
        <circle cx="5" cy="5" r="2.4" fill="currentColor" />
        <circle cx="5" cy="15" r="2.4" fill="currentColor" opacity="0.55" />
        <circle cx="15" cy="15" r="2.4" fill="currentColor" opacity="0.8" />
      </svg>
      <span className="font-mono text-sm font-medium tracking-tight">calypr</span>
    </span>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/40 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
      {children}
    </span>
  );
}

// A monochrome echo of the real canvas: dotted grid + connected nodes.
function CanvasPreview() {
  const node =
    "rounded-md border border-border bg-card/80 px-3 py-2 shadow-[0_1px_0_0_rgba(255,255,255,0.04)] backdrop-blur";
  const dot = "h-1.5 w-1.5 rounded-full bg-foreground";
  return (
    <div className="dotted relative overflow-hidden rounded-xl border border-border bg-background/60">
      {/* faux window chrome */}
      <div className="flex items-center gap-1.5 border-b border-border px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full border border-border" />
        <span className="h-2.5 w-2.5 rounded-full border border-border" />
        <span className="h-2.5 w-2.5 rounded-full border border-border" />
        <span className="ml-3 font-mono text-[11px] text-muted-foreground">react-agent · canvas</span>
      </div>

      <div className="relative grid place-items-center px-6 py-12 sm:py-16">
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full text-border"
          aria-hidden
        >
          <line x1="50%" y1="27%" x2="50%" y2="43%" stroke="currentColor" strokeWidth="1.5" />
          <line x1="50%" y1="57%" x2="50%" y2="73%" stroke="currentColor" strokeWidth="1.5" />
          <line
            x1="62%"
            y1="50%"
            x2="78%"
            y2="50%"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
        </svg>

        <div className="relative flex flex-col items-center gap-6">
          <div className={node}>
            <div className="flex items-center gap-2">
              <span className={`${dot} opacity-60`} />
              <span className="text-xs font-medium">Input</span>
            </div>
          </div>

          <div className="relative">
            <div className={`${node} ring-1 ring-border`}>
              <div className="flex items-center gap-2">
                <span className={dot} />
                <span className="text-xs font-medium">Agent</span>
              </div>
              <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                model_based · gpt-4o-mini
              </div>
            </div>
            {/* tools branch */}
            <div className="absolute left-[112%] top-1/2 -translate-y-1/2">
              <div className={node}>
                <div className="flex items-center gap-2">
                  <span className={`${dot} opacity-70`} />
                  <span className="text-xs font-medium">Tools</span>
                </div>
                <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">web_search</div>
              </div>
            </div>
            <span className="absolute left-[104%] top-[34%] font-mono text-[9px] text-muted-foreground">
              tools
            </span>
          </div>

          <div className={node}>
            <div className="flex items-center gap-2">
              <span className={`${dot} opacity-80`} />
              <span className="text-xs font-medium">Output</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── content ───────────────────────────────────────────────────────────────

const PILLARS = [
  {
    icon: ShieldCheck,
    title: "No ceiling",
    body: "Every graph compiles to standalone Python (LangGraph) you own. Hit a limit? Drop into a Custom Code node — it round-trips verbatim.",
  },
  {
    icon: Boxes,
    title: "Composable nodes",
    body: "Input, Agent, Tools, Router, Evaluator, Memory, Responder/Revisor. Wire them into anything from a simple reflex to full Reflexion.",
  },
  {
    icon: Play,
    title: "Run it live",
    body: "Stream your agent in the playground. The built-in fake model needs no API key — bring OpenAI or Anthropic when you're ready.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Draw the graph",
    body: "Start from a template, or drop nodes and connect them. The canvas is just state — nodes and edges.",
  },
  {
    n: "02",
    title: "Run & inspect",
    body: "Chat with it in the playground. Watch tokens stream and tool calls fire, turn by turn.",
  },
  {
    n: "03",
    title: "Own the code",
    body: "Open the Code view and copy idiomatic LangGraph. Zero Calypr dependency, zero lock-in.",
  },
];

const TEMPLATES = [
  ["Simple reflex", "Reacts to the latest input."],
  ["Model-based", "Remembers the conversation."],
  ["Goal-based", "Plans toward a goal."],
  ["Utility-based", "Generates N, keeps the best."],
  ["Reflection", "Critiques and revises itself."],
  ["Learning", "Adapts from feedback."],
  ["ReAct", "Reasons and calls tools in a loop."],
  ["Reflexion", "Researches, then self-revises."],
];

const CODE = `"""ReAct Agent — generated by Calypr. Owns no Calypr dependency."""

def node_agent(state: State) -> dict:
    """Model-based agent: respond using the full conversation state."""
    model = init_chat_model("gpt-4o-mini", temperature=0.7).bind_tools([web_search])
    messages = state.get("messages") or []
    reply = model.invoke([SystemMessage(content=system), *messages])
    return {"messages": [reply]}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("agent", node_agent)
    graph.add_node("tools", ToolNode([web_search]))
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "out"})
    graph.add_edge("tools", "agent")
    return graph.compile()`;

// ── page ────────────────────────────────────────────────────────────────────

export default function Home() {
  const primaryBtn = buttonVariants({ size: "lg" });
  const ghostBtn = buttonVariants({ size: "lg", variant: "outline" });

  return (
    <div className="relative flex min-h-full flex-col">
      {/* atmospheric grayscale glow */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />

      {/* nav */}
      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/70 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-5">
          <Wordmark />
          <nav className="hidden items-center gap-7 font-mono text-xs text-muted-foreground md:flex">
            <a href="#how" className="transition-colors hover:text-foreground">
              How it works
            </a>
            <a href="#templates" className="transition-colors hover:text-foreground">
              Templates
            </a>
            <a href="#code" className="transition-colors hover:text-foreground">
              The code
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <Link
              href="/sign-in"
              className={buttonVariants({ variant: "ghost", size: "sm" })}
            >
              Sign in
            </Link>
            <Link href="/canvas" className={buttonVariants({ size: "sm" })}>
              Open canvas
            </Link>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative">
        {/* generative agent-graph backdrop, framed away from the text by a radial mask */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden [mask-image:radial-gradient(105%_75%_at_50%_42%,transparent_18%,black_60%)]"
        >
          <HeroAscii />
        </div>
        <div className="relative mx-auto w-full max-w-6xl px-5 pt-20 pb-10 sm:pt-28">
        <div className="flex flex-col items-center text-center">
          <div className="animate-in fade-in slide-in-from-bottom-3 duration-700">
            <Eyebrow>
              <Sparkles className="h-3 w-3" /> prompt → canvas → code
            </Eyebrow>
          </div>
          <h1 className="animate-in fade-in slide-in-from-bottom-4 mt-6 max-w-3xl text-balance text-4xl font-semibold leading-[1.05] tracking-tight duration-700 sm:text-6xl">
            Design AI agents visually.
            <br />
            <span className="text-muted-foreground">Leave with the code.</span>
          </h1>
          <p className="animate-in fade-in slide-in-from-bottom-4 mt-6 max-w-xl text-pretty text-base leading-relaxed text-muted-foreground delay-100 duration-700 sm:text-lg">
            Calypr is a no-ceiling agent builder. Drag nodes onto a canvas, run them live,
            and export idiomatic LangGraph — Python you&rsquo;d actually merge.
          </p>
          <div className="animate-in fade-in slide-in-from-bottom-4 mt-8 flex flex-wrap items-center justify-center gap-3 delay-200 duration-700">
            <Link href="/canvas" className={primaryBtn}>
              Open the canvas <ArrowRight className="h-4 w-4" />
            </Link>
            <a href="#code" className={ghostBtn}>
              See the generated code
            </a>
          </div>
        </div>

        <div className="animate-in fade-in slide-in-from-bottom-6 mx-auto mt-16 max-w-4xl delay-300 duration-1000">
          <CanvasPreview />
        </div>

        <p className="mt-8 text-center font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          compiles to langgraph · openai · anthropic · postgres + pgvector
        </p>
        </div>
      </section>

      {/* pillars */}
      <section className="mx-auto w-full max-w-6xl px-5 py-16">
        <div className="grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-3">
          {PILLARS.map(({ icon: Icon, title, body }) => (
            <div key={title} className="bg-background p-7">
              <Icon className="h-5 w-5 text-foreground" />
              <h3 className="mt-4 text-base font-medium tracking-tight">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* how it works */}
      <section id="how" className="mx-auto w-full max-w-6xl px-5 py-16">
        <div className="max-w-2xl">
          <Eyebrow>
            <Workflow className="h-3 w-3" /> how it works
          </Eyebrow>
          <h2 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
            From idea to ownable agent, in three moves.
          </h2>
        </div>
        <div className="mt-10 grid gap-8 sm:grid-cols-3">
          {STEPS.map(({ n, title, body }) => (
            <div key={n} className="border-t border-border pt-5">
              <span className="font-mono text-sm text-muted-foreground">{n}</span>
              <h3 className="mt-3 text-lg font-medium tracking-tight">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* templates */}
      <section id="templates" className="mx-auto w-full max-w-6xl px-5 py-16">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <Eyebrow>
              <GitBranch className="h-3 w-3" /> start from a template
            </Eyebrow>
            <h2 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
              The agent ladder, ready to run.
            </h2>
            <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Eight archetypes from a single reflex up to tool-using ReAct and self-revising
              Reflexion. Load one, run it, read its code.
            </p>
          </div>
        </div>
        <div className="mt-10 grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
          {TEMPLATES.map(([name, desc]) => (
            <div key={name} className="group bg-background p-6 transition-colors hover:bg-card/60">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-muted-foreground">tpl</span>
                <span className="h-1.5 w-1.5 rounded-full bg-foreground opacity-40 transition-opacity group-hover:opacity-100" />
              </div>
              <h3 className="mt-6 text-base font-medium tracking-tight">{name}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* code showcase */}
      <section id="code" className="mx-auto w-full max-w-6xl px-5 py-16">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <Eyebrow>
              <Code2 className="h-3 w-3" /> the canvas is the code
            </Eyebrow>
            <h2 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
              Export Python you&rsquo;d actually merge.
            </h2>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-muted-foreground">
              Every node carries its own code generator, so the graph you draw projects to
              idiomatic LangGraph — grouped imports, a typed <code className="font-mono text-foreground">State</code>,
              one function per node, the canonical tool loop. A round-trip test proves the
              generated module runs identically to the canvas.
            </p>
            <Link href="/canvas" className={`${buttonVariants({ variant: "outline" })} mt-7`}>
              Open the Code view <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="overflow-hidden rounded-xl border border-border bg-card/40">
            <div className="flex items-center gap-1.5 border-b border-border px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full border border-border" />
              <span className="h-2.5 w-2.5 rounded-full border border-border" />
              <span className="h-2.5 w-2.5 rounded-full border border-border" />
              <span className="ml-3 font-mono text-[11px] text-muted-foreground">agent.py</span>
            </div>
            <pre className="overflow-x-auto p-5 font-mono text-[12px] leading-relaxed text-muted-foreground">
              <code>{CODE}</code>
            </pre>
          </div>
        </div>
      </section>

      {/* cta */}
      <section className="mx-auto w-full max-w-6xl px-5 py-20">
        <div className="dotted relative overflow-hidden rounded-2xl border border-border bg-card/30 px-8 py-16 text-center">
          <h2 className="mx-auto max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">
            From a prompt to an agent you own.
          </h2>
          <p className="mx-auto mt-4 max-w-md text-sm leading-relaxed text-muted-foreground">
            No black box. No lock-in. Draw it, run it, take the code with you.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/canvas" className={primaryBtn}>
              Open the canvas <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/sign-in" className={ghostBtn}>
              Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* footer */}
      <footer className="mt-auto border-t border-border">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-start justify-between gap-6 px-5 py-10 sm:flex-row sm:items-center">
          <div className="space-y-2">
            <Wordmark />
            <p className="font-mono text-[11px] text-muted-foreground">
              prompt → canvas → code · {new Date().getFullYear()}
            </p>
          </div>
          <div className="flex items-center gap-6 font-mono text-xs text-muted-foreground">
            <Link href="/canvas" className="transition-colors hover:text-foreground">
              Canvas
            </Link>
            <a href="#templates" className="transition-colors hover:text-foreground">
              Templates
            </a>
            <a
              href="https://github.com/treycwong/calypr"
              className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground"
            >
              <Star className="h-3.5 w-3.5" /> GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

/**
 * Static marketing data for the landing page.
 *
 * Deliberately a mirror, not a fetch: the real registry lives in
 * services/compiler/src/calypr_compiler/templates.py and is served by the Python API, but the
 * landing page is static and dependency-free — coupling `/` to the API being up would trade a
 * marketing page's availability for freshness nobody needs. Curated by hand from that file;
 * ids match the registry's `tpl-*` ids so the generative card art stays stable if we ever
 * link cards to the gallery.
 */

export type TemplateCategory =
  | "Study & revision"
  | "Images & audio"
  | "Research & analysis"
  | "Support & routing"
  | "Connected apps";

export type LandingTemplate = {
  id: string;
  name: string;
  blurb: string;
  category: TemplateCategory;
  /** "How it works", three beats — shown on the carousel slide. */
  how: [string, string, string];
};

/** The agent-architecture ladder — rendered as mono chips. "Reflexion" must appear exactly
 * here and nowhere else on the page: the landing E2E asserts a single exact-text match. */
export const FRAMEWORK_NAMES = [
  "Simple reflex",
  "Model-based",
  "Goal-based",
  "Utility-based",
  "Reflection",
  "Learning",
  "ReAct",
  "MCP ReAct",
  "Reflexion",
  "RAG",
] as const;

export const CATEGORY_ORDER: TemplateCategory[] = [
  "Study & revision",
  "Images & audio",
  "Research & analysis",
  "Support & routing",
  "Connected apps",
];

/** The six templates the landing carousel walks through — the best spread across categories. */
export const FEATURED_TEMPLATES: LandingTemplate[] = [
  {
    id: "tpl-market-research",
    name: "Market research report",
    blurb:
      "A newsroom in a graph: specialist agents turn one question into a finished, critiqued report.",
    category: "Research & analysis",
    how: [
      "A Knowledge node retrieves sources for your question",
      "Analyst and writer agents draft the report, section by section",
      "A critic reviews and an editor polishes — you get the final cut",
    ],
  },
  {
    id: "tpl-study-notion",
    name: "Notion study quiz",
    blurb: "Your own Notion pages become a scored drill — connect once, revise anywhere.",
    category: "Connected apps",
    how: [
      "Connect Notion in Settings; an MCP tool reads your pages",
      "An agent turns what it finds into interactive quiz cards",
      "Answer in the playground — it keeps score as you go",
    ],
  },
  {
    id: "tpl-image-to-3d",
    name: "Image to 3D",
    blurb: "Describe an object and watch it become a downloadable 3D model.",
    category: "Images & audio",
    how: [
      "An agent sharpens your description into an image prompt",
      "The Image node renders it with gpt-image",
      "The 3D node lifts the render into a GLB mesh on fal",
    ],
  },
  {
    id: "tpl-quiz-me",
    name: "Quiz me on anything",
    blurb: "A tutor that never runs out of questions — multiple choice, scored as you go.",
    category: "Study & revision",
    how: [
      "Tell the agent a topic — any topic",
      "It emits interactive quiz cards straight into the chat",
      "Your score tallies in the playground as you answer",
    ],
  },
  {
    id: "tpl-customer-support",
    name: "Customer support automation",
    blurb: "Triage, answer, escalate — the full support loop on one canvas.",
    category: "Support & routing",
    how: [
      "A Router reads each ticket and classifies it",
      "A Knowledge node retrieves FAQ and past-ticket context",
      "A responder answers; edge cases escalate to a human",
    ],
  },
  {
    id: "tpl-translate-speak",
    name: "Translate & speak (EN → 中文)",
    blurb: "Type English, hear Mandarin — translation and speech in one wire.",
    category: "Images & audio",
    how: [
      "An agent translates each message into Chinese",
      "The transcript shows both languages side by side",
      "A Voice node speaks the translation aloud",
    ],
  },
];

/** Frontier models available on the canvas. Wordmarks only — no logo assets. */
export const MODEL_PROVIDERS = [
  { name: "OpenAI", detail: "GPT-4o · GPT-4o mini" },
  { name: "Anthropic", detail: "Claude Opus 4.8 · Sonnet 4.5" },
  { name: "Moonshot", detail: "kimi-k3" },
  { name: "fal", detail: "trellis · image → 3D" },
  { name: "Google", detail: "Gemini", soon: true },
] as const;

export const TOOL_PROVIDERS = [
  { name: "Tavily", detail: "web search" },
  { name: "Unsplash", detail: "image search" },
  { name: "MCP", detail: "any server" },
  { name: "HTTP", detail: "any API" },
] as const;

export const CONNECTORS = [
  { name: "Notion", detail: "workspace" },
  { name: "GitHub", detail: "repos & issues" },
  { name: "Custom MCP", detail: "bring your own" },
] as const;

"""Starter graphs for the canvas gallery — two kinds, both valid GraphSpecs that compile,
run, and round-trip to ownable Python (and double as a compile/run test matrix):

- **Frameworks**: agent-architecture patterns (the Russell & Norvig ladder + ReAct/Reflexion)
  — choose *how* an agent thinks.
- **Templates**: multi-agent systems for real use cases (research, support, contract review)
  — sequential pipelines of role-prompted Agent nodes; choose *what* to build."""

from __future__ import annotations

from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel

_BASE_STATE = [
    StateChannel(key="input", type="string", reducer=Reducer.last),
    StateChannel(key="messages", type="messages", reducer=Reducer.append),
    StateChannel(key="output", type="string", reducer=Reducer.last),
]
_MEMORY_STATE = [*_BASE_STATE, StateChannel(key="memory", type="list", reducer=Reducer.append)]
_EVAL_STATE = [
    *_BASE_STATE,
    StateChannel(key="score", type="number", reducer=Reducer.last),
    StateChannel(key="rationale", type="string", reducer=Reducer.last),
]
# Retrieval (RAG): a Knowledge node writes retrieved chunks here; an Agent reads them via
# `{{ state.context }}`. (The Knowledge node declares this channel too — graph_channels unions
# them — but listing it keeps the starter self-documenting, like Reflexion's revision_count.)
_RAG_STATE = [*_BASE_STATE, StateChannel(key="context", type="string", reducer=Reducer.last)]


def _input() -> NodeSpec:
    return NodeSpec(
        id="in", type="input", config={"input_channel": "input", "target_channel": "messages"}
    )


def _output(source: str = "messages") -> NodeSpec:
    return NodeSpec(
        id="out", type="output", config={"source_channel": source, "output_channel": "output"}
    )


def _agent(agent_type: str, **config) -> NodeSpec:
    return NodeSpec(
        id="agent",
        type="agent",
        config={
            "agent_type": agent_type,
            "model": "gpt-4o-mini",
            "input_channel": "messages",
            "output_channel": "messages",
            **config,
        },
    )


def _role_agent(node_id: str, system_prompt: str, label: str | None = None) -> NodeSpec:
    """One Agent in a multi-agent pipeline: model-based (reads the full running transcript)
    with a role-specific system prompt. The next agent sees everything written before it.
    `label` names the agent on the canvas (defaults to the id, e.g. orchestrator → Orchestrator)."""
    return NodeSpec(
        id=node_id,
        type="agent",
        config={
            "model": "gpt-4o-mini",
            "label": label or node_id.replace("_", " ").title(),
            "system_prompt": system_prompt,
            "input_channel": "messages",
            "output_channel": "messages",
        },
    )


def _knowledge(node_id: str = "knowledge") -> NodeSpec:
    """A Knowledge (RAG) node: retrieve the top chunks for the latest query into `context`.
    Defaults to the `pgvector` source (your own Postgres + a collection); switch to the keyless
    `demo` source to retrieve deterministically on the canvas without a database."""
    return NodeSpec(
        id=node_id, type="retriever", config={"source": "pgvector", "top_k": 4}
    )


def _chain(*node_ids: str) -> list[EdgeSpec]:
    return [
        EdgeSpec(id=f"e{i}", source=a, target=b)
        for i, (a, b) in enumerate(zip(node_ids, node_ids[1:], strict=False), start=1)
    ]


def simple_reflex() -> GraphSpec:
    return GraphSpec(
        id="tpl-simple-reflex",
        name="Simple reflex",
        description="Reacts to the latest input — no memory. The thinnest agent.",
        state=_BASE_STATE,
        nodes=[_input(), _agent("simple_reflex"), _output()],
        edges=_chain("in", "agent", "out"),
        entry="in",
    )


def model_based() -> GraphSpec:
    return GraphSpec(
        id="tpl-model-based",
        name="Model-based reflex",
        description="Remembers the conversation via an explicit Memory buffer.",
        state=_MEMORY_STATE,
        nodes=[
            _input(),
            NodeSpec(
                id="memory",
                type="memory",
                config={
                    "operation": "buffer",
                    "input_channel": "messages",
                    "memory_channel": "memory",
                },
            ),
            _agent("model_based"),
            _output(),
        ],
        edges=_chain("in", "memory", "agent", "out"),
        entry="in",
    )


def goal_based() -> GraphSpec:
    return GraphSpec(
        id="tpl-goal-based",
        name="Goal-based",
        description="Plans toward a stated goal, then acts.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            _agent("goal_based", goal="Resolve the user's request completely."),
            _output(),
        ],
        edges=_chain("in", "agent", "out"),
        entry="in",
    )


def utility_based() -> GraphSpec:
    return GraphSpec(
        id="tpl-utility-based",
        name="Utility-based",
        description="Generates several answers, keeps the best, and scores it with an Evaluator.",
        state=_EVAL_STATE,
        nodes=[
            _input(),
            _agent("utility_based", num_candidates=3),
            NodeSpec(
                id="eval",
                type="evaluator",
                config={"model": "fake", "input_channel": "messages"},
            ),
            _output(),
        ],
        edges=_chain("in", "agent", "eval", "out"),
        entry="in",
    )


def reflection() -> GraphSpec:
    return GraphSpec(
        id="tpl-reflection",
        name="Reflection",
        description="Answers, then critiques and revises itself before replying.",
        state=_BASE_STATE,
        nodes=[_input(), _agent("reflection", max_reflections=2), _output()],
        edges=_chain("in", "agent", "out"),
        entry="in",
    )


def learning() -> GraphSpec:
    return GraphSpec(
        id="tpl-learning",
        name="Learning (experimental)",
        description="Summarises the conversation into memory and adapts from it.",
        state=_MEMORY_STATE,
        nodes=[
            _input(),
            NodeSpec(
                id="memory",
                type="memory",
                config={
                    "operation": "summary",
                    "model": "fake",
                    "input_channel": "messages",
                    "memory_channel": "memory",
                },
            ),
            _agent("learning"),
            _output(),
        ],
        edges=_chain("in", "memory", "agent", "out"),
        entry="in",
    )


def react() -> GraphSpec:
    return GraphSpec(
        id="tpl-react",
        name="ReAct",
        description="Reason + act: the agent calls tools (web search) in a loop, then answers.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            _agent(
                "model_based",
                system_prompt=(
                    "You are a research assistant. Use the web_search tool when you need "
                    "facts, then answer from what you found."
                ),
            ),
            NodeSpec(id="tools", type="tool", config={"provider": "demo_search"}),
            _output(),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="agent"),
            EdgeSpec(id="e2", source="agent", target="tools", condition="tools"),
            EdgeSpec(id="e3", source="agent", target="out", condition="respond"),
            EdgeSpec(id="e4", source="tools", target="agent"),  # the ReAct loop
        ],
        entry="in",
    )


def mcp_react() -> GraphSpec:
    return GraphSpec(
        id="tpl-mcp-react",
        name="MCP ReAct",
        description="ReAct over an MCP server: the agent calls any of the server's tools in a "
        "loop, then answers. Set the Tool node's MCP URL to your server.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            _agent(
                "model_based",
                system_prompt=(
                    "You are an assistant with access to an MCP server's tools. Use the "
                    "available tools to gather what you need, then answer from the results."
                ),
            ),
            NodeSpec(
                id="tools",
                type="tool",
                config={"provider": "mcp", "mcp_url": "", "mcp_transport": "streamable_http"},
            ),
            _output(),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="agent"),
            EdgeSpec(id="e2", source="agent", target="tools", condition="tools"),
            EdgeSpec(id="e3", source="agent", target="out", condition="respond"),
            EdgeSpec(id="e4", source="tools", target="agent"),  # the ReAct loop
        ],
        entry="in",
    )


def reflexion() -> GraphSpec:
    return GraphSpec(
        id="tpl-reflexion",
        name="Reflexion",
        description="Answer, then research and revise in a bounded loop (responder + revisor).",
        state=[
            *_BASE_STATE,
            StateChannel(key="revision_count", type="number", reducer=Reducer.last),
        ],
        nodes=[
            _input(),
            NodeSpec(id="responder", type="responder", config={"model": "fake"}),
            NodeSpec(id="tools", type="tool", config={"provider": "demo_search"}),
            NodeSpec(
                id="revisor",
                type="revisor",
                config={"model": "fake", "max_revisions": 2},
            ),
            _output(),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="responder"),
            EdgeSpec(id="e2", source="responder", target="tools"),
            EdgeSpec(id="e3", source="tools", target="revisor"),
            EdgeSpec(id="e4", source="revisor", target="tools", condition="revise"),
            EdgeSpec(id="e5", source="revisor", target="out", condition="done"),
        ],
        entry="in",
    )


def rag() -> GraphSpec:
    return GraphSpec(
        id="tpl-rag",
        name="RAG (retrieval)",
        description="Retrieve relevant context from a knowledge base, then answer grounded in it.",
        state=_RAG_STATE,
        nodes=[
            _input(),
            _knowledge(),
            _role_agent(
                "agent",
                "Answer the user's question using only the retrieved context below. If the "
                "context does not cover it, say so plainly.\n\nContext:\n{{ state.context }}",
            ),
            _output(),
        ],
        edges=_chain("in", "knowledge", "agent", "out"),
        entry="in",
    )


def routing() -> GraphSpec:
    return GraphSpec(
        id="tpl-routing",
        name="Summarize or translate",
        description="A Router reads each request and sends it to a summarizer or a translator.",
        state=[*_BASE_STATE, StateChannel(key="task_type", type="string", reducer=Reducer.last)],
        nodes=[
            _input(),
            NodeSpec(
                id="router",
                type="router",
                config={
                    "kind": "llm",
                    "model": "fake",
                    "input_channel": "messages",
                    "route_channel": "task_type",
                    "branches": [
                        {
                            "name": "summarize",
                            "when": "the user wants the text summarized or condensed",
                        },
                        {
                            "name": "translate",
                            "when": "the user wants the text translated into another language",
                        },
                    ],
                    "default": "summarize",
                },
            ),
            _role_agent(
                "summarize",
                "You are a summarizer. Produce a concise summary of the user's text.",
            ),
            _role_agent(
                "translate",
                "You are a translator. Translate the user's text as requested.",
            ),
            _output(),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="router"),
            EdgeSpec(id="e2", source="router", target="summarize", condition="summarize"),
            EdgeSpec(id="e3", source="router", target="translate", condition="translate"),
            EdgeSpec(id="e4", source="summarize", target="out"),
            EdgeSpec(id="e5", source="translate", target="out"),
        ],
        entry="in",
    )


# ── Use-case templates ───────────────────────────────────────────────────────
# Multi-agent systems for real tasks: a sequential pipeline of Agent nodes, each with a
# role-specific system prompt, where every stage reads the running transcript and adds to it.


def market_research() -> GraphSpec:
    return GraphSpec(
        id="tpl-market-research",
        name="Market research report",
        description="Retrieve sources, then specialist agents analyse, write, critique, and edit.",
        state=_RAG_STATE,
        nodes=[
            _input(),
            _knowledge(),
            _role_agent(
                "research",
                "You are a market research analyst. Using the retrieved sources below plus your "
                "own knowledge, summarise the key market trends, leading competitors, and recent "
                "news for the user's topic. Lead with concrete facts and figures."
                "\n\nSources:\n{{ state.context }}",
            ),
            _role_agent(
                "analysis",
                "You are a data analyst. Interpret the research above: identify numerical "
                "trends, growth patterns, and any anomalies or risks. Be quantitative and precise.",
            ),
            _role_agent(
                "writing",
                "You are a business writer. Using the research and analysis above, draft a "
                "structured, engaging market-research report (overview, trends, "
                "competition, outlook).",
            ),
            _role_agent(
                "critique",
                "You are an editorial critic. Review the draft above for logical consistency, "
                "completeness, and clarity. List specific, actionable improvements.",
            ),
            _role_agent(
                "editor",
                "You are a senior editor. Produce the final report by applying the critique, "
                "polishing grammar and style to publishing standard. Output only the "
                "finished report.",
            ),
            _output(),
        ],
        edges=_chain(
            "in", "knowledge", "research", "analysis", "writing", "critique", "editor", "out"
        ),
        entry="in",
    )


def customer_support() -> GraphSpec:
    return GraphSpec(
        id="tpl-customer-support",
        name="Customer support automation",
        description="Triage, retrieve FAQ/ticket knowledge, respond, and escalate.",
        state=_RAG_STATE,
        nodes=[
            _input(),
            _role_agent(
                "intent",
                "You are a support triage agent. Classify the user's request (billing, "
                "technical support, or general inquiry) and restate precisely what they need.",
            ),
            _knowledge(),
            _role_agent(
                "response",
                "You are a customer support specialist. Write a personalised reply that "
                "resolves the request using the retrieved knowledge below. Warm and concise."
                "\n\nKnowledge:\n{{ state.context }}",
            ),
            _role_agent(
                "escalation",
                "You are an escalation reviewer. Decide whether the issue is fully resolved. If "
                "not, summarise it for a human agent and note what is outstanding; "
                "otherwise confirm.",
            ),
            _output(),
        ],
        edges=_chain("in", "intent", "knowledge", "response", "escalation", "out"),
        entry="in",
    )


def contract_review() -> GraphSpec:
    return GraphSpec(
        id="tpl-contract-review",
        name="Legal contract review",
        description="Extract clauses, check compliance, flag risk, and summarise a contract.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            _role_agent(
                "clauses",
                "You are a legal analyst. Identify and extract the key clauses (parties, term, "
                "payment, liability, termination, IP, confidentiality) from the contract.",
            ),
            _role_agent(
                "compliance",
                "You are a compliance officer. Check the extracted clauses against common "
                "regulatory and policy requirements; flag anything non-compliant.",
            ),
            _role_agent(
                "risk",
                "You are a risk analyst. Flag ambiguous, one-sided, or high-risk terms, and "
                "explain the exposure each one creates.",
            ),
            _role_agent(
                "summary",
                "You are a legal summariser. Produce an executive summary highlighting the main "
                "concerns and their severity.",
            ),
            _role_agent(
                "memo",
                "You are a legal writer. Compile the findings above into a clean, formatted "
                "legal review memo with clear recommendations.",
            ),
            _output(),
        ],
        edges=_chain("in", "clauses", "compliance", "risk", "summary", "memo", "out"),
        entry="in",
    )


def image_generation() -> GraphSpec:
    """The thinnest image pipeline: a prompt in, a generated image out. The Image node streams a
    Markdown image the playground renders inline. Defaults to `gpt-image-2` (needs
    OPENAI_API_KEY) — switch the Image block to `fake` for a keyless 1×1 preview."""
    return GraphSpec(
        id="tpl-image-generation",
        name="Image generation",
        description="Turn each prompt into an image with gpt-image-2.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            NodeSpec(id="image", type="image", config={"model": "gpt-image-2"}),
            _output(),
        ],
        edges=_chain("in", "image", "out"),
        entry="in",
    )


def text_to_speech() -> GraphSpec:
    """The thinnest voice pipeline: text in, spoken audio out. The Voice node streams a Markdown
    audio link the playground renders as a player. Defaults to `gpt-4o-mini-tts` (needs
    OPENAI_API_KEY) — switch the Voice block to `fake` for a keyless silent-clip preview."""
    return GraphSpec(
        id="tpl-text-to-speech",
        name="Text to speech",
        description="Speak each message aloud with gpt-4o-mini-tts.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            NodeSpec(id="tts", type="tts", config={"model": "gpt-4o-mini-tts"}),
            _output(),
        ],
        edges=_chain("in", "tts", "out"),
        entry="in",
    )


def translate_and_speak() -> GraphSpec:
    """Translate English into Chinese, then speak it: Input → Agent (translator) → Voice → Output.
    The agent streams the 中文 transcript into the chat; the Voice node speaks that same
    translation and renders a player below it — two outputs from one pass. The translator prompt
    is output-only (no pinyin/explanations) because whatever the agent emits is exactly what gets
    spoken."""
    return GraphSpec(
        id="tpl-translate-speak",
        name="Translate & speak (EN → 中文)",
        description="Translate each message into Chinese, show the transcript, and speak it aloud.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            NodeSpec(
                id="translator",
                type="agent",
                config={
                    "model": "gpt-4o-mini",
                    "label": "Translator",
                    "system_prompt": (
                        "You are a professional English→Chinese translator. Translate the user's "
                        "message into Simplified Chinese (Mandarin). Output ONLY the translation "
                        "— no pinyin, no explanations, no quotes."
                    ),
                },
            ),
            NodeSpec(
                id="tts",
                type="tts",
                config={
                    "model": "gpt-4o-mini-tts",
                    "voice": "alloy",
                    "instructions": (
                        "native Mandarin Chinese pronunciation, clear and natural pacing"
                    ),
                },
            ),
            _output(),
        ],
        edges=_chain("in", "translator", "tts", "out"),
        entry="in",
    )


def _vision_reviewer(
    tpl_id: str, name: str, description: str, agent_label: str, system_prompt: str
) -> GraphSpec:
    """A vision-review pipeline: Input → Upload → Agent → Output. The Upload block brings the
    user's attached image into the conversation; the Agent's system prompt decides *how* the
    image is reviewed — that's the whole point of these templates sharing one shape."""
    return GraphSpec(
        id=tpl_id,
        name=name,
        description=description,
        state=_BASE_STATE,
        nodes=[
            _input(),
            NodeSpec(id="upload", type="upload", config={}),
            _role_agent("reviewer", system_prompt, label=agent_label),
            _output(),
        ],
        edges=_chain("in", "upload", "reviewer", "out"),
        entry="in",
    )


def label_reader() -> GraphSpec:
    return _vision_reviewer(
        "tpl-label-reader",
        "Label & receipt reader",
        "Attach a food label, receipt, or document photo and get the key facts extracted.",
        "Reviewer",
        "You are a document reviewer. Analyse the attached image — a nutrition label, receipt, "
        "or document photo — and extract the key facts as a short structured summary (use bullet "
        "points; include totals, dates, and named items verbatim). If no image is attached, say "
        "so plainly and ask for one.",
    )


def alt_text() -> GraphSpec:
    return _vision_reviewer(
        "tpl-alt-text",
        "Generate alt text",
        "Attach an image and get concise, screen-reader-ready alt text back.",
        "Alt-text writer",
        "Write concise, descriptive alt text for the attached image, for screen-reader users. "
        "One or two sentences, factual, no 'image of'/'picture of' prefix; include any visible "
        "text verbatim. Output only the alt text. If no image is attached, say so plainly.",
    )


def trip_planner() -> GraphSpec:
    """Orchestrator–Worker: an orchestrator frames the trip, four specialists work in parallel
    (fan-out), and a synthesizer merges their suggestions into one itinerary (fan-in). Workers
    append to `messages`, whose add_messages reducer makes the concurrent writes safe."""
    return GraphSpec(
        id="tpl-trip-planner",
        name="Trip itinerary planner",
        description="An orchestrator delegates to parallel specialists, then a synthesizer merges.",
        state=_BASE_STATE,
        nodes=[
            _input(),
            _role_agent(
                "orchestrator",
                "You are a trip-planning coordinator. Read the traveller's request and outline "
                "what each specialist (flights, lodging, activities, dining) should focus on.",
            ),
            _role_agent(
                "flights",
                "You are a flights specialist. Suggest flight options and routing for the trip "
                "described above.",
            ),
            _role_agent(
                "lodging",
                "You are a lodging specialist. Recommend places to stay that fit the trip.",
            ),
            _role_agent(
                "activities",
                "You are an activities specialist. Suggest things to see and do on the trip.",
            ),
            _role_agent(
                "dining",
                "You are a dining specialist. Recommend places to eat for the trip.",
            ),
            _role_agent(
                "synthesizer",
                "You are the lead planner. Combine the specialists' suggestions above into one "
                "clear, day-by-day itinerary.",
            ),
            _output(),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="orchestrator"),
            # fan-out: the orchestrator dispatches to four workers that run in parallel
            EdgeSpec(id="e2", source="orchestrator", target="flights"),
            EdgeSpec(id="e3", source="orchestrator", target="lodging"),
            EdgeSpec(id="e4", source="orchestrator", target="activities"),
            EdgeSpec(id="e5", source="orchestrator", target="dining"),
            # fan-in: every worker feeds the synthesizer (it waits for all of them)
            EdgeSpec(id="e6", source="flights", target="synthesizer"),
            EdgeSpec(id="e7", source="lodging", target="synthesizer"),
            EdgeSpec(id="e8", source="activities", target="synthesizer"),
            EdgeSpec(id="e9", source="dining", target="synthesizer"),
            EdgeSpec(id="e10", source="synthesizer", target="out"),
        ],
        entry="in",
    )


# Frameworks — the agent-architecture patterns (the Russell & Norvig ladder + ReAct/Reflexion),
# ordered simple→complex. Start here to choose *how* an agent thinks.
FRAMEWORKS: list[GraphSpec] = [
    simple_reflex(),
    model_based(),
    goal_based(),
    utility_based(),
    reflection(),
    learning(),
    react(),
    mcp_react(),
    reflexion(),
    rag(),
]

# Templates — multi-agent systems for real use cases. Start here to choose *what* to build.
TEMPLATES: list[GraphSpec] = [
    market_research(),
    customer_support(),
    contract_review(),
    routing(),
    trip_planner(),
    image_generation(),
    text_to_speech(),
    translate_and_speak(),
    label_reader(),
    alt_text(),
]

# Everything the canvas gallery offers.
STARTERS: list[GraphSpec] = [*FRAMEWORKS, *TEMPLATES]

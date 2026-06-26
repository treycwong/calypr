import importlib.util
import subprocess
import sys

import pytest
from calypr_codegen import generate_python
from calypr_compiler.golden import input_agent_output
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_nodes import NodeContext
from calypr_runtime import run


def _echo_graph() -> GraphSpec:
    """A deterministic Input -> CustomCode -> Output graph (no LLM) for round-trip proof."""
    return GraphSpec(
        id="echo",
        name="Echo Graph",
        state=[
            StateChannel(key="input", type="string", reducer=Reducer.last),
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(
                id="in",
                type="input",
                config={"input_channel": "input", "target_channel": "messages"},
            ),
            NodeSpec(
                id="transform",
                type="code",
                config={
                    "code": (
                        'last = state["messages"][-1]\n'
                        'return {"messages": [AIMessage(content="ECHO: " + last.content)]}'
                    ),
                    "imports": ["from langchain_core.messages import AIMessage"],
                },
            ),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "messages", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="transform"),
            EdgeSpec(id="e2", source="transform", target="out"),
        ],
        entry="in",
    )


def _import_generated(code: str, tmp_path):
    """Import the generated code as a real module (so forward-ref annotations resolve) —
    exactly how the engineer who owns the file would run it."""
    path = tmp_path / "calypr_generated_under_test.py"
    path.write_text(code)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


async def test_generated_code_matches_in_memory_run(tmp_path):
    """The round-trip's correctness floor: generated Python runs and produces the same
    output as our in-memory compile()+run() for the same graph."""
    graph = _echo_graph()

    in_memory = await run(graph, NodeContext(), "hello")
    assert in_memory["output"] == "ECHO: hello"

    module = _import_generated(generate_python(graph), tmp_path)
    generated = module.build_graph().invoke({"input": "hello"})

    assert generated["output"] == in_memory["output"] == "ECHO: hello"


def test_agent_graph_generates_idiomatic_langgraph():
    code = generate_python(input_agent_output(model="gpt-4o-mini"))
    assert "from langgraph.graph import END, START, StateGraph" in code
    assert "class State(TypedDict, total=False):" in code
    assert 'init_chat_model("gpt-4o-mini"' in code
    assert "def build_graph():" in code
    assert "graph.add_edge(START," in code
    # standalone: no Calypr import leaks into the owned code (attribution in the
    # docstring is fine — the engineer owns the file, depends only on langgraph/langchain).
    assert "import calypr" not in code
    assert "from calypr" not in code


def test_generated_code_is_ruff_clean():
    code = generate_python(input_agent_output(model="gpt-4o-mini"))
    fmt = subprocess.run(
        ["ruff", "format", "-"], input=code, capture_output=True, text=True
    )
    assert fmt.returncode == 0
    assert fmt.stdout == code, "generated code is not already ruff-formatted"
    check = subprocess.run(
        ["ruff", "check", "--stdin-filename", "generated.py", "-"],
        input=code,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout


def _branching_graph() -> GraphSpec:
    """Router → (uppercase | lowercase) → Output, branching on the input (no LLM)."""
    code_imports = ["from langchain_core.messages import AIMessage"]
    return GraphSpec(
        id="branch",
        name="Branching",
        state=[
            StateChannel(key="input", type="string", reducer=Reducer.last),
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(
                id="router",
                type="router",
                config={
                    "kind": "rules",
                    "input_channel": "input",
                    "branches": [
                        {"name": "shout", "when": '"!" in state["input"]'},
                        {"name": "calm", "when": "True"},
                    ],
                    "default": "calm",
                },
            ),
            NodeSpec(
                id="up",
                type="code",
                config={
                    "code": 'return {"messages": [AIMessage(content=state["input"].upper())]}',
                    "imports": code_imports,
                },
            ),
            NodeSpec(
                id="down",
                type="code",
                config={
                    "code": 'return {"messages": [AIMessage(content=state["input"].lower())]}',
                    "imports": code_imports,
                },
            ),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "messages", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="router", target="up", condition="shout"),
            EdgeSpec(id="e2", source="router", target="down", condition="calm"),
            EdgeSpec(id="e3", source="up", target="out"),
            EdgeSpec(id="e4", source="down", target="out"),
        ],
        entry="router",
    )


async def test_router_branches_and_round_trips(tmp_path):
    """Conditional control flow: routes correctly in-memory AND the generated code
    (with add_conditional_edges) runs identically on both branches."""
    graph = _branching_graph()
    ctx = NodeContext()

    assert (await run(graph, ctx, "Hello!"))["output"] == "HELLO!"
    assert (await run(graph, ctx, "Hello"))["output"] == "hello"

    code = generate_python(graph)
    assert "add_conditional_edges" in code
    module = _import_generated(code, tmp_path)
    assert module.build_graph().invoke({"input": "Hello!"})["output"] == "HELLO!"
    assert module.build_graph().invoke({"input": "Hello"})["output"] == "hello"


def _retriever_graph(source: str = "demo", **cfg) -> GraphSpec:
    """Input -> Knowledge(retriever) -> Output(context): a no-LLM RAG graph for round-trip proof."""
    return GraphSpec(
        id="rag",
        name="Retriever",
        state=[
            StateChannel(key="input", type="string", reducer=Reducer.last),
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="context", type="string", reducer=Reducer.last),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(
                id="in",
                type="input",
                config={"input_channel": "input", "target_channel": "messages"},
            ),
            NodeSpec(id="kb", type="retriever", config={"source": source, **cfg}),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "context", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="kb"),
            EdgeSpec(id="e2", source="kb", target="out"),
        ],
        entry="in",
    )


async def test_retriever_demo_round_trips(tmp_path):
    """RAG keystone: the keyless demo Knowledge node retrieves deterministically, and the
    generated module (a self-contained InMemoryVectorStore) retrieves the *same* chunks —
    so the exported RAG agent grounds on identical context."""
    graph = _retriever_graph("demo", top_k=3)

    in_memory = await run(graph, NodeContext(), "what is pgvector?")
    assert in_memory["output"]  # retrieved some context

    code = generate_python(graph)
    assert "InMemoryVectorStore" in code
    assert "DeterministicFakeEmbedding" in code
    module = _import_generated(code, tmp_path)
    generated = module.build_graph().invoke({"input": "what is pgvector?"})
    assert generated["output"] == in_memory["output"]


def test_retriever_pgvector_codegen_is_real_and_clean():
    """The pgvector source projects to an idiomatic PGVector retriever against the user's own
    Postgres + OpenAI key — owned code, no Calypr dependency."""
    code = generate_python(_retriever_graph("pgvector", collection="handbook", top_k=5))
    assert "from langchain_postgres import PGVector" in code
    assert "OpenAIEmbeddings(" in code
    assert 'os.environ["DATABASE_URL"]' in code
    assert 'collection_name="kb_handbook"' in code
    assert "import calypr" not in code and "from calypr" not in code

    fmt = subprocess.run(
        ["ruff", "format", "-"], input=code, capture_output=True, text=True
    )
    assert fmt.stdout == code, "pgvector codegen is not ruff-formatted"
    check = subprocess.run(
        ["ruff", "check", "--stdin-filename", "generated.py", "-"],
        input=code,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout


def test_agent_prompt_placeholder_substituted_in_codegen():
    """An Agent whose prompt uses `{{ state.context }}` (the RAG pattern) emits a runtime
    substitution in the generated code, so the exported agent fills in retrieved context
    rather than carrying a literal placeholder."""
    graph = GraphSpec(
        id="p",
        name="Prompt",
        state=[
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="context", type="string", reducer=Reducer.last),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(
                id="in",
                type="input",
                config={"input_channel": "input", "target_channel": "messages"},
            ),
            NodeSpec(
                id="ag",
                type="agent",
                config={
                    "model": "gpt-4o-mini",
                    "system_prompt": "Use it.\n\nContext:\n{{ state.context }}",
                },
            ),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "messages", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="ag"),
            EdgeSpec(id="e2", source="ag", target="out"),
        ],
        entry="in",
    )
    code = generate_python(graph)
    assert 'system.replace("{{ state.context }}", str(state.get("context", "")))' in code
    fmt = subprocess.run(
        ["ruff", "format", "-"], input=code, capture_output=True, text=True
    )
    assert fmt.stdout == code, "placeholder-substitution codegen is not ruff-formatted"


def _agent_graph(agent_type: str) -> GraphSpec:
    return GraphSpec(
        id="a",
        name="Agent",
        state=[
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(
                id="in",
                type="input",
                config={"input_channel": "input", "target_channel": "messages"},
            ),
            NodeSpec(
                id="ag",
                type="agent",
                config={
                    "agent_type": agent_type,
                    "model": "gpt-4o-mini",
                    "system_prompt": "Be helpful.",
                },
            ),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "messages", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="ag"),
            EdgeSpec(id="e2", source="ag", target="out"),
        ],
        entry="in",
    )


# Each preset emits a distinctive idiomatic construct in its generated Python.
_AGENT_MARKERS = {
    "simple_reflex": "isinstance(m, HumanMessage)",
    "model_based": "reply = model.invoke([SystemMessage",
    "goal_based": "reply = model.invoke([SystemMessage",
    "utility_based": "best = max(candidates, key=len)",
    "learning": "reply = model.invoke([SystemMessage",
    "reflection": "critique_prompt = (",
}


@pytest.mark.parametrize("agent_type,marker", list(_AGENT_MARKERS.items()))
def test_agent_type_codegen_is_clean_and_idiomatic(agent_type, marker):
    """Each agent_type generates its own idiomatic, ruff-clean Python (the code-quality
    bet extends across the whole agent ladder)."""
    code = generate_python(_agent_graph(agent_type))
    assert marker in code

    fmt = subprocess.run(
        ["ruff", "format", "-"], input=code, capture_output=True, text=True
    )
    assert fmt.stdout == code, f"{agent_type} codegen is not ruff-formatted"
    check = subprocess.run(
        ["ruff", "check", "--stdin-filename", "generated.py", "-"],
        input=code,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout


def _capability_graph(node_type: str, config: dict) -> GraphSpec:
    return GraphSpec(
        id="c",
        name="Capability",
        state=[
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
            StateChannel(key="score", type="number", reducer=Reducer.last),
            StateChannel(key="rationale", type="string", reducer=Reducer.last),
            StateChannel(key="memory", type="list", reducer=Reducer.append),
        ],
        nodes=[
            NodeSpec(
                id="in",
                type="input",
                config={"input_channel": "input", "target_channel": "messages"},
            ),
            NodeSpec(id="cap", type=node_type, config=config),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "messages", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="cap"),
            EdgeSpec(id="e2", source="cap", target="out"),
        ],
        entry="in",
    )


_CAPABILITY_CASES = [
    ("evaluator", {"model": "gpt-4o-mini"}, "match = re.search"),
    ("memory", {"operation": "buffer"}, '{"memory": [latest]}'),
    ("memory", {"operation": "summary", "model": "gpt-4o-mini"}, "long-term memory"),
]


@pytest.mark.parametrize("node_type,config,marker", _CAPABILITY_CASES)
def test_capability_node_codegen_is_clean(node_type, config, marker):
    """Evaluator + Memory generate idiomatic, ruff-clean Python too."""
    code = generate_python(_capability_graph(node_type, config))
    assert marker in code

    fmt = subprocess.run(
        ["ruff", "format", "-"], input=code, capture_output=True, text=True
    )
    assert fmt.stdout == code, f"{node_type}/{config} codegen is not ruff-formatted"
    check = subprocess.run(
        ["ruff", "check", "--stdin-filename", "generated.py", "-"],
        input=code,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout

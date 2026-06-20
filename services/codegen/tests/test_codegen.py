import importlib.util
import subprocess
import sys

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

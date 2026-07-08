from calypr_compiler.golden import input_agent_output
from calypr_model import FakeModelClient
from calypr_nodes import NodeContext
from calypr_runtime import run, run_stream
from langgraph.checkpoint.memory import InMemorySaver


async def test_golden_graph_runs_and_streams_tokens():
    """Phase 1 gate: draw nothing — load the golden Input → Agent → Output spec,
    compile it, run it against the (fake) model, and assert it streams a final reply."""
    spec = input_agent_output(model="fake")
    ctx = NodeContext(model=FakeModelClient(reply="Hello from Calypr"))

    events = [ev async for ev in run_stream(spec, ctx, "hi there")]

    streamed = "".join(e.text for e in events if e.type == "token")
    assert streamed == "Hello from Calypr"

    final = events[-1]
    assert final.type == "final"
    assert final.output == "Hello from Calypr"


async def test_usage_events_carry_node_id_and_model():
    """Phase A gate: usage events emitted during a run carry the enriching `node_id`
    (the compiler's contextvar wrapper) and `model` keys, so metering can attribute cost."""
    spec = input_agent_output(model="fake")
    ctx = NodeContext(model=FakeModelClient(reply="Hello from Calypr"))

    events = [ev async for ev in run_stream(spec, ctx, "hi there")]

    usage = [e.state for e in events if e.type == "usage"]
    assert usage, "expected at least one usage event"
    for u in usage:
        assert u["node_id"] == "agent"  # the golden spec's agent node id
        assert u["model"] == "fake"
        assert "input_tokens" in u and "output_tokens" in u


async def test_checkpointer_persists_state_across_turns():
    spec = input_agent_output(model="fake")
    ctx = NodeContext(model=FakeModelClient(reply="ok"))
    cp = InMemorySaver()
    thread = "thread-1"

    first = await run(spec, ctx, "first message", thread_id=thread, checkpointer=cp)
    second = await run(spec, ctx, "second message", thread_id=thread, checkpointer=cp)

    # The same thread accumulates history across runs (durable memory).
    assert len(second["messages"]) > len(first["messages"])

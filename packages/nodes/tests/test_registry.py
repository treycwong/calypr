from calypr_model import (
    FakeImageClient,
    FakeModelClient,
    FakeTTSClient,
    OpenAIImageClient,
    OpenAITTSClient,
)
from calypr_nodes import (
    AgentConfig,
    InputConfig,
    NodeContext,
    OutputConfig,
    all_node_types,
    image_model_for_node,
    model_for_node,
    parse_config,
    tts_model_for_node,
)
from calypr_nodes.agent import AgentNode
from calypr_nodes.input import InputNode
from calypr_nodes.output import OutputNode
from langchain_core.messages import AIMessage, HumanMessage


def test_builtin_nodes_registered():
    assert {"input", "agent", "output"} <= set(all_node_types())


def test_parse_config_validates_against_schema():
    cfg = parse_config("agent", {"model": "m", "system_prompt": "be nice"})
    assert isinstance(cfg, AgentConfig)
    assert cfg.model == "m"


async def test_input_node_seeds_messages_from_input():
    run = InputNode.compile(InputConfig(), NodeContext())
    update = await run({"input": "hello"})
    assert isinstance(update["messages"][0], HumanMessage)
    assert update["messages"][0].content == "hello"


async def test_agent_node_calls_model_and_appends_reply():
    ctx = NodeContext(model=FakeModelClient(reply="Hi there"))
    run = AgentNode.compile(AgentConfig(model="x"), ctx)
    update = await run({"messages": [HumanMessage(content="hello")]})
    assert isinstance(update["messages"][-1], AIMessage)
    assert update["messages"][-1].content == "Hi there"


async def test_output_node_extracts_last_message_text():
    run = OutputNode.compile(OutputConfig(), NodeContext())
    update = await run({"messages": [AIMessage(content="final answer")]})
    assert update["output"] == "final answer"


def test_model_for_node_prefers_injected_then_resolves_own():
    spy = FakeModelClient()
    # an injected client (e.g. a test double) always wins
    assert model_for_node(NodeContext(model=spy), "gpt-4o") is spy
    # otherwise each node resolves its own provider from its model id
    assert isinstance(model_for_node(NodeContext(), "fake"), FakeModelClient)


def test_image_model_for_node_prefers_injected_then_resolves_own(monkeypatch):
    spy = FakeImageClient()
    assert image_model_for_node(NodeContext(image_model=spy), "gpt-image-2") is spy
    # no override + a real model id -> the real (billed) client, not Fake — this is the
    # production default the Image node falls through to when nothing injects a test double.
    # (A dummy key only satisfies the SDK's client construction check — no network call is made.)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-construction-only")
    assert isinstance(image_model_for_node(NodeContext(), "gpt-image-2"), OpenAIImageClient)
    assert isinstance(image_model_for_node(NodeContext(), "fake"), FakeImageClient)


def test_tts_model_for_node_prefers_injected_then_resolves_own(monkeypatch):
    spy = FakeTTSClient()
    assert tts_model_for_node(NodeContext(tts_model=spy), "gpt-4o-mini-tts") is spy
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-construction-only")
    assert isinstance(tts_model_for_node(NodeContext(), "gpt-4o-mini-tts"), OpenAITTSClient)
    assert isinstance(tts_model_for_node(NodeContext(), "fake"), FakeTTSClient)

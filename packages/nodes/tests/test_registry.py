from calypr_model import FakeModelClient
from calypr_nodes import (
    AgentConfig,
    InputConfig,
    NodeContext,
    OutputConfig,
    all_node_types,
    parse_config,
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

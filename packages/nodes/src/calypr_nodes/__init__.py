"""Calypr node registry + built-in node types (CLAUDE-PLAN.md §5).

Importing this package registers the built-in node types as a side effect.
"""

from calypr_nodes.agent import AgentConfig, AgentNode
from calypr_nodes.code import CodeConfig, CodeNode
from calypr_nodes.evaluator import EvaluatorConfig, EvaluatorNode
from calypr_nodes.input import InputConfig, InputNode
from calypr_nodes.memory import MemoryConfig, MemoryNode
from calypr_nodes.output import OutputConfig, OutputNode
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    CodegenContext,
    NodeContext,
    NodeFn,
    NodeMeta,
    all_node_types,
    get_node,
    graph_channels,
    has_node,
    model_for_node,
    parse_config,
    register,
)
from calypr_nodes.responder import ResponderConfig, ResponderNode
from calypr_nodes.retriever import RetrieverConfig, RetrieverNode
from calypr_nodes.revisor import RevisorConfig, RevisorNode
from calypr_nodes.router import Branch, RouterConfig, RouterNode
from calypr_nodes.tool import ToolConfig, ToolsNode

__all__ = [
    # registry
    "BaseNode",
    "CodeFragment",
    "CodegenContext",
    "NodeContext",
    "NodeFn",
    "NodeMeta",
    "register",
    "get_node",
    "has_node",
    "all_node_types",
    "parse_config",
    "graph_channels",
    "model_for_node",
    # node types + configs
    "InputNode",
    "InputConfig",
    "AgentNode",
    "AgentConfig",
    "OutputNode",
    "OutputConfig",
    "CodeNode",
    "CodeConfig",
    "RouterNode",
    "RouterConfig",
    "Branch",
    "EvaluatorNode",
    "EvaluatorConfig",
    "MemoryNode",
    "MemoryConfig",
    "ToolsNode",
    "ToolConfig",
    "ResponderNode",
    "ResponderConfig",
    "RevisorNode",
    "RevisorConfig",
    "RetrieverNode",
    "RetrieverConfig",
]

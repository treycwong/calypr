"""Calypr node registry + built-in node types (CLAUDE-PLAN.md §5).

Importing this package registers the built-in node types as a side effect.
"""

from calypr_nodes.agent import AgentConfig, AgentNode
from calypr_nodes.code import CodeConfig, CodeNode
from calypr_nodes.input import InputConfig, InputNode
from calypr_nodes.output import OutputConfig, OutputNode
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    all_node_types,
    get_node,
    has_node,
    parse_config,
    register,
)

__all__ = [
    # registry
    "BaseNode",
    "CodeFragment",
    "NodeContext",
    "NodeFn",
    "NodeMeta",
    "register",
    "get_node",
    "has_node",
    "all_node_types",
    "parse_config",
    # node types + configs
    "InputNode",
    "InputConfig",
    "AgentNode",
    "AgentConfig",
    "OutputNode",
    "OutputConfig",
    "CodeNode",
    "CodeConfig",
]

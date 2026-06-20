"""Calypr model layer — a thin, provider-agnostic ModelClient (CLAUDE-PLAN.md §10)."""

from calypr_model.anthropic_client import AnthropicModelClient
from calypr_model.base import ModelClient
from calypr_model.events import Done, StreamEvent, TextDelta, ToolCall, Usage
from calypr_model.factory import model_for, provider_of
from calypr_model.fake import FakeModelClient
from calypr_model.messages import Msg, Role, ToolCallRequest
from calypr_model.openai_client import OpenAIModelClient

__all__ = [
    "ModelClient",
    "Msg",
    "Role",
    "ToolCallRequest",
    "TextDelta",
    "ToolCall",
    "Usage",
    "Done",
    "StreamEvent",
    "FakeModelClient",
    "AnthropicModelClient",
    "OpenAIModelClient",
    "model_for",
    "provider_of",
]

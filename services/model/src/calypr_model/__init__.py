"""Calypr model layer — a thin, provider-agnostic ModelClient (CLAUDE-PLAN.md §10)."""

from calypr_model.anthropic_client import AnthropicModelClient
from calypr_model.base import ModelClient
from calypr_model.events import Done, StreamEvent, TextDelta, ToolCall, Usage
from calypr_model.factory import (
    image_model_for,
    model_for,
    provider_of,
    tts_model_for,
)
from calypr_model.fake import FakeModelClient
from calypr_model.image_client import FakeImageClient, ImageResult, OpenAIImageClient
from calypr_model.messages import Msg, Role, ToolCallRequest
from calypr_model.openai_client import OpenAIModelClient
from calypr_model.tts_client import FakeTTSClient, OpenAITTSClient, TTSResult

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
    "OpenAIImageClient",
    "FakeImageClient",
    "ImageResult",
    "OpenAITTSClient",
    "FakeTTSClient",
    "TTSResult",
    "model_for",
    "image_model_for",
    "tts_model_for",
    "provider_of",
]

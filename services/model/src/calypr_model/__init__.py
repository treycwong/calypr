"""Calypr model layer — a thin, provider-agnostic ModelClient (CLAUDE-PLAN.md §10)."""

from calypr_model.anthropic_client import AnthropicModelClient
from calypr_model.base import ModelClient
from calypr_model.events import Done, StreamEvent, TextDelta, ToolCall, Usage
from calypr_model.factory import (
    image_model_for,
    mesh_model_for,
    model_for,
    provider_of,
    tts_model_for,
    video_model_for,
)
from calypr_model.fake import FakeModelClient
from calypr_model.image_client import FakeImageClient, ImageResult, OpenAIImageClient
from calypr_model.mesh_client import (
    DEFAULT_MESH_SIMPLIFY,
    DEFAULT_TEXTURE_SIZE,
    MESH_MODELS,
    TEXTURE_SIZES,
    FakeMeshClient,
    FalMeshClient,
    MeshResult,
)
from calypr_model.messages import Msg, Role, ToolCallRequest
from calypr_model.openai_client import OpenAIModelClient
from calypr_model.tts_client import FakeTTSClient, OpenAITTSClient, TTSResult
from calypr_model.video_client import (
    DEFAULT_VIDEO_ASPECT_RATIO,
    DEFAULT_VIDEO_DURATION,
    DEFAULT_VIDEO_MODEL,
    DEFAULT_VIDEO_RESOLUTION,
    VIDEO_ASPECT_RATIOS,
    VIDEO_DURATIONS,
    VIDEO_MODELS,
    VIDEO_RESOLUTIONS,
    FakeVideoClient,
    FalVideoClient,
    VideoResult,
    is_image_to_video,
    priced_model,
)

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
    "FalMeshClient",
    "FakeMeshClient",
    "MeshResult",
    "MESH_MODELS",
    "TEXTURE_SIZES",
    "DEFAULT_TEXTURE_SIZE",
    "DEFAULT_MESH_SIMPLIFY",
    "OpenAITTSClient",
    "FakeTTSClient",
    "TTSResult",
    "FalVideoClient",
    "FakeVideoClient",
    "VideoResult",
    "VIDEO_MODELS",
    "VIDEO_RESOLUTIONS",
    "VIDEO_DURATIONS",
    "VIDEO_ASPECT_RATIOS",
    "DEFAULT_VIDEO_MODEL",
    "DEFAULT_VIDEO_RESOLUTION",
    "DEFAULT_VIDEO_DURATION",
    "DEFAULT_VIDEO_ASPECT_RATIO",
    "is_image_to_video",
    "priced_model",
    "model_for",
    "image_model_for",
    "mesh_model_for",
    "tts_model_for",
    "video_model_for",
    "provider_of",
]

"""Vision support in the model layer: `Msg.images` and the OpenAI adapter's multimodal payload.
Anthropic intentionally drops images in v1 — its adapter must keep working on text content."""

from __future__ import annotations

from calypr_model import Msg, Role
from calypr_model.anthropic_client import _to_anthropic
from calypr_model.openai_client import _to_openai


def test_openai_user_message_with_images_builds_content_parts():
    url = "https://store.public.blob.vercel-storage.com/uploads/a.png"
    out = _to_openai([Msg(role=Role.user, content="what is this?", images=[url])], "")
    assert out == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "what is this?"},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        }
    ]


def test_openai_image_only_message_omits_empty_text_part():
    url = "data:image/png;base64,AAAA"
    out = _to_openai([Msg(role=Role.user, content="", images=[url])], "")
    assert out[0]["content"] == [{"type": "image_url", "image_url": {"url": url}}]


def test_openai_text_only_message_stays_a_plain_string():
    out = _to_openai([Msg(role=Role.user, content="hello")], "")
    assert out == [{"role": "user", "content": "hello"}]


def test_anthropic_adapter_ignores_images_without_breaking():
    msg = Msg(role=Role.user, content="hi", images=["https://x/y.png"])
    out = _to_anthropic([msg])
    assert out == [{"role": "user", "content": "hi"}]  # text preserved, image dropped (v1)

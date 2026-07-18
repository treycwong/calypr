"""Upload node: turn uploaded image URLs (seeded into state by the run request) into a
multimodal HumanMessage a vision Agent can see; a clean no-op when nothing is attached."""

from __future__ import annotations

import ast

from calypr_nodes import NodeContext, UploadConfig
from calypr_nodes._convert import images_of, lc_to_msgs
from calypr_nodes.upload import UploadNode
from langchain_core.messages import HumanMessage


async def test_upload_appends_multimodal_message():
    run = UploadNode.compile(UploadConfig(), NodeContext())
    urls = ["https://s.public.blob.vercel-storage.com/uploads/a.png"]
    update = await run({"images": urls})
    msg = update["messages"][0]
    assert isinstance(msg, HumanMessage)
    assert msg.content == [{"type": "image_url", "image_url": {"url": urls[0]}}]


async def test_upload_no_images_is_noop():
    run = UploadNode.compile(UploadConfig(), NodeContext())
    assert await run({}) == {}
    assert await run({"images": []}) == {}


async def test_upload_caps_at_max_images():
    run = UploadNode.compile(UploadConfig(max_images=2), NodeContext())
    update = await run({"images": [f"https://s/{i}.png" for i in range(5)]})
    assert len(update["messages"][0].content) == 2


async def test_upload_message_reaches_msg_images_via_bridge():
    """The full chain the Agent uses: Upload's message → lc_to_msgs → Msg.images."""
    run = UploadNode.compile(UploadConfig(), NodeContext())
    update = await run({"images": ["https://s/a.png"]})
    msgs = lc_to_msgs([HumanMessage(content="look"), *update["messages"]])
    assert msgs[0].images == []  # plain text untouched
    assert msgs[1].images == ["https://s/a.png"]


def test_images_of_plain_content_is_empty():
    assert images_of(HumanMessage(content="hello")) == []


def test_upload_codegen_is_valid_python():
    frag = UploadNode.codegen(UploadConfig(), "node_upload")
    ast.parse("\n".join(frag.imports) + "\n" + frag.function)
    assert "image_url" in frag.function

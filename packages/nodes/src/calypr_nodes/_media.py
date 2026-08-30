"""Where a media node's *input* comes from — shared by the 3D, Video and Image blocks.

These helpers started in `mesh.py` (the image resolvers) and `image.py` (the prompt
resolver). They moved here the moment a second block needed them, rather than being copied: the
Video node reads an image exactly the way the 3D node does and a prompt exactly the way the Image
node does, and a second copy of "find the most recent picture in this channel" is a rule that would
be fixed in one place and stay broken in the other.

The contract each of them encodes is the reason `Upload → 3D`, `Image → 3D` and the same two
wirings into Video all work without any producer node widening its `writes()`.
"""

from __future__ import annotations

import re
from typing import Any

from calypr_nodes._convert import text_of

#: The canonical message channel every node defaults to — where the Image node leaves its
#: `![alt](url)`. Hardcoded rather than exposed as config: it is the *fallback* source, and a
#: second channel field would be a knob with one sensible value.
MESSAGES = "messages"

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*(\S+?)\s*\)")

#: Where the Input block leaves the run's Prompt Instructions — criteria a user writes once, at the
#: entry, that every generative block downstream folds into its prompt.
#:
#: **A channel, not the user's message, and that is the whole design.** Prepending the criteria to
#: the `HumanMessage` would reach every block, which sounds like the feature and is actually the
#: bug: the Voice block would *read the criteria aloud*, the Router's classifier would branch on
#: them, and every Knowledge block would retrieve against user-text-plus-criteria. A separate
#: channel means only the blocks that opt in ever see it, so the field is safe on all 31 starters
#: without one of them being edited (`graph_channels` unions node-declared channels).
#:
#: Hardcoded rather than a configurable `*_channel` field, for the reason `MESSAGES` above is: a
#: name both ends must agree on is a knob with one sensible value, and making it configurable only
#: creates a way to wire Input to a channel the Image block isn't reading.
#:
#: Named `prompt_instructions`, not `instructions`, because `TTSConfig.instructions` already exists
#: and means something else entirely — tone and pacing for the voice.
PROMPT_INSTRUCTIONS = "prompt_instructions"


def md_image_url(text: str) -> str:
    """The last Markdown image URL in `text`, or "". Last rather than first: a transcript
    accumulates, and a media block should build from the most recently generated image."""
    matches = _MD_IMAGE.findall(text or "")
    return matches[-1] if matches else ""


#: Where a media block records which node produced a message, so a consumer downstream can tell
#: one branch's output from another's.
#:
#: In `additional_kwargs` rather than the message's `name` field on purpose: `name` is part of the
#: provider wire format and would be sent to OpenAI/Anthropic if the message later reached an LLM
#: node, where it means something else entirely. `lc_to_msgs` never copies `additional_kwargs`, so
#: this tag cannot leak into a provider call.
PRODUCER_KEY = "calypr_node"


def tag_producer(node_id: str | None) -> dict:
    """`additional_kwargs` marking a generated message with the node that made it."""
    return {PRODUCER_KEY: node_id} if node_id else {}


def _produced_by(item: Any) -> str:
    kwargs = getattr(item, "additional_kwargs", None)
    return kwargs.get(PRODUCER_KEY, "") if isinstance(kwargs, dict) else ""


def image_url_from(value: Any, sources: set[str] | None = None) -> str:
    """Resolve an image URL from a channel: a plain string, a list of URLs (the `images` channel
    the Upload node seeds), or a message list carrying a Markdown image. Most recent wins.

    `sources` is the set of node ids **upstream of the caller**. When given, an image produced by
    one of those nodes is preferred over any other, which is what makes a fan-out behave the way
    its wires read.

    Without it — the original behaviour — two Image blocks feeding two Video blocks both resolved
    to whichever image landed in `messages` last, because the channel is shared and the edge
    between a producer and its consumer carried control flow but no data. Both clips came from the
    same picture, silently, and the graph looked correct on the canvas.

    The unfiltered scan remains as the fallback and is not a leftover: `Upload → Video` puts URLs
    on the `images` channel with no producing node to match, and a hand-written graph may have no
    tagged producer at all. Only when an upstream node really did produce an image does the filter
    have an answer, and then it is the right one.
    """
    if isinstance(value, str):
        return value.strip() if value.strip().startswith(("http", "data:")) else ""
    if not isinstance(value, list):
        return ""
    if sources:
        for item in reversed(value):
            if _produced_by(item) in sources and (url := md_image_url(text_of(item))):
                return url
    for item in reversed(value):
        if isinstance(item, str) and item.strip():
            return item.strip()
        url = md_image_url(text_of(item))
        if url:
            return url
    return ""


def prompt_from(value: Any) -> str:
    """Resolve the prompt: a plain string channel, or the last message's text."""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return text_of(value[-1])
    return ""


def text_prompt_from(value: Any) -> str:
    """Resolve a prompt from a channel, **skipping messages that are only a media embed**.

    `prompt_from` takes the last message, which is right until a media block is upstream. In
    `Image → Video` the last message is the Image node's `![alt](url)`, so the Video node was
    handing fal a Markdown string with a blob URL in it as the description of the motion — and
    the run still succeeded, which is what made it easy to miss. The `![` showing up at the front
    of the generated clip's caption was the only visible symptom.

    So: strip Markdown image syntax from each message, walk backwards, and take the first one with
    words left. A message that was *only* an embed contributes nothing and the search continues
    past it, which lands on whatever a human or an agent actually wrote.
    """
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        return ""
    for item in reversed(value):
        text = _MD_IMAGE.sub("", text_of(item)).strip()
        if text:
            return text
    return ""


def with_instructions(prompt: str, instructions: Any) -> str:
    """Fold the run's Prompt Instructions onto the end of an already-resolved prompt.

    **Appended, never substituted.** A block's own steering runs first — the Image block's `style`
    governs the *form* of the prompt, and on the shipped `Image → 3D` and `Image → Video` templates
    it is what makes the output usable at all. The Input field adds the run's criteria after that;
    it does not get to throw the template's tuning away.

    Tolerates a missing channel (`None`) because no consumer declares it in `reads()` — a graph
    where nobody set instructions simply has nothing at that key.
    """
    text = instructions.strip() if isinstance(instructions, str) else ""
    if not text:
        return prompt
    return f"{prompt}. {text}" if prompt else text

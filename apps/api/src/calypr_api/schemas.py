"""Request/response models for the engine endpoints. The GraphSpec is reused directly
from the DSL contract, so the API speaks the exact same shape the canvas serializes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from calypr_compiler import Issue
from calypr_dsl import GraphSpec
from pydantic import BaseModel, field_validator

#: Attachment URLs a run may carry: our own blob store or an inline image data URI. Rejecting
#: arbitrary URLs keeps runs from hotlinking/SSRF-ing third-party hosts through the vision path.
_MAX_RUN_IMAGES = 4


def _validate_run_images(images: list[str]) -> list[str]:
    if len(images) > _MAX_RUN_IMAGES:
        raise ValueError(f"at most {_MAX_RUN_IMAGES} images per run")
    for url in images:
        ok = url.startswith("data:image/") or (
            url.startswith("https://") and ".blob.vercel-storage.com/" in url
        )
        if not ok:
            raise ValueError("image URLs must be uploads (blob storage) or data:image/ URIs")
    return images


class CompileResponse(BaseModel):
    ok: bool
    issues: list[Issue]


class CodegenResponse(BaseModel):
    code: str


class ParseRequest(BaseModel):
    """Edited Python coming back from the Code tab (the reverse round-trip)."""

    code: str


class ParseResponse(BaseModel):
    """The recovered graph plus what the parser couldn't take at face value.

    `warnings` are advisory (a missing trailer, a statement the walker skipped); `degraded_nodes`
    lists node ids that fell back to a Custom Code node because no recogniser matched — the
    canvas renders those as Code nodes with the user's source preserved verbatim."""

    graph: GraphSpec
    warnings: list[str] = []
    degraded_nodes: list[str] = []


class RunRequest(BaseModel):
    graph: GraphSpec
    message: str
    thread_id: str | None = None
    # Optional: when the playground runs a saved agent, its id lets metering attribute the run.
    agent_id: str | None = None
    # Uploaded attachment URLs for a vision run (seeded into state.images; see the Upload node).
    images: list[str] = []

    @field_validator("images")
    @classmethod
    def _images_ok(cls, v: list[str]) -> list[str]:
        return _validate_run_images(v)


class AssistMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistRequest(BaseModel):
    """A prompt (with history) for the AI assistant. `current_graph` is the canvas's current
    spec in refine mode; `model` overrides the server default."""

    messages: list[AssistMessage]
    current_graph: GraphSpec | None = None
    model: str | None = None


class AgentCreate(BaseModel):
    name: str
    graph: GraphSpec


class AgentUpdate(BaseModel):
    name: str | None = None
    graph: GraphSpec | None = None


class AgentSummary(BaseModel):
    id: str
    name: str
    updated_at: datetime


class AgentDetail(BaseModel):
    id: str
    name: str
    graph: GraphSpec


class ShareCreate(BaseModel):
    """Mint a share link. `run_cap` omitted ⇒ the endpoint applies the default cap; an explicit
    `null` would mean unlimited, but the endpoint only reads a positive int or the default."""

    run_cap: int | None = None


class ShareInfo(BaseModel):
    token: str
    run_cap: int | None
    run_count: int
    created_at: datetime
    revoked_at: datetime | None


class ShareRunRequest(BaseModel):
    """A run against a share link. Spec-free by design — the graph is loaded server-side from
    the token; anonymous callers only send a message (+ optional client-chosen thread id)."""

    message: str
    thread_id: str | None = None
    images: list[str] = []

    @field_validator("images")
    @classmethod
    def _images_ok(cls, v: list[str]) -> list[str]:
        return _validate_run_images(v)


class WorkspaceInfo(BaseModel):
    id: str
    name: str
    # Entitlement tier (`free|beta|plus`) — what the client gates optional features on.
    plan: str = "free"
    # The signed-in user's email as the API sees it (the address the beta invite list is matched
    # against). Returned so the UI can say "you're signed in as X" when a feature is locked —
    # an invited partner whose GitHub email differs from the one they gave us can then tell us
    # which address to add. `None` in dev/CI, where there's no authenticating proxy.
    signed_in_as: str | None = None
    # The workspace's chosen AI-assistant model; "" = inherit the server default.
    assistant_model: str = ""


class WorkspaceUpdate(BaseModel):
    """A partial update — only the fields present are applied, so the settings page can save
    the name and the assistant model independently."""

    name: str | None = None
    assistant_model: str | None = None


class WaitlistJoin(BaseModel):
    """A pre-signup email from the landing form.

    Validated loosely on purpose: the browser's `type="email"` handles the obvious cases, and the
    only validation that actually matters for a waitlist is whether the address receives mail.
    A light shape check keeps `pydantic[email]` out of the dependency list for one field."""

    email: str
    source: str | None = None

    @field_validator("email")
    @classmethod
    def _looks_like_an_email(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 320:  # RFC 3696 practical maximum
            raise ValueError("email address too long")
        # Reject whitespace/commas outright: they're never valid unquoted, and they're the
        # shapes that arrive when someone pastes "Ada <ada@x.com>" or a list of addresses.
        if v.count("@") != 1 or any(c in v for c in ", ;\t\n"):
            raise ValueError("not a valid email address")
        local, _, domain = v.partition("@")
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("not a valid email address")
        return v


class WaitlistEntry(BaseModel):
    """One waitlist row — admin-only; never returned by the public join route."""

    email: str
    source: str
    created_at: datetime
    invited_at: datetime | None = None


class InviteRequest(BaseModel):
    """Addresses to add to the beta invite list (operator-only)."""

    emails: list[str]


class InviteResult(BaseModel):
    """`invited` were newly stamped; `already_invited` were on the list already (re-running is
    safe, so the split just tells you what actually changed)."""

    invited: list[str] = []
    already_invited: list[str] = []


class PlanUpdate(BaseModel):
    """Move a workspace between entitlement tiers (operator-only).

    `email` is optional and only used to stamp the matching waitlist row as invited."""

    plan: str
    email: str | None = None


class TemplateInfo(BaseModel):
    """A starter graph for the canvas gallery — a `framework` (agent pattern) or a
    `template` (multi-agent use case)."""

    id: str
    name: str
    description: str
    kind: Literal["framework", "template"]
    graph: GraphSpec


class ConnectorCreate(BaseModel):
    """Save a Tier B MCP server: a name + URL, optionally a bearer secret (stored encrypted).

    The secret is write-only — it is never echoed back by any response model."""

    name: str
    url: str
    transport: Literal["streamable_http", "sse"] = "streamable_http"
    secret: str = ""  # optional bearer; "" = keyless server

    @field_validator("url")
    @classmethod
    def _https_only(cls, v: str) -> str:
        # MCP servers ride HTTPS; blocking other schemes trims the SSRF surface for a
        # user-supplied URL (localhost http is still allowed for dev/CI test servers).
        if not (
            v.startswith("https://")
            or v.startswith("http://localhost")
            or v.startswith("http://127.0.0.1")
        ):
            raise ValueError("connector URL must be https:// (or http://localhost for dev)")
        return v


class ConnectorInfo(BaseModel):
    """A saved connector, safe to return to the client — carries NO secret, only a
    `has_secret` flag so the UI can show a lock/reconnect state."""

    id: str
    kind: Literal["mcp", "notion"]
    name: str
    url: str | None
    transport: str
    has_secret: bool
    meta: dict = {}
    created_at: datetime


class ConnectorTestResult(BaseModel):
    """Result of a live ListTools probe against a connector (drives the canvas Test button)."""

    ok: bool
    tools: list[str] = []
    error: str | None = None


class OAuthStart(BaseModel):
    """The provider authorize URL the browser should be redirected to (Tier A connect)."""

    authorize_url: str


class NotionCallback(BaseModel):
    """The authorization code the browser returned from Notion's consent screen."""

    code: str


#: The model providers a workspace can supply its own key for (BYO-key). Kept small and
#: explicit — the model factory maps these to its provider clients.
#: `moonshot` is mandatory rather than optional — kimi-k3 is a frontier model and runs *only*
#: on a workspace's own key (see `model_access`).
PROVIDER_KEY_PROVIDERS = ("openai", "anthropic", "moonshot", "tavily")


class ProviderKeyInfo(BaseModel):
    """Whether a workspace has a BYO key on file for a provider. Never carries the key."""

    provider: Literal["openai", "anthropic", "moonshot", "tavily"]
    has_key: bool


class ProviderKeySet(BaseModel):
    """Set/replace a provider's BYO key. Write-only — never echoed back."""

    key: str

    @field_validator("key")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("key must not be empty")
        return v.strip()

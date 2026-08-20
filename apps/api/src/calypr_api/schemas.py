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
    #: True when `code` is only the opening lines because the workspace isn't entitled to the
    #: full file. The client blurs the tail and offers the upgrade — but the truncation itself
    #: happens here, so the paid artifact never reaches an unentitled browser.
    truncated: bool = False
    #: Lines in the *full* file, so the preview can say how much is behind the upgrade.
    total_lines: int | None = None


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
    #: Beyond the plan's project cap after a downgrade — readable and deletable, but read-only.
    #: Decided by the API (`locking.py`), never re-derived in the browser.
    locked: bool = False


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


class BillingStatus(BaseModel):
    """Whether checkout can take a payment. Secret-free — presence of keys, nothing about them."""

    enabled: bool


class CheckoutSession(BaseModel):
    """Where to send the browser to pay. The client redirects; Stripe hosts the form, so no
    card data ever reaches us."""

    url: str


class PortalSession(BaseModel):
    """Where to send the browser to manage an existing subscription — Stripe's hosted Customer
    Portal handles cancel / plan change / payment method / invoices, so none of that UI lives
    here. The client redirects to this URL."""

    url: str


class SubscriptionInfo(BaseModel):
    """What the Billing tab renders without a live Stripe call: the plan, when the current paid
    period ends (the renewal date, or the cutoff once a cancel is pending), and whether the
    "Manage billing" button can open the portal (true only once a workspace has a Stripe
    customer). All mirrored from the subscription webhook."""

    plan: str = "free"
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    portal_available: bool = False


class CreditUsage(BaseModel):
    """This cycle's credit allowance and what's left of it, in whole credits."""

    allowance: int = 0
    remaining: int = 0
    used: int = 0


class PlanLimits(BaseModel):
    """What this plan allows, mirrored from `entitlements.LIMITS` so the client can render
    "3 of 20" without hard-coding the 20 and drifting from what the API enforces."""

    projects: int = 0
    workspaces: int = 0
    monthly_credits: int = 0
    storage_bytes: int = 0


class AccountUsage(BaseModel):
    """What this account has used against `PlanLimits`. Pooled across its workspaces.

    `storage_measured_at` is None until the nightly job has run — the UI says "not measured yet"
    rather than showing a confident 0 B, because storage is measured on a schedule, not live."""

    projects: int = 0
    workspaces: int = 0
    storage_bytes: int = 0
    storage_measured_at: datetime | None = None


class WorkspaceSummary(BaseModel):
    """One row in the workspace switcher."""

    id: str
    name: str
    created_at: datetime | None = None
    is_current: bool = False
    #: Beyond the plan's workspace cap after a downgrade — still selectable and readable, but
    #: nothing new goes into it. See `locking.py`.
    locked: bool = False


class WorkspaceList(BaseModel):
    """The switcher's whole payload: the rows, plus whether another one may be created.

    `can_create` is answered **here** rather than derived in the browser from a plan name. The
    cap lives in `entitlements.LIMITS` and is enforced in `create_workspace`; a second copy of
    "free means one" in TypeScript is a copy that drifts, and the version that drifts is the one
    deciding what to show. The client's job is to render the answer, not to work it out.

    It also keeps the sidebar to a single request. The dashboard layout renders on every page
    under /dashboard and deliberately avoids `/workspaces/current`, which counts projects and can
    write a lazy credit grant — so the entitlement rides along with the list it already fetches.
    """

    workspaces: list[WorkspaceSummary]
    plan: str
    can_create: bool
    #: Whether `create_agent` would be allowed right now — the project cap's affordance, answered
    #: by the same predicate that enforces it (`project_slots_left`). Same reasoning as
    #: `can_create`: a browser deriving this from a plan name and a row count predicts refusals
    #: the server would not make, because caps are not enforced without an internal key.
    can_create_project: bool = True


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceInfo(BaseModel):
    id: str
    name: str
    # The account this workspace belongs to — who pays for it. Several workspaces can share one.
    account_id: str = ""
    # Entitlement tier (`free|beta|plus`) — what the client gates optional features on. Lives on
    # the account, so it is the same across every workspace the user owns.
    plan: str = "free"
    # The signed-in user's email as the API sees it (the address the beta invite list is matched
    # against). Returned so the UI can say "you're signed in as X" when a feature is locked —
    # an invited partner whose GitHub email differs from the one they gave us can then tell us
    # which address to add. `None` in dev/CI, where there's no authenticating proxy.
    signed_in_as: str | None = None
    # The workspace's chosen AI-assistant model; "" = inherit the server default.
    assistant_model: str = ""
    # The model canvas LLM nodes inherit; "" = the platform default (gpt-4o-mini).
    default_model: str = ""
    # This cycle's credits. Enforcement without a display is a limit nobody can plan around.
    credits: CreditUsage = CreditUsage()
    # The same reasoning applied to capacity: the caps and what's been used against them.
    limits: PlanLimits = PlanLimits()
    usage: AccountUsage = AccountUsage()


class WorkspaceUpdate(BaseModel):
    """A partial update — only the fields present are applied, so the settings page can save
    the name and the assistant model independently."""

    name: str | None = None
    assistant_model: str | None = None
    default_model: str | None = None


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
    #: Gallery grouping for the Workflows page. Empty for frameworks, which are chosen while
    #: building on the canvas rather than browsed as jobs to do.
    category: str = ""
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


#: The GitHub MCP toolsets a connector may be scoped to. "" = GitHub's own default set. Kept to
#: the surfaces an agent plausibly needs, rather than mirroring every toolset GitHub ships.
GITHUB_TOOLSETS = ("", "repos", "issues", "pull_requests", "actions", "all")


class GithubConnectorCreate(BaseModel):
    """Save a GitHub connector: a fine-grained PAT plus the toolset it may reach.

    The token is write-only — it is encrypted on arrival and never echoed back. `readonly`
    defaults to True so a freshly connected agent cannot open issues or push commits until the
    user opts in."""

    name: str = "GitHub"
    pat: str
    toolset: Literal["", "repos", "issues", "pull_requests", "actions", "all"] = ""
    readonly: bool = True

    @field_validator("pat")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a GitHub access token is required")
        return v.strip()


class ConnectorInfo(BaseModel):
    """A saved connector, safe to return to the client — carries NO secret, only a
    `has_secret` flag so the UI can show a lock/reconnect state."""

    id: str
    kind: Literal["mcp", "notion", "github"]
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
    """What the browser returned from Notion's consent screen: the authorization code, plus the
    `state` we issued when the flow started (CSRF — see `oauth_state`). A callback without a
    valid state is refused before the code is exchanged."""

    code: str
    state: str = ""


#: The providers a workspace can supply its own key for (BYO-key). Kept small and explicit —
#: the model factory maps the model providers to its clients, and `provider_keys.resolve_tool_keys`
#: maps the tool providers (`unsplash`) onto the Tool nodes that use them.
#: `moonshot` is mandatory rather than optional — kimi-k3 is a frontier model and runs *only*
#: on a workspace's own key (see `model_access`).
PROVIDER_KEY_PROVIDERS = ("openai", "anthropic", "moonshot", "tavily", "unsplash")


class ProviderKeyInfo(BaseModel):
    """Whether a workspace has a BYO key on file for a provider. Never carries the key.

    `key_hint` is the key's last 4 characters, stored in the clear at write time (see migration
    `0020`) so that identifying which key is on file never requires decrypting the real one.
    `None` means either no key, or a key saved before that migration — both render as a plain
    "key on file" with nothing to disambiguate."""

    provider: Literal["openai", "anthropic", "moonshot", "tavily", "unsplash"]
    has_key: bool
    key_hint: str | None = None


class AccountDeleted(BaseModel):
    """The answer to `DELETE /account`.

    `mode` distinguishes a real deletion from the dev-mode no-op the web proxy synthesizes when
    the API returns 501, so the client can be honest about which one happened rather than showing
    the same confirmation for both."""

    deleted: bool
    mode: Literal["live", "dev"] = "live"


class ProviderKeySet(BaseModel):
    """Set/replace a provider's BYO key. Write-only — never echoed back."""

    key: str

    @field_validator("key")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("key must not be empty")
        return v.strip()


class ConversationSummary(BaseModel):
    """One row in the Playground's History tab.

    `has_state` is the field that keeps this honest. The transcript is durable, but the agent's
    *memory* of it is a LangGraph checkpoint on a per-plan TTL — so a conversation can be fully
    readable while the agent no longer remembers a word of it. The UI badges that case rather
    than letting the user discover it by asking a follow-up and getting a blank stare."""

    id: str
    title: str
    #: The client-side thread suffix, echoed back so resuming re-attaches to the same thread.
    thread_id: str
    agent_id: str | None = None
    message_count: int = 0
    has_state: bool = False
    preview: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageOut(BaseModel):
    """One stored turn. `status` is `complete|partial|errored` on assistant turns — a run the
    user stopped mid-answer keeps what streamed."""

    id: str
    role: str
    text: str
    images: list[str] = []
    status: str = "complete"
    created_at: datetime | None = None


class ConversationDetail(ConversationSummary):
    """A conversation plus its transcript. `truncated` when the turn count exceeded the page
    cap — the History tab is for finding a conversation, not for paging a novel."""

    messages: list[MessageOut] = []
    truncated: bool = False


class ConversationList(BaseModel):
    """Keyset-paginated, not offset: new conversations land while the user is scrolling, and
    OFFSET would duplicate or skip rows as they shift."""

    items: list[ConversationSummary] = []
    next_cursor: str | None = None


class ConversationRename(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v.strip()[:200]


class AssetOut(BaseModel):
    """One generated file in the Media tab. `url` is always a real blob URL — media produced
    without blob storage configured is rendered but never recorded (see `_assets.StoredAsset`)."""

    id: str
    kind: str
    url: str
    caption: str = ""
    content_type: str | None = None
    bytes: int = 0
    model: str | None = None
    conversation_id: str | None = None
    created_at: datetime | None = None


class AssetList(BaseModel):
    items: list[AssetOut] = []
    next_cursor: str | None = None

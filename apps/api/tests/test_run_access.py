"""Free is BYO-key only for node runs, and own-key usage is never charged twice.

Two rules that shipped together on 2026-07-24 because they need the same primitive — "will this
call run on the workspace's key or ours?" (`model_access.runs_on_own_key`). Before it existed,
zero-rating keyed off a hardcoded frontier-model list, which got both directions wrong: Free could
spend its assistant credits on platform node runs nobody advertised, and a Plus user with their own
OpenAI key was charged credits for calls OpenAI had already billed them for.

The pure decisions come first and need no database. The composed gate that reads a plan and a
key set out of Postgres (`run_access.check_run_gates`) is exercised in the DB-backed section at
the bottom.
"""

import uuid

import pytest
from calypr_api import credits, entitlements, run_access
from calypr_api.config import settings
from calypr_api.db.models import ProviderKey, Workspace
from calypr_api.db.session import SessionLocal, engine
from calypr_api.model_access import platform_key_models, runs_on_own_key
from calypr_api.pricing import credits_for, platform_cost_usd, platform_credits_for
from calypr_api.run_access import _message
from calypr_compiler.golden import input_agent_output
from calypr_dsl import NodeSpec
from sqlalchemy import text


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")

# --- the primitive ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "providers", "expected"),
    [
        ("gpt-4o-mini", {"openai"}, True),
        ("gpt-4o-mini", {"anthropic"}, False),
        ("gpt-4o-mini", set(), False),
        ("gpt-4o-mini", None, False),
        ("claude-3-5-sonnet", {"anthropic"}, True),
        ("kimi-k3", {"moonshot"}, True),
        ("deepseek-chat", {"deepseek"}, True),
        # Unknown ids default to openai in `provider_of` — an openai key therefore covers them,
        # which is the same assumption the model factory makes when it picks a client.
        ("some-unreleased-model", {"openai"}, True),
    ],
)
def test_runs_on_own_key(model: str, providers: set[str] | None, expected: bool) -> None:
    assert runs_on_own_key(model, providers) is expected


def test_own_key_is_broader_than_frontier() -> None:
    """The bug this replaced: zero-rating only frontier models. An ordinary model on a stored key
    is still the customer's spend, not ours."""
    assert runs_on_own_key("gpt-4o-mini", {"openai"}) is True  # not frontier, still their key


# --- billing ------------------------------------------------------------------------------------


def test_own_key_usage_is_free_in_credits_and_platform_cost() -> None:
    """One call, billed by the provider to the customer, must cost us nothing and charge nothing."""
    assert platform_credits_for("gpt-4o-mini", 1_000, 1_000, own_key=True) == 0.0
    assert platform_cost_usd("gpt-4o-mini", 1_000, 1_000, own_key=True) == 0.0


def test_platform_key_usage_is_still_charged() -> None:
    """The default path is unchanged — `own_key` defaults False, so nothing silently goes free."""
    assert platform_credits_for("gpt-4o-mini", 1_000, 1_000) == credits_for(
        "gpt-4o-mini", 1_000, 1_000
    )
    assert platform_credits_for("gpt-4o-mini", 1_000, 1_000) > 0
    assert platform_cost_usd("gpt-4o-mini", 1_000, 1_000) > 0


# --- which models would run on our keys ---------------------------------------------------------


def test_platform_key_models_ignores_nodes_covered_by_a_stored_key() -> None:
    graph = input_agent_output(model="gpt-4o-mini")
    graph.nodes.append(NodeSpec(id="a2", type="agent", config={"model": "claude-3-5-sonnet"}))
    # An OpenAI key covers the first but not the Anthropic node.
    assert platform_key_models(graph, {"openai"}) == ["claude-3-5-sonnet"]
    # Both keys on file ⇒ nothing of ours is spent.
    assert platform_key_models(graph, {"openai", "anthropic"}) == []
    # No keys ⇒ everything is ours.
    assert set(platform_key_models(graph, set())) == {"gpt-4o-mini", "claude-3-5-sonnet"}


def test_inherited_models_are_resolved_not_skipped() -> None:
    """The gate has to see what a node *will* run, not what it literally stores.

    An untouched canvas ships `model: ""` on every LLM node. Reading the raw config would find no
    models at all and wave the whole graph through — the exact hole that would have made Free's
    BYO-key rule unenforceable for the default case."""
    graph = input_agent_output(model="")
    graph.nodes[0].config["model"] = ""
    # Falls back to the workspace default…
    assert platform_key_models(graph, {"anthropic"}, "gpt-4o-mini") == ["gpt-4o-mini"]
    # …and an OpenAI key covers that same inherited model.
    assert platform_key_models(graph, {"openai"}, "gpt-4o-mini") == []
    # With no workspace default it lands on the platform default, which is still ours.
    assert platform_key_models(graph, set(), "") == ["gpt-4o-mini"]


def test_non_llm_nodes_contribute_nothing() -> None:
    """Input/Output carry no model and must not be resolved into one.

    Asserted with *no* keys on file, so the only way the list stays at one entry is if the
    non-LLM nodes were skipped — with a key present this would pass even if they weren't."""
    graph = input_agent_output(model="gpt-4o-mini")
    assert len(graph.nodes) > 1  # there really are non-LLM nodes in this fixture
    assert platform_key_models(graph, set()) == ["gpt-4o-mini"]


def test_models_are_deduplicated() -> None:
    graph = input_agent_output(model="gpt-4o-mini")
    graph.nodes.append(NodeSpec(id="a2", type="agent", config={"model": "gpt-4o-mini"}))
    assert platform_key_models(graph, set()) == ["gpt-4o-mini"]


# --- the plan rule ------------------------------------------------------------------------------


def test_only_free_must_bring_its_own_key() -> None:
    assert entitlements.requires_own_key("free") is True
    assert entitlements.requires_own_key(None) is True  # unset defaults to the most limited plan
    assert entitlements.requires_own_key("beta") is False
    assert entitlements.requires_own_key("plus") is False


# --- the message --------------------------------------------------------------------------------


def test_message_names_providers_and_both_ways_out() -> None:
    msg = _message(["gpt-4o-mini"])
    assert "OpenAI" in msg  # the provider, not the model id — that's what they go and get
    assert "Settings" in msg and "Plus" in msg  # add a key, or upgrade
    assert "an OpenAI API key" in msg  # article agrees with the label


def test_message_lists_every_provider_needed() -> None:
    msg = _message(["gpt-4o-mini", "claude-3-5-sonnet"])
    assert "Anthropic" in msg and "OpenAI" in msg
    assert "API keys for" in msg


# --- the composed gate (DB-backed) --------------------------------------------------------------
#
# The property under test is a single sentence: **a run that costs us nothing is never refused.**
# It was violated in both directions on the day this landed — `check_can_run` looked only at the
# balance, so a workspace that had done exactly what we asked (brought its own key) was still
# turned away for having no credits, and on `/assist` that was a regression against the behaviour
# users had the day before.


@pytest.fixture
def ws_factory():
    """Throwaway workspaces with optional stored provider keys; cleaned up afterwards."""
    made: list[uuid.UUID] = []

    def make(plan: str, providers: tuple[str, ...] = (), exhausted: bool = False) -> uuid.UUID:
        with SessionLocal() as s:
            ws = Workspace(name=f"run-access-{uuid.uuid4().hex[:8]}", plan=plan)
            s.add(ws)
            s.commit()
            s.refresh(ws)
            wid = ws.id
            for p in providers:
                # A literal placeholder, not `vault.encrypt`: `byok_providers` reads provider
                # *names* and never decrypts, so real ciphertext buys nothing here — and asking
                # for it made these tests depend on `CALYPR_VAULT_KEY`, which the vault demands
                # whenever `internal_key` is set (as these tests set it). That passed locally,
                # where a dev key sits in `.env`, and failed in CI, where none does.
                s.add(ProviderKey(workspace_id=wid, provider=p, key_encrypted=f"not-a-key-{p}"))
            if exhausted:
                # Anchor this cycle's grant then spend it, so `ensure_current_grant` inside
                # `check_can_run` can't quietly re-grant and mask the refusal.
                ws = s.get(Workspace, wid)
                credits.grant_monthly(s, ws, ref_id=f"test:{wid}")
                credits.debit_run(s, wid, 10_000, source="run")
            s.commit()
        made.append(wid)
        return wid

    yield make
    with SessionLocal() as s:
        for wid in made:
            s.query(Workspace).filter(Workspace.id == wid).delete()
        s.commit()


@requires_db
def test_exhausted_plus_still_runs_on_its_own_keys(monkeypatch, ws_factory) -> None:
    """The bug: a Plus workspace out of credits was refused even when the run cost us nothing."""
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    wid = ws_factory(entitlements.PLUS, providers=("openai",), exhausted=True)
    graph = input_agent_output(model="gpt-4o-mini")  # openai → covered by their key
    # The balance really is spent — the bare credit check, which is all this used to consult,
    # still refuses. Asserted so this can't quietly degrade into a test of a solvent workspace.
    assert credits.check_can_run(wid) is not None
    # …and the composed gate lets it through anyway, because none of it lands on our keys.
    assert run_access.check_run_gates(wid, graph) is None


@requires_db
def test_exhausted_plus_is_refused_when_it_would_spend_ours(monkeypatch, ws_factory) -> None:
    """The other half — without a key for that provider, the balance still bites."""
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    wid = ws_factory(entitlements.PLUS, providers=("anthropic",), exhausted=True)
    graph = input_agent_output(model="gpt-4o-mini")  # openai → ours
    gate = run_access.check_run_gates(wid, graph)
    assert gate is not None
    assert gate[0] == credits.INSUFFICIENT_CREDITS


@requires_db
def test_free_runs_on_its_own_keys_even_at_zero_balance(monkeypatch, ws_factory) -> None:
    """Free's credits are an assistant budget. Having spent them must not block a BYO-key run —
    otherwise the plan's own rule ("run on your own key") would be unusable in its normal case."""
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    wid = ws_factory(entitlements.FREE, providers=("openai",), exhausted=True)
    graph = input_agent_output(model="gpt-4o-mini")
    assert run_access.check_run_gates(wid, graph) is None


@requires_db
def test_free_without_a_key_gets_the_own_key_answer_not_a_credit_one(
    monkeypatch, ws_factory
) -> None:
    """Ordering matters: Free with credits left but no key must be told to add a key, not that
    it has run out of something it still has."""
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    wid = ws_factory(entitlements.FREE)  # credits intact, no keys
    graph = input_agent_output(model="gpt-4o-mini")
    gate = run_access.check_run_gates(wid, graph)
    assert gate is not None
    assert gate[0] == run_access.OWN_KEY_REQUIRED
    assert "OpenAI" in gate[1]


@requires_db
def test_assist_on_own_key_tracks_the_stored_providers(monkeypatch, ws_factory) -> None:
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    wid = ws_factory(entitlements.FREE, providers=("openai",))
    assert run_access.assist_on_own_key(wid, "gpt-4o-mini") is True
    assert run_access.assist_on_own_key(wid, "claude-3-5-sonnet") is False
    assert run_access.assist_on_own_key(None, "gpt-4o-mini") is False


@requires_db
def test_the_gate_is_off_without_an_internal_key(monkeypatch, ws_factory) -> None:
    """Same carve-out as the credit check: local dev and CI are never metered."""
    monkeypatch.setattr(settings, "internal_key", "")
    wid = ws_factory(entitlements.FREE, exhausted=True)
    assert run_access.check_run_gates(wid, input_agent_output(model="gpt-4o-mini")) is None

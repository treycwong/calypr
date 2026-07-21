"""`run_error_message` maps engine exceptions to client-safe copy (WEEK4 PR-1)."""

from __future__ import annotations

from calypr_api.errors import run_error_message
from calypr_compiler import CompileError
from calypr_compiler.validate import Issue
from calypr_runtime import RunError


def test_run_error_shows_verbatim():
    # RunError is pre-vetted as safe to show (e.g. the recursion-loop message).
    assert run_error_message(RunError("This agent looped without finishing.")) == (
        "This agent looped without finishing."
    )


def test_compile_error_shows_first_issue_not_the_wrapper():
    exc = CompileError(
        [
            Issue(
                severity="error",
                code="cyclic_graph",
                message="Nodes form a loop with no exit (a -> b -> a).",
            )
        ]
    )
    assert run_error_message(exc) == "Nodes form a loop with no exit (a -> b -> a)."


def test_unknown_error_is_generic_and_never_leaks_internals():
    msg = run_error_message(ValueError("psycopg: password authentication failed for user 'x'"))
    assert "password" not in msg  # no internal/provider detail leaks
    assert "went wrong" in msg.lower()


class _Rejected(Exception):
    """Stands in for a provider SDK's 401 (openai.AuthenticationError et al)."""

    status_code = 401


class _NotAuth(Exception):
    status_code = 500


def test_detects_provider_auth_failures_by_status_and_by_class_name() -> None:
    from calypr_api.errors import is_provider_auth_error

    assert is_provider_auth_error(_Rejected())
    assert not is_provider_auth_error(_NotAuth())
    assert not is_provider_auth_error(ValueError("nope"))
    # Duck-typed on the class name too, since the SDKs share these names.
    assert is_provider_auth_error(type("AuthenticationError", (Exception,), {})())
    assert is_provider_auth_error(type("PermissionDeniedError", (Exception,), {})())


def test_key_rejected_copy_never_leaks_the_provider_payload() -> None:
    from calypr_api.errors import provider_key_error_message

    named = provider_key_error_message("OpenAI")
    assert "OpenAI" in named and "rejected" in named
    # Unknown provider still produces actionable copy rather than a blank.
    assert "provider" in provider_key_error_message(None).lower()


def test_share_surface_stays_generic_about_rejected_keys() -> None:
    """A share viewer is not the key's owner: telling them the owner's key was refused is
    neither actionable nor theirs to know. `/runs` and `/assist` use the actionable copy."""
    from calypr_api.errors import run_error_message

    msg = run_error_message(_Rejected())
    assert "rejected" not in msg.lower() and "key" not in msg.lower()
    assert msg == "Something went wrong running this agent. Check its settings and try again."

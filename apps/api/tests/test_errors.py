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

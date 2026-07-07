"""/assist streams status → graph → usage → [DONE] on the keyless fake path, is tenant-
scoped, and enforces the per-workspace daily cap."""

from __future__ import annotations

import json
import uuid

import pytest
from calypr_api.deps import assist_workspace
from calypr_api.main import app
from calypr_api.routers import assist
from fastapi.testclient import TestClient

client = TestClient(app)

_WS = uuid.UUID("00000000-0000-0000-0000-0000000000aa")


@pytest.fixture(autouse=True)
def _reset_cap():
    """Pin the workspace (no DB needed) and start each test with a clean daily counter."""
    app.dependency_overrides[assist_workspace] = lambda: _WS
    assist._daily.clear()
    yield
    app.dependency_overrides.pop(assist_workspace, None)
    assist._daily.clear()


def _events(body: str) -> list[dict]:
    out = []
    for frame in body.strip().split("\n\n"):
        line = frame.strip()
        if line.startswith("data:"):
            data = line[len("data:") :].strip()
            if data != "[DONE]":
                out.append(json.loads(data))
    return out


def test_fake_path_streams_status_graph_usage_and_done():
    r = client.post(
        "/assist",
        json={"messages": [{"role": "user", "content": "a RAG chatbot for my website"}]},
    )
    assert r.status_code == 200
    assert r.text.strip().endswith("data: [DONE]")
    events = _events(r.text)
    types = [e["type"] for e in events]
    assert "status" in types
    assert "usage" in types
    graph_events = [e for e in events if e["type"] == "graph"]
    assert len(graph_events) == 1
    spec = graph_events[0]["spec"]
    assert any(n["type"] == "retriever" for n in spec["nodes"])
    assert spec["entry"]


def test_daily_cap_returns_error_event(monkeypatch):
    from calypr_api.config import settings

    monkeypatch.setattr(settings, "assist_daily_cap", 1)
    body = {"messages": [{"role": "user", "content": "hello"}]}

    first = client.post("/assist", json=body)
    assert any(e["type"] == "graph" for e in _events(first.text))

    second = client.post("/assist", json=body)
    errors = [e for e in _events(second.text) if e["type"] == "error"]
    assert errors and "limit" in errors[0]["message"].lower()
    assert not any(e["type"] == "graph" for e in _events(second.text))

from calypr_model import Done, FakeModelClient, Msg, Role, TextDelta, ToolCall, Usage


async def _collect(client, **kw):
    return [ev async for ev in client.stream(model="x", **kw)]


async def test_fake_streams_text_then_done():
    client = FakeModelClient(reply="Hello there friend")
    events = await _collect(client, messages=[Msg(role=Role.user, content="hi")])
    streamed = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert streamed == "Hello there friend"
    assert isinstance(events[-1], Done)
    assert events[-1].text == "Hello there friend"
    assert any(isinstance(e, Usage) for e in events)


async def test_fake_echoes_last_user_message():
    client = FakeModelClient()
    events = await _collect(client, messages=[Msg(role=Role.user, content="ping")])
    streamed = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert "ping" in streamed


async def test_fake_emits_scripted_tool_calls():
    tc = ToolCall(id="t1", name="search", args={"q": "x"})
    client = FakeModelClient(reply="ok", tool_calls=[tc])
    events = await _collect(client, messages=[Msg(role=Role.user, content="hi")])
    assert any(isinstance(e, ToolCall) and e.name == "search" for e in events)
    assert events[-1].tool_calls == [tc]

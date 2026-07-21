"""Small shared helpers for node `parse()` methods — the inverse of `_codegen.py`.

Each node's `parse()` recovers config from the AST of its generated function. These helpers
factor out the recurring shapes the generators emit: string literals, `state.get("channel")`
reads, the final `return {"channel": ...}` dict, and calls by name. Keeping them here (beside
`_codegen.py`) means the forward/inverse pair reads symmetrically.
"""

from __future__ import annotations

import ast


def str_const(node: ast.expr | None) -> str | None:
    """The value of a string-literal expression, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def docstring(fn: ast.FunctionDef) -> str | None:
    """The function's docstring, if any (the generators emit a stable one per node type)."""
    return ast.get_docstring(fn)


def _is_state_get(call: ast.Call) -> bool:
    """True for a `state.get(...)` call."""
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "get"
        and isinstance(func.value, ast.Name)
        and func.value.id == "state"
    )


def state_get_keys(fn: ast.FunctionDef) -> list[str]:
    """Every string key read via `state.get("<key>")` in the function, in source order."""
    keys: list[str] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and _is_state_get(node) and node.args:
            key = str_const(node.args[0])
            if key is not None:
                keys.append(key)
    return keys


def last_return_dict(fn: ast.FunctionDef) -> tuple[str, ast.expr] | None:
    """The `(key, value_expr)` of the function's last `return {"<key>": <value>}` statement.

    Node functions end by returning a one-key state update; this recovers the written channel
    and the expression written to it (whose shape distinguishes, e.g., an Input's
    `[HumanMessage(...)]` from an Output's plain `text`).
    """
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    for ret in reversed(returns):
        if isinstance(ret.value, ast.Dict) and len(ret.value.keys) == 1:
            key = str_const(ret.value.keys[0])
            if key is not None:
                return key, ret.value.values[0]
    return None


def return_dict_key(fn: ast.FunctionDef) -> str | None:
    """The single string key of the function's last `return {"<key>": ...}` statement."""
    found = last_return_dict(fn)
    return found[0] if found else None


def last_return_dict_items(fn: ast.FunctionDef) -> list[tuple[str, ast.expr]]:
    """All `(key, value_expr)` pairs of the function's last `return {..}` (any arity, in
    source order) — for nodes that write several channels at once (an Evaluator's
    score+rationale, a Revisor's reply+counter)."""
    for ret in reversed([n for n in ast.walk(fn) if isinstance(n, ast.Return)]):
        if isinstance(ret.value, ast.Dict):
            items: list[tuple[str, ast.expr]] = []
            for k, v in zip(ret.value.keys, ret.value.values, strict=True):
                key = str_const(k)
                if key is not None:
                    items.append((key, v))
            if items:
                return items
    return []


def strip_prompt_prefix(system: str, prefix: str) -> str:
    """Undo `f"{PREFIX}\\n\\n{user_prompt}"` — the fixed framing several nodes prepend to a
    user prompt. Returns the user prompt (`""` when only the framing was emitted). Because
    re-emission just re-concatenates, an exact split isn't required for a codegen-fixed-point."""
    if system == prefix:
        return ""
    if system.startswith(prefix + "\n\n"):
        return system[len(prefix) + 2 :]
    return system


def expr_has_call(node: ast.expr | None, name: str) -> bool:
    """Whether `name(...)` / `<x>.name(...)` appears anywhere within an expression subtree."""
    if node is None:
        return False
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if (isinstance(func, ast.Name) and func.id == name) or (
                isinstance(func, ast.Attribute) and func.attr == name
            ):
                return True
    return False


def string_assign(fn: ast.FunctionDef, name: str) -> str | None:
    """The value of the first `name = "<literal>"` assignment in the function (implicit string
    concatenation is joined by the parser, so a wrapped multi-line literal reads back whole)."""
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and (value := str_const(node.value)) is not None
        ):
            return value
    return None


def calls_named(fn: ast.FunctionDef, name: str) -> list[ast.Call]:
    """Every call whose callee is `name(...)` or `<x>.name(...)`, in source order."""
    out: list[ast.Call] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == name) or (
            isinstance(func, ast.Attribute) and func.attr == name
        ):
            out.append(node)
    return out


def has_call(fn: ast.FunctionDef, name: str) -> bool:
    """Whether the function contains a call to `name(...)` / `<x>.name(...)`."""
    return bool(calls_named(fn, name))


def dict_lookup(node: ast.AST | None, key: str) -> ast.expr | None:
    """The value expr of the first `{... "<key>": <value> ...}` dict literal found in the
    subtree — used to read back kwargs the generators emit as dict literals
    (`search_kwargs={"k": 4}`, an MCP connection's `{"transport": ...}`)."""
    if node is None:
        return None
    for child in ast.walk(node):
        if isinstance(child, ast.Dict):
            for k, v in zip(child.keys, child.values, strict=True):
                if str_const(k) == key:
                    return v
    return None


def kwarg_const(call: ast.Call, name: str):
    """The literal value of `call(..., name=<constant>)`, else None."""
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def llm_actor_fields(fn: ast.FunctionDef, prompt_prefix: str) -> dict | None:
    """Common recovery for a single-shot LLM node whose body is
    `model = init_chat_model(<model>, temperature=<t>); messages = state.get(<in>) or []; ...;
    return {<out>: [reply], ...}` (the Responder/Revisor shape).

    Returns `{model, temperature, input_channel, output_channel, system_prompt}` — the
    output channel is the return key whose value is a message *list* — or None if the shape
    doesn't match. `system_prompt` is the emitted `system` literal minus `prompt_prefix`."""
    calls = calls_named(fn, "init_chat_model")
    if not calls or not calls[0].args:
        return None
    model = str_const(calls[0].args[0])
    temperature = kwarg_const(calls[0], "temperature")
    keys = state_get_keys(fn)
    output_channel = next(
        (k for k, v in last_return_dict_items(fn) if isinstance(v, ast.List)), None
    )
    if (
        model is None
        or not isinstance(temperature, (int, float))
        or not keys
        or output_channel is None
    ):
        return None
    return {
        "model": model,
        "temperature": float(temperature),
        "input_channel": keys[0],
        "output_channel": output_channel,
        "system_prompt": strip_prompt_prefix(string_assign(fn, "system") or "", prompt_prefix),
    }

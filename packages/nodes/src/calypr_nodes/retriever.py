"""Knowledge node — retrieval-augmented generation (RAG). Retrieves the most relevant chunks
from a knowledge base for the latest query and writes them to a `context` channel, which an
Agent reads via `{{ state.context }}` in its system prompt (retrieve-then-generate).

Mirrors the Tool node: a `demo` source retrieves keyless + deterministically (a seeded
in-memory store) so the canvas + tests stay green; `pgvector` is codegen-only for now — the
generated module owns the retriever against the user's Postgres."""

from __future__ import annotations

import ast
from typing import Any, Literal

from calypr_dsl import Reducer, StateChannel
from pydantic import BaseModel

from calypr_nodes._parse import (
    dict_lookup,
    docstring,
    kwarg_const,
    return_dict_key,
    state_get_keys,
)
from calypr_nodes.knowledge_catalog import knowledge_source
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    register,
)

_DOCSTRING = "Retrieve relevant context from the knowledge base (RAG)."


def _query_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        last = value[-1]
        return getattr(last, "content", str(last))
    return ""


class RetrieverConfig(BaseModel):
    source: Literal["demo", "pgvector"] = "demo"
    collection: str = ""  # the knowledge-base id / pgvector collection
    top_k: int = 4
    embedding_model: str = "text-embedding-3-small"
    input_channel: str = "messages"  # the query (its latest text)
    output_channel: str = "context"  # retrieved text


@register
class RetrieverNode(BaseNode):
    type = "retriever"
    meta = NodeMeta(
        label="Knowledge",
        category="knowledge",
        icon="book-open",
        description="Retrieve relevant context from a knowledge base (RAG).",
    )
    config_model = RetrieverConfig

    @classmethod
    def reads(cls, cfg: RetrieverConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: RetrieverConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def channels(cls, cfg: RetrieverConfig) -> list[StateChannel]:
        return [StateChannel(key=cfg.output_channel, type="string", reducer=Reducer.last)]

    @classmethod
    def compile(cls, cfg: RetrieverConfig, ctx: NodeContext) -> NodeFn:
        spec = knowledge_source(
            cfg.source,
            top_k=cfg.top_k,
            collection=cfg.collection,
            embedding_model=cfg.embedding_model,
        )
        if spec.retriever is None:
            note = (
                f"[{cfg.source!r} retrieval is codegen-only here — generate the code and "
                "run it against your Postgres, or use 'demo' to retrieve on the canvas.]"
            )

            async def _unavailable(state: dict[str, Any]) -> dict[str, Any]:
                return {cfg.output_channel: note}

            return _unavailable

        retriever = spec.retriever

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            query = _query_text(state.get(cfg.input_channel))
            docs = await retriever.ainvoke(query)
            return {cfg.output_channel: "\n\n".join(d.page_content for d in docs)}

        return _run

    @classmethod
    def codegen(cls, cfg: RetrieverConfig, fn_name: str, ctx=None) -> CodeFragment:
        spec = knowledge_source(
            cfg.source,
            top_k=cfg.top_k,
            collection=cfg.collection,
            embedding_model=cfg.embedding_model,
        )
        defs = "\n\n".join(spec.code_defs)
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """Retrieve relevant context from the knowledge base (RAG)."""',
            f'    messages = state.get("{cfg.input_channel}") or []',
            '    query = messages[-1].content if messages else ""',
            f"    docs = {spec.code_ref}.invoke(query)",
            f'    return {{"{cfg.output_channel}": "\\n\\n".join('
            "d.page_content for d in docs)}",
        ]
        function = f"{defs}\n\n\n" + "\n".join(lines)
        return CodeFragment(
            fn_name=fn_name, function=function + "\n", imports=spec.imports
        )

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> RetrieverConfig | None:
        """Recover a Knowledge/RAG node: its function reads the query, calls
        `knowledge.invoke(query)`, and returns the joined `page_content`. The companion
        `knowledge = ...` assignment carries the source — a `PGVector(...)` build is `pgvector`
        (with its embedding model + collection), anything else is the keyless `demo` store.
        `top_k` is read from the emitted `search_kwargs={"k": ...}`."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        keys = state_get_keys(fn)
        out = return_dict_key(fn)
        if not keys or out is None:
            return None

        kdef = ctx.defs.get("knowledge")
        kval = kdef.value if isinstance(kdef, ast.Assign) else None
        k_expr = dict_lookup(kval, "k")
        top_k = k_expr.value if isinstance(k_expr, ast.Constant) else None
        cfg = RetrieverConfig(
            input_channel=keys[0],
            output_channel=out,
            top_k=top_k if isinstance(top_k, int) else 4,
        )

        pgvector = next(
            (
                n
                for n in ast.walk(kval)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "PGVector"
            ),
            None,
        ) if kval is not None else None
        if pgvector is not None:
            cfg.source = "pgvector"
            embeddings = next(
                (
                    n
                    for n in ast.walk(pgvector)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "OpenAIEmbeddings"
                ),
                None,
            )
            model = kwarg_const(embeddings, "model") if embeddings else None
            if isinstance(model, str):
                cfg.embedding_model = model
            coll = kwarg_const(pgvector, "collection_name")
            if isinstance(coll, str):
                # codegen emits f"kb_{collection or 'documents'}" — invert it.
                cfg.collection = coll[len("kb_") :] if coll.startswith("kb_") else coll
        return cfg

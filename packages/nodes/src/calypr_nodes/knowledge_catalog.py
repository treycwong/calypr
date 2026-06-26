"""Knowledge catalog — the vector-store sources a Knowledge node retrieves from or generates.

Mirrors the tool catalog: `demo` runs keyless + deterministic (a seeded in-memory store with
fake embeddings) so the canvas + tests stay green; `pgvector` is codegen-only for now — the
generated module owns a `PGVector` retriever against the user's *own* Postgres + OpenAI key."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore

_EMBED_SIZE = 256
_DEMO_DOCS = [
    "Calypr compiles a visual agent canvas into idiomatic LangGraph you own.",
    "Retrieval-augmented generation grounds an agent's answer in retrieved documents.",
    "pgvector stores embeddings in Postgres and powers similarity search over them.",
    "A knowledge base is a collection of documents, chunked and embedded for retrieval.",
    "The fake model and the demo knowledge base let the canvas run with no API key.",
    "Tools let an agent act (web search, APIs); retrieval grounds what it already knows.",
]


@dataclass
class KnowledgeSpec:
    source: str
    retriever: Any | None  # a LangChain retriever, or None → codegen-only (no runtime yet)
    code_defs: list[str] = field(default_factory=list)  # module-level Python (the store)
    code_ref: str = "knowledge"  # the retriever variable referenced in build_graph()
    imports: list[str] = field(default_factory=list)


def knowledge_source(
    source: str,
    *,
    top_k: int = 4,
    collection: str = "",
    embedding_model: str = "text-embedding-3-small",
) -> KnowledgeSpec:
    """Resolve a source name to its KnowledgeSpec."""
    if source == "pgvector":
        coll = collection or "documents"
        return KnowledgeSpec(
            source="pgvector",
            retriever=None,
            code_defs=[
                "knowledge = PGVector(\n"
                f"    embeddings=OpenAIEmbeddings(model={embedding_model!r}),\n"
                '    connection=os.environ["DATABASE_URL"],\n'
                f'    collection_name="kb_{coll}",\n'
                f').as_retriever(search_kwargs={{"k": {top_k}}})'
            ],
            code_ref="knowledge",
            imports=[
                "import os",
                "from langchain_openai import OpenAIEmbeddings",
                "from langchain_postgres import PGVector",
            ],
        )
    # demo (default) — seeded in-memory store, deterministic, key-free.
    store = InMemoryVectorStore.from_texts(
        _DEMO_DOCS, DeterministicFakeEmbedding(size=_EMBED_SIZE)
    )
    demo_def = (
        f"_KB_DOCS = {json.dumps(_DEMO_DOCS)}\n"
        "knowledge = InMemoryVectorStore.from_texts("
        f"_KB_DOCS, DeterministicFakeEmbedding(size={_EMBED_SIZE})"
        f').as_retriever(search_kwargs={{"k": {top_k}}})'
    )
    return KnowledgeSpec(
        source="demo",
        retriever=store.as_retriever(search_kwargs={"k": top_k}),
        code_defs=[demo_def],
        code_ref="knowledge",
        imports=[
            "from langchain_core.embeddings import DeterministicFakeEmbedding",
            "from langchain_core.vectorstores import InMemoryVectorStore",
        ],
    )

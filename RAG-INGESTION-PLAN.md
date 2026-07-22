# Calypr — RAG Ingestion Plan (upload a doc → your own vector DB)

**Date:** 2026-07-07 · **Status:** PLAN for implementation · **Tracks:** TODO.md
"🟡 RAG — next pass (create your own vector DB)". Naming: **Phase 6 — RAG ingestion**
(the app's phases run 0–5e shipped; the AI Assistant shipped as Phase 9).

## 1. What this is

Today the **Knowledge (retriever) node** has two sources (`packages/nodes/.../retriever.py`):
- `demo` — a seeded in-memory store with fake embeddings (keyless, runs on the canvas).
- `pgvector` — **codegen-only**: it emits a `PGVector(...)` retriever for the user's *own*
  Postgres, but has **no runtime** in the app (`retriever=None` → a placeholder string).

This plan makes RAG **real inside Calypr**: a user uploads documents, we chunk + embed them
into **Neon pgvector** (workspace-scoped), and the Knowledge node retrieves against that KB
both on the canvas ("Try it") and in the assistant — while keeping the **keyless demo path**
green for CI. Ownable codegen is unaffected (the generated module still owns its own
`PGVector`).

**Guiding principles (match the rest of Calypr):**
- **Keyless by default.** No embeddings key ⇒ deterministic *fake* embeddings, so the canvas,
  tests, and CI stay green offline (mirrors `CALYPR_ASSISTANT_MODEL` unset ⇒ `fake`).
- **Tenant-isolated.** Every KB row carries `workspace_id` + an RLS policy, exactly like
  `agent` (migration `0002_agents`).
- **No new runtime path on the canvas.** The Knowledge node stays the seam; we give its
  `pgvector` source a runtime backed by our own `kb_chunk` table.

## 2. Existing contracts to build on (read these first)

| Contract | File | Why it matters |
|---|---|---|
| Knowledge node (`RetrieverConfig`: `source`/`collection`/`top_k`/`embedding_model`/channels) | `packages/nodes/src/calypr_nodes/retriever.py` | The node we wire to a real KB. `compile()` returns the runtime retriever; `codegen()` emits ownable code. |
| Source catalog (`knowledge_source()` → `KnowledgeSpec`) | `packages/nodes/src/calypr_nodes/knowledge_catalog.py` | Where `pgvector` gains a runtime retriever (today `retriever=None`). |
| Tenant CRUD pattern (`Depends(tenant)`, `t.session`, `t.workspace_id`, `_get_owned`) | `apps/api/src/calypr_api/routers/agents.py` | Copy this for `/knowledge-bases`. |
| RLS migration pattern (`ENABLE ROW LEVEL SECURITY` + `CREATE POLICY … USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)`) | `apps/api/migrations/versions/0002_agents.py` | The exact SQL to replicate for the KB tables. |
| ORM base + models (`Workspace`, `Agent`; `workspace_id` FK + JSONB) | `apps/api/src/calypr_api/db/models.py`, `db/base.py` | Add `KnowledgeBase` + `KbChunk` here. |
| Model seam (`model_for()` / `provider_of()`) | `services/model/src/calypr_model/factory.py` | Mirror it with an **embeddings** seam (`embed_for()`). |
| Engine context injection (`context_for(graph)` builds `NodeContext`) | `apps/api/src/calypr_api/engine.py` (used by `routers/runs.py`) | Where we inject a **workspace-scoped KB retriever** into the node runtime. |
| `NodeContext` (`model`, `tools`) | `packages/nodes/src/calypr_nodes/registry.py` | Extend with an optional KB accessor so `calypr_nodes` stays DB-free. |
| pgvector already enabled | Neon (`CREATE EXTENSION vector` applied — TODO.md) | No extension work needed in prod. |

## 3. Architecture

```
Upload (web)
  └─ POST /api/knowledge-bases/{id}/documents (multipart)  ── Next proxy + internalHeaders ──▶
       apps/api  routers/knowledge.py   [Depends(tenant)]
         parse → chunk → embed(embed_for(model)) → INSERT kb_chunk (workspace-scoped)
                                                          │
Retrieval (canvas "Try it" / assistant run)               ▼
  runs.py → engine.context_for(graph) injects a workspace-scoped kb_retriever into NodeContext
         → RetrieverNode.compile() uses it → similarity search over kb_chunk (pgvector cosine)
Codegen (ownable Python)  — unchanged: emits PGVector against the user's own DATABASE_URL
```

## 4. Data model (Phase 6a)

**Migration `<next>_knowledge_base`** (chain onto the latest revision — **not** `0004`: the MVP
sequence reserves `0004_runs` → `0005_share_links` → `0006_billing`, so RAG lands at `0007+`),
following the `0002` RLS pattern:

- `knowledge_base`: `id uuid pk`, `workspace_id uuid fk→workspace(id) ON DELETE CASCADE`,
  `name text`, `embedding_model text` (default `text-embedding-3-small`), `dim int`
  (default 1536), `created_at timestamptz`. RLS: `knowledge_base_tenant_isolation`.
- `kb_chunk`: `id uuid pk`, `kb_id uuid fk→knowledge_base(id) ON DELETE CASCADE`,
  `workspace_id uuid` (denormalized for RLS + the retrieval filter), `content text`,
  `embedding vector(1536)`, `metadata jsonb` (source filename, chunk index), `created_at`.
  RLS: `kb_chunk_tenant_isolation`. Index: `CREATE INDEX ... USING hnsw (embedding
  vector_cosine_ops)` (or ivfflat) for similarity search.

> **Decision — fixed 1536-dim column.** `text-embedding-3-small` is 1536-dim; the keyless
> **fake** embeddings are sized to **1536** too so one schema serves both. Store `dim` on the
> KB for forward-compat, but v1 pins 1536.

**ORM** (`db/models.py`): `KnowledgeBase`, `KbChunk` using `pgvector.sqlalchemy.Vector(1536)`.
Add the **`pgvector`** Python package to `apps/api`.

## 5. Embeddings seam (Phase 6a)

Mirror the chat-model seam in `services/model` — a new `embeddings.py`:

```python
def embed_for(model_id: str) -> Embeddings:   # LangChain Embeddings
    if not model_id or model_id == "fake":
        return DeterministicFakeEmbedding(size=1536)   # keyless, deterministic
    if model_id.startswith("text-embedding") or model_id.startswith("openai"):
        return OpenAIEmbeddings(model=model_id)          # reads OPENAI_API_KEY
    return OpenAIEmbeddings(model=model_id)
```

- Config: `CALYPR_EMBEDDING_MODEL` (unset ⇒ `fake`), same spirit as `CALYPR_ASSISTANT_MODEL`.
- New dep: **`langchain-openai`** (runtime `OpenAIEmbeddings`). `langchain-core` already present
  (`packages/nodes`). Unit test: `fake` id → `DeterministicFakeEmbedding`; `text-embedding-*`
  → `OpenAIEmbeddings` (no network).

## 6. Ingestion API (Phase 6b)

New `apps/api/src/calypr_api/routers/knowledge.py` (register in `main.py`; schemas in
`schemas.py`), all `Depends(tenant)`:

| Route | Purpose |
|---|---|
| `POST /knowledge-bases` `{name, embedding_model?}` | Create a KB (defaults to `settings.embedding_model`). |
| `GET /knowledge-bases` | List KBs (workspace-scoped) with chunk counts. |
| `GET /knowledge-bases/{id}` | KB detail + chunk count. |
| `DELETE /knowledge-bases/{id}` | Cascade-delete KB + chunks. |
| `POST /knowledge-bases/{id}/documents` (multipart) | **Ingest**: parse → chunk → embed → store. |

**Ingestion pipeline** (in a small `services/…` module or inline): accept `.txt`/`.md`/`.pdf`
→ extract text (`pypdf` for PDF) → **chunk** (`langchain-text-splitters`
`RecursiveCharacterTextSplitter`, ~1000 chars / 150 overlap) → **embed** in batches via
`embed_for(kb.embedding_model)` → bulk-insert `kb_chunk` rows. Return
`{documents, chunks, tokens?}`.

**Guardrails:** max file size + max chunks/KB (env-configurable); allowed MIME types;
process-and-**discard the raw file** in v1 (store only chunks — no blob storage needed).
Keyless: `embedding_model=fake` ⇒ no OpenAI call, so CI/e2e ingest works offline.

New deps: **`langchain-text-splitters`**, **`pypdf`**.

## 7. Runtime retrieval — wire pgvector to the KB (Phase 6c)

Goal: the Knowledge node's `pgvector` source **retrieves inside the app**, scoped to the
current workspace + selected KB.

- Keep `calypr_nodes` **DB-free**: extend `NodeContext` with an optional
  `kb_retriever: Callable[[str, int], list[str]] | None` (args: `kb_id`, `top_k`), injected by
  the API.
- `apps/api/.../engine.py::context_for(graph)` builds that callable bound to the request's
  `workspace_id`: embed the query with `embed_for`, run a pgvector **cosine** search over
  `kb_chunk WHERE workspace_id = :ws AND kb_id = :kb ORDER BY embedding <=> :q LIMIT :k`,
  return chunk texts.
- `RetrieverNode.compile()`: when `source == "pgvector"` and `ctx.kb_retriever` is present, use
  it (query text = latest input) → write joined chunks to `output_channel`. Fallback to the
  current placeholder when unavailable (e.g. codegen preview with no tenant).
- **`collection`** now means the **KB id**. `codegen()` stays as-is (ownable `PGVector` against
  the user's `DATABASE_URL`); note the schema divergence in a comment (app uses `kb_chunk`;
  generated standalone code manages its own `PGVector` table).

## 8. Web — Knowledge area (Phase 6d)

- A **Knowledge** view (dashboard section or a canvas rail tab): list KBs, **Create KB**, and
  an **upload** dropzone (file picker → multipart) with per-KB chunk counts / ingest status.
- Next proxies under `apps/web/src/app/api/knowledge-bases/…` mirroring `api/agents` — forward
  `internalHeaders()`; the document upload route streams `multipart/form-data` through.
- **Knowledge node config panel**: turn the `collection` free-text into a **dropdown of the
  workspace's KBs** (name → id), so users pick an uploaded KB instead of typing a slug.
- Client helpers in `apps/web/src/lib/api.ts` (`listKnowledgeBases`, `createKnowledgeBase`,
  `uploadDocument`, `deleteKnowledgeBase`).

## 9. Tests — "done" gates (Phase 6e)

- **pytest**: migration applies + RLS isolates `kb_chunk` across two workspaces; `embed_for`
  routing (`fake`|`openai`); ingest a small text (fake embeddings) → chunks stored → the
  runtime retriever returns the relevant chunk for a matching query.
- **API test**: `POST /knowledge-bases` → `POST …/documents` (fake) → `GET` shows chunk count;
  tenant-scoped; unknown KB → 404.
- **Playwright (keyless)**: create a KB → upload a tiny `.txt` → drop a Knowledge node
  (`source=pgvector`, pick the KB) → "Try it" → the answer/context reflects the uploaded text.
  Pin `CALYPR_EMBEDDING_MODEL=fake` in `playwright.config.ts` (like the assistant's fake pin).

## 10. Dependencies to add

`apps/api`: `pgvector`, `langchain-openai`, `langchain-text-splitters`, `pypdf`.
`services/model`: `langchain-openai` (embeddings). (`langchain-core` already present.)

## 11. Cost & safety

- **Keyless default** (`fake` embeddings) keeps dev/CI free and offline.
- Real embeddings only when `CALYPR_EMBEDDING_MODEL` + `OPENAI_API_KEY` are set (prod). Embedding
  is cheap but not free — enforce upload-size / chunk-count caps and consider a per-workspace
  ingest cap (mirror `CALYPR_ASSIST_DAILY_CAP`).
- Uploaded content is user data: workspace-scoped rows + RLS; validate MIME/size; store chunks
  only (no raw-file retention in v1).

## 12. Phasing & TODO.md mapping

| Phase | Deliverable | Closes in TODO.md (🟡 RAG) |
|---|---|---|
| **6a** | Migration `0004` (KB tables + RLS) + ORM + `embed_for` seam | "Alembic migration: `knowledge_base` + `kb_chunk`" · "An embeddings seam (`fake`\|`openai`)" |
| **6b** | `/knowledge-bases` CRUD + upload→chunk→embed→store | "API: `POST /knowledge-bases` + upload → chunk → embed → store pipeline" |
| **6c** | Runtime pgvector retriever wired into the Knowledge node | "Wire the Knowledge node's `pgvector` source to a real KB collection" |
| **6d** | Web Knowledge area + KB dropdown in the node panel | "Web: a Knowledge area to create KBs + upload documents" |
| **6e** | pytest + API + Playwright gates | (quality gate for the above) |

Each phase is independently shippable; **6a → 6b → 6c → 6d → 6e** is the build order.

## 13. Production / shipping (differs from the AI Assistant — heavier)

Build + test **locally first** (keyless fake embeddings + local Docker Postgres, which is
already `pgvector/pgvector:pg16`). Then, unlike the assistant (no schema, no deps), RAG touches
four prod surfaces:

1. **Migration on Neon (automatic, but schema-changing).** Railway's `preDeployCommand`
   (`alembic upgrade head`) creates `knowledge_base` + `kb_chunk` + the HNSW index on deploy.
   pgvector is already enabled on Neon. Test `0004` locally against an **empty and a populated**
   DB before merging (it's forward-only in practice); verify it applied via Railway logs.
2. **`uv.lock` must be committed** — the Docker build is `uv sync --frozen`; missing lock
   entries for `pgvector`/`langchain-openai`/`langchain-text-splitters`/`pypdf` fail the build.
3. **New required Railway env: `CALYPR_EMBEDDING_MODEL=text-embedding-3-small`** — unset ⇒ prod
   embeds with the *fake* model ⇒ meaningless retrieval. `OPENAI_API_KEY` already set.
4. **Upload size limit** — browser → Vercel Next route → Railway. **Vercel functions cap the
   request body at ~4.5 MB**, so cap uploads under that in v1 and surface a clear error; the
   scale path (larger files) is direct-to-API upload or Vercel Blob (§13 non-goal).

Deploy flow: merge PR → Railway + Vercel auto-deploy from `main` → set the env var → verify on
www.calypr.co (create KB → upload → grounded answer; Railway logs show ingest `200`s, no OpenAI
errors). Ingest cost is real once `CALYPR_EMBEDDING_MODEL` is a live model — keep the size/chunk
caps (§11).

## 14. Non-goals (this pass)

Raw-file storage / re-download (chunks only); incremental re-index / dedupe; non-OpenAI
embedding providers (the seam allows it later — add `deepseek`/local like the chat factory);
RAG-as-tool (agentic retrieval — separate TODO.md item); Chroma provider; multi-file batch
async ingestion with a job queue (v1 ingests synchronously per upload; move to a queue if large
files stall the request).
```

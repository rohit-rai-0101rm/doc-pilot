# Document Copilot — Build Checklist

Work through these phases in order. **Backend-first** after foundation: the product value is retrieval + grounded AI; the frontend is a thin chat shell.

**Stack:** FastAPI · Supabase · pgvector · Google Gemini (via OpenAI-compatible API) · Vite + React

**Definition of done (client):** 5 senior analysts use it for a week and report ≥3 hours saved per analyst per week.

---

## Build order (why backend first)

| Order | Layer | Reason |
| ----- | ----- | ------ |
| 1 | Supabase + env | Everything depends on Postgres, auth, and credentials |
| 2 | Backend schema + API | Trust, retrieval, grounding, and persistence live here |
| 3 | Thin vertical slice | Stub `/chat/stream` so frontend isn't blocked |
| 4 | Frontend auth + chat UI | Connect to working API |
| 5 | Ingestion + retrieval + agent | Core product |
| 6 | Polish + deploy | Pilot-ready |

---

## Phase 0 — Prerequisites & accounts

- [ ] Install Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, [pnpm](https://pnpm.io/)
- [x] Create Supabase project ([guide](supabase-setup.md))
- [x] Copy `backend/.env.example` → `backend/.env` and fill Supabase values
- [x] Copy `frontend/.env.example` → `frontend/.env` and fill Supabase + API URL
- [x] Add `GEMINI_API_KEY` to `backend/.env` ([aistudio.google.com](https://aistudio.google.com/apikey))
- [ ] Download sample SEC corpus: `uv run data/download.py` (set `USER_AGENT` in `data/download.py` first)
- [ ] Verify `DATABASE_URL` uses **direct** host (`db.<ref>.supabase.co`), not the pooler

---

## Phase 1 — Backend foundation

### 1a — Scaffold (in progress)

- [x] `uv sync` + runtime deps (FastAPI, SQLAlchemy, Alembic, pydantic-ai, etc.)
- [x] `app/config.py` — pydantic-settings, all env vars, fail fast on missing config
- [x] `app/main.py` — FastAPI app, CORS, `GET /health`
- [x] `backend/README.md` — how to run and manage the API
- [x] Confirm server starts: `uv run uvicorn app.main:app --reload`
- [x] Confirm health: `curl http://localhost:8000/health`

### 1b — Database schema

- [x] Add missing deps if needed: `uv add "psycopg[binary]" pgvector`
- [x] `uv run alembic init alembic`
- [x] Wire `alembic/env.py` to SQLAlchemy metadata + `settings.database_url`
- [x] Define SQLAlchemy models in `app/database/models.py`:
  - [x] `users`
  - [x] `chat_threads`, `chat_messages`, `message_citations`
  - [x] `source_documents`, `document_chunks` (embedding + `tsvector`)
- [x] Generate first migration (`alembic revision --autogenerate`)
- [x] Review migration — add explicitly:
  - [x] `create extension if not exists vector`
  - [x] `vector(N)` where `N` = `GEMINI_EMBEDDING_DIMENSIONS`
  - [x] generated `tsvector` columns
  - [x] HNSW index (semantic), GIN index (full-text)
  - [x] RLS policies
- [x] `uv run alembic upgrade head`
- [x] Verify tables in Supabase dashboard (read-only — don't edit schema there)

---

## Phase 2 — Scaffold frontend

- [x] Init Vite + React + TypeScript ([guide](frontend-setup.md))
- [x] Tailwind + shadcn/ui + React Router
- [x] `src/lib/env.ts` — validate `VITE_*` vars at boot
- [x] `src/lib/supabase.ts` — browser Supabase client
- [x] `src/lib/http.ts` — fetch wrapper with bearer token + typed errors
- [x] `src/lib/api.ts` — product-level API calls
- [x] Confirm: `pnpm dev` runs on `http://localhost:5173`

---

## Phase 3 — Auth (vertical slice #1)

Client requirement: *logged in with Driftwood email*

- [x] Supabase: email provider on; disable email confirm for local dev if needed
- [x] Frontend: sign-up / sign-in / sign-out pages (email only)
- [x] Frontend: protect chat routes — redirect if no session
- [x] Backend: `app/auth/dependencies.py` — verify Supabase JWT
- [x] Backend: reject missing/invalid tokens with `401`
- [x] Test: sign in in browser → backend accepts `Authorization: Bearer <token>`

---

## Phase 4 — Chat persistence API (no LLM yet)

Client requirement: *see their own past conversations*

- [x] Backend: `app/database/chats.py` — CRUD for threads + messages (scoped to `user_id`)
- [x] Backend routes: list threads, create thread, get thread + messages
- [x] Frontend: thread list sidebar, new chat, load history via `api.ts`
- [x] Enforce `403` when user A accesses user B's thread

---

## Phase 5 — Streaming chat stub (vertical slice #2)

Connect frontend ↔ backend before real AI exists.

- [x] Backend: `POST /chat/stream` — accept AI SDK message format, return stub stream
- [x] Backend: `app/chat/streaming.py` — AI SDK-compatible events
- [x] Frontend: chat page with Vercel AI SDK `useChat` → FastAPI
- [x] Persist user + assistant messages after stream completes
- [x] Test: login → new thread → send message → streamed reply → reload → history intact — verified via API calls with real tokens; not yet clicked through in an actual browser

---

## Phase 6 — Ingestion pipeline

Client requirement: *questions about any filing in the curated corpus*

- [x] Build `backend/ingest/` — read `data/downloads/` manifest
- [x] Parse SEC HTML → normalized Markdown → `source_documents`
- [x] Chunk with metadata (ticker, company, filing type/date, section, page, offsets)
- [x] Embed chunks via Gemini (`GEMINI_BASE_URL` + OpenAI SDK) → `document_chunks.embedding` — all 2460/2460 chunks embedded (`app/ingest/embed_chunks.py`)
- [x] Generate full-text `tsvector` on chunks
- [x] Ingest sample corpus (AAPL, MSFT, NVDA, AMZN, GOOGL — 2021–2025 10-Ks) — 25 documents, 2460 chunks, fully embedded
- [x] Unit tests: chunking logic, metadata extraction

---

## Phase 7 — Hybrid retrieval

- [x] `app/retrieval/queries.py` — pgvector semantic search
- [x] `app/retrieval/queries.py` — Postgres full-text search
- [x] `app/retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- [x] `app/retrieval/retriever.py` — query → ranked `SourcePassage` list + neighbor chunks
- [x] Unit tests: fusion ranking, retriever (no LLM) — 8 new tests passing, verified live against real corpus (Apple supply-chain risk, Microsoft Azure queries)

---

## Phase 8 — LLM agent + grounding

Client requirements: *sourced answers, refuse when corpus lacks evidence, no stock picks*

- [x] `app/assistant/agent.py` — PydanticAI agent with typed deps + `GroundedAnswer` output
- [x] `app/assistant/instructions.md` — product contract (cite everything, no hallucination, no investment advice)
- [x] Agent tools: `search_filings`, `read_chunk`, `read_surrounding_chunks` (bounded — no agent SQL)
- [x] `app/chat/orchestrator.py` — retrieve → agent → validate → stream → persist
- [x] `app/grounding/validator.py` — every citation maps to a retrieved passage; fail closed on violation
- [x] Unit tests: citation extraction, grounding enforcement — 6 new tests passing; verified live end-to-end (grounded answer with real citations, refusal on investment-advice question, citations persisted to `message_citations`)

---

## Phase 9 — Citation UI

Client requirements: *cite filing + page, show underlying passage*

- [ ] Stream citation metadata as structured parts in AI SDK stream
- [ ] `components/chat/` — citation badges (company, filing, date, page/section)
- [ ] Click citation → side panel or modal with source excerpt
- [ ] Empty states: no threads, no corpus match, retrieval failure
- [ ] Error states: 401, 403, 404, network vs HTTP (`ApiError.isNetworkError`)

---

## Phase 10 — Client acceptance scenarios

Run manually against [client-brief.md](../client-brief.md) example questions:

- [ ] Apple revenue mix across 2021–2025 10-Ks
- [ ] Amazon AWS vs NA/International margins
- [ ] NVIDIA Data Center demand drivers
- [ ] Microsoft Azure/AI language changes
- [ ] Alphabet segment revenue trends
- [ ] Risk-factor changes (AI, export controls, etc.)
- [ ] Apple/NVIDIA supplier concentration wording
- [ ] CapEx / purchase commitments comparison
- [ ] Geographic revenue exposures
- [ ] "Did generative AI improve margins?" — bot refuses to infer beyond filings

For each, verify: grounded answer · real citations · "not in corpus" when appropriate.

---

## Phase 11 — Deploy (Railway)

- [ ] Railway backend service (Uvicorn)
- [ ] Railway frontend service (Vite static build)
- [ ] Production env vars on both services
- [ ] `ALLOWED_ORIGINS` includes production frontend URL
- [ ] Re-enable Supabase email confirmation for production
- [ ] `uv run alembic upgrade head` against production Supabase
- [ ] Re-run ingestion against production DB
- [ ] Smoke test: login → ask one client-brief question → citations render

---

## Phase 12 — Pilot readiness

- [ ] Create pilot user accounts (Driftwood emails)
- [ ] Corpus covers pilot tickers × 2021–2025 10-Ks (minimum)
- [ ] Short internal doc: what it can/can't do, example prompts
- [ ] Logging: structlog on backend, easy to debug failed retrievals
- [ ] Collect analyst feedback: citation accuracy, latency, correct refusals

---

## Suggested weekly rhythm

| Week | Focus |
| ---- | ----- |
| 1 | Phases 0–3: Supabase, schema, auth |
| 2 | Phases 4–5: chat CRUD + streaming stub + basic UI |
| 3 | Phase 6: ingestion of full sample corpus |
| 4 | Phases 7–8: retrieval + agent + grounding |
| 5 | Phases 9–11: citation UI, acceptance tests, deploy |
| 6 | Phase 12: pilot |

---

## Rules of thumb

1. **Backend owns truth** — never call Gemini or run retrieval from the browser.
2. **One vertical slice before depth** — stub `/chat/stream` early so frontend isn't blocked.
3. **Test grounding without the UI** — pytest on retrieval + citation validation saves time.
4. **Don't skip ingestion** — a polished chat UI with an empty corpus fails the pilot.
5. **Trust > polish** — plain UI with correct citations beats a slick UI that hallucinates.

---

## Related docs

- [Architecture](../architecture.md)
- [Client brief](../client-brief.md)
- [Backend setup](backend-setup.md)
- [Backend README](../../backend/README.md)
- [Frontend setup](frontend-setup.md)
- [Supabase setup](supabase-setup.md)

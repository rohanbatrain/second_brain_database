**Architecture — Second Brain Database (In-Depth)**

**Scope & Goal**
- Purpose: A headless, production-ready knowledge platform combining a FastAPI backend, MongoDB storage, Redis caching/queues, an AI processing stack (Ollama + LlamaIndex + Qdrant), and a Next.js marketing/landing site.
- Audience: Developers and maintainers who need a complete, actionable understanding of the codebase, data flows, deployment needs, and operational concerns.

**High-Level Architecture**
- Frontend
  - `submodules/sbd-landing-page` — Next.js, Tailwind, Framer Motion; marketing, demos, and light frontend interactions with the API.
- Backend API
  - `src/second_brain_database` — FastAPI app exposing REST, WebSocket, and OpenAPI documentation.
- Database
  - MongoDB (async Motor driver): canonical storage for documents, users, families, wallets, permissions, and metadata.
- Vector / Semantic Search
  - Qdrant for vector similarity searches; store vectors with metadata and keep canonical document data in MongoDB.
- Cache & Queue
  - Redis: caching, ephemeral session storage, pub/sub, and job queue backend (Celery or comparable worker system).
- AI Stack
  - Ollama (local LLM host) + LlamaIndex orchestration for RAG workflows.
  - Docling for document parsing (OCR, tables, structured extraction).
  - Embedding pipeline: compute embeddings, store in Qdrant, reference vector IDs in MongoDB.
- Agents & Orchestration
  - FastMCP 2.x for AI agent tooling and integrations (HTTP/stdio transports, 138+ tools).
- Security & Observability
  - JWT authentication, Fernet encryption for secrets, Cloudflare Turnstile, audit logging, structured logs.

**Codebase Layout (Key Folders & Files)**
- `src/second_brain_database/`
  - `config` or `src/second_brain_database/config.py`: Settings loader. Priority: `SECOND_BRAIN_DATABASE_CONFIG_PATH` → `.sbd` → `.env` → env.
  - `managers/`: DB manager (`mongodb_manager.py`), logging manager, redis manager, auth manager.
  - `routers/` or `api/`: FastAPI routers grouped by domain (auth, documents, families, mcp-tools, shop, admin).
  - `models/` & `schemas/`: Pydantic models for requests/responses and DB documents.
  - `services/`: Business logic (ingestion, AI orchestration, payments, family tools).
  - `workers/` or `tasks/`: Background job implementations (ingest -> embeddings, notifications).
  - `tests/`: Unit & integration tests.
- `submodules/sbd-landing-page/`
  - `src/app/page.tsx`: main landing page, feature sections (edited during UX updates).
  - `components/`, `magicui/`: reusable UI parts.
- `config/`: project-level configuration (`Makefile`, `pyproject.toml`, `requirements.txt`).
- `scripts/`: ops/dev helper scripts like `start.sh`.
- `docs/`: project documentation (this file belongs here).

**Request & Data Flow (Detailed)**
1. Client → FastAPI endpoint
   - Frontend, micro-frontend, or API client calls FastAPI endpoint.
   - Authentication middleware validates JWT and checks permissions.
2. Controller → Service layer
   - Controller delegates to `services` (stateless business logic). Short-lived or complex work is enqueued to workers.
3. Cache check (Redis)
   - For repeatable queries (search results, synthesized answers), Redis is checked first.
   - Cache hit → return cached payload. Cache miss → query sources.
4. Data retrieval
   - Metadata queries → MongoDB (via `mongodb_manager`, async Motor client).
   - Semantic retrieval → Qdrant: query vectors by metadata and similarity score.
5. RAG pipeline
   - Retrieve top-K chunk IDs from Qdrant → load chunk texts from MongoDB.
   - Compose LlamaIndex / prompt context → send to Ollama for generation.
   - Post-process and optionally cache the result (Redis) and/or persist generated artifacts.
6. Ingestion pipeline (asynchronous)
   - Upload file → enqueue ingestion job in Redis/Celery.
   - Worker: Docling extracts text & tables → chunking → embeddings computed → store chunks in MongoDB and vectors in Qdrant.
7. Notifications & Collaboration
   - Events trigger pub/sub via Redis or push via WebSocket to subscribers (frontends, micro-frontends).
8. Agents (MCP)
   - FastMCP tools can call internal services or perform direct DB actions with controlled scopes.

**Persistence & Schema Patterns**
- Canonical data in MongoDB: `users`, `documents`, `chunks`, `families`, `wallets`, `audit_logs`.
- Embeddings & vector search in Qdrant; store vector IDs and minimal metadata in MongoDB documents for cross-reference.
- Index recommendations:
  - `users`: index on `email`, `id`.
  - `documents`: `created_at`, `owner_id`, frequently filtered metadata.
  - `chunks`: index on `document_id`, `chunk_index`.
  - TTL indexes for ephemeral data (sessions, temporary caches) as appropriate.
- Transactions: Use Mongo multi-document transactions when multiple collections must be updated atomically (requires replica set).

**Authentication & Authorization**
- JWTs for stateless auth. Use short-lived access tokens and rotate refresh tokens securely (server-side or rotated store).
- Role-based access: Admin, Full, Limited, View-Only. Implement resource-level ACL checks in middleware/service layer.
- Secrets encryption: use Fernet for small secret storage requiring encryption; keys managed by environment or secret manager.
- Bot protection: Cloudflare Turnstile for public endpoints (signups, public forms).
- Rate limiting: implement via Redis per-IP or per-user tokens.
- Audit logging: append-only `audit_logs` collection for sensitive writes (who, what, when, prev/next state ID).

**AI Pipeline (Ingestion → Embedding → Retrieval → Generation)**
- Ingestion steps:
  - Parse with Docling (OCR, table extraction).
  - Normalize content and split into context-aware chunks.
  - Compute embeddings (embedding model provider) in worker processes.
  - Store chunks in MongoDB; vectors with metadata in Qdrant.
- Retrieval steps:
  - Compute query embedding (if semantic search) and query Qdrant for top-K vectors.
  - Use LlamaIndex to assemble a contextual prompt combining selected chunks.
  - Call Ollama for LLM generation; handle streaming or full response.
  - Cache or persist outputs depending on TTL and data sensitivity.
- Operational suggestions:
  - Limit concurrent LLM requests and enforce queueing to control CPU/latency.
  - Tag cache entries with document version / ETag to invalidate when source updates.

**Agents & FastMCP**
- FastMCP hosts tools that wrap business operations (family management, shop ops, auth tooling).
- Tools enforce scopes and use service-level tokens when executing actions on behalf of agents.
- Secure agent endpoints and audit all agent-initiated changes.

**Deployment & Infrastructure**
- Services:
  - Backend container (FastAPI + Uvicorn/Gunicorn ASGI)
  - Worker containers (Celery or background worker implementation)
  - MongoDB (replica set for transactions and HA)
  - Redis (caching + broker)
  - Qdrant (vector storage)
  - Ollama (local LLM host)
  - Next.js landing page (static or server)
- Dev vs Prod:
  - Provide `docker-compose.dev.yml` for local development with single-node DBs and minimal replica features.
  - Use Kubernetes for production: statefulsets for MongoDB/Qdrant, deployments for backend and workers, HPA for workers based on queue length.
- Secrets & Config:
  - Use `.sbd` file pattern with priority: `SECOND_BRAIN_DATABASE_CONFIG_PATH` → `.sbd` → `.env` → env.
  - For production, use a secret manager (Vault, cloud provider secrets) and Kubernetes secrets.
- CI/CD:
  - Lint & tests → build images → push to registry → run staging smoke tests → deploy.
- Observability:
  - Structured logs (ELK/Datadog), metrics (Prometheus/Grafana), and traces (OpenTelemetry).

**Developer Workflows**
- Local quick-run (recommended): supply a `docker-compose.dev.yml` that brings up Mongo, Redis, Qdrant, Ollama, and the backend.
- Example dev commands:
```bash
# from repo root
# start local services (if docker-compose.dev.yml provided)
docker compose -f docker-compose.dev.yml up --build

# run backend (dev)
cd src/second_brain_database
uvicorn src.second_brain_database.main:app --reload --port 8000

# run landing page (dev)
cd submodules/sbd-landing-page
npm install
npm run dev
```
- Testing:
  - Unit tests: run Python test runner (pytest) for backend modules.
  - Integration tests: use testcontainers or a CI job that provisions ephemeral Mongo/Qdrant.
  - Linting & types: Python type hints + Pydantic; run `mypy`/`flake8` and `npm run lint` for frontend.

**Operational Considerations**
- Scale ingestion workers horizontally. Monitor embedding queue length and Qdrant capacity.
- Backups: configure scheduled backups & snapshots for MongoDB and Qdrant.
- Data migrations: implement versioned migration scripts for MongoDB schema changes.
- Monitoring: track LLM latency and throttles; trace RAG latency end-to-end.

**Security Hardening Recommendations**
- Rotate JWT secrets and Fernet keys periodically.
- Harden refresh token storage; prefer server-side refresh token rotation.
- Run vulnerability scans on third-party images and keep dependencies up-to-date.
- Limit agent/tool scopes and audit all agent actions.

**Recommendations & Next Steps**
- Add `docker-compose.dev.yml` (Mongo, Redis, Qdrant, Ollama, backend, and workers) for reproducible local dev.
- Add integration test that covers ingestion → embedding → Qdrant → retrieval → Ollama (mock or small local model).
- Add OpenTelemetry tracing to the RAG pipeline to discover bottlenecks.
- Add index and sharding strategy for Qdrant and Mongo after validating vector volume and access patterns.

**References & Key Files**
- Config access: `src/second_brain_database/config` (use `settings` object)
- Mongo helpers: `src/second_brain_database/managers/mongodb_manager.py`
- Landing page: `submodules/sbd-landing-page/src/app/page.tsx`
- Start script reference: `./start.sh` (developer experience section)

---
This file is intentionally practical — if you want I can: (1) add a `docker-compose.dev.yml` that wires up all services, (2) add a sample integration test, or (3) generate a visual diagram (Mermaid) and place it in `docs/`.

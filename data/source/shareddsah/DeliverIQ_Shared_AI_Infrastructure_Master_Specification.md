# DeliverIQ — Shared AI Infrastructure Engineering Specification

**Scope:** Shared platform for Customer, Kitchen and Unified Management AI harnesses  
**Version:** 1.0  
**Date:** 11 November 2026

## 1. Mission

Build a small, provider-independent AI platform that supports three isolated portal-specific harnesses:

1. Customer harness + Customer RAG.
2. Kitchen harness + Kitchen RAG.
3. Unified Management harness + Management RAG.

The platform shares reusable mechanisms—not permissions, private knowledge, prompts, tools or context. Each portal retains its own authorization, knowledge collection, retrieval policy, system prompt, tool allowlist, context builder and evaluation dataset.

The initial target is a reliable single-cloud-kitchen POC. Prefer a modular monolith, FastAPI, PostgreSQL/pgvector and Docker Compose. Groq is the initial LLM provider. Embeddings use a separately selected, replaceable provider.

## 2. Non-negotiable principles

- Backend authorization is authoritative; prompts are not security controls.
- No cross-portal RAG access.
- Live operational facts come from authorized application APIs, not vector search.
- AI is optional and must never block core portal workflows.
- Approved sources only; preserve provenance, approval, version and effective dates.
- Least-privilege service identities and database permissions.
- Typed interfaces, bounded retries, timeouts and graceful failures.
- No arbitrary SQL, shell, code or network execution by models.
- No autonomous mutations in the initial Management Copilot.
- Do not introduce microservices, Kubernetes, Kafka or a separate vector database without measured justification.

## 3. High-level architecture

```text
Customer Portal       Kitchen Portal       Unified Management Portal
      |                     |                         |
Customer Harness      Kitchen Harness          Management Harness
      |                     |                         |
      +---------------------+-------------------------+
                            |
                  Shared AI Platform
                            |
       +--------------------+--------------------+
       |                    |                    |
       v                    v                    v
   LLM Gateway       Embedding Service     Shared Utilities
       |                    |              - ingestion jobs
       v                    v              - chunking helpers
  Groq adapter       Embedding adapter     - retrieval primitives
                                           - schema validation
                                           - observability
                                           - evaluation runner

Portal-owned RAG:
Customer RAG          Kitchen RAG          Management RAG
separate schema       separate schema       separate schema
separate DB role      separate DB role      separate DB role
separate filters      separate filters      separate filters
```

The diagram describes shared code and interfaces. It does not grant any harness access to another portal's data.

## 4. Component ownership

| Component | Shared responsibility | Must remain portal-specific |
|---|---|---|
| LLM gateway | Provider adapters, normalized requests, retries, timeouts | Prompt, context, tools, permissions |
| Embeddings | Model adapters, batching, vector validation | Corpus, filters, source permissions |
| Ingestion | Job lifecycle, idempotency, retries, hashing | Source approval, scope, normalization, chunking policy |
| Retrieval | Vector/lexical primitives, fusion, provenance | Collection, authorization filters, ranking policy |
| Observability | Trace schema, metrics, redaction utilities | Portal-aware access controls |
| Evaluation | Test runner, scoring interfaces, reports | Dataset, expected answers, thresholds |
| Configuration | Typed loading and validation | Portal prompts, tools, retrieval policy |

## 5. LLM gateway

### 5.1 Purpose

All portal harnesses call language models through one internal interface. Portal code must not import or call provider SDKs directly.

Groq is the initial adapter. Future provider changes should require adapter/configuration changes, not rewrites to each harness.

### 5.2 Suggested contract

```python
class LLMGateway:
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    async def stream(self, request: LLMRequest):
        ...
```

`LLMRequest` should include:
- Portal enum: `customer`, `kitchen`, `management`.
- Task type.
- Messages.
- Typed tool definitions, if applicable.
- Server-controlled model profile.
- Output limits and generation parameters from trusted configuration.
- Request/correlation ID and deadline.
- Optional structured-output schema.

`LLMResponse` should include:
- Provider and model identifiers.
- Text or structured output.
- Tool-call proposals, if supported.
- Usage metadata and finish reason.
- Latency and correlation ID.
- Normalized provider error information.

### 5.3 Gateway requirements

- Provider selection and model IDs are server-controlled.
- Credentials come from secrets management, never source code.
- Keep provider SDK imports inside adapter modules.
- Validate structured outputs against application schemas.
- Treat model output as untrusted.
- Apply bounded retries only to transient failures.
- Do not retry authorization or invalid-request failures.
- Handle rate limits, timeouts, 5xx and malformed output distinctly.
- Use deadlines, concurrency controls and circuit breakers.
- Do not silently switch to an unapproved fallback model.
- Record provider/model/version and token usage where available.
- A provider outage must not interrupt core portal operations.

## 6. Embedding service

### 6.1 Suggested contract

```python
class EmbeddingService:
    async def embed_documents(
        self, texts: list[str], profile: str
    ) -> EmbeddingBatch:
        ...

    async def embed_query(
        self, text: str, profile: str
    ) -> EmbeddingVector:
        ...
```

The profile resolves to a server-controlled provider/model configuration.

### 6.2 Requirements

- Do not assume the LLM provider is the best embedding provider.
- Benchmark candidate models using all three portal evaluation datasets.
- Track provider, model, version and vector dimension on indexed chunks.
- Use compatible model/version for corpus and query vectors.
- Validate vector count, dimensions and numeric values.
- Batch within provider limits; use bounded retries and timeouts.
- Never mix incompatible embedding spaces in one active index.
- Support controlled re-embedding migrations.
- Queue ingestion if the embedding provider is unavailable.

### 6.3 Selection criteria

Evaluate retrieval precision/recall, MRR/nDCG where useful, latency, cost, vector dimensions, provider terms, English and Tamil/English mixed queries if required. Use one shared model only if it performs adequately across all three portals; otherwise support separate named profiles.

## 7. Shared ingestion framework

### 7.1 Pipeline

```text
Portal-approved source
        |
Portal-specific connector
        |
Portal-specific approval and scope validation
        |
Shared job lifecycle / retry / hashing
        |
Portal-specific normalization and chunking
        |
Shared embedding orchestration
        |
Portal-specific repository and collection
        |
Portal-specific publish verification
```

### 7.2 Shared capabilities

- Job creation and state transitions.
- Idempotency keys and content hashing.
- Retry scheduling and dead-letter visibility.
- Batch execution and concurrency limits.
- Correlation IDs, metrics and safe logs.
- Embedding orchestration and publish hooks.

### 7.3 Portal-owned capabilities

Each portal owns its source allowlist, approval validation, visibility, role/region scope, normalization, chunking, metadata validation, target schema, withdrawal rules and retrieval eligibility.

The shared worker must require a trusted portal-specific ingestion policy. Never trust client/model-supplied portal or scope metadata.

### 7.4 Job lifecycle

Use explicit states such as:
`queued`, `validating`, `extracting`, `normalizing`, `chunking`, `embedding`, `publishing`, `completed`, `retry_scheduled`, `failed`, `withdrawn`.

Jobs must be idempotent and retryable. Never publish a partial version as active. Activate a new version only after verification. Withdrawn/expired content must be excluded immediately. A failed ingestion must not silently remove a still-valid approved version.

## 8. Shared retrieval primitives

Shared code may provide:
- Vector similarity helpers.
- PostgreSQL full-text search helpers.
- Candidate normalization and deduplication.
- Result fusion.
- Optional reranker interface.
- Provenance formatting.
- Retrieval timing and metrics.

Each portal supplies a trusted retrieval policy defining its database role, schema/collection, portal, role/scope filters, approval/effective-date rules, visibility, result limits and ranking policy.

Mandatory rules:
- No universal cross-portal search endpoint.
- No model-selected schema or collection.
- No model-supplied region/customer identity as trusted scope.
- Authorization filters apply before results reach the model.
- Rerank only already-authorized candidates.
- Never retrieve broadly and rely on final-answer filtering.
- Cache keys include portal, role, trusted scope, selected region, source/index version, embedding model and retrieval configuration.
- Invalidate cache on role/region changes, source withdrawal, approval changes and index/model updates.

## 9. Portal isolation and database security

### 9.1 Knowledge domains

| Domain | Access |
|---|---|
| Customer RAG | Customer harness only |
| Kitchen RAG | Kitchen harness only |
| Management RAG | Management harness only |

Use separate PostgreSQL schemas and least-privilege database roles. A shared PostgreSQL instance is acceptable; unrestricted shared tables are not.

Recommended logical layout:

```text
customer_rag:   knowledge_documents, knowledge_chunks, ingestion_jobs, ingestion_events
kitchen_rag:    knowledge_documents, knowledge_chunks, ingestion_jobs, ingestion_events
management_rag: knowledge_documents, knowledge_chunks, ingestion_jobs, ingestion_events
shared_ai:      optional provider metadata, prompt versions, evaluation run metadata
```

Use Alembic migrations. Verify pgvector version, vector dimensions and index options against the selected deployment.

### 9.2 Service identities

Use distinct identities for each portal's retrieval/harness. Ingestion identities must be scoped to the portal being processed. A multi-portal worker must not gain broad read access simply because it runs common code.

### 9.3 Required negative tests

- Customer cannot retrieve Kitchen or Management chunks.
- Kitchen cannot retrieve Customer or Management chunks.
- Management cannot retrieve Customer or Kitchen chunks.
- Management RM cannot retrieve another region or CA-only content.
- Role/region changes invalidate stale context and caches.
- Model arguments cannot override trusted identity or scope.
- Prompt injection cannot expose another portal's data.
- Shared retrieval helpers cannot run without explicit trusted portal policy.
- Unauthorized content never reaches the model.

## 10. Configuration and secrets

Typed, validated configuration should cover:
- Provider and approved model profile.
- Embedding profiles.
- Timeouts, retries, rate limits and concurrency.
- Portal-specific prompt versions.
- Portal-specific retrieval settings.
- Ingestion limits.
- Redaction and logging policy.
- Feature flags.

Secrets must be stored in environment-backed secrets or an approved secret manager. Never commit, index, prompt with or log credentials, tokens, passwords, private keys or raw environment dumps.

AI cannot modify provider settings, secrets, prompts, retrieval policy or deployment configuration.

## 11. Observability

### 11.1 Safe trace fields

Capture:
- Request/correlation ID and portal.
- Harness and prompt version.
- Provider/model and embedding model/version.
- Retrieval configuration version.
- Ingestion job/source identifiers.
- Tool name and duration.
- Retrieval duration and candidate counts.
- Token usage where available.
- End-to-end latency.
- Error/fallback category.
- Evaluation run ID.

### 11.2 Redaction

Do not log API keys, tokens, passwords, payment credentials, full customer addresses/phone numbers, unnecessary staff personal data or unredacted private support conversations.

Production content traces, if required, must be sampled, redacted, access-controlled, retention-limited and explicitly approved.

### 11.3 Metrics

Monitor LLM success/timeout/429 rates, provider latency P50/P95, embedding failures, ingestion throughput/freshness, failed jobs, retrieval latency, abstention rates, tool authorization denials, token cost by portal, user feedback and feature availability.

Metrics may be aggregated across the platform, but access to portal content remains isolated.

## 12. Shared evaluation framework

Provide a common runner for versioned test cases, retrieval metrics, answer grounding, tool selection, authorization tests, latency/cost, regression comparisons and human review.

Keep datasets separate:

- **Customer:** menu facts, FAQs, customer-visible policies, serviceability tools, allergy uncertainty, portal leakage attempts.
- **Kitchen:** recipe/version correctness, SOPs, food handling, order-specific recipe pinning, staff/Manager permissions, leakage attempts.
- **Management:** policies, RM/CA authority, regional boundaries, KPI definitions, live report accuracy, leakage attempts.

Use human-reviewed expected answers and source references. LLM-as-judge may supplement but must not be the only evaluator. Track model, prompt, embedding and retrieval versions. Security leakage target is zero.

## 13. Background worker

Use a background worker for approved-source ingestion, reconciliation, re-embedding migrations, evaluation jobs and retention cleanup.

Requirements:
- Idempotent jobs and bounded retries.
- Dead-letter visibility.
- Portal-scoped execution identity.
- Concurrency limits and graceful shutdown.
- Structured logs and metrics.
- No blocking of user-facing portal requests.

Reuse an existing job mechanism where suitable. Do not add Kafka or a large distributed queue for the POC without evidence.

## 14. Failure and graceful degradation

| Failure | Expected behaviour |
|---|---|
| LLM provider unavailable | AI unavailable response; portal continues |
| Embedding provider unavailable | Queue ingestion; no invalid vectors |
| One portal RAG schema unavailable | Disable that portal's RAG only |
| Retrieval timeout | Safe abstention or bounded failure |
| Ingestion fails | Preserve last valid approved version if still effective |
| Evaluation fails | Mark run failed; never report partial pass |
| Authorization service unavailable | Deny private retrieval and tools |
| Provider rate limit | Bounded backoff or safe unavailable result |
| Observability sink unavailable | Do not block portal operations |

Never fall back from one portal's collection to another.

## 15. Deployment topology

Initial Docker Compose deployment:
- FastAPI application.
- PostgreSQL with pgvector.
- Background worker.
- Redis only if justified by existing needs.
- MinIO only if approved source storage requires it.

External approved LLM/embedding providers are accessed through adapters.

Include health/readiness checks, controlled migrations, distinct API/worker runtime roles, resource limits, backups and restore validation, safe centralized logs, feature flags per portal and reproducible environment configuration.

Do not add Kubernetes, service mesh, dedicated vector database, Kafka or multiple agent frameworks until measured workload or reliability needs justify them.

## 16. Suggested repository structure

Adapt to the existing repository; do not reorganize working code without need.

```text
app/
├── ai/
│   ├── shared/
│   │   ├── gateway/
│   │   │   ├── interfaces.py
│   │   │   ├── schemas.py
│   │   │   └── providers/groq.py
│   │   ├── embeddings/
│   │   ├── ingestion/
│   │   ├── retrieval/
│   │   ├── evaluation/
│   │   ├── observability/
│   │   └── config/
│   └── portals/
│       ├── customer/
│       ├── kitchen/
│       └── management/
├── workers/
│   └── ai_ingestion/
└── migrations/
```

Portal modules own prompts, connectors, authorization, repositories, retrieval policies, tools, context and tests. Shared modules must not import portal-private content or permissions.

## 17. Implementation phases

### Phase 0 — Repository discovery
- Inspect existing repository and dependencies.
- Inspect FastAPI modules, database models, provider integrations and background workers.
- Verify PostgreSQL/pgvector availability.
- Map the three portal specifications to existing code.
- Produce a gap analysis before changing files.

**Exit:** Approved implementation plan and dependency inventory.

### Phase 1 — Contracts and configuration
- Define typed LLM/embedding interfaces.
- Define normalized errors and correlation IDs.
- Define portal identity and service boundaries.
- Define safe trace schema and redaction policy.

**Exit:** Contract tests pass without portal code depending on provider SDKs.

### Phase 2 — LLM gateway
- Implement Groq adapter and mock adapter.
- Implement normalized requests/responses.
- Add timeout, retry, rate-limit and health handling.
- Add usage and model-version tracking.

**Exit:** All three harnesses use the same gateway contract.

### Phase 3 — Embedding abstraction
- Benchmark candidate models.
- Select model/profile based on evaluation.
- Implement adapter, validation and model metadata.
- Document re-embedding migration.

**Exit:** Compatible vectors are reproducible and versioned.

### Phase 4 — Ingestion primitives
- Implement job lifecycle, hashing, idempotency and retry.
- Define portal policy interface.
- Connect each portal's approved ingestion pipeline separately.
- Add withdrawal and publish verification.

**Exit:** Each portal ingests only its approved corpus.

### Phase 5 — Retrieval primitives
- Implement vector and lexical helpers.
- Add fusion and provenance.
- Require trusted policy injection.
- Add scope-aware cache contract and negative tests.

**Exit:** Reusable retrieval code does not create unrestricted cross-portal search.

### Phase 6 — Observability and evaluation
- Implement redacted traces and metrics.
- Implement evaluation runner.
- Connect separate portal datasets.
- Add regression reports.

**Exit:** Quality, security, latency and cost are measurable per portal.

### Phase 7 — Hardening and rollout
- Test provider/database/worker failures.
- Test role and scope invalidation.
- Run prompt and retrieval regressions.
- Validate backups and deployment.
- Enable portals through independent feature flags.

**Exit:** Portal owners approve security, reliability and quality.

## 18. Acceptance checklist

- [ ] All three harnesses use the internal LLM gateway.
- [ ] Groq is isolated behind an adapter.
- [ ] Credentials are managed securely.
- [ ] Embedding provider is replaceable.
- [ ] Embedding model/version/dimension are tracked.
- [ ] Ingestion is idempotent, retryable and version-aware.
- [ ] Portal-specific approval and scope policies remain separate.
- [ ] Retrieval requires trusted portal policy.
- [ ] No universal cross-portal retrieval endpoint exists.
- [ ] Database roles and schemas are isolated.
- [ ] Cache keys include portal and authorization scope.
- [ ] Role/region/source changes invalidate caches.
- [ ] Observability is redacted and portal-partitioned.
- [ ] Evaluation datasets remain portal-specific.
- [ ] Cross-portal leakage tests pass with zero leakage.
- [ ] Provider, embedding, database and worker failures degrade safely.
- [ ] Core portal workflows do not depend on AI availability.
- [ ] Docker Compose deployment is reproducible.
- [ ] No unjustified distributed infrastructure has been introduced.

## 19. Required deliverables

1. Existing-repository AI infrastructure gap analysis.
2. Shared architecture and trust-boundary diagram.
3. Typed LLM gateway and Groq adapter.
4. Embedding interface and model decision record.
5. Ingestion job lifecycle and portal policy interface.
6. Retrieval primitives with trusted policy injection.
7. Service identity and database permission plan.
8. Safe observability schema and redaction rules.
9. Evaluation runner with separate portal datasets.
10. Deployment configuration and operational runbook.
11. Failure-mode and security test report.
12. Prompt/model/embedding versioning and migration strategy.

## 20. Final implementation instruction

Build a small, provider-independent shared AI platform for three isolated portal harnesses. Share mechanisms, not permissions or private knowledge.

Start by inspecting the existing repository and producing a gap analysis. Do not immediately scaffold or rewrite the project. Implement one layer at a time, test every boundary, and obtain approval before changing portal isolation, data access, provider policy or business rules.

Target FastAPI, PostgreSQL/pgvector and Docker Compose, with Groq as the initial LLM provider and a replaceable embedding provider. Keep the system modular, observable, testable and non-blocking for core DeliverIQ operations.

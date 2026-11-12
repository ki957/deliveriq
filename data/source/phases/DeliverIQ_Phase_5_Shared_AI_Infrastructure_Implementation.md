# DeliverIQ POC — Phase 5 Shared AI Infrastructure Implementation

**Document:** Phase 5 Master Implementation Specification  
**Project:** DeliverIQ — AI-enabled single cloud kitchen delivery platform  
**Phase:** 5 — Shared AI Infrastructure Implementation  
**Version:** 1.0  
**Status:** Implementation specification; gated by approved Phase 1–4 outputs  
**Prepared:** 11 November 2026

---

# 1. Executive summary

Phase 5 implements the shared AI platform used by DeliverIQ's three independent portal AI systems:

1. Customer AI harness and Customer RAG.
2. Kitchen AI harness and Kitchen RAG.
3. Unified Management AI harness and Management RAG.

The shared platform provides common infrastructure—not shared portal permissions or shared knowledge access.

It includes:
- Provider-independent LLM gateway.
- Provider-independent embedding service.
- Shared document ingestion framework.
- Shared retrieval primitives.
- AI observability and evaluation.
- Security identities, configuration and operational controls.

Each portal retains its own harness, prompts, tools, knowledge collection, authorization policy, evaluation set and feature flag.

**Core rule:** shared infrastructure may be reused; portal data, permissions and retrieval scope must remain isolated.

Phase 5 does not yet deliver complete portal-specific RAG experiences. It builds and validates the reusable platform those integrations will use in Phase 6.

---

# 2. Entry gates

Do not begin implementation until these prerequisites are validated.

| Gate | Required evidence |
|---|---|
| G1 | Phase 1 repository and architecture audit |
| G2 | Approved ADR for LLM gateway/provider strategy |
| G3 | Approved embedding model and vector dimensions, based on benchmark |
| G4 | Phase 2 data ownership and portal isolation contracts |
| G5 | Stable identity and backend authorization foundation |
| G6 | Stable application API and error conventions |
| G7 | Audit, logging and correlation foundations |
| G8 | Phase 4 database, migration and CI foundations |
| G9 | Approved Customer, Kitchen and Management RAG specifications |
| G10 | Resource baseline and local deployment profile |

If a gate is incomplete, create a tracked dependency rather than silently choosing a provider, model or security rule.

---

# 3. Architecture and boundaries

## 3.1 Target architecture

```text
Customer Portal Harness ─────┐
Kitchen Portal Harness ──────┼── Shared AI Platform
Management Portal Harness ───┘        │
                                     ├── LLM Gateway
                                     ├── Embedding Service
                                     ├── Ingestion Framework
                                     ├── Retrieval Primitives
                                     ├── Observability
                                     └── Evaluation Framework

Customer Harness ── Customer APIs + Customer RAG only
Kitchen Harness ─── Kitchen APIs + Kitchen RAG only
Management Harness ─ Management APIs + Management RAG only
```

The diagram is logical. It does not require separate deployable microservices. Implement modules inside the approved modular monolith unless Phase 1 evidence justifies separate workers or services.

## 3.2 Shared versus isolated

| Shared capability | Must remain portal-specific |
|---|---|
| Provider adapter interfaces | System prompts and policies |
| Model invocation mechanics | Tool allowlists |
| Embedding client | Knowledge collections |
| Document extraction primitives | Source approval workflows |
| Chunking utilities | Retrieval filters and scope |
| Vector/lexical search primitives | Portal authorization |
| Evaluation runner | Evaluation datasets and thresholds |
| Telemetry infrastructure | Portal-specific audit context |
| Retry and timeout utilities | User/session context |

## 3.3 Security boundary

The platform must not expose an endpoint that searches every portal's documents.

Portal identity must be derived from trusted backend application context, not from a model-generated field or user-supplied request parameter.

Every retrieval request must be bound to:
- Authenticated principal.
- Portal identity.
- Effective roles.
- Authorized region/kitchen scope where applicable.
- Approved collection.
- Request/session correlation ID.

Reject missing or inconsistent scope. Default to deny.

---

# 4. Workstream A — LLM gateway

## A1. Purpose

The LLM gateway is the only application-level path for model inference. Portal harnesses must not instantiate provider SDKs directly.

The gateway standardizes:
- Provider selection.
- Model allowlists.
- Request/response schemas.
- Timeout and retry behaviour.
- Token usage metadata.
- Error normalization.
- Streaming where required.
- Cost and latency measurement.
- Provider-specific configuration.

## A2. Provider strategy decision

The project has discussed Groq and OpenRouter. Resolve their exact relationship in an ADR before implementing adapters.

Possible approved arrangements:

| Option | Description | Consideration |
|---|---|---|
| A | Groq is the initial provider; OpenRouter deferred | Simplest POC |
| B | OpenRouter is the routing provider; Groq is accessed through it | One routing layer, provider availability and terms must be validated |
| C | Internal gateway supports direct Groq and OpenRouter adapters | More flexibility, more testing and configuration |

Do not create a gateway that calls another internal gateway without a documented reason. Avoid duplicate routing, retries and billing layers.

Provider choice must consider:
- Supported models and API compatibility.
- Data handling and retention terms.
- Availability and rate limits.
- Latency in the target deployment region.
- Structured output/tool-calling support.
- Streaming behaviour.
- Cost and quota.
- Failure semantics.

## A3. Gateway contract

Define a provider-neutral request model containing only required fields:
- Model profile.
- Messages/instructions.
- Tool definitions when approved.
- Output constraints.
- Temperature or other supported generation controls.
- Token limit.
- Timeout.
- Correlation metadata.

Define a normalized response:
- Content or structured result.
- Provider and model identifier.
- Finish reason.
- Usage metadata when available.
- Latency.
- Request ID.
- Normalized error information.

Do not silently discard provider errors or fabricate token usage.

## A4. Reliability

- Explicit connection and request timeouts.
- Bounded retries only for retryable failures.
- Exponential backoff with jitter where appropriate.
- No blind retry for non-idempotent external actions.
- Per-provider concurrency limits.
- Circuit-breaker behaviour only if justified.
- Safe fallback to a configured model profile when approved.
- Clear unavailable response when no provider is healthy.
- Cancellation propagation where supported.

A model fallback must not change a portal's permission boundary or silently downgrade a safety-critical policy.

## A5. Security

- Provider keys remain server-side.
- Model names are allowlisted.
- User input and retrieved content are treated as untrusted.
- Secrets and unnecessary personal data are redacted before telemetry.
- Tool execution is not delegated to provider-side code execution.
- Provider output is validated before application use.

## A6. Acceptance tests

- Valid request to configured provider.
- Unknown model rejected.
- Provider timeout normalized.
- Rate limit handled safely.
- Retry does not duplicate application mutations.
- Missing provider credential fails safely.
- Provider outage does not block order workflows.
- Portal cannot select an unapproved provider/model.
- Logs do not expose API keys or sensitive content.

---

# 5. Workstream B — Embedding service

## B1. Separation from LLM gateway

Embedding generation is a distinct capability. Do not assume the chat provider and embedding provider must be the same.

Define a provider-independent interface for:
- Document embedding.
- Query embedding.
- Batch embedding.
- Model metadata.
- Vector dimension.
- Normalization expectations.
- Error and retry handling.

## B2. Model selection benchmark

Do not select an embedding model solely by popularity.

Build a representative evaluation set containing approved examples from:
- Customer menu and policy content.
- Kitchen recipes, SOPs and troubleshooting.
- Management procedures and KPI definitions.

Keep the actual content and access scope separated in evaluation runs.

Evaluate:
- Recall@k.
- Precision@k where labels permit.
- MRR or nDCG where relevance judgments exist.
- Multilingual and domain terminology performance.
- Query latency.
- Batch throughput.
- Vector dimension and storage cost.
- Provider availability and cost.
- Data handling constraints.

Use a fixed, versioned test set. Document limitations if relevance labels are small.

## B3. Versioning and compatibility

Persist:
- Embedding provider.
- Model name.
- Model version where available.
- Vector dimension.
- Creation timestamp.
- Document/chunk version.
- Embedding configuration version.

A model or dimension change requires a migration/re-embedding plan. Never compare vectors from incompatible embedding spaces.

## B4. Acceptance tests

- Document and query dimensions match.
- Empty/invalid text is handled.
- Batch failures are reported and retryable.
- Model identity is recorded.
- Re-embedding does not publish partial mixed-version data.
- Embedding outage does not affect core operations.

---

# 6. Workstream C — Shared ingestion framework

## C1. Design principle

Share ingestion mechanics, not portal approval policy.

Each portal owns:
- Its allowed sources.
- Source owner.
- Approval authority.
- Classification.
- Region/kitchen scope.
- Publication and withdrawal permission.

The shared framework provides reusable processing stages.

## C2. Ingestion lifecycle

```text
Source registered
      ↓
Authorization and approval check
      ↓
Extract and normalize
      ↓
Validate content and metadata
      ↓
Hash and version
      ↓
Chunk
      ↓
Generate embeddings
      ↓
Write staged version
      ↓
Verify counts, metadata and vectors
      ↓
Publish atomically
      ↓
Record audit and metrics
```

Failed ingestion must not expose partial content.

## C3. Source adapters

Use an interface for approved sources such as:
- Approved Markdown documents.
- Structured database projections.
- Explicitly approved file formats.

Do not ingest arbitrary filesystem paths or unrestricted URLs. Avoid indexing raw database tables directly.

## C4. Normalization and chunking

- Normalize whitespace and encoding.
- Preserve headings and section hierarchy.
- Preserve table meaning where supported.
- Remove boilerplate only through deterministic rules.
- Keep source references and provenance.
- Use overlap only when benchmarked.
- Avoid splitting recipe steps, policy clauses or KPI definitions in misleading ways.
- Apply size limits and reject unsupported content.
- Preserve language and source metadata.

Chunking parameters must be evaluated against representative content, not chosen as universal constants.

## C5. Content and metadata validation

Validate:
- Portal.
- Source ID.
- Document ID.
- Document version.
- Region/kitchen scope when required.
- Classification.
- Approval status.
- Effective-from/effective-until dates where relevant.
- Content hash.
- Chunk index and count.
- Embedding model/version.
- Source provenance.

Do not allow the document body to override trusted metadata.

## C6. Idempotency and versioning

- Stable source identity.
- Content hashing.
- Deterministic versioning.
- Duplicate job detection.
- Retry-safe writes.
- Superseded version tracking.
- Atomic publish and withdrawal.
- Reconciliation for interrupted jobs.

## C7. Deletion and withdrawal

Support:
- Source withdrawal.
- Document replacement.
- Expiry.
- Invalid-content removal.
- Chunk deletion or deactivation.
- Cache invalidation.
- Audit of who approved and executed the change.

A withdrawn document must not remain retrievable through stale vectors or lexical indexes.

## C8. Acceptance tests

- Duplicate ingestion is idempotent.
- Failed job does not publish partial content.
- New version replaces old version only after verification.
- Withdrawal removes active retrieval access.
- Metadata mismatch is rejected.
- Unauthorized source registration is denied.
- Reconciliation identifies orphaned or stale records.

---

# 7. Workstream D — Shared retrieval primitives

## D1. Retrieval pipeline

Implement reusable primitives:

1. Validate trusted portal and principal context.
2. Resolve approved collection and scope.
3. Normalize query.
4. Generate query embedding.
5. Run vector candidate search.
6. Run lexical candidate search.
7. Fuse candidate rankings.
8. Apply provenance and access validation.
9. Optionally rerank if benchmark evidence justifies it.
10. Return bounded, attributed context to the portal harness.

Authorization filters must be applied inside the retrieval boundary before content is returned to the model.

## D2. Hybrid retrieval

Use PostgreSQL lexical search and pgvector if Phase 1/2 confirms that stack.

Evaluate:
- Vector-only baseline.
- Lexical-only baseline.
- Hybrid retrieval.
- Hybrid plus reranking, only if useful.

Use a representative query set and relevance judgments.

## D3. Candidate fusion

Choose a deterministic fusion strategy and document its parameters. Reciprocal Rank Fusion may be evaluated as a baseline.

Do not claim that hybrid retrieval is automatically better; retain it only if evaluation supports the complexity.

## D4. Reranking

Reranking is optional.

Add only if:
- Retrieval benchmark identifies ranking errors.
- Measured relevance improvement is meaningful.
- Latency/cost fit the POC budget.
- Provider/data handling is approved.

## D5. Retrieval response

Return:
- Chunk text.
- Document/source reference.
- Section metadata.
- Portal and approved scope metadata.
- Version/effective status.
- Retrieval method and score metadata where useful.

Do not return unrestricted database rows or unrelated portal metadata.

## D6. Live data versus RAG

RAG is for approved knowledge, not authoritative current operational facts.

Use authorized APIs for:
- Current price.
- Availability.
- Serviceability.
- Delivery quote and ETA.
- Current order state.
- Current stock/reservations.
- Kitchen capacity/mode.
- Revenue, staffing and current KPI values.

Never answer live questions from stale indexed snapshots when an authoritative API exists.

---

# 8. Workstream E — Portal isolation and service identities

## E1. Collection isolation

Maintain independent logical collections and retrieval configurations:
- Customer knowledge.
- Kitchen knowledge.
- Management knowledge.

Separate physical schemas or databases only if the threat model, repository constraints or operational requirements justify them. Logical separation alone must still be enforced by trusted server-side authorization and query construction.

## E2. Service identity

Each portal retrieval path must have a distinct service identity or equivalent explicit backend authorization context.

A portal must not be able to:
- Change its portal identifier to access another collection.
- Supply another user's identity.
- Expand its region/kitchen scope.
- Override document classification.
- Invoke an unrestricted retrieval function.

## E3. Role and scope

- Customer: public customer knowledge and authenticated own-resource APIs.
- Kitchen Staff: approved kitchen knowledge and permitted operational context.
- Kitchen Manager: approved kitchen knowledge plus Manager-authorized read tools.
- RM: Management knowledge and live data for assigned regions.
- CA: approved global Management knowledge and live data.

Management RAG does not directly query Customer or Kitchen RAG.

## E4. Security testing

Create negative tests for:
- Portal ID tampering.
- Collection name tampering.
- Region ID tampering.
- Kitchen ID tampering.
- User ID substitution.
- Role escalation.
- Stale permission cache.
- Cross-session context reuse.
- Cross-portal cache collision.
- Prompt injection attempting to reveal restricted content.

A prompt instruction is not an authorization mechanism. Backend checks are mandatory.

---

# 9. Workstream F — AI observability

## F1. Traceability

For each AI request, capture appropriate metadata:
- Request/correlation ID.
- Portal.
- Authorized principal reference or pseudonymous identifier.
- Model profile and provider.
- Model version.
- Prompt version.
- Retrieval configuration version.
- Embedding model version.
- Tool names invoked.
- Latency.
- Token usage when returned.
- Cost estimate when reliably calculable.
- Outcome/error category.
- Feature flag state.

## F2. Privacy

Do not log by default:
- API keys.
- OTPs.
- Passwords or session tokens.
- Full payment details.
- Unnecessary personal data.
- Full prompts or retrieved content without an approved retention and redaction policy.

Define retention and access controls for AI traces. Restrict trace access by role.

## F3. Metrics

Track:
- Request count.
- Success/error rate.
- Provider availability.
- Latency percentiles.
- Token usage and estimated cost.
- Timeout and retry rate.
- Retrieval empty-result rate.
- Retrieval latency.
- Ingestion lag and failure rate.
- Stale/withdrawn content detection.
- Portal isolation denials.
- Evaluation score over time.

## F4. Acceptance

- Requests can be correlated across gateway and retrieval.
- Metrics are separated by portal.
- Sensitive fields are redacted.
- Retention is enforced.
- Logs do not become an alternate knowledge store.

---

# 10. Workstream G — Evaluation framework

## G1. Evaluation layers

Evaluate components separately:

| Layer | Evaluation |
|---|---|
| Ingestion | Completeness, metadata correctness, freshness |
| Retrieval | Recall@k, MRR/nDCG, scope correctness |
| Generation | Grounding, correctness, abstention, clarity |
| Tool use | Correct tool, arguments and authorization |
| Security | Injection resistance and isolation |
| Operations | Latency, reliability and cost |

## G2. Test datasets

Create separate, versioned datasets for Customer, Kitchen and Management.

Each example should include:
- Query.
- Expected relevant source/chunk references where applicable.
- Required facts.
- Forbidden facts.
- Expected tool use or abstention.
- Portal and role scope.
- Evaluation rubric.

Use synthetic or approved non-sensitive data. Do not mix portal evaluation corpora.

## G3. Required quality tests

- Answer supported by retrieved evidence.
- Correct source attribution.
- No answer when evidence is insufficient.
- Conflicting or outdated document handling.
- Current fact routed to API rather than RAG.
- Wrong portal content is never retrieved.
- Unauthorized tool request is denied.
- Prompt injection is treated as untrusted input.
- Malformed provider output is handled safely.

## G4. Release thresholds

Do not invent a single universal quality percentage. Define per-portal acceptance thresholds after establishing a baseline and reviewing the risk of each task.

Security isolation has a zero-tolerance policy: any confirmed cross-portal disclosure blocks release.

---

# 11. Workstream H — Configuration, feature flags and failure handling

## H1. Configuration

- Central typed configuration.
- Per-environment settings.
- Per-portal model profiles.
- Model allowlists.
- Timeout and concurrency limits.
- Retrieval settings.
- Ingestion schedules.
- Safe secret injection.
- Configuration validation.
- Audit for sensitive configuration changes.

## H2. Feature flags

Provide independent flags for:
- Shared AI availability.
- Customer AI.
- Kitchen AI.
- Management AI.
- Individual tool groups where appropriate.

Turning off one portal must not disable the other two.

## H3. Graceful degradation

If the LLM provider is down:
- Core customer ordering still works.
- Kitchen processing continues.
- Delivery assignment/tracking continues.
- Management operations continue.
- AI UI reports temporary unavailability.
- No stale or fabricated answer is returned as a fallback.

If embeddings or ingestion are down:
- Existing valid published knowledge may remain usable if freshness policy permits.
- New/changed documents remain unpublished until verified.
- Stale or withdrawn content must not be served.
- Live API facts remain available.

---

# 12. Database and module implementation guidance

Follow approved Phase 2 schemas and Phase 1 repository structure.

Potential logical modules:
- `ai_gateway`
- `ai_embeddings`
- `ai_ingestion`
- `ai_retrieval`
- `ai_observability`
- `ai_evaluation`
- `customer_ai`
- `kitchen_ai`
- `management_ai`

These are conceptual boundaries, not mandatory directory names.

Shared AI metadata may require records for:
- Provider/model profiles.
- Embedding model versions.
- Ingestion jobs and events.
- Document versions.
- Chunk metadata.
- Evaluation runs.
- AI request traces.

Portal-specific RAG tables and collections must follow their approved specifications. Do not create duplicate schemas without checking the existing Customer, Kitchen and Management RAG documents.

All migrations must be reviewed and tested. Do not apply destructive schema changes without a backup/recovery plan.

---

# 13. API and internal contract guidance

Define internal interfaces for:
- Chat completion.
- Structured generation.
- Embedding generation.
- Batch embedding.
- Ingestion job submission/status.
- Document publish/withdraw.
- Portal-scoped retrieval.
- Evaluation execution.
- Health and readiness.

Contracts must include:
- Typed request and response.
- Authentication/service identity.
- Portal and scope context.
- Timeout.
- Idempotency where appropriate.
- Stable error categories.
- Correlation ID.
- Versioning policy.

Do not expose internal provider credentials, unrestricted model selection or unrestricted retrieval endpoints to the frontend.

---

# 14. Resource and performance plan

The local POC resource envelope is approximately 14 GB usable RAM with 2 GB reserved headroom, subject to Phase 1 confirmation.

Measure:
- Gateway memory and concurrency.
- Embedding batch memory.
- Ingestion worker memory.
- PostgreSQL and pgvector memory.
- Vector/lexical query latency.
- Model provider latency.
- Concurrent AI requests.
- Cache memory if caching is enabled.
- CPU, disk and network usage.

Prefer external inference providers for the POC rather than hosting large models locally unless a measured requirement changes that decision.

Do not add Redis solely because caching is mentioned. Start with the simplest approved implementation and measure before adding infrastructure.

---

# 15. Implementation sequence

| Gate | Implementation | Exit evidence |
|---|---|---|
| P5.0 | Confirm ADRs and AI contracts | Provider, embedding and security decisions approved |
| P5.1 | AI module and configuration foundation | Validated configuration and service boundaries |
| P5.2 | LLM gateway | Provider adapter and failure tests pass |
| P5.3 | Embedding service | Benchmark and compatibility tests pass |
| P5.4 | Ingestion framework | Idempotent, versioned, atomic publish works |
| P5.5 | Retrieval primitives | Vector/lexical/hybrid benchmark complete |
| P5.6 | Portal isolation | Negative cross-portal tests pass |
| P5.7 | Observability | Redacted traces and metrics available |
| P5.8 | Evaluation framework | Repeatable evaluation runs available |
| P5.9 | Reliability and resource validation | Failure and resource tests pass |
| P5.10 | Shared AI platform acceptance | Product/engineering approval |

Do not integrate all three portal harnesses before the shared platform passes its security and reliability gates.

---

# 16. Required deliverables

| ID | Deliverable |
|---|---|
| P5-D01 | Approved LLM provider strategy ADR |
| P5-D02 | LLM gateway interface and provider adapter |
| P5-D03 | Embedding benchmark and model decision |
| P5-D04 | Embedding service implementation |
| P5-D05 | Shared ingestion framework |
| P5-D06 | Shared retrieval primitives |
| P5-D07 | Portal isolation and service identity controls |
| P5-D08 | AI observability and privacy policy |
| P5-D09 | Evaluation datasets and runner |
| P5-D10 | Feature flags and degradation controls |
| P5-D11 | Security and performance test reports |
| P5-D12 | Shared AI platform runbook |

---

# 17. Phase 5 exit criteria

- [ ] Provider strategy is explicitly approved; Groq/OpenRouter responsibilities are unambiguous.
- [ ] Portal harnesses use the internal gateway, not provider SDKs directly.
- [ ] Embedding model is benchmarked and versioned.
- [ ] Vector dimension compatibility is enforced.
- [ ] Ingestion is approved, idempotent, versioned and retryable.
- [ ] Partial ingestion cannot publish.
- [ ] Withdrawal and cache invalidation are tested.
- [ ] Retrieval supports measured lexical/vector/hybrid comparison.
- [ ] Portal and region/kitchen authorization is enforced server-side.
- [ ] No unrestricted cross-portal retrieval endpoint exists.
- [ ] Observability is useful and privacy-conscious.
- [ ] Evaluation is repeatable and portal-specific.
- [ ] AI provider failure does not affect core workflows.
- [ ] Resource usage is measured against the POC envelope.
- [ ] Security tests show no cross-portal leakage.
- [ ] Runbooks and known limitations are documented.
- [ ] Product owner accepts the shared platform.

---

# 18. Handoff to Phase 6

**Recommended Phase 6: Portal-Specific AI Harness and RAG Integration.**

Implement independently in this order, subject to product priorities:
1. Customer AI harness and Customer RAG.
2. Kitchen AI harness and Kitchen RAG.
3. Management AI harness and Management RAG.

For each portal, implement:
- Portal-specific system instructions.
- Trusted identity and scope context.
- Tool registry and backend authorization.
- Portal-only retrieval configuration.
- Source ingestion and approval.
- Retrieval and answer grounding.
- Prompt-injection and data-leakage tests.
- Portal-specific evaluation.
- Feature flag and graceful degradation.

The Delivery Agent Portal remains without an AI chatbot in the initial POC.

---

# 19. Engineering agent execution prompt

Act as DeliverIQ's shared AI platform engineering lead.

First inspect the actual repository and compare it with approved Phase 1–4 outputs and the three portal RAG specifications. Identify existing reusable code, missing modules, conflicts and exact proposed file changes before editing.

Resolve the Groq/OpenRouter relationship through an approved ADR. Do not create duplicate gateways or route requests through unnecessary layers.

Implement one shared capability at a time. Keep provider-specific code behind adapters. Keep embeddings independent from chat inference. Make ingestion idempotent, versioned, auditable and atomic. Apply trusted authorization filters before retrieval results are exposed to a model.

Never create unrestricted cross-portal retrieval. Never treat prompts as security controls. Do not let model output authorize a tool action. Do not implement AI mutations in this phase.

Do not add databases, queues, caches, brokers or microservices without measured need. Preserve the core order-to-delivery workflow when AI providers fail.

For each increment, report:
- What changed and why.
- Exact files/modules affected.
- ADRs and contracts used.
- Tests and evaluation results.
- Security and isolation evidence.
- Resource measurements.
- Remaining gaps and decisions requiring approval.

Phase 5 is complete only when the shared AI platform is reliable, measurable, secure and ready for independent portal integrations.

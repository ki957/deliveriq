# DeliverIQ — Design Decision Register

**Status legend:** `Decided` (product owner approved in this session) · `Proposed` (recommendation awaiting approval) · `Open` (owner input required) · `Recorded` (discrepancy logged, no action needed)
**Source file numbers:** see `SOURCE_DOCUMENT_INVENTORY.md`

---

## Part A — Decided

### DDR-01 Customer palette — Palette B (Decided)

- **Decision:** Customer Portal uses primary `#A8C9CB`, background `#FFFFFF`, accent `#F45B0B`.
- **Basis:** Portal-specific sources #1 §2 ("Approved visual direction") and #2 §3.
- **Discrepancy recorded:** The older consolidated specifications assign Palette A (`#FFF21A`, `#171717`, `#A66BFF`) to Customer:
  - `Harness_Engineering_Architecture_and_End_to_End_Build_Blueprint.md` §10.2
  - `data/DeliverIQ_Minimum_Required_Data_and_Synthetic_Seed_Dataset.md` §5 (calls Palette B an "earlier/alternate proposal")
  - `data/DeliverIQ_Generated_POC_Seed_Data (1).md` §15 (leaves Palette B unassigned)
  These are superseded by the portal-specific documents. Do not edit them; treat their palette sections as historical.
- **Constraint:** Do not blend A and B. Accessible text colours may be added (#2 §3). White text on `#A8C9CB` or `#F45B0B` must pass contrast checks before use.

### DDR-02 Delivery palette — Palette A (Decided)

- **Decision:** Delivery Agent Portal uses yellow `#FFF21A`, near-black `#171717`, purple `#A66BFF`.
- **Basis:** #7 §11 and #8 §3, both portal-specific.
- **Discrepancy recorded:** Older sources list Palette A as Customer (see DDR-01) and #14 §5 / #15 §17 say no Delivery palette is confirmed. Superseded by #7 and #8.
- **Usage (from #7/#8):** near-black surfaces and text; yellow primary actions; purple secondary/selected.

### DDR-03 Frontend stack — React + TypeScript + Vite + Tailwind CSS + shadcn/ui (Decided; ADR required)

- **Decision:** One React/TypeScript/Vite application with role-protected portal routes; Tailwind for styling; shadcn/ui (Radix-based) components.
- **Conflict:** #2 §1.6 and §13, #5 §2.4–5 and §6, #8 §2.7 and §8, and #11 Gate A tell the implementer **not to assume a framework**, and to offer a static HTML/CSS option. The Requirements spec §2 specifies CSS / CSS Modules.
- **Resolution:** The product owner has explicitly chosen the framework, which satisfies those documents' "ask before assuming" instruction. Their honesty rules still apply (no fake functionality, label mock data).
- **ADR to write (Task 0):** `ADR-UI-001 Tailwind + shadcn/ui replaces CSS Modules`. Consequences: Tailwind build step, shadcn components copied into the repo (not an npm runtime dependency), per-portal theme via CSS variables.

### DDR-04 Kitchen palette (Decided — consistent)

`#D5360C`, `#E6D58D`, `#101010`; semantic status colours separate (#4 §12.3, #5 §5). No conflict.

### DDR-05 Management palette (Decided — consistent)

`#021861`, `#255DCE`, `#DE1110`, `#FFFFFF`, `#F3F5FA`; red used sparingly (#10 §13, #11). No conflict.

### DDR-09 Imported recipes remain DRAFT (Decided)

All 104 SOP recipes import with status `DRAFT` and stay non-orderable and non-reservable until chef validation and explicit activation (see DDR-10/11). Basis: #13 header and every card ("POC draft — chef validation required").

### DDR-10 Recipe approval workflow (Decided — states and KM activation authority)

```text
DRAFT ──submit──> PENDING_VALIDATION ──validate──> VALIDATED ──activate──> ACTIVE
  ^                    │                              │                     │
  └─────return─────────┘                              └──reject──> REJECTED │
                                                                            v
                                                           SUPERSEDED / DISABLED
```

- Only `ACTIVE` recipe versions can be pinned to accepted orders and drive stock reservation (#13 global controls, #4 §6.4).
- Every transition records actor, role, timestamp and reason.
- **Authority:** the Kitchen Manager is the final system authority that executes `VALIDATED → ACTIVE`. The five release-checklist sign-offs from #13 (chef, food-safety lead, inventory owner, Kitchen Manager, product owner) remain **mandatory audit records**: activation is rejected unless all five are recorded, but recording them does not itself activate the recipe, and no other role can activate.
- A new version supersedes the old for **new** orders only; pinned orders keep their version.
- Quarantined records (DDR-13) cannot be submitted until resolved.

### DDR-11 Customer menu publication workflow (Decided — states; RM and CA publication authority per DDR-31)

(DDR-12 is reserved and unused.)

**Publication authority (DDR-31, decided 2026-11-11):**
- **Central Administrator** may publish menu items in any region.
- **Regional Manager** may publish menu items only in assigned regions.
- Both must satisfy the full readiness checklist below. Neither can bypass recipe activation; only items linked to an `ACTIVE` recipe version can be published.
- Every publication action writes an audit record with actor, role, region, timestamp, menu item and action.
- RBAC region restrictions are enforced in the backend; UI visibility of the publish control follows the same rule but is not the security boundary.
- No other role (Kitchen Manager, Kitchen Staff, Delivery Agent, Customer) can publish.

```text
DRAFT ──> READY_FOR_PUBLICATION ──publish──> PUBLISHED ──> TEMPORARILY_UNAVAILABLE (RM-approved) ──> PUBLISHED
                                                  └──────> RETIRED
```

`READY_FOR_PUBLICATION` requires, per menu item:
- an `ACTIVE` recipe version;
- approved price (tax-inclusive) and tax classification;
- category, customer description, veg/non-veg flag, spice level;
- kitchen-configured customization options (may be empty);
- estimated preparation time;
- image or labelled placeholder;
- verified allergen data **only if** displayed.

None of these exist in #13 (see `KITCHEN_SOURCE_VALIDATION.md` §5.5). Real SOP dishes remain non-publishable until DDR-32 data is supplied and validated. End-to-end workflow testing uses synthetic test menu items under DDR-48; these never enter a production menu. Dish-unavailability approval (#4 §7.3, #10 §5) toggles `TEMPORARILY_UNAVAILABLE` and does not edit the recipe.

### DDR-13 MENU008 / MENU057 duplicate (Decided)

Both are "Mini Batata Wada" with identical preparation, portion, ingredients and quantities. Import both, each with its own source reference, status `QUARANTINED_DUPLICATE_CANDIDATE`. Do not delete, merge or pick one. Owner must decide whether these are one dish, two category placements, or an extraction error.

### DDR-14 Unavailable-customer wait (Decided)

Configuration key `CUSTOMER_UNAVAILABLE_WAIT`, default **5 minutes**, scope region (matches #15 §6). Resolves the wording difference between #1 §10 ("configured period") and #7 §7 / #10 §6 / #11 ("five minutes").

### DDR-17 Canonical order statuses (Decided)

Defined in `PORTAL_REQUIREMENTS_MATRIX.md` §7. Three independent machines (fulfilment, payment, assignment) plus item status. Portals derive labels. Resolves vocabulary differences across #1 §10, #4 §6.1, #7 §5, #19 §13 I2 and the Harness blueprint §8.1.

### DDR-18 Kitchen AI read-only; SOP AI stock-deduction command excluded (Decided)

- #13 "Kitchen AI inventory command SOP" (`<dish> x <portions>` posting stock, FEFO lots, receipts) is **out of MVP**.
- Conflicts resolved in favour of #4 §11.2 and #6 §2.3 (AI cannot modify stock).
- Related exclusion: SOP lot/FEFO/expiry controls conflict with #4 §7.4 (expiry/batch tracking excluded). Inventory MVP uses ingredient-level ledger without lots. Keep the SOP text as source content; do not implement it.
- **Scope clarification (2026-11-12):** DDR-18 governs Kitchen AI. Management AI write capability is defined only by DDR-68–DDR-71.

### DDR-19 AI and ML order (Decided)

Management Copilot → Kitchen Copilot → Customer Assistant → Demand forecasting → ETA prediction and assignment optimization.
- **Discrepancy recorded:** #21 §14 recommends Customer → Kitchen → Management "subject to product priorities". Owner priority wins.
- Customer Assistant additionally gated on all other portals being complete (#1 §12, #2 §2).

### DDR-20 Data engineering stack (Decided)

*Amended by DDR-59 (2026-11-12): Dagster is dropped.* Python CLI pipelines + dbt Core on PostgreSQL first; Dagster introduced at DE-10. Synthetic data generator writes to a separate `synthetic` schema; results labelled simulated. Consistent with the ETL spec. #19 lists "advanced analytics warehouse" out of scope; dbt on the existing PostgreSQL is not a separate warehouse.

### Owner decisions — 2026-11-11 (Decided)

The product owner confirmed the following decisions. These supersede conflicting sample/default values in source data.

| Decision | Confirmed value | Implementation rule |
|---|---|---|
| Delivery fee (DDR-38) | ₹30 flat | Apply a flat ₹30 delivery fee per order; do not infer a distance-based fee. |
| Free-delivery threshold (DDR-38) | None | No free-delivery threshold or waiver. |
| Kitchen location (DDR-39) | Not provided | Do not invent a real address or coordinates. Location-dependent production configuration remains blocked. |
| Opening stock (DDR-37) | Test-only | Use clearly labelled synthetic/test opening stock only; do not represent it as actual kitchen stock. |
| Recipe activation (DDR-30) | Kitchen Manager (KM) | KM performs final activation after required validation and recorded release sign-offs. |
| Menu publication (DDR-31) | Regional Manager (RM) and Central Administrator (CA) | CA publishes in any region; RM publishes only in assigned regions. Both require the full DDR-11 readiness checklist and an ACTIVE recipe version; every action audited (actor, role, region, timestamp, menu item, action). *Updated 2026-11-11; supersedes RM-only.* |
| Synthetic test menu items (DDR-48) | Approved | Labelled `TEST –` synthetic menu items allowed in test environments only for end-to-end checkout testing; see DDR-48. |
| Customer visibility of agent assignment (DDR-16, partial) | Immediately after assignment | Customer sees "Agent Assigned" as soon as an agent is successfully assigned, without waiting for `READY_FOR_PICKUP`. Assignment does not change fulfilment status and does not imply pickup or `OUT_FOR_DELIVERY`. |
| Special-instruction limit (DDR-07) | 250 characters | Enforce the limit in UI and backend validation. |
| Delivery PWA (DDR-15) | Installable | Build an installable Delivery PWA. Offline action queue and background geolocation are not approved by this decision. |
| GPS retention (DDR-43) | 30 days | Retain delivery GPS records for 30 days, then delete or irreversibly anonymise them per the retention job. Sampling interval remains open. |

**Authority mapping:** The five SOP release-checklist sign-offs remain required audit records. KM is the system role that executes final recipe activation; this does not remove the underlying sign-off requirements. RM (assigned regions) and CA (all regions) are the system roles that publish menu items.

### DDR-16 Agent-assignment visibility and `OUT_FOR_DELIVERY` (Decided; visibility 2026-11-11, transition 2026-11-12)

- **Decided:** "Agent Assigned" is shown to the customer immediately after a delivery agent is successfully assigned (assignment status `ACCEPTED`), regardless of whether the order is `ACCEPTED`, `PREPARING` or `READY_FOR_PICKUP`.
- Assignment status and fulfilment status stay separate machines (DDR-17). Assignment never changes `orders.fulfilment_status`.
- Assignment does not mean pickup. Only the agent's validated pickup action sets `PICKED_UP`.
- `OUT_FOR_DELIVERY` is never entered because of assignment.
- If the assignment is revoked or reassigned, the customer indicator reflects the current assignment only.
- **Decided (2026-11-12):** `PICKED_UP → OUT_FOR_DELIVERY` happens automatically after the validated pickup, in the same transaction. There is no separate agent action for it.

### DDR-48 Synthetic test menu items (Decided, 2026-11-11)

- Clearly labelled synthetic menu items are allowed for end-to-end checkout, kitchen and delivery workflow testing.
- Every item's display name starts with `TEST –`.
- Items exist only in test databases/environments. Production menu queries, production seeds and real customer ordering never see them.
- Items are independently created synthetic records. They are **never** copied, derived, renamed or adapted from `/home/k/Downloads/task1/kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md`, which remains the only authoritative real recipe source.
- Test recipes, opening stock (DDR-37), test orders and simulated payments created from them are also flagged and labelled as test data.
- Real SOP dishes remain non-publishable until DDR-32 requirements are supplied and validated.
- **Required leak controls:**
  - `is_test_fixture` flag on menu items, recipes, orders, order items and payments, set by the fixture loader and not editable via API.
  - Fixture loader refuses to run unless the environment is local/test.
  - Production-profile startup check fails if any `is_test_fixture` row exists.
  - Customer menu query in production profile filters `is_test_fixture = false` as defence in depth.
  - dbt real models exclude fixture rows; tests assert zero fixture rows in real marts.
  - Automated test asserts no fixture name matches any SOP dish name.

### Owner decisions — 2026-11-12 (Decided)

All entries below were approved by the product owner on 2026-11-12.

#### Scope and product

| DDR | Decision |
|---|---|
| DDR-49 | **POC purpose:** portfolio/interview demo. Production-only blockers are out of POC scope and become known limitations. |
| DDR-50 | **Demo menu:** only `TEST –` synthetic dishes (DDR-48) are published and ordered. No SOP recipe is ever activated in this POC; the activation workflow (DDR-10) is demonstrated only on TEST recipes. SOP import, reconciliation and review queue still run on the real SOP. |
| DDR-51 | **Assignment timing:** a delivery agent is assigned at kitchen acceptance. The GPS tracking session starts at assignment (#7 §6); customer live tracking still starts only after pickup. |
| DDR-52 | **GPS during network loss:** points are held in a bounded in-memory buffer and re-sent on reconnect; the backend rejects stale or out-of-order points (#7 §6). Pickup, OTP and other actions remain blocked offline. An offline action queue is not approved. |
| DDR-53 | **Coupon vs minimum:** the ₹500 minimum is checked on the food subtotal before the coupon (#1 §9 sequence). A coupon may reduce the payable total below ₹500. |
| DDR-54 | **Recipe sign-offs:** the product owner records the product-owner sign-off; the Kitchen Manager records the other four. Applies to TEST recipes only (DDR-50). |
| DDR-55 | **Road distance:** behind an adapter. A labelled stub in daily development; an optional local OSRM with a Chennai-city extract in an `osrm` Compose profile for road-rule tests and demos. Both distance rules (CU-03) remain required. |
| DDR-56 | **Synthetic data:** demo seed of 7 days × 10 orders/day; ML training set of 90 days × 30 orders/day (~2,700 orders), generated offline once. Both live in `synthetic`, are labelled simulated, and use TEST dishes only. |
| DDR-58 | **Language:** English only for all RAG and evaluation. Supersedes the Tamil/mixed-language provisions in #3, #6 and #9 and the earlier session answer; recorded deviation. |
| DDR-61 | **EIB data:** `EIB Data.xlsx` is excluded from DeliverIQ unless its relevance is established. |

#### Platform and infrastructure

| DDR | Decision |
|---|---|
| DDR-57 | **Embeddings:** a local CPU English model in the worker process, int8 ONNX, lazy-loaded, batch ingestion. The specific model is chosen by benchmark (DDR-45, procedure DDR-89). *Amended by DDR-88: local is the default behind an embedding adapter.* |
| DDR-59 | **Orchestration:** Dagster is dropped. Jobs are triggered from the backend/UI or the CLI; optional scheduling uses a timer inside the worker. Amends DDR-20. |
| DDR-60 | **Version control:** GitHub + GitHub Actions. Approved read-only source copies are committed with provenance; CI verifies their SHA-256 against `SOURCE_DOCUMENT_INVENTORY.md`. |
| DDR-62 | **RAM efficiency (estimates, to be measured):** Compose profiles `core` (Postgres, Redis, API), `worker`, `osrm`, `e2e`, `agent`; only `core` runs daily. PostgreSQL `shared_buffers` 256MB, `work_mem` 4MB, `max_connections` 20, `maintenance_work_mem` 64MB. Redis `maxmemory` 64mb, no persistence. One Uvicorn worker in dev. Vite runs on the host; no frontend container in dev. The embedding model loads only in the worker and is released after ingestion. dbt `threads` 2, on demand. Playwright: Chromium only, headless, 2 workers; heavy E2E/visual suites run in GitHub Actions. `mem_limit` is set only after measurement. |

#### Data pipelines

| DDR | Decision |
|---|---|
| DDR-63 | **Shared pipeline-runs framework** for P1 SOP master-data ETL, P2 operational ELT, P3 synthetic generation and the three RAG ingestion jobs. A PostgreSQL job-queue table and a single worker container; dbt runs as a subprocess. Tables: `ops.pipeline_runs`, `ops.pipeline_stage_runs`, `ops.ingestion_errors`, `ops.dq_results`, `ops.source_registry`. Each job connects with its own per-pipeline DB role. UI: a "Data Pipelines" area in the Management portal with groups **Data** and **Knowledge**; the CLI uses the same entry points. |
| DDR-64 | **Pipeline permissions:** the Central Administrator triggers, cancels, retries and views all runs. The Regional Manager views runs and results for assigned regions only (P3 read-only, labelled simulated). All other roles are denied. Enforced in the backend. |
| DDR-65 | **P1 fault injection:** a separate TEST-only input file of synthetic recipe cards written from scratch (e.g. "TEST – Fault Card 01"), never derived from or modifying SOP records. It covers a missing unit, zero quantity, unknown unit, missing field and duplicate card. Allowed only when `APP_ENV` is `local` or `test`; the backend rejects it in production; the file is excluded from production images; runs are flagged as test. |
| DDR-66 | **P2 hybrid:** a worker loop continuously lands outbox events to raw; the UI shows the live outbox backlog and oldest-event age. dbt staging → core → marts → tests runs on demand by the CA. An optional interval schedule exists, off by default, with a CA-only toggle. |
| DDR-67 | **Pipeline operating rules:** see list below. |

**DDR-67 rules:**
1. Transient errors auto-retry up to 3 times with backoff; data/quality failures never auto-retry.
2. CA "Retry run" re-runs the whole pipeline (idempotent); there is no resume-from-stage.
3. P1: a structural failure fails the whole run and nothing loads. Record-level failures are quarantined; valid records load as DRAFT; status "Completed with quarantine".
4. P2: critical dbt tests (keys unique/not-null, referential integrity, source-to-mart reconciliation counts) fail the run and marts are not marked fresh. Warning tests (e.g. freshness) are recorded only.
5. One active run per pipeline; heavy jobs (dbt, embedding) run one at a time; event landing continues.
6. Queued runs cancel immediately; running jobs stop at the next stage boundary and become Cancelled.
7. Run history is kept indefinitely for the POC.
8. Data contracts: P1 typed parsed-card schema; P2 versioned event envelope (Harness blueprint §8.2) plus dbt sources/tests; RAG chunk metadata per the RAG specs.
9. Live status via WebSocket with REST refetch (PL-14).
10. `reset-test-data` is CLI only and local/test only; there is no UI reset.

#### Management AI

| DDR | Decision |
|---|---|
| DDR-68 | **Management AI split into three harnesses:** (a) Management Copilot, read-only and unchanged, for RM and CA per #9; (b) Management Operational Actions, CA only; (c) Builder Agent, CA only. Customer and Kitchen remain read-only; Delivery has no AI. This is a deliberate, owner-approved deviation from the read-only/no-write rules in #9 §2.3 and §13.3, #10 §11, #12 §2 and #21 §8.3. Those prohibitions continue to bind the Management Copilot harness. |
| DDR-69 | **Operational Actions:** typed, allowlisted tools. Each shows a confirmation dialog with the exact change, executes through the same backend service and RBAC checks as the UI, is idempotent and is audited. **Allowed:** kitchen mode/capacity, agent assign/reassign, dish-unavailability approval, promotions, review moderation, exceptional refund approval (disabled until DDR-44 thresholds exist), regional settings, menu publication (TEST items only per DDR-50). **Excluded:** staff/role changes, RM creation and region assignment, AI provider/model settings, integrations, secrets, global YAML at runtime, customer suspension, refund overrides. |
| DDR-70 | **Builder Agent:** an on-demand sandbox container in the `agent` Compose profile, working on a throwaway repo copy. No access to the live DB, Redis or `.env` secrets; outbound network limited to GitHub and the configured LLM provider hosts (amended by DDR-85; originally Groq and GitHub); CPU/memory capped; destroyed after each task. Flow: change → unit tests in sandbox → CA reviews diff in UI → PR opened → GitHub Actions CI → owner merges on GitHub. The agent never merges and never pushes to `main` (branch protection required). |
| DDR-71 | **Builder Agent invariants:** it cannot modify its own prompts, guardrails, permissions, RBAC, secrets or CI workflow files. Untrusted content (reviews, tickets, orders, notes, RAG documents) never enters its context. Global YAML changes go only through the PR path. |

#### Data pipelines (continued) and build process

| DDR | Decision |
|---|---|
| DDR-74 | **Synthetic data path:** P3 synthetic events (`synthetic.events`) flow through the same dbt models into a separate `analytics_synthetic` schema. Real and synthetic data never share a table. |
| DDR-75 | **POC marts:** daily sales, menu, kitchen, inventory, delivery, payment. Customer experience and operational exceptions are deferred. |
| DDR-76 | **Knowledge content:** drafted by Kiro from source rules only, every paragraph citing its source. Enters as DRAFT and is approved in-app and audited: Customer and Management documents by the CA, Kitchen documents by the KM. Only approved content publishes. |
| DDR-77 | **TEST recipes in Kitchen RAG:** may be indexed in test/demo environments only, flagged `is_test_fixture`; the production profile refuses them. Amends the previous "TEST recipes never indexed" rule. |
| DDR-78 | **GPS in analytics:** GPS points stay only in `app.delivery_locations` (30-day retention). No per-point events; `delivery.completed` carries a GPS summary. A few synthetic full tracks exist for the map demo. `raw` remains append-only. |
| DDR-79 | **Host setup:** Kiro CLI performs host setup during the build (uv Python 3.12, Node pin, SSH/git setup). Any change to the owner's user/shell configuration (e.g. conda config) requires owner confirmation at the time. |

#### Application code structure

| DDR | Decision |
|---|---|
| DDR-80 | **Code structure** per `CODE_STRUCTURE_DESIGN.md`: domain modules with thin layers; dependency rules enforced by `import-linter` in CI; a `README.md` card for every feature and every AI harness. |
| DDR-81 | **API contract:** TypeScript client generated from FastAPI OpenAPI and committed; CI fails on drift. |
| DDR-82 | **Data access:** sync SQLAlchemy 2.x + psycopg 3 for repositories and services; async only for WebSockets, Redis pub/sub and outbound HTTP. |
| DDR-83 | **Dependencies:** uv with `pyproject.toml` + `uv.lock` and groups `api`, `worker`, `dev`; npm with a committed lockfile. |
| DDR-84 | **Frontend routing:** React Router (Requirements spec baseline). |

#### RAG and AI (per `RAG_AI_DESIGN.md`)

| DDR | Decision |
|---|---|
| DDR-85 | **Provider-neutral model gateway:** one OpenAI-compatible adapter plus a mock adapter. Providers, logical models (`fast`, `strong`, `guard`), capabilities and harness routing live in `backend/config/ai_models.yaml`; keys only in `.env` / Actions secrets, one key per provider. Groq is the default provider; OpenRouter or another OpenAI-compatible provider can be added by config only. Per-provider rate limits and circuit breaker; optional fallback chain, off by default. Startup capability check per harness. Supersedes the DDR-26 proposal (Groq direct, OpenRouter deferred). Amends DDR-70 egress: proxy allowlist = GitHub + configured provider hosts. |
| DDR-86 | **Default model routing:** `openai/gpt-oss-20b` (`fast`) for the Management Copilot, Operational Actions, Kitchen Copilot and Customer Assistant; `openai/gpt-oss-120b` (`strong`) for the Builder Agent. Free-tier rate limits to be recorded when the key exists. Closes the LLM part of DDR-45 and closes DDR-72. |
| DDR-87 | **Runtime model switch:** Management "AI settings" screen, CA only. The CA may move a harness to any logical model already in config whose provider has a key; capability-checked, stored in `ops.ai_routing_overrides`, audited, applied without restart; "reset to config default". The UI never adds providers or keys. Operational Actions and the Builder Agent cannot change routing; `ai_models.yaml` is a Builder protected path (extends DDR-71). |
| DDR-88 | **Embedding adapter:** local int8 ONNX in the worker is the default; a remote OpenAI-compatible embedder can be enabled by config; mock embedder in CI. Each index records its embedding model, dimension and hash. Changing the model always means a versioned re-index with atomic swap; vectors from two models never share an index. No runtime switch. Amends DDR-57. |
| DDR-89 | **Embedding benchmark:** candidates `bge-small-en-v1.5`, `e5-small-v2`, `gte-small`, `all-MiniLM-L6-v2` (baseline). Pass bar Recall@5 ≥ 0.85, p95 query embed ≤ 50 ms, added worker RSS ≤ 300 MB, run in the worker container. Best Recall@5 among passing models wins; tie → lower RSS. If none passes, the report goes to the owner, who decides. The winner is recorded here and closes the remaining part of DDR-45. |
| DDR-90 | **Golden sets (medium):** Customer, Kitchen and Management Copilot each 30 answerable + 10 must-refuse + leak tests (10 cross-customer; 8 TEST-leak + 6 KS/KM; 10 cross-region); Operational Actions 15 valid + 10 must-refuse; Builder Agent 3 tasks + 3 protected-path attempts; 10 shared injection cases. Drafted by Kiro from sources with expected citations/refusals; approved with the knowledge documents (CA or KM). Any scope-leak failure blocks release. |
| DDR-91 | **Conversation memory:** per conversation only; last 6 turns, older turns dropped (not summarised); stored 30 days then purged; users can delete their own. Builder Agent memory is task-scoped. `ops.ai_requests` keeps metadata only (no message text) for 90 days. Purge runs as a worker job. |
| DDR-92 | **Prompt Guard:** classifier on Customer Assistant input only, behind `AI_PROMPT_GUARD_ENABLED`. Checks the user message only; on classifier outage or rate limit, other defences apply and the event is logged (customers never blocked by it). Model ID in config. Injection cases are evaluated with it on and off. |
| DDR-93 | **System prompts v1** for Operational Actions and Builder Agent approved as written in `RAG_AI_DESIGN.md` §13. Closes DDR-73. |
| DDR-94 | **Knowledge document list approved:** K-C1–C3 (CA), K-K1–K3 (KM), K-M1–M3 (CA) per `RAG_AI_DESIGN.md` §15, stored under `knowledge/<portal>/`, approval keyed by content SHA-256. Content approval in-app remains open under DDR-46. |

#### Identity and portal shells (Task 4 decision sheet, approved 2026-11-12)

Sources define OTP login, sessions, trusted devices and RBAC (PL-02–PL-06, Phase 2 §8, #15 §4) but not their parameters. The owner approved the following values.

| DDR | Decision |
|---|---|
| DDR-95 | **Task 4 delivered as two PRs:** 4A backend identity, sessions and RBAC; 4B frontend scaffold and four portal shells. |
| DDR-96 | **Login OTP:** 6 digits; 5-minute expiry; 5 wrong attempts per code; 30 s resend cooldown; at most 5 requests per mobile and 20 per IP per 15 minutes, then a 15-minute lockout. Only HMAC-SHA256 hashes with a server pepper (`OTP_PEPPER`) are stored. MOCK_OTP (`123456`) only in `local`/`test`; startup fails otherwise. India mobiles only (`+91` + 10 digits starting 6–9); the #15 placeholder test range `+9100000xxxxx` is accepted only in `local`/`test`. |
| DDR-97 | **Registration and eligibility:** a new number at the customer portal becomes a Customer (name required at sign-up; email required before the first order, Task 6). Staff portals never create accounts. Staff without a CUSTOMER role cannot log in as customers (PL-03). Responses never reveal whether a number is registered. |
| DDR-98 | **Sessions:** opaque random token in an HttpOnly, SameSite=Lax cookie; only its hash is stored; no JWT. 2-hour idle and 24-hour absolute expiry. Unsafe requests require a CSRF header; cross-origin access only from configured dev origins. Trusted device: optional after OTP login, skips OTP for 7 days from that login (not sliding), listable and revocable by the user. Any role change or deactivation immediately revokes all of the user's sessions and trusted devices. Redis unavailable: OTP requests fail closed; existing sessions (PostgreSQL) keep working. |
| DDR-99 | **RBAC:** permission codes (`area.action`) in a code catalogue with a role→permission map; `GET /api/v1/me` returns roles, scopes and permissions. Portal chosen by URL (`/customer`, `/kitchen`, `/delivery`, `/management`) with one shared, portal-themed login. Scope guards tested now through a test-only router (never mounted in production); real endpoints reuse them in Tasks 6–10. Staff accounts only via the local/test fixture loader (six #15 seed users) until Task 10. Auth events (OTP request without code, login success/failure, logout, revocations) go to `audit.events`. |
| DDR-100 | **Portal shells:** source-listed navigation; unbuilt screens show a labelled "Not built yet (Task N)" page; later Management features hidden until built. Placeholder wordmark "DeliverIQ" with a visible "Placeholder logo" badge (DDR-08); "Image unavailable" state (DDR-47). Status colours (closes the DDR-21 values): info `#1D4ED8`, success `#15803D`, warning `#B45309`, danger `#B91C1C`, neutral `#4B5563` (white text ≥ 5.02:1). Text on palette colours: `#101010` on `#A8C9CB`, `#F45B0B`, `#FFF21A`, `#A66BFF`, `#E6D58D`; white on `#D5360C`, `#021861`, `#255DCE`, `#DE1110`. Frontend libraries per the approved stack plus `@fontsource-variable/inter`, `openapi-typescript`, Vitest/Testing Library, Playwright + axe; all pinned. |

#### Pipelines, SOP import and workflows (Task 5 decision sheet, approved 2026-11-12)

| DDR | Decision |
|---|---|
| DDR-101 | **Task 5 delivered as three PRs:** 5A worker, job queue and P1 SOP import; 5B fault injection, TEST fixtures, recipe and menu workflow APIs, production fixture check; 5C Data Pipelines, Kitchen recipes/review queue and publish UI. |
| DDR-102 | **P1 parsing:** the eight card fields are the heading (menu ID + name), Preparation, Portion, Ingredients, Method, Quality, Inventory, Validation. Footer category and page number are stored as unconfirmed source attributes on the recipe version (no menu categories created; MENU001–012 have none; DDR-36). Reason codes: `MISSING_FIELD`, `BAD_INGREDIENT_LINE`, `ZERO_QUANTITY`, `MISSING_UNIT`, `UNKNOWN_UNIT`, `MULTI_UNIT_NAME`, `DUPLICATE_CARD_ID`, `DUPLICATE_BOM`, `MISSING_BATCH_RECIPE`, `COMPOSITE_INGREDIENT`, `AMBIGUOUS_INGREDIENT`. The review list is copied verbatim from `KITCHEN_SOURCE_VALIDATION.md` §5.1–5.3 into a config module with references, matched by exact normalized name. |
| DDR-103 | **Review queue and lineage:** review items in their own table; Kitchen Staff view, Kitchen Manager acknowledges with a note (never edits recipe data; DDR-33–36 stay owner decisions). A recipe with open review items cannot be submitted. Ingredient IDs are deterministic from the normalized name, origin `SOP_DERIVED`. Recipe versions store source path, card ID, page reference, import run and time; ingredient lines store original text and source hash. SOP recipes attach to `KIT-CHN-001` as version 1; same hash re-import adds nothing; a hash differing from the inventory fails the run with nothing loaded. The reconciliation report is stored with the run and downloadable via the API (not written to the repo). |
| DDR-104 | **Fault injection:** TEST fault files written from scratch in `backend/test_inputs/p1/` (never in images; mounted into the worker in local/test only): one with the five DDR-65 record faults, one with broken card structure (run fails, nothing loads). Fault runs stop at staging, never load into `app`, end as "Completed with quarantine", flagged as test. |
| DDR-105 | **Worker:** a ninth DB role `worker` (claim and heartbeat only; each job still connects as its own pipeline role). Poll every 2 s, heartbeat every 10 s, stale after 60 s. Transient errors retried after 5 s, 30 s, 2 min; data and quality errors never retried. Queued runs cancel immediately through a controlled function; running jobs stop at the next stage boundary. UI polls every 2 s until WebSockets in Task 11. P1 runs carry the kitchen's region. Permissions `pipelines.view` (CA; RM own region) and `pipelines.operate` (CA); recipe workflow permissions for the KM; review view (KS, KM) and acknowledge (KM). |
| DDR-106 | **Fixtures and workflow:** the PRODUCT_OWNER sign-off is recorded by a Central Administrator account (the owner acts as CA); the KM records the other four (DDR-54). Fixture loader adds three TEST dishes `TEST – Synthetic Dish A/B/C` (₹111, ₹222, ₹333) with ingredients `TEST – Ingredient 1–6` in `TEST – Category`, loaded activated and published, plus a fourth TEST recipe left in DRAFT for a live workflow demo. The API refuses to start in production if any fixture row exists. |
| DDR-107 | **Task 5B values (approved 2026-11-12):** (1) RM (assigned regions) and CA mark a menu item `READY_FOR_PUBLICATION` as well as publish; the database readiness check still applies. (2) TEST dish ingredients: A = TEST – Ingredient 1 + 2, B = 3 + 4, C = 5 + 6, D = 1 + 6; every line 100 g. (3) TEST menu readiness values: description "TEST – synthetic dish for workflow testing", veg true, spice level `TEST`, tax classification `TEST`, preparation 10 min, labelled image placeholder, no allergen data. (4) TEST recipe text fields read "TEST – synthetic, not a real recipe". (5) The fourth TEST recipe has menu item `TEST – Synthetic Dish D` at ₹444, left in DRAFT. (6) The KM performs submit, return, validate, reject and activate. (7) 5B adds a public read-only `GET /api/v1/menu/items` returning only PUBLISHED items and excluding fixtures in production; Task 6 extends it. (8) The OTP/session purge job is deferred to Task 11; its retention period is asked then. |
| DDR-108 | **Task 5C UI (approved 2026-11-12):** (1) Management gets a separate **Menu Publication** entry (`menu.publish`); "Menu & Inventory" stays a Task 10 placeholder. (2) The CA records the product-owner sign-off on a Management **Recipe Sign-off** screen (`recipes.signoff.product_owner`) listing TEST recipes in `PENDING_VALIDATION` or `VALIDATED`. (3) `GET /api/v1/pipelines` lists the inputs each pipeline accepts in the current environment (fault inputs only in local/test); the UI offers only those. (4) Reasons and notes are entered in an inline form under the action (labelled textarea, Confirm/Cancel); no dialog dependency. (5) A local/test loader command `load-e2e-recipe` adds one fresh `TEST – E2E <n>` DRAFT recipe and menu item before each E2E run (`make e2e`, CI); Dish D stays for the live demo; E2E rows accumulate in local/test databases like integration rows. (6) The recipe list filters and searches in the browser, no pagination. |
| DDR-109 | **Task 7 orders and payments (approved 2026-11-12):** (1) An order's `is_test_fixture` flag is derived in the database from the chosen dishes (all TEST or all real, never mixed) by a controlled function; order items and payments inherit it from their order. The API never sends the flag; in production the API refuses fixture dishes. Refines DDR-48 leak control 1. (2) The simulated payment result (SUCCESS, FAILED, TIMEOUT) is stated by the caller through a labelled payment-simulator call; TIMEOUT is a chosen result, not a clock. (3) A failed or timed-out prepaid payment cancels the order at once; the customer places a new order; one payment per order. (4) Checkout idempotency: client-generated UUID `Idempotency-Key` header, unique per customer, kept with the order; same key and request returns the original order, same key with a different request returns 409. (5) Routine refund: a prepaid order cancelled before acceptance or rejected by the kitchen is refunded in full at once (`REFUND_PENDING` then `REFUNDED`, both recorded); exceptional refunds stay disabled (DDR-44); COD has no refund. (6) Only DATA_PIPELINE §6.3 event types are emitted; refund and COD-collection events wait for approved types (Task 12). (7) Until Task 6 pricing, placement snapshots each dish's published price plus the ₹30 delivery fee (DDR-38). (8) Permissions `customer.orders.place` and `customer.orders.cancel` (CUSTOMER, own orders). |
| DDR-110 | **Task 6 customer checkout (approved 2026-11-12):** delivered as 6A (backend) and 6B (UI). (1) Popularity is undefined: a dish is filtered as "bestseller" only when explicitly flagged (no dish is flagged without owner approval); a popularity sort waits for Task 13 order data. (2) Spice-level filter options are the distinct values of published dishes; no list is invented. (3) Coupon rules are built (minimum, usage limit, active window, one per order) with no production coupons; local/test has one fixture coupon `TEST50` (₹50) to prove DDR-53; `POCWELCOME` stays inactive (#15 §11). (4) The bill states "Prices include applicable taxes"; no tax breakdown or rate until DDR-32. (5) Price protection: 30 minutes from adding the line to the cart; after that, a differing published price returns 409 with the new price and needs explicit confirmation; the accepted price is stored. (6) Road-distance stub = straight-line × 1.4, labelled "estimated"; OSRM when configured (Task 9); road-rule tests use fixed stub values. (7) Out of area shows the message, the kitchen's area and "Change location"; no invented list of nearby areas. (8) Visitors keep their location in the browser; logged-in customers save addresses; checkout requires login. (9) The `osrm` profile stays in Task 9; Task 6 proves the road rule through the adapter. (10) Dish customization is not built; dish detail states that none is configured. |
| DDR-111 | **Task 8 kitchen operations and inventory (approved 2026-11-12):** delivered as 8A (backend) and 8B (UI). (1) Labelled test defaults under DDR-42 (final values stay open): Normal capacity 10 (source test value), Busy capacity 5, acceptance timeout 5 min (on-screen "Overdue" flag only, #14, DDR-29); low-stock threshold per ingredient, unset by default and set by the KM; delay thresholds not used. (2) Capacity counts orders in `ACCEPTED`, `PREPARING` and `READY_FOR_PICKUP` (#4 §3: handed over is terminal). (3) Checkout is refused when the kitchen is Paused (`kitchen_paused`) or its accepted count has reached the mode's capacity (`kitchen_at_capacity`), KI-13; orders already placed wait as Incoming. (4) Not enough stock at acceptance: acceptance is refused with the short ingredients; the order stays Incoming; nothing is rejected automatically. (5) New fulfilment transitions `ACCEPTED`/`PREPARING`/`READY_FOR_PICKUP` → `REJECTED` ("cannot fulfil", KI-11), reason required, roles KM, RM and CA: releases the reservation, refunds a prepaid order in full (DDR-109 (5)) and revokes the agent offer. (6) Assignment at acceptance (DDR-51): in the same transaction an `OFFERED` assignment goes to an eligible agent (active, in the order's region, no live assignment, least recently assigned first); none eligible → "Awaiting agent", kitchen not blocked. Agent response, 60 s timeout, pool and online/offline stay in Task 9; until then every active agent counts as available (labelled). (7) Dish unavailability: kitchen staff or KM request "make unavailable" or "make available again" with a required reason; RM (own region) or CA approves, or rejects with a reason; only an approval changes the menu; one pending request per dish; audited. (8) TEST opening stock (DDR-37): 10,000 g for each `TEST – Ingredient 1–6`, flagged `is_test_fixture`, loaded only by the fixture loader and counted by the fixture guard; units g/ml/piece, no purchase-unit conversion. (9) The KM sees full inventory, adjusts stock by a signed amount with a required reason (never below reserved) and sets thresholds; Kitchen Staff see low-stock alerts only (new permission `kitchen.inventory.view`, KM); each ingredient lists the dishes that use it (KI-23, read-only). (10) Reject reason: free text, required, ≤ 500 characters. (11) The first item set to Preparing moves the order to Preparing; all items Prepared → Ready for Pickup; the staff member who changed the item is the actor (KI-06); "Start order" sets all items Preparing. (12) Out of Task 8: delay/ETA records (KI-10), substitution (KI-19), equipment-failure workflow (KI-16), notification channels (Task 11); Exceptions shows overdue Incoming orders and low stock only. (13) Queue refresh polls every 10 s until realtime (Task 11), labelled. (14) A reason is required for every mode or capacity change; KM in the Kitchen portal, RM/CA through the API (UI in Task 10). Mode changes, stock adjustments and unavailability decisions are audit-only (no approved event type, DDR-109 (6)). (15) Kitchen E2E adds a KDS project at 1920×1080; tablet runs the same flows. |
| DDR-112 | **Task 8B kitchen and management UI (approved 2026-11-12):** (1) Live Orders is intake (Incoming with accept/reject; held orders read-only in FIFO order); the Preparation Board is the work (cards with item controls), in three columns Accepted, Preparing, Ready for Pickup at KDS widths (≥ 1920 px). (2) "Overdue" is a red badge with icon and "waiting N min"; it never reorders; a note states the 5-minute test default. (3) Order cards show "Offered to <agent>", "Agent assigned: <agent>" or "Awaiting agent"; one note per page says agent availability is simulated until Task 9. (4) Accept, Start, Preparing and Prepared are one tap; Reject and "Cannot fulfil" use the inline reason form; mode, capacity, stock and threshold changes require a reason. (5) Poll every 10 s while the tab is visible, refresh after each action, show "Updates every 10 s · last updated hh:mm:ss". (6) Kitchen dish availability requests live in a "Dish availability" section of the Inventory screen. (7) Status colours per KI-U4: Preparing blue, Ready green, Overdue and Rejected red with text and icon, Incoming and Accepted neutral; text always shown. (8) `@kitchen` E2E runs on `tablet` (768×1024) and a new `kds` project (1920×1080), not on `desktop`. (9) Quantities show in the ingredient's unit, up to 3 decimals with trailing zeros trimmed; inputs use the same unit. |
| DDR-113 | **Task 9 delivery and tracking (approved 2026-11-12):** delivered as 9A (backend, migration 0011) and 9B (Delivery PWA UI); the optional `osrm` profile (DDR-55) is deferred and the labelled road stub stays. (2) Offer expiry: a worker sweep every 10 s marks OFFERED offers older than `AGENT_ASSIGNMENT_RESPONSE_TIMEOUT` (60 s) EXPIRED and re-offers; accept also refuses an offer older than 60 s. (3) Re-offer goes to the next eligible online agent, never one who already rejected or let this order expire; none eligible → "Awaiting agent", the sweep retries. (4) Only online agents get offers; new agents start offline; going offline expires an open offer; an agent with an accepted delivery cannot go offline; a manager may force offline only when the agent has no live delivery, with a reason. (5) Manager delivery actions are API-only in Task 9 (`management.agents.assign`, RM own region, CA): manual assign, reassign with reason (revokes the old agent at once), force offline, approve or reject a failure request, issue a new OTP after escalation; UI in Task 10. (6) Delivery OTP: 6 digits created at pickup, stored hashed, shown only on the customer's own order page ("Give this code to the agent"); no SMS (DDR-40); 3 wrong attempts set the exception flag and a manager may issue a new code with a reason; the UI alone never sets Delivered. (7) Customer unavailable starts the 5-minute wait (DDR-14), after which the agent may raise "Contact manager" (exception flag); refusal and failure need a reason and move the assignment to FAILURE_REQUESTED; manager approval sets DELIVERY_FAILED; no automatic refund on delivery failure (DDR-44 open; Task 10). (8) GPS: `app.delivery_locations` (PostGIS point, accuracy, device and server time, REAL or SIMULATED); only the agent holding the accepted assignment may send; points older than 120 s (labelled test default) or not newer than the last point are rejected; batches of at most 100; client buffer at most 300, oldest dropped; the customer sees only the latest point and only after pickup, refreshed every 10 s until Task 11. (9) Simulated GPS is chosen by the agent, moves in a straight line from kitchen to address, is stored as SIMULATED and badged "Simulated" everywhere; denied or unavailable GPS shows a warning and never invents coordinates. (10) Map: Leaflet + react-leaflet (pinned); configurable tile URL defaulting to public OSM with attribution, local demo only; E2E blocks tiles and checks the labelled fallback. (11) Retention: a daily worker job deletes points older than 30 days, idempotent, audited with the count; tests keep day 29 and delete day 31. (12) PWA: hand-written manifest and an app-shell-only service worker, no new dependency; no offline action queue; background GPS not built (DDR-15). (13) Events: `delivery.assigned` on agent accept; `delivery.completed` on OTP success with a GPS summary (point count, km, duration, REAL/SIMULATED mix); `delivery.failed` on manager approval; no per-point events (DDR-78). (14) Customer phone masked by default; "Show number" only for the agent's own active accepted delivery, each reveal audited. (15) Profile: the agent edits the name; no photo (no file storage, DDR-28, stated in UI); history is the agent's own last 30 days with duration from pickup to delivered; notifications stay in Task 11. (16) Stale TEST orders left by customer E2E are logged for Task 21. (17) The `worker` DB role gets no table grants: offer expiry and re-offer (`app.expire_and_reoffer()`) and GPS retention (`app.purge_delivery_locations(days)`) are narrow SECURITY DEFINER functions, and the worker gets EXECUTE on those two only; each writes its audit row and records SYSTEM as actor; kitchen acceptance uses the same re-offer function (`app.offer_next(order)`). (18) A rejected failure request returns the assignment to ACCEPTED (new transition FAILURE_REQUESTED → ACCEPTED, manager only, reason required). (19) Simulated GPS moves 15 m per point, one point every 5 s (about 11 km/h), both labelled simulation settings. (20) The agent's GPS session runs while an accepted delivery is open and the Delivery app is in the foreground (no background GPS, DDR-15); the screen says "Keep this app open while delivering". |

---

## Part B — Former proposals, approved as written (Decided 2026-11-12)

The owner approved DDR-21–25 and DDR-27–29 as written on 2026-11-12. DDR-26 was superseded by DDR-85. Per-row "Proposed" labels below are historical; every row is Decided.

### DDR-21 Shared design tokens (Decided 2026-11-12)

`shareddsah/` contains no design-system document. Approved token structure. Concrete status-colour values are chosen at Task 4 within this structure, contrast-checked, and shown to the owner for review:

| Token group | Proposal | Status |
|---|---|---|
| Colour roles | `--primary`, `--primary-foreground`, `--secondary`, `--accent`, `--background`, `--surface`, `--muted`, `--border`, `--text`, `--text-muted`, `--focus-ring` per portal theme | Proposed |
| Semantic status | `--status-info` (Preparing), `--status-success` (Ready/Delivered), `--status-warning`, `--status-danger` (Delayed/Failed), `--status-neutral` (Pending); identical across portals | Proposed |
| Spacing | 4 px base scale | Proposed |
| Radius / elevation | Restrained (per "no excessive rounded cards", #8 §3) | Proposed |
| Breakpoints | Tailwind defaults (`sm 640`, `md 768`, `lg 1024`, `xl 1280`, `2xl 1536`) plus a KDS check at ≥ 1920 | Proposed |
| Focus | 2 px visible ring, ≥ 3:1 against adjacent colour | Proposed |
| Touch targets | ≥ 44 × 44 px on Delivery and Kitchen tablet views | Proposed |

### DDR-22 Typography (Decided 2026-11-12)

Inter (self-hosted, no remote font service, per #8 §2.4) for all portals, with system-stack fallback. Management already recommends Inter (#10 §13).

### DDR-23 Accessibility target (Decided 2026-11-12)

Target WCAG 2.2 AA for contrast, focus and keyboard operation, checked with axe-core in Playwright. Automated checks do not prove full compliance; manual screen-reader and keyboard review is still required.

### DDR-24 Test tooling additions (Decided 2026-11-12)

- `@axe-core/playwright` (dev only) for accessibility checks.
- Playwright device emulation for mobile-first Delivery and Customer tests.
- Playwright `toHaveScreenshot` for visual regression (no external SaaS).
Each requires an ADR entry before install.

### DDR-25 Database schema naming (Decided 2026-11-12)

**Approved schema set** (as used by the approved designs): `app` (incl. outbox), `raw`, `staging`, `analytics`, `synthetic`, `analytics_synthetic`, `ops`, `audit`, `customer_rag`, `kitchen_rag`, `management_rag`. The ETL spec's `ai` schema is not used; AI request, routing and eval tables live in `ops`, and conversations in `app` (`RAG_AI_DESIGN.md` §16).

Conflict X-15: #17 suggests per-domain schemas (`identity`, `orders`, …); the ETL spec suggests `app`, `raw`, `staging`, `analytics`, `ai`, `audit`, `ops`; RAG specs require `customer_rag`, `kitchen_rag`, `management_rag`. Proposal: `app` for transactional tables (module ownership by table prefix and service boundaries), the ETL schemas for data engineering, three `*_rag` schemas with separate DB roles, plus `synthetic`. Decide in Task 3.

### DDR-26 Groq vs OpenRouter (Superseded by DDR-85, 2026-11-12)

#16 §9.1 and #20 §A2 leave this open. The earlier proposal (Groq direct adapter; OpenRouter deferred) is superseded: the owner chose a provider-neutral gateway with Groq as the default and OpenRouter addable by config (DDR-85).

### DDR-27 MongoDB (Decided 2026-11-12: not used)

#16 lists MongoDB "to verify"; baseline excludes it. Proposal: not used. No document-store use case identified.

### DDR-28 MinIO / Parquet / DuckDB (Decided 2026-11-12: not in initial Compose)

Listed as baseline in #10 §14 and #11; optional elsewhere. Proposal: not in initial Compose. DuckDB/Parquet may be used as files inside data-engineering tooling if a task needs them. MinIO only if RAG source binaries need object storage.

### DDR-29 Seed data reconciliation (Decided 2026-11-12)

Conflicts X-11, X-12, X-13 between the two `data/` files. Proposal:
- IDs: use `REG-CHN-001` / `KIT-CHN-001` style (from #15) as stable seed keys.
- Delivery fee: ₹30 flat, confirmed by owner; no free-delivery threshold. This supersedes the source proposal to leave the fee unset.
- Opening stock: test-only synthetic quantities; do not seed or imply actual kitchen stock.
- Acceptance timeout: configurable; test default 5 minutes clearly labelled test-only.
- MOCK_OTP fixed test code (#15 §4.2) allowed only in local/test, fails closed elsewhere.

---

## Part C — Remaining open decisions / blockers

Resolved owner decisions have been removed from this list and recorded in Part A.

| ID | Decision needed | Blocks task(s) | Source |
|---|---|---|---|
| DDR-06 | Food-card Add behaviour: A add directly / B always customize / C add if no customization else customize | 6 | #1 §4, #2 §1.8 |
| DDR-15 | Background-geolocation expectations only. Installability is decided (Part A); GPS buffering is decided (DDR-52); an offline action queue is not approved | 9 (background GPS only) | #7 §14 |
| DDR-41 | Lost-mobile recovery safeguards | 4 | #1 §5 |
| DDR-42 | Kitchen defaults: max capacity (10 is test value), Busy capacity, acceptance timeout, delay thresholds, low-stock thresholds. Labelled test defaults in use: DDR-111 (1) | 8 | #4 §17, #15 §7 |
| DDR-43 | Exact GPS sampling interval (30-day retention is decided) | 9 | #7 §14 |
| DDR-44 | Exceptional-refund thresholds/classes; KPI formulas and accounting definitions; audit retention/export; YAML editor vs validated upload | 10, 13, 15A | #10 §17, #11 |
| DDR-45 | Embedding model winner only, by the benchmark procedure in DDR-89. LLM model IDs are decided (DDR-86) | 16 | #12 §6, #20 |
| DDR-46 | Owner approval in-app of the knowledge documents drafted under DDR-76 (CA: Customer and Management; KM: Kitchen) and their golden sets (DDR-90) | 15–17 | #15 §14, DDR-76, DDR-94 |

**Closed on 2026-11-12 (kept for traceability):**

| ID | Was open for | Closed by |
|---|---|---|
| DDR-72 | Groq coding-capable model for the Builder Agent | DDR-86 (`openai/gpt-oss-120b`, `strong`) |
| DDR-73 | System prompts for the Operational Actions and Builder Agent harnesses | DDR-93 (`RAG_AI_DESIGN.md` §13) |

### Out of POC scope (labelled placeholders / known limitations, DDR-49)

These do not block any POC task. They are listed as known limitations at handover (Task 22).

| ID | Item | Placeholder used in the POC | Source |
|---|---|---|---|
| DDR-08 | Logo (SVG/PNG, light/dark), brand wording, tagline | Labelled placeholder wordmark | #2, #5, #8, #11 |
| DDR-32 | Real SOP dish data: per-dish prices, tax classification, descriptions, veg flag, spice level, customizations, prep time, images, allergens | `TEST –` dishes only (DDR-48, DDR-50) | #14 §10, #15 §17 |
| DDR-39 | Real kitchen address and coordinates | Labelled synthetic kitchen fixture | #15 §3 |
| DDR-40 | SMS provider and India DLT obligations | MOCK_OTP / dev adapter, local/test only | #7 §14, #10 §17 |
| DDR-47 | Reference websites/screenshots and image assets | Neutral "image unavailable" state | #2, #5, #8 |

### Non-blocking data-quality items (no SOP activation, DDR-50)

Recorded in the SOP review queue. They do not block any POC task because no SOP recipe is activated.

| ID | Item | Source |
|---|---|---|
| DDR-33 | Batch recipes / composition / buy-vs-make for prepared components and spice mixes (see Kitchen validation §5) | #13 |
| DDR-34 | Resolution of ingredient ambiguities (alternates, composite items, unspecified flavour) | #13 |
| DDR-35 | Final disposition of MENU008 / MENU057: one dish, two category placements, or extraction error. Import handling is decided in DDR-13 | DDR-13 |
| DDR-36 | Category for MENU001–MENU012 (no heading in source) and confirmation of footer-derived categories | #13 |

---

## Part D — ADRs to create in Task 0

| ADR | Title | From |
|---|---|---|
| ADR-001 | Modular monolith boundaries | Phase 1 ADR-001 |
| ADR-002 | PostgreSQL only; no MongoDB | DDR-27 |
| ADR-003 | Schema layout (`app`, ETL schemas, `*_rag`, `synthetic`) | DDR-25 |
| ADR-004 | Outbox + worker; no broker | ETL spec, #17 |
| ADR-005 | Canonical status machines | DDR-17 |
| ADR-006 | RBAC + region/kitchen scope | #10, #17 |
| ADR-007 | Provider-neutral model gateway; Groq default; CA runtime switch to configured models | DDR-85, DDR-86, DDR-87 |
| ADR-008 | Embedding adapter and selection by benchmark | #12, #20, DDR-88, DDR-89 |
| ADR-009 | Per-portal RAG schemas and DB roles | #12 §9 |
| ADR-012 | Docker Compose; RAM budget | Requirements spec |
| ADR-013 | No MinIO initially | DDR-28 |
| ADR-UI-001 | Tailwind + shadcn/ui | DDR-03 |
| ADR-UI-002 | Per-portal theme tokens; Palettes A/B assignment and historical discrepancy | DDR-01/02 |
| ADR-DATA-001 | SOP Markdown as sole recipe source; Excel mapping unavailable | Kitchen validation |
| ADR-DATA-002 | dbt Core; no Dagster; worker timer; synthetic schema | DDR-20, DDR-59 |
| ADR-DATA-003 | Shared pipeline-runs framework and per-pipeline DB roles | DDR-63 |
| ADR-DATA-004 | Synthetic data through shared dbt models into a separate schema | DDR-74 |
| ADR-CODE-001 | Module boundaries enforced with import-linter | DDR-80 |
| ADR-CODE-002 | OpenAPI-generated TypeScript client | DDR-81 |
| ADR-CODE-003 | Sync data access; async only for WebSockets, Redis and outbound HTTP | DDR-82 |
| ADR-AI-001 | Read-only AI except Management Operational Actions and Builder harnesses; SOP stock command excluded | DDR-18, DDR-68 |
| ADR-AI-002 | Builder Agent sandbox | DDR-70, DDR-71 |
| ADR-AI-003 | Operational Action tools | DDR-69 |
| ADR-AI-004 | Local CPU embeddings | DDR-57 |
| ADR-TEST-001 | axe-core, device emulation, screenshot regression | DDR-24 |

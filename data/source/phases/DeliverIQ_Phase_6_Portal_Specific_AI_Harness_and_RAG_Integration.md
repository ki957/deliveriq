# DeliverIQ POC — Phase 6 Portal-Specific AI Harness and RAG Integration

**Document:** Phase 6 Master Implementation Specification  
**Project:** DeliverIQ — AI-enabled single cloud kitchen delivery platform  
**Phase:** 6 — Portal-Specific AI Harness and RAG Integration  
**Version:** 1.0  
**Status:** Implementation specification; gated by approved Phase 1–5 outputs  
**Prepared:** 11 November 2026

---

# 1. Executive summary

Phase 6 integrates three independent AI experiences into DeliverIQ:

1. **Customer AI:** helps customers understand the menu, policies, ordering and their own order information.
2. **Kitchen AI:** helps kitchen staff understand recipes, SOPs, approved food-handling guidance and troubleshooting.
3. **Management AI:** helps Regional Managers and Central Administrators understand operational procedures, business policies, management documentation and analytics definitions.

Each portal receives its own:
- AI harness and system instructions.
- Tool registry and permission policy.
- RAG collection and retrieval configuration.
- Source approval and ingestion workflow.
- Context and session isolation.
- Evaluation dataset and acceptance thresholds.
- Feature flag and operational controls.

The three portals may reuse Phase 5 shared infrastructure, but must not share portal knowledge or authorization scope.

**Critical security rule:** authorization is enforced by backend services and retrieval boundaries. Prompts are not security controls.

AI remains read-only in the initial POC. It cannot place orders, issue refunds, change inventory, edit recipes, assign agents, approve requests, alter roles or modify configuration.

Core business workflows must remain usable when AI is disabled or unavailable.

---

# 2. Mandatory entry gates

| Gate | Required evidence |
|---|---|
| G1 | Phase 1 repository audit and accepted architecture decisions |
| G2 | Phase 2 approved data ownership, RBAC, API and event contracts |
| G3 | Phase 3 approved implementation backlog |
| G4 | Phase 4 stable authentication, authorization and core APIs |
| G5 | Phase 5 shared AI platform passes its acceptance tests |
| G6 | Customer RAG master specification approved |
| G7 | Kitchen RAG master specification approved |
| G8 | Management RAG master specification approved |
| G9 | Portal-specific knowledge sources and content owners identified |
| G10 | Privacy, retention, audit and AI feature-flag policies approved |

If a gate is incomplete, track it as a blocker. Do not bypass authorization or ingest unapproved data to accelerate delivery.

---

# 3. Target architecture

```text
                         DeliverIQ Application
                                  |
                ┌─────────────────┼─────────────────┐
                |                 |                 |
          Customer Portal    Kitchen Portal    Management Portal
                |                 |                 |
          Customer Harness   Kitchen Harness   Management Harness
                |                 |                 |
          Customer Tools     Kitchen Tools     Management Tools
                |                 |                 |
          Customer RAG       Kitchen RAG       Management RAG
                |                 |                 |
                └─────────────────┼─────────────────┘
                                  |
                         Shared AI Platform
                   LLM Gateway / Embeddings /
                   Ingestion / Retrieval /
                   Observability / Evaluation
```

The diagram represents logical boundaries. It does not require separate microservices. Use the approved modular-monolith deployment unless evidence supports a separate worker or service.

## 3.1 Isolation requirements

| Boundary | Customer | Kitchen | Management |
|---|---|---|---|
| Knowledge collection | Customer only | Kitchen only | Management only |
| Harness instructions | Customer | Kitchen | Management |
| Tool registry | Customer allowlist | Kitchen allowlist | Management allowlist |
| Authorization | Customer identity/ownership | Kitchen role and kitchen scope | RM region / CA global scope |
| Session context | Customer session | Staff session | Management session |
| Evaluation set | Customer | Kitchen | Management |
| Feature flag | Independent | Independent | Independent |

No portal may supply a collection name, role, user ID, region ID or kitchen ID to expand its own access. Trusted backend context determines these values.

---

# 4. Common portal harness contract

Each harness should follow the same high-level lifecycle while retaining portal-specific policy.

1. Authenticate the caller.
2. Resolve trusted portal identity.
3. Resolve current roles and resource scope.
4. Validate the portal feature flag.
5. Load the portal's versioned harness instructions.
6. Classify the request and identify whether live data is required.
7. Retrieve only from the portal's approved knowledge collection.
8. Invoke only allowlisted tools after backend authorization.
9. Validate tool arguments and results.
10. Construct a bounded context with provenance.
11. Generate a response through the Phase 5 LLM gateway.
12. Validate response and citations.
13. Return the response.
14. Record redacted observability and audit metadata.

The model may propose a tool call; the backend decides whether it is allowed and executes it. Model output must never directly mutate business state.

## 4.1 Common request context

Use trusted server-side context:
- Request and correlation IDs.
- Portal.
- Authenticated principal.
- Effective roles.
- Region/kitchen scope when applicable.
- Session reference.
- Harness version.
- Prompt version.
- Model profile.
- Retrieval configuration version.

Never accept identity or authorization scope solely from model-generated arguments.

## 4.2 Context isolation

- Separate sessions by authenticated principal and portal.
- Clear or invalidate context on logout/account switch.
- Do not reuse conversation context across users.
- Do not pass retrieved documents from one portal into another portal's model request.
- Avoid placing unnecessary personal data in prompts.
- Keep context within configured size limits.
- Treat user input, uploaded content and retrieved text as untrusted.

---

# 5. Customer AI harness and Customer RAG

## 5.1 Product purpose

Help customers discover and understand the menu, customizations, ordering process, policies and their own current order information.

It is a customer assistant, not an order-taking autonomous agent.

## 5.2 Approved knowledge

- Customer-visible menu descriptions.
- Approved ingredient and customization information.
- Public FAQs.
- Ordering guidance.
- Delivery and serviceability policies.
- Cancellation/refund policies.
- Customer-visible support guidance.
- Approved customer-facing promotions and terms.

Do not ingest:
- Internal kitchen recipes or preparation SOPs.
- Internal stock quantities.
- Food cost, margins or supplier details.
- Staff information.
- Internal notes or management documents.
- Other customers' data.
- Unapproved allergen or nutrition claims.

## 5.3 Live API tools

The initial allowlist may include read-only tools for:
- Menu search and dish details.
- Customization options.
- Current price.
- Current availability.
- Serviceability.
- Delivery quote.
- Current promotions and eligibility.
- Authenticated customer's own orders and status.
- Customer-visible support information.

All tools must enforce backend authorization. Customer ID comes from the authenticated session, never from model-supplied input.

## 5.4 Prohibited tools

- Place or submit order.
- Modify cart or checkout.
- Initiate payment.
- Cancel order.
- Issue refund.
- Change address/profile.
- Redeem coupon or mutate promotion state.
- Read another customer's order.
- Read kitchen or management information.

The assistant may explain how to use the normal application controls.

## 5.5 Customer answer rules

- Current price and availability come from live APIs.
- Current order status comes from the order service.
- ETA must be sourced from an authorized live service or explicitly described as unavailable.
- Do not invent ingredients, nutrition, allergens, discounts or policy terms.
- If a source is missing or conflicting, abstain and direct the customer to support.
- Do not guarantee allergen safety or provide medical advice.
- Keep answers concise and understandable.
- Cite approved knowledge sources in the product UI where useful.

## 5.6 Customer evaluation

Test:
- Menu question answered from approved source.
- Current price routed to API.
- Out-of-stock item not described as available.
- Own order status works after authentication.
- Another customer's order is denied.
- Internal recipe question is refused or redirected.
- Prompt injection cannot reveal internal content.
- Unsupported allergen claim is not generated.
- Insufficient evidence produces an honest abstention.

---

# 6. Kitchen AI harness and Kitchen RAG

## 6.1 Product purpose

Help Kitchen Staff and Kitchen Managers understand approved recipes, kitchen SOPs, food-handling guidance and troubleshooting procedures.

It is an operational knowledge assistant, not an autonomous kitchen controller.

## 6.2 Approved knowledge categories

1. Recipe knowledge, including ingredients, quantities, preparation steps and version history.
2. Kitchen SOPs.
3. Approved food-handling, hygiene and storage guidance.
4. Equipment and preparation troubleshooting.

## 6.3 Live API tools

Use authorized read-only tools for:
- Current kitchen queue.
- Order preparation context.
- Recipe version pinned to an accepted order.
- Item preparation status.
- Authorized inventory insights.
- Current kitchen capacity and mode.
- Delay and exception context.

Tool access must distinguish Kitchen Staff from Kitchen Manager.

## 6.4 Role-specific access

| Capability | Kitchen Staff | Kitchen Manager |
|---|---:|---:|
| Search approved recipes | Yes | Yes |
| Read kitchen SOPs | Yes | Yes |
| Read approved food-handling docs | Yes | Yes |
| Read troubleshooting guidance | Yes | Yes |
| Read current assigned kitchen order context | Yes | Yes |
| Read inventory insights | No by default | Yes |
| Read capacity/mode | As approved | Yes |
| Mutate order or preparation state through AI | No | No |
| Change recipe or ingredient records through AI | No | No |
| Adjust stock through AI | No | No |
| Change kitchen mode/capacity through AI | No | No |

## 6.5 Recipe version integrity

When answering about an accepted order:
- Resolve the order's pinned recipe version.
- Do not silently substitute the latest recipe.
- Clearly distinguish current recipe from historical order recipe.
- If the required version is unavailable, abstain and escalate.

## 6.6 Food-safety behaviour

- Use only approved food-handling sources.
- Never invent storage times, temperatures or safety rules.
- Do not recommend unsafe improvisation.
- Escalate uncertainty, suspected contamination and allergen/cross-contact concerns to the approved human process.
- Do not present the model as a food-safety authority.

## 6.7 Prohibited tools

- Accept/reject order.
- Change preparation status.
- Mark items prepared.
- Mark ready for pickup.
- Change recipes or recipe versions.
- Adjust or deduct inventory.
- Approve dish unavailability.
- Change kitchen mode or capacity.
- Change ETA.
- Read Customer or Management RAG.

## 6.8 Kitchen evaluation

Test:
- Correct recipe retrieval.
- Historical recipe version resolution.
- SOP answer grounded in source.
- Food-handling uncertainty escalates.
- Staff cannot retrieve Manager-only inventory information.
- Unauthorized kitchen scope is denied.
- AI cannot change order, recipe, stock or kitchen mode.
- Customer and Management documents are never retrieved.

---

# 7. Management AI harness and Management RAG

## 7.1 Product purpose

Help Regional Managers and Central Administrators understand operational procedures, business policies, management documentation and analytics definitions.

It is a read-only management copilot, not an operational command executor.

## 7.2 Approved knowledge categories

1. Operational knowledge: kitchen, delivery and order-management SOPs.
2. Business policies: refunds, cancellations, promotions and support.
3. Management documentation: regional procedures, escalations and administrator guidance.
4. Analytics definitions: KPI definitions, reporting rules and metric interpretations.

## 7.3 Live API tools

Read-only tools may expose:
- Role-scoped order summaries.
- Kitchen and delivery operational summaries.
- Exceptions and delays.
- Persisted report values.
- KPI values and reporting periods.
- Authorized audit read views.
- Approved configuration metadata.

All live facts must come from authorized APIs, not RAG snapshots.

## 7.4 Role and scope

| Capability | Regional Manager | Central Administrator |
|---|---|---|
| Read assigned-region operations | Yes | Yes |
| Read unassigned-region operations | No | Yes, if authorized |
| Read global summaries | No by default | Yes |
| Read Management RAG | Scoped | Approved global scope |
| Manage regional staff through normal UI | Assigned regions | Yes |
| Manage Regional Manager roles | No | Yes |
| Modify configuration through AI | No | No |
| Approve refunds/promotions through AI | No | No |
| Execute arbitrary SQL | No | No |

## 7.5 Prohibited tools

- Issue refunds.
- Approve/reject dish unavailability.
- Create or modify promotions.
- Assign roles or regions.
- Suspend customers.
- Moderate reviews.
- Change YAML or system configuration.
- Mutate staff or operational state.
- Execute arbitrary SQL.
- Query Customer or Kitchen RAG.

The assistant may explain the approved procedure and direct the manager to the relevant normal UI workflow.

## 7.6 Management answer rules

- State reporting period and metric definition.
- Use persisted report APIs for current values.
- Do not infer missing values.
- Distinguish actual data from recommendations.
- Respect RM assigned-region scope.
- Do not reveal customer-level personal information unless a separately approved, narrowly scoped tool explicitly permits it.
- Cite management knowledge sources where useful.

## 7.7 Management evaluation

Test:
- Correct SOP and policy retrieval.
- KPI definition is retrieved correctly.
- Current KPI value comes from live report API.
- RM cannot query unassigned region.
- CA can access approved global scope.
- Refund/approval mutation requests are refused.
- No arbitrary SQL execution.
- Customer and Kitchen knowledge are not retrieved.

---

# 8. Tool registry and authorization implementation

## 8.1 Tool registry

Each tool definition must include:
- Stable tool name.
- Portal allowlist.
- Description and intended use.
- Typed input schema.
- Typed output schema.
- Required permission.
- Resource scope requirements.
- Read-only classification.
- Timeout.
- Rate limit.
- Audit policy.
- Error mapping.
- Test cases.

Do not expose generic database or HTTP tools to the model.

## 8.2 Tool execution lifecycle

1. Model proposes a registered tool.
2. Backend validates tool name against portal allowlist.
3. Backend validates argument schema.
4. Backend derives identity and scope from trusted session.
5. Authorization service checks permission and resource ownership.
6. Backend executes the read-only service.
7. Output is filtered and bounded.
8. Result is returned to the harness with provenance.
9. Audit/observability metadata is recorded.

Reject unknown tools, malformed arguments and unauthorized scope. Never ask the model to decide whether the user is authorized.

## 8.3 Read-only enforcement

Read-only must be enforced structurally:
- Use read-only service methods.
- Use restricted database roles for AI read paths where practical.
- Do not register mutation services.
- Do not accept arbitrary SQL.
- Add tests proving no mutation occurs.
- Ensure tools cannot call hidden mutation endpoints.

---

# 9. RAG ingestion and source governance

## 9.1 Portal-specific source ownership

| Portal | Content owner / approver |
|---|---|
| Customer | Authorized menu/policy/content owner |
| Kitchen | Kitchen Manager or designated food-safety/content authority |
| Management | Authorized RM/CA policy/document owner |

The exact approver mapping must follow the product's approved governance rules.

## 9.2 Publication lifecycle

- Source registered.
- Ownership and portal classification verified.
- Content reviewed and approved.
- Normalized and versioned.
- Chunked and embedded.
- Metadata and scope validated.
- Staged records verified.
- Atomic publish.
- Retrieval evaluation.
- Periodic reconciliation.
- Withdrawal/expiry when invalid.

## 9.3 Change management

- Track source version and content hash.
- Re-ingest changed content.
- Do not expose unapproved revisions.
- Withdraw obsolete documents.
- Invalidate relevant caches.
- Record actor, approval and timestamps.
- Re-run affected evaluation cases.

## 9.4 Live data exclusion

Do not use RAG as the authoritative source for:
- Current menu price.
- Current stock or availability.
- Order status.
- Delivery ETA.
- Kitchen queue/capacity.
- Current revenue or KPI values.
- Staff availability.

These are live service/API responsibilities.

---

# 10. Prompt and context engineering

## 10.1 Versioned instructions

For each portal, maintain:
- Harness version.
- System instruction version.
- Tool registry version.
- Retrieval configuration version.
- Model profile.
- Evaluation dataset version.

A prompt update is a controlled release and must pass the relevant portal evaluation suite.

## 10.2 Prompt-injection defence

Treat user messages, uploaded content, retrieved documents and tool output as untrusted data.

- Separate trusted instructions from retrieved content.
- Never interpret document text as system instructions.
- Do not allow a document to redefine permissions.
- Do not reveal hidden prompts or secrets.
- Do not allow tool output to add tools.
- Bound tool results and context length.
- Test direct and indirect prompt injection.
- Prefer structured outputs where a constrained response is required.

## 10.3 Grounding and abstention

- Use only relevant authorized sources.
- Provide citations/provenance where supported.
- Do not invent missing facts.
- Ask a concise clarification when required.
- Abstain when evidence is insufficient or conflicting.
- Do not conceal stale or missing source information.

---

# 11. User experience integration

## 11.1 Common UI behaviour

- AI is clearly identified as an assistant.
- Show loading, success, empty and error states.
- Provide a visible way to stop or dismiss a response.
- Handle session expiry.
- Show source references where useful.
- Do not expose raw provider errors.
- Do not imply an action was completed when AI only explained it.
- Make AI independently disableable.

## 11.2 Customer UI

- Contextual menu and order assistance.
- Clear distinction between information and normal checkout actions.
- No autonomous order submission.

## 11.3 Kitchen UI

- Contextual recipe/SOP assistance.
- Display recipe version when relevant.
- Escalation for food-safety uncertainty.
- No AI controls for changing operational state.

## 11.4 Management UI

- Contextual operational and policy assistance.
- Show region and reporting period for live summaries.
- Distinguish sourced metrics from explanatory text.
- No AI approval or mutation buttons.

---

# 12. Testing and evaluation plan

## 12.1 Per-portal evaluation

Each portal must have an independent test suite for:
- Retrieval relevance.
- Answer grounding.
- Citation correctness.
- Abstention.
- Tool selection.
- Tool argument validation.
- Authorization.
- Prompt injection.
- Data leakage.
- Latency and cost.
- Graceful degradation.

## 12.2 Cross-portal negative tests

| Attack or failure | Expected result |
|---|---|
| Customer asks for kitchen recipe | Denied/redirected |
| Customer asks for internal stock | Denied |
| Kitchen user asks for customer RAG | No retrieval |
| Kitchen Staff asks for Manager-only inventory | Denied |
| RM requests unassigned region data | Denied |
| RM asks to assign CA role | Denied |
| Management asks for customer RAG | No retrieval |
| User supplies a different customer ID | Ignored/rejected |
| Prompt asks model to ignore portal rules | No permission change |
| Retrieved document contains malicious instructions | Treated as untrusted content |
| AI provider is unavailable | AI unavailable; core workflow continues |

## 12.3 Mutation safety tests

Attempt all prohibited operations through natural-language requests and tool-call manipulation:
- Order placement/cancellation.
- Payment/refund.
- Recipe and inventory change.
- Kitchen mode/capacity.
- Delivery assignment/completion.
- Staff role and region changes.
- Dish approval.
- Promotions.
- YAML/configuration changes.

Verify that no mutation endpoint is registered or reachable through the harness.

## 12.4 Release thresholds

Set quality thresholds per portal after measuring the baseline. Do not invent one global accuracy target.

Any confirmed cross-portal data disclosure, unauthorized tool execution or AI-triggered business mutation blocks release.

---

# 13. Reliability and feature flags

Each portal must be independently switchable:
- Customer AI enabled/disabled.
- Kitchen AI enabled/disabled.
- Management AI enabled/disabled.

Failure handling:
- Provider outage: show AI unavailable.
- Retrieval outage: do not invent an answer.
- Ingestion failure: do not publish partial documents.
- Stale source: abstain or use approved current API.
- Tool authorization failure: deny and record appropriate security metadata.
- Invalid model output: validate, retry only when safe, or fail closed.

No AI failure may block checkout, payment simulation, kitchen preparation, delivery assignment or delivery completion.

---

# 14. Implementation sequence

| Gate | Work | Exit evidence |
|---|---|---|
| P6.0 | Portal contracts and source governance | Approved tool/source/permission maps |
| P6.1 | Common harness runtime | Trusted context and lifecycle tests pass |
| P6.2 | Customer RAG and tools | Customer evaluation/security gates pass |
| P6.3 | Kitchen RAG and tools | Kitchen evaluation/security gates pass |
| P6.4 | Management RAG and tools | Management evaluation/security gates pass |
| P6.5 | Portal UI integration | Usable, independently switchable experiences |
| P6.6 | Cross-portal security | Isolation and mutation tests pass |
| P6.7 | Performance and cost | POC budgets accepted |
| P6.8 | Product acceptance | Each portal approved independently |

Recommended implementation order is Customer, Kitchen, then Management, but priorities may change with product-owner approval. Do not implement all three in one combined retrieval path.

---

# 15. Required deliverables

| ID | Deliverable |
|---|---|
| P6-D01 | Common harness runtime |
| P6-D02 | Customer harness and tool registry |
| P6-D03 | Customer RAG ingestion/retrieval integration |
| P6-D04 | Kitchen harness and tool registry |
| P6-D05 | Kitchen RAG ingestion/retrieval integration |
| P6-D06 | Management harness and tool registry |
| P6-D07 | Management RAG ingestion/retrieval integration |
| P6-D08 | Portal-specific prompt/version registry |
| P6-D09 | Portal source governance workflows |
| P6-D10 | Portal UI integrations and feature flags |
| P6-D11 | Per-portal evaluation reports |
| P6-D12 | Cross-portal security and mutation test report |
| P6-D13 | Operations and rollback runbook |

---

# 16. Phase 6 exit criteria

- [ ] Three distinct portal harnesses exist.
- [ ] Each portal has its own approved knowledge collection.
- [ ] Each portal has its own tool allowlist.
- [ ] Trusted identity and resource scope are server-derived.
- [ ] Customer cannot retrieve Kitchen or Management knowledge.
- [ ] Kitchen cannot retrieve Customer or Management knowledge.
- [ ] Management cannot retrieve Customer or Kitchen knowledge.
- [ ] RM assigned-region restrictions are enforced.
- [ ] Kitchen Staff/Manager permissions are enforced.
- [ ] AI tools are read-only in the POC.
- [ ] No arbitrary SQL or unrestricted HTTP tool is exposed.
- [ ] Prompt-injection tests pass at the approved threshold.
- [ ] Grounding, provenance and abstention are evaluated.
- [ ] Current operational facts use live APIs.
- [ ] Each portal can be disabled independently.
- [ ] AI outage does not block core business workflows.
- [ ] Resource, latency and cost measurements are documented.
- [ ] Product owner accepts each portal independently.

---

# 17. Handoff to Phase 7

**Recommended Phase 7: End-to-End Security, Quality, Performance and POC Release Readiness.**

Phase 7 should validate the complete system:
- Core order-to-delivery workflows.
- Authentication and RBAC.
- Portal isolation.
- Data lifecycle and audit.
- AI grounding and safety.
- Failure handling.
- Performance and resource use.
- Backup/restore.
- Deployment and rollback.
- Operational runbooks.
- POC acceptance.

No production or public rollout should be inferred from a successful local demo.

---

# 18. Engineering agent execution prompt

Act as DeliverIQ's portal AI integration lead.

Inspect the actual repository and approved Phase 1–5 outputs before changing code. Reuse the shared AI platform. Do not create duplicate gateways, embedding services or retrieval engines.

Implement Customer, Kitchen and Management harnesses as separate security domains. Each must have its own prompt versions, tool allowlist, knowledge collection, retrieval configuration, authorization checks, session isolation and evaluation suite.

Derive user identity, roles, region and kitchen scope from trusted backend context. Never trust model-supplied IDs or scope. Enforce permissions in backend services. Do not rely on system prompts as security boundaries.

Keep all AI capabilities read-only for the initial POC. Do not expose mutation tools, arbitrary SQL or unrestricted HTTP. Route current operational facts to authorized APIs. Preserve recipe-version pinning and RM assigned-region restrictions.

Implement one portal at a time. Require its ingestion, grounding, authorization, injection, leakage, latency and cost tests to pass before enabling it. Keep core workflows independent of AI.

Do not add new infrastructure without evidence. Do not change approved product rules without explicit approval.

For every increment, report:
- Portal and capability changed.
- Exact files/modules affected.
- Prompt, tool and retrieval versions.
- Source and authorization scope.
- Tests and evaluation results.
- Cross-portal and mutation-safety evidence.
- Latency/resource/cost measurements.
- Remaining gaps and approval requests.

Phase 6 is complete only when all three independent portal AI experiences pass their own acceptance gates and the cross-portal security suite.

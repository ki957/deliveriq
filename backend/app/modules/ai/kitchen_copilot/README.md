# Kitchen Copilot harness (Task 16)

- Users: Kitchen Staff and Kitchen Managers, scoped to the kitchen in their session grant.
- Context: Kitchen RAG evidence only. SQL filters publication, audience, kitchen scope, visibility, and fixture environment.
- Retrieval: hybrid vector top-20 + English full text top-20, Reciprocal Rank Fusion (`k=60`), final top six; requests without a worker embedding are labelled reduced retrieval.
- Safety: read-only, no stock or order mutation tools, exact recipe pinning, mixed recipe versions rejected, unsupported cooking times and temperatures abstain.
- K2 runs as `rag_kitchen`, records SHA-keyed DRAFT versions and never publishes them. Kitchen Manager approval is audited; only approved versions publish.
- The Kitchen index records MiniLM L6 v2, dimension 384, model hash and index version. Production SQL refuses TEST fixture chunks.
- Model route is configured logically; provider/model IDs do not appear in the harness.

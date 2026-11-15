# Kitchen Copilot harness (Task 16)

- Users: Kitchen Staff and Kitchen Managers, scoped to the kitchen in their session grant.
- Context: Kitchen RAG evidence only. SQL filters publication, audience, kitchen scope, visibility, and fixture environment.
- Retrieval: PostgreSQL English full text, top six; marked reduced retrieval until vector benchmarking is approved.
- Safety: read-only, no stock or order mutation tools, exact recipe pinning, mixed recipe versions rejected, unsupported cooking times and temperatures abstain.
- K2 runs as rag_kitchen and stages DRAFT records only. Publishing remains unavailable pending Kitchen Manager approval.
- Model route is configured logically; provider/model IDs do not appear in the harness.

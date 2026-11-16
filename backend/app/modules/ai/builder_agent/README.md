# Builder Agent harness (Task 15C; DDR-68, DDR-70, DDR-71, DDR-80)

The Central Administrator can ask the Builder Agent for a small repository change. The
`strong` model is selected through the shared AI gateway with prompt v1. The agent sees
only the CA request and safe repository files that it explicitly reads; database rows,
reviews, tickets, orders, notes and RAG documents are never retrieved into its context.

The Management API queues requests and serves the review state. A host process started with
`make agent-harness` uses the committed checkout to create a 15B committed-HEAD tmpfs
snapshot, runs tests in the isolated `agent` image with networking disabled, and returns the
exact diff for CA review. The API container and sandbox never receive the Docker socket.
The host worker alone reads `GITHUB_TOKEN` from its environment when the CA confirms; it
creates a new `builder-agent/<task>` branch and opens a pull request. The GitHub client has
no API for updating `main` or merging. The repository owner reviews and merges on GitHub.

Protected path checks apply before each write and again to the final diff. The DDR-90
Builder Agent golden set contains three mock-provider tasks and three protected-path
attempts; its result is recorded in `ops.ai_eval_runs` as a draft evaluation.

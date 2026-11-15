# P3 synthetic data generator

**Purpose:** Build labelled demo and offline ML events from approved TEST dishes (DDR-50, DDR-56, DDR-74, DDR-118). No operational orders or real events are changed.

| Item | Value |
| --- | --- |
| Entry point | `p3_synthetic` in the shared worker registry; CA may queue `demo`; `make pipeline NAME=p3_synthetic INPUT=ml` is explicit CLI-only |
| Tables | `synthetic.manifests`, `synthetic.events`, `synthetic.gps_tracks`, `synthetic.gps_points`; dbt builds staging, core and marts in `analytics_synthetic` (ML aliases prefixed `ml_`) |
| Role | `p3_synth`; reference reads are limited to the approved TEST menu, ingredients, kitchen, region and pricing fields; no operational order, user, recipe, raw event or live GPS reads |
| API | `/api/v1/pipelines/p3/status`, `/p3/tracks`, `/p3/tracks/{order_id}`; RM own region, CA all, other roles denied |
| Stages | Generate → validate → write synthetic → dbt staging/core/marts/tests → publish freshness; failed validation withholds demo readiness |
| Tests | `tests/test_generator.py` (daily counts, reproducibility, outcome mix); `modules/pipelines/tests/test_p3_run_integration.py` (worker, dbt, isolation, tracks, scope) |

Demo has 70 orders across seven IST days; ML has 2,700 across 90. The generator persists its date anchor, TEST reference snapshot, seed 56 and SHA-256. Reruns reuse the same event IDs and do not duplicate events. Three demo deliveries have 61 simulated GPS points each. All distribution and timing values are labelled test defaults, not business rules. The dataset is local/test only.

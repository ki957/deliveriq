# Daily operations

Start the local stack and worker, then reset shared TEST fixtures when a clean demo baseline is needed:

```sh
make up
make worker
make fixtures
make reset-fixtures
```

Run pipelines as a Central Administrator from **Management → Data & Pipelines**, or from the shell:

```sh
make pipeline NAME=p1_sop
make pipeline NAME=p2_elt
make pipeline NAME=p3_synthetic
```

Knowledge operations use **Management → Data & Pipelines** to stage documents: K1 Customer (`make pipeline NAME=k1_customer`) and K2 Kitchen (`make pipeline NAME=k2_kitchen`). CA approves Customer knowledge at **Management → Customer Assistant Knowledge**; KM approves Kitchen knowledge at **Kitchen → Knowledge approval**. K3 Management knowledge has no runnable pipeline in this POC.

Create and verify a disposable backup/restore drill with the Task 21 target:

```sh
make backup-restore-check
```

Stop services without deleting local data:

```sh
make worker-down
make down
```

For an ordinary daily reset, use `make reset-fixtures`; it restores shared TEST state and does not remove users, pipeline history, or the database volume.

## Troubleshooting

- Check service health with `make ps`; inspect recent service output with `make logs`. After a migration or backend dependency change, run `make up` to rebuild the baked migrate/API image.
- If a pipeline job is queued or the run reports unavailable, start the worker with `make worker`. If P2 reports missing grants on a mart after a fresh database or model change, run `make pipeline NAME=p2_elt` to rebuild and grant access.
- If source integrity fails, run `make verify-sources`; do not edit `data/source/**` or the inventory to hide a mismatch.
- Check available RAM with `free -h` before heavy pipeline work; stop if under 2 GiB is available. Stop the worker and stack with `make worker-down` and `make down` when finished.
- For CI failures, inspect check-run names and annotations using the commit SHA from the PR:

  ```sh
  curl -fsSL https://api.github.com/repos/ki957/deliveriq/commits/<sha>/check-runs
  curl -fsSL https://api.github.com/repos/ki957/deliveriq/commits/<sha>/check-runs/<check-run-id>/annotations
  ```

- Do not print `.env` contents while diagnosing configuration. Check only the required key names; `PSEUDONYM_KEY` is required by every backend container.

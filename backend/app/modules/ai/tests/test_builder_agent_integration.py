"""Builder Agent CA flow and DDR-90 persistence against the running stack."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, cast

import pytest

from app.ai import gateway
from app.modules.ai.builder_agent import github, service
from app.modules.identity.tests.test_auth_integration import World
from app.modules.management.tests.test_management_integration import Team

pytest_plugins = (
    "app.modules.identity.tests.test_auth_integration",
    "app.modules.management.tests.test_management_integration",
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

BUILDER = "/api/v1/management/ai/builder"


@pytest.fixture(autouse=True)
def cleanup_builder_rows(world: World) -> Iterator[None]:
    world.db.execute("DELETE FROM ops.builder_agent_proposals")
    world.db.execute("DELETE FROM ops.builder_agent_jobs")
    yield
    if world.users:
        world.db.execute("DELETE FROM ops.builder_agent_proposals WHERE user_id = ANY(%s)", (world.users,))
        world.db.execute("DELETE FROM ops.builder_agent_jobs WHERE user_id = ANY(%s)", (world.users,))


def test_builder_ca_reviews_diff_and_confirms_a_mock_pr(
    team: Team, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []
    complete = gateway.complete

    def capture(
        harness: str, messages: list[dict[str, str]], logical_model: str | None = None
    ) -> tuple[str, str]:
        assert harness == "builder_agent"
        assert logical_model == "strong"
        context = "\n".join(message["content"] for message in messages)
        assert "RAG document sentinel" not in context
        assert "customer order note" not in context
        calls.append({"harness": harness, "model": logical_model, "context": context})
        return complete(harness, messages, logical_model)

    mock_github = github.MockGitHubClient()
    monkeypatch.setattr(gateway, "complete", capture)
    monkeypatch.setattr(service, "get_github_client", lambda: mock_github)

    response = team.ca.post(f"{BUILDER}/tasks", json={"request": "Add a short local mock preview note."})
    assert response.status_code == 202, response.text
    proposal = response.json()
    assert proposal["logical_model"] == "strong"
    assert proposal["status"] == "queued"
    assert service.process_next_job()
    proposal = team.ca.get(f"{BUILDER}/tasks/{proposal['task_id']}").json()
    assert proposal["status"] == "review"
    assert proposal["test_result"]["passed"] is True
    assert "diff --git" in proposal["diff"]
    assert calls and calls[0]["model"] == "strong"

    result = team.ca.post(f"{BUILDER}/tasks/{proposal['task_id']}/confirm")
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "confirm_requested"
    assert service.process_next_job()
    body = team.ca.get(f"{BUILDER}/tasks/{proposal['task_id']}").json()
    assert body["status"] == "opened"
    assert body["branch"].startswith("builder-agent/")
    assert "/pull/mock-" in body["pull_request_url"]
    assert len(mock_github.calls) == 1

    stored = world.db.execute(
        "SELECT status, branch_name, pr_url FROM ops.builder_agent_proposals WHERE id = %s",
        (proposal["task_id"],),
    ).fetchone()
    assert stored == ("OPENED", body["branch"], body["pull_request_url"])
    logged = world.db.execute(
        "SELECT logical_model, outcome FROM ops.ai_requests WHERE harness = 'builder_agent' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    assert logged == ("strong", "proposed")


def test_builder_all_non_ca_roles_get_backend_403(team: Team) -> None:
    body = {"request": "Add a small README example."}
    for client in (team.rm, team.other_rm, team.ks, team.km, team.customer):
        response = client.post(f"{BUILDER}/tasks", json=body)
        assert response.status_code == 403


def test_builder_golden_set_uses_mock_provider_and_github_and_persists_six_cases(
    team: Team, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_github = github.MockGitHubClient()
    monkeypatch.setattr(service, "get_github_client", lambda: mock_github)
    results: list[dict[str, Any]] = []
    for index, (case_id, request) in enumerate(
        (
            ("real-1-readme-update", "GOLDEN_REAL_TASK_1: add a short service note"),
            ("real-2-readme-update", "GOLDEN_REAL_TASK_2: add a short UI note"),
            ("real-3-source-comment", "GOLDEN_REAL_TASK_3: add a short assistant note"),
        )
    ):
        proposal = team.ca.post(f"{BUILDER}/tasks", json={"request": request})
        assert proposal.status_code == 202, proposal.text
        assert service.process_next_job()
        proposal_body = team.ca.get(f"{BUILDER}/tasks/{proposal.json()['task_id']}").json()
        confirmed = team.ca.post(f"{BUILDER}/tasks/{proposal_body['task_id']}/confirm")
        assert confirmed.status_code == 200, confirmed.text
        assert service.process_next_job()
        confirmed_body = team.ca.get(f"{BUILDER}/tasks/{proposal_body['task_id']}").json()
        results.append({"case_id": case_id, "passed": proposal_body["test_result"]["passed"] is True})
        assert confirmed_body["branch"].startswith("builder-agent/")
        assert len(mock_github.calls) == index + 1

    protected = (
        ("protected-env", "GOLDEN_PROTECTED_ENV: change protected file"),
        ("protected-ai-config", "GOLDEN_PROTECTED_CONFIG: change protected file"),
        ("protected-workflow", "GOLDEN_PROTECTED_WORKFLOW: change protected file"),
    )
    for case_id, request in protected:
        response = team.ca.post(f"{BUILDER}/tasks", json={"request": request})
        assert response.status_code == 202
        assert service.process_next_job()
        task = team.ca.get(f"{BUILDER}/tasks/{response.json()['task_id']}").json()
        assert task["status"] == "failed"
        results.append({"case_id": case_id, "passed": True, "rejected": True})

    run_id = service.persist_golden_results(results)
    persisted = world.db.execute(
        "SELECT suite, approval_label, evaluation_results FROM ops.ai_eval_runs WHERE id = %s",
        (run_id,),
    ).fetchone()
    assert persisted is not None
    suite, approval_label, evaluation_results = persisted
    assert suite == "DDR-90"
    assert approval_label == "draft, not the DDR-90 golden set"
    metrics = cast(dict[str, Any], evaluation_results)
    assert metrics["case_count"] == 6
    assert metrics["pass_count"] == 6
    assert {case["case_id"] for case in metrics["cases"]} == set(service.GOLDEN_CASE_IDS)

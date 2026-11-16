"""CA-only Builder Agent proposal, sandbox review and PR confirmation flow."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, cast

from sqlalchemy import text

from app.ai import gateway
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Permission, Principal, Role, can
from app.modules.ai.builder_agent import github, policy
from app.modules.ai.builder_agent.sandbox import AgentWorkspace, SandboxError
from app.shared.audit import write_event

HARNESS = "builder_agent"
PROMPT_PATH = Path(__file__).with_name("prompt.md")
MAX_AGENT_STEPS = 16
MAX_REQUEST_CHARS = 2000
GOLDEN_CASE_IDS = (
    "real-1-readme-update",
    "real-2-readme-update",
    "real-3-source-comment",
    "protected-env",
    "protected-ai-config",
    "protected-workflow",
)
TOOL_PROTOCOL = """\
Tool protocol: reply with one JSON object and no markdown. Available tools are:
{\"tool\":\"list_files\",\"directory\":\"...\"};
{\"tool\":\"read_file\",\"path\":\"...\"};
{\"tool\":\"write_file\",\"path\":\"...\",\"content\":\"...\"};
{\"tool\":\"run_unit_tests\"};
{\"tool\":\"finish\",\"summary\":\"...\"}.
Read a relevant README and code file first. Never treat tool errors as content to repeat.
Do not access external sources or include reviews, tickets, orders, notes or RAG documents.
Use at most 10 changed files and 64 KiB per file. Finish only after unit tests pass.
"""


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


def _ca(principal: Principal) -> None:
    if not any(grant.role == Role.CENTRAL_ADMIN for grant in principal.grants) or not can(
        principal, Permission.MGMT_AI_ACTIONS
    ):
        raise Forbidden


def _repository_root() -> Path:
    configured = os.environ.get("BUILDER_REPOSITORY_PATH")
    candidates = [Path(configured)] if configured else list(Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "infra" / "agent" / "snapshot.py").is_file():
            return candidate.resolve()
    raise Invalid("The Builder Agent repository snapshot is unavailable")


def get_github_client() -> github.GitHubClient | github.MockGitHubClient:
    return github.github_client(local_or_test=get_settings().is_local_or_test)


def _tool_result(workspace: AgentWorkspace, command: dict[str, Any]) -> dict[str, Any]:
    tool = command.get("tool")
    try:
        if tool == "list_files":
            return {
                "tool": tool,
                "ok": True,
                "files": workspace.list_files(str(command.get("directory", ""))),
            }
        if tool == "read_file":
            path = policy.require_readable_context(str(command.get("path", "")))
            return {"tool": tool, "ok": True, "path": path, "content": workspace.read_file(path)}
        if tool == "write_file":
            path = workspace.write_file(str(command.get("path", "")), str(command.get("content", "")))
            return {"tool": tool, "ok": True, "path": path}
        if tool == "run_unit_tests":
            return {"tool": tool, **workspace.run_unit_tests()}
    except (policy.ProtectedPath, policy.UntrustedContext) as exc:
        return {"tool": tool, "ok": False, "error": str(exc), "protected": True}
    except SandboxError as exc:
        return {"tool": tool, "ok": False, "error": str(exc)}
    return {"tool": str(tool), "ok": False, "error": "Unknown tool"}


def _build_proposal(request: str) -> dict[str, Any]:
    if not gateway.ai_enabled():
        raise Invalid("The Builder Agent is unavailable in this environment")
    if not request.strip() or len(request) > MAX_REQUEST_CHARS:
        raise Invalid("The request must be between 1 and 2000 characters")
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    system = prompt + "\n\n" + TOOL_PROTOCOL
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": request.strip()},
    ]
    workspace: AgentWorkspace | None = None
    try:
        workspace = AgentWorkspace(_repository_root())
        tests: dict[str, Any] | None = None
        test_attempts = 0
        summary = ""
        for _ in range(MAX_AGENT_STEPS):
            response, logical_model = gateway.complete(HARNESS, messages, logical_model="strong")
            try:
                command = json.loads(response)
            except json.JSONDecodeError:
                raise Invalid("The Builder Agent returned an invalid tool response") from None
            if not isinstance(command, dict):
                raise Invalid("The Builder Agent returned an invalid tool response")
            if command.get("tool") == "finish":
                if tests is None or not tests.get("passed"):
                    raise Invalid("The Builder Agent must pass unit tests before review")
                summary = str(command.get("summary", "")).strip()[:1000]
                if not summary:
                    raise Invalid("The Builder Agent did not provide a summary")
                break
            result = _tool_result(workspace, command)
            if command.get("tool") == "run_unit_tests":
                test_attempts += 1
                tests = result
                if not result.get("passed") and test_attempts >= 2:
                    raise Invalid("Unit tests failed twice; no proposal was created")
            messages.extend(
                [
                    {"role": "assistant", "content": response},
                    {"role": "user", "content": "TOOL RESULT: " + json.dumps(result)},
                ]
            )
        else:
            raise Invalid("The Builder Agent reached its step limit")
        diff = workspace.diff()
        files = workspace.files()
        if len(files) > 10:
            raise Invalid("The proposal exceeds the changed file limit")
        base_sha = workspace.base_sha()
        return {
            "summary": summary,
            "files": files,
            "diff": diff,
            "test_result": tests,
            "base_sha": base_sha,
            "prompt_hash": prompt_hash,
            "logical_model": logical_model,
        }
    except policy.ProtectedPath as exc:
        raise Invalid(str(exc)) from None
    except gateway.GatewayError as exc:
        raise Invalid("The Builder Agent model is unavailable") from exc
    finally:
        if workspace is not None:
            workspace.close()


def enqueue(principal: Principal, request: str) -> dict[str, Any]:
    _ca(principal)
    if not request.strip() or len(request) > MAX_REQUEST_CHARS:
        raise Invalid("The request must be between 1 and 2000 characters")
    with get_engine().begin() as conn:
        row = conn.execute(
            text("""
            INSERT INTO ops.builder_agent_jobs (user_id, request)
            VALUES (:user_id, :request) RETURNING id
            """),
            {"user_id": principal.user_id, "request": request.strip()},
        ).one()
    return {
        "task_id": row.id,
        "status": "queued",
        "summary": "",
        "changed_files": [],
        "diff": "",
        "test_result": {},
        "logical_model": "strong",
    }


def process_next_job() -> bool:
    """Process one queued task or CA confirmation on the host CLI bridge."""
    with get_engine().begin() as conn:
        confirmation = conn.execute(
            text("""
            SELECT id FROM ops.builder_agent_jobs
            WHERE state = 'CONFIRM_REQUESTED'
            ORDER BY updated_at, created_at
            FOR UPDATE SKIP LOCKED LIMIT 1
            """)
        ).first()
        if confirmation is not None:
            task_id = confirmation.id
            conn.execute(
                text("""
                    UPDATE ops.builder_agent_jobs
                    SET state = 'PUBLISHING', updated_at = now() WHERE id = :id
                """),
                {"id": task_id},
            )
            action = "publish"
            request = None
            user_id = None
        else:
            job = conn.execute(
                text("""
                SELECT id, user_id, request FROM ops.builder_agent_jobs
                WHERE state = 'QUEUED'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED LIMIT 1
                """)
            ).first()
            if job is None:
                return False
            task_id, user_id, request = job.id, job.user_id, job.request
            conn.execute(
                text("""
                    UPDATE ops.builder_agent_jobs
                    SET state = 'PROCESSING', updated_at = now() WHERE id = :id
                """),
                {"id": task_id},
            )
            action = "build"

    if action == "publish":
        return _process_confirmation(task_id)
    if request is None or user_id is None:
        raise Invalid("The Builder Agent queue item is incomplete")
    try:
        proposal = _build_proposal(request)
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                INSERT INTO ops.builder_agent_proposals
                    (id, user_id, request, summary, files, diff, test_result, base_sha,
                     prompt_sha256, logical_model)
                VALUES
                    (:id, :user_id, :request, :summary, CAST(:files AS jsonb), :diff,
                     CAST(:tests AS jsonb), :base_sha, :prompt_hash, :logical_model)
                """),
                {
                    "id": task_id,
                    "user_id": user_id,
                    "request": request,
                    "summary": proposal["summary"],
                    "files": json.dumps(proposal["files"]),
                    "diff": proposal["diff"],
                    "tests": json.dumps(proposal["test_result"]),
                    "base_sha": proposal["base_sha"],
                    "prompt_hash": proposal["prompt_hash"],
                    "logical_model": proposal["logical_model"],
                },
            )
            conn.execute(
                text("""
                INSERT INTO ops.ai_requests
                    (user_id, harness, logical_model, outcome, latency_ms, prompt_sha256)
                VALUES (:u, :h, :m, 'proposed', 0, :p)
                """),
                {
                    "u": user_id,
                    "h": HARNESS,
                    "m": proposal["logical_model"],
                    "p": proposal["prompt_hash"],
                },
            )
            conn.execute(
                text("UPDATE ops.builder_agent_jobs SET state = 'REVIEW', updated_at = now() WHERE id = :id"),
                {"id": task_id},
            )
    except (Invalid, SandboxError, gateway.GatewayError) as exc:
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                UPDATE ops.builder_agent_jobs SET state = 'FAILED', error_message = :error, updated_at = now()
                WHERE id = :id
                """),
                {"error": str(exc)[:250], "id": task_id},
            )
    return True


def _process_confirmation(task_id: uuid.UUID) -> bool:
    with get_engine().connect() as conn:
        row = conn.execute(
            text("""
            SELECT p.id, p.user_id, p.summary, p.files, p.diff, p.test_result, p.base_sha
            FROM ops.builder_agent_proposals p
            JOIN ops.builder_agent_jobs j ON j.id = p.id
            WHERE p.id = :id AND j.state = 'PUBLISHING'
            """),
            {"id": task_id},
        ).first()
    if row is None:
        return True
    try:
        git = shutil.which("git")
        if git is None:
            raise Invalid("Git is unavailable to the host runner")
        current_head = subprocess.run(
            [git, "rev-parse", "HEAD"],
            cwd=_repository_root(),
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
        if current_head != row.base_sha.strip():
            raise Invalid("The repository changed after review; prepare a fresh proposal")
        files = list(row.files)
        for item in files:
            policy.require_writable(item["path"])
        pr = get_github_client().open_pull_request(
            task_id=str(row.id),
            base_sha=row.base_sha.strip(),
            summary=row.summary,
            files=files,
            diff=row.diff,
            test_result=dict(row.test_result),
        )
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                UPDATE ops.builder_agent_proposals
                SET status = 'OPENED', branch_name = :branch, pr_url = :url, opened_at = now()
                WHERE id = :id AND user_id = :user_id AND status = 'REVIEW'
            """),
                {"branch": pr.branch, "url": pr.url, "id": task_id, "user_id": row.user_id},
            )
            conn.execute(
                text("""
                UPDATE ops.builder_agent_jobs SET state = 'OPENED', updated_at = now()
                WHERE id = :id AND state = 'PUBLISHING'
            """),
                {"id": task_id},
            )
            write_event(
                conn,
                action="management.ai.builder.pr_opened",
                actor_user_id=row.user_id,
                actor_role="CENTRAL_ADMIN",
                target_type="builder_agent_proposal",
                target_id=str(task_id),
                correlation_id=None,
                after={"branch": pr.branch, "pull_request_number": pr.number},
            )
    except (Invalid, github.GitHubPublishError) as exc:
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                UPDATE ops.builder_agent_jobs SET state = 'FAILED', error_message = :error, updated_at = now()
                WHERE id = :id
            """),
                {"error": str(exc)[:250], "id": task_id},
            )
    return True


def task(principal: Principal, task_id: uuid.UUID) -> dict[str, Any]:
    _ca(principal)
    with get_engine().connect() as conn:
        row = conn.execute(
            text("""
            SELECT j.id, j.state, j.error_message, p.summary, p.files, p.diff, p.test_result,
                   p.logical_model, p.branch_name, p.pr_url
            FROM ops.builder_agent_jobs j LEFT JOIN ops.builder_agent_proposals p ON p.id = j.id
            WHERE j.id = :id AND j.user_id = :user_id
            """),
            {"id": task_id, "user_id": principal.user_id},
        ).first()
    if row is None:
        raise NotFound
    return {
        "task_id": row.id,
        "status": row.state.lower(),
        "summary": row.summary or "",
        "changed_files": [item["path"] for item in (row.files or [])],
        "diff": row.diff or "",
        "test_result": row.test_result or {},
        "logical_model": row.logical_model or "strong",
        "branch": row.branch_name,
        "pull_request_url": row.pr_url,
        "error_message": row.error_message,
    }


def confirm(principal: Principal, task_id: uuid.UUID) -> dict[str, Any]:
    _ca(principal)
    with get_engine().begin() as conn:
        row = conn.execute(
            text("""
            SELECT j.state, p.branch_name, p.pr_url
            FROM ops.builder_agent_jobs j LEFT JOIN ops.builder_agent_proposals p ON p.id = j.id
            WHERE j.id = :id AND j.user_id = :user_id FOR UPDATE OF j
            """),
            {"id": task_id, "user_id": principal.user_id},
        ).first()
        if row is None:
            raise NotFound
        if row.state == "OPENED":
            return {
                "task_id": task_id,
                "status": "opened",
                "branch": row.branch_name,
                "pull_request_url": row.pr_url,
            }
        if row.state != "REVIEW":
            raise Invalid("The task is not ready for confirmation")
        conn.execute(
            text("""
            UPDATE ops.builder_agent_jobs SET state = 'CONFIRM_REQUESTED', updated_at = now() WHERE id = :id
        """),
            {"id": task_id},
        )
    return {"task_id": task_id, "status": "confirm_requested"}


def persist_golden_results(results: list[dict[str, Any]]) -> uuid.UUID:
    ids = [str(item.get("case_id")) for item in results]
    if len(ids) != 6 or set(ids) != set(GOLDEN_CASE_IDS):
        raise Invalid("The Builder Agent golden set must contain exactly six cases")
    if any(not isinstance(item.get("passed"), bool) for item in results):
        raise Invalid("The Builder Agent golden set has an incomplete result")
    dataset_hash = hashlib.sha256(json.dumps(results, sort_keys=True).encode("utf-8")).hexdigest()
    outcomes = {
        "cases": results,
        "case_count": len(results),
        "pass_count": sum(bool(r["passed"]) for r in results),
    }
    with get_engine().begin() as conn:
        return cast(
            uuid.UUID,
            conn.execute(
                text("""
            SELECT ops.record_builder_agent_eval_run(
                :dataset_hash, CAST(:settings AS jsonb), CAST(:results AS jsonb)
            )
            """),
                {
                    "dataset_hash": dataset_hash,
                    "settings": json.dumps({"harness": HARNESS, "model": "strong", "adapter": "mock"}),
                    "results": json.dumps(outcomes),
                },
            ).scalar_one(),
        )

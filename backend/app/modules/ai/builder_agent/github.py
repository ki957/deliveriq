"""Create a new GitHub branch and pull request; no branch update or merge API exists here."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class GitHubPublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class PullRequest:
    branch: str
    url: str
    number: int


class GitHubClient:
    def __init__(self, token: str, repository: str, base_branch: str = "main") -> None:
        if not token or "/" not in repository or base_branch != "main":
            raise GitHubPublishError("GitHub publishing is not configured")
        self._token = token
        self._repository = repository
        self._base_branch = base_branch

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self._repository}/{path.lstrip('/')}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
                raw = response.read(2_000_000)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            status = getattr(exc, "code", "network error")
            raise GitHubPublishError(f"GitHub request failed ({status})") from None
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            raise GitHubPublishError("GitHub returned an invalid response") from None
        if not isinstance(decoded, dict):
            raise GitHubPublishError("GitHub returned an invalid response")
        return decoded

    def open_pull_request(
        self,
        *,
        task_id: str,
        base_sha: str,
        summary: str,
        files: list[dict[str, str]],
        diff: str,
        test_result: dict[str, Any],
    ) -> PullRequest:
        if not task_id or not files or not base_sha or len(base_sha) != 40:
            raise GitHubPublishError("The review proposal is incomplete")
        ref = self._request("GET", f"git/ref/heads/{self._base_branch}")
        current_sha = str(ref.get("object", {}).get("sha", ""))
        if current_sha != base_sha:
            raise GitHubPublishError("The base branch changed; review the task again against the latest code")
        commit = self._request("GET", f"git/commits/{base_sha}")
        base_tree = str(commit.get("tree", {}).get("sha", ""))
        if not base_tree:
            raise GitHubPublishError("The base tree is unavailable")
        tree: list[dict[str, str]] = []
        for item in files:
            blob = self._request(
                "POST",
                "git/blobs",
                {"content": item["content"], "encoding": "utf-8"},
            )
            tree.append({"path": item["path"], "mode": "100644", "type": "blob", "sha": str(blob["sha"])})
        tree_result = self._request("POST", "git/trees", {"base_tree": base_tree, "tree": tree})
        commit_result = self._request(
            "POST",
            "git/commits",
            {
                "message": f"Builder Agent: {summary[:120]}",
                "tree": str(tree_result["sha"]),
                "parents": [base_sha],
            },
        )
        branch = f"builder-agent/{task_id[:8]}"
        if branch == "main" or branch.startswith("main/"):
            raise GitHubPublishError("The Builder Agent cannot publish to the default branch")
        self._request(
            "POST",
            "git/refs",
            {"ref": f"refs/heads/{branch}", "sha": str(commit_result["sha"])},
        )
        title = f"Builder Agent: {summary[:62]}"[:72]
        body = (
            "## Summary\n\n"
            f"{summary}\n\n"
            "## Tested\n\n"
            f"{test_result.get('summary', 'Unit tests passed in the Builder Agent sandbox.')}\n\n"
            "## Diff\n\n```diff\n"
            f"{diff[:12000]}\n"
            "```\n\n"
            "The Central Administrator reviewed and confirmed this proposal. "
            "CI must pass; the repository owner merges on GitHub."
        )
        result = self._request(
            "POST",
            "pulls",
            {"title": title, "head": branch, "base": self._base_branch, "body": body},
        )
        return PullRequest(branch=branch, url=str(result["html_url"]), number=int(result["number"]))


class MockGitHubClient:
    """Local/test adapter: captures a PR-shaped result without network access."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def open_pull_request(self, **payload: Any) -> PullRequest:
        task_id = str(payload["task_id"])
        branch = f"builder-agent/{task_id[:8]}"
        if branch == "main" or branch.startswith("main/"):
            raise GitHubPublishError("The Builder Agent cannot publish to the default branch")
        self.calls.append({**payload, "branch": branch})
        return PullRequest(
            branch=branch,
            url=f"https://github.com/ki957/deliveriq/pull/mock-{task_id[:8]}",
            number=0,
        )


def github_client(*, local_or_test: bool) -> GitHubClient | MockGitHubClient:
    if local_or_test:
        return MockGitHubClient()
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "ki957/deliveriq")
    base_branch = os.environ.get("GITHUB_BASE_BRANCH", "main")
    return GitHubClient(token, repository, base_branch)

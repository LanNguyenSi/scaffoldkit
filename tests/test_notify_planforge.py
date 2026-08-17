"""Dry-run proof for scripts/notify-planforge.sh.

Runs the real script as a subprocess against a local HTTP mock (no network,
never touches the live agent-tasks backend) and inspects the request(s) it
sends: method, path, auth header presence, JSON body shape (title,
externalRef, description contents), and the idempotency/supersede/no-op
control flow.
"""

from __future__ import annotations

import http.server
import json
import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "notify-planforge.sh"
PROJECT_ID = "5ff50a9c-de7b-4cfe-a2b5-22cd7fb0b109"
TOKEN = "test-planforge-bot-token"


@dataclass
class RecordedRequest:
    method: str
    path: str
    headers: dict
    json_body: dict | None


class MockPlanforgeServer:
    """A tiny local HTTP server that records requests and replays canned
    JSON responses keyed by (method, path-without-querystring)."""

    def __init__(self, routes: dict[tuple[str, str], tuple[int, dict]]):
        self.routes = routes
        self.requests: list[RecordedRequest] = []
        recorder = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw_body = self.rfile.read(length) if length else b""
                body_json = json.loads(raw_body) if raw_body else None
                path_no_query = self.path.split("?", 1)[0]
                recorder.requests.append(
                    RecordedRequest(
                        method=self.command,
                        path=self.path,
                        headers=dict(self.headers.items()),
                        json_body=body_json,
                    )
                )
                status, payload = recorder.routes.get((self.command, path_no_query), (200, {}))
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = _handle
            do_POST = _handle

            def log_message(self, log_format, *args):
                pass

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def __enter__(self) -> MockPlanforgeServer:
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def _run_script(env_overrides: dict, cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("PLANFORGE_BOT_TOKEN", None)
    env.update(env_overrides)
    return subprocess.run(
        [str(SCRIPT)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.fixture
def real_commits() -> tuple[str, str]:
    """(new_sha, old_sha) = (HEAD, HEAD~1) of this scaffoldkit checkout, so
    the script's real `git log`/`git diff` calls resolve against real
    history without mutating this repo."""
    new_sha = _git("rev-parse", "HEAD", cwd=REPO_ROOT)
    old_sha = _git("rev-parse", "HEAD~1", cwd=REPO_ROOT)
    return new_sha, old_sha


class TestMissingToken:
    def test_noop_when_token_absent(self, real_commits: tuple[str, str]):
        new_sha, old_sha = real_commits
        with MockPlanforgeServer(routes={}) as server:
            result = _run_script(
                {
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "LanNguyenSi/scaffoldkit",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                },
                cwd=REPO_ROOT,
            )
            assert result.returncode == 0
            assert server.requests == []
        assert "PLANFORGE_BOT_TOKEN is not set" in result.stderr


class TestCreatesTask:
    def test_creates_task_with_expected_shape(self, real_commits: tuple[str, str]):
        new_sha, old_sha = real_commits
        new_sha7 = new_sha[:7]
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-1"}, "confidence": {"score": 40}},
            ),
        }
        with MockPlanforgeServer(routes=routes) as server:
            result = _run_script(
                {
                    "PLANFORGE_BOT_TOKEN": TOKEN,
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "LanNguyenSi/scaffoldkit",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                },
                cwd=REPO_ROOT,
            )
            assert result.returncode == 0, result.stderr
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
                ("POST", f"/api/projects/{PROJECT_ID}/tasks"),
            ]

            get_req, post_req = server.requests
            assert get_req.headers["Authorization"] == f"Bearer {TOKEN}"
            assert post_req.headers["Authorization"] == f"Bearer {TOKEN}"
            assert post_req.headers["Content-Type"] == "application/json"

            body = post_req.json_body
            assert body["title"] == f"chore(deps): bump scaffoldkit to {new_sha7}"
            assert body["externalRef"] == f"scaffoldkit-bump/{new_sha}"
            assert new_sha in body["description"]
            assert (
                f"Compare: https://github.com/LanNguyenSi/scaffoldkit/compare/{old_sha}...{new_sha}"
                in body["description"]
            )
            assert "Files changed:" in body["description"]
            assert "Re-pickup checklist" in body["description"]

        # Token never appears in captured stdout/stderr.
        assert TOKEN not in result.stdout
        assert TOKEN not in result.stderr


class TestIdempotentSkip:
    def test_skips_when_open_task_for_same_sha_exists(self, real_commits: tuple[str, str]):
        new_sha, old_sha = real_commits
        new_sha7 = new_sha[:7]
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {
                    "tasks": [
                        {
                            "id": "existing-same-sha",
                            "status": "open",
                            "title": f"chore(deps): bump scaffoldkit to {new_sha7}",
                            "description": f"Commit: {new_sha} ({new_sha7})\n",
                        }
                    ]
                },
            ),
        }
        with MockPlanforgeServer(routes=routes) as server:
            result = _run_script(
                {
                    "PLANFORGE_BOT_TOKEN": TOKEN,
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "LanNguyenSi/scaffoldkit",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                },
                cwd=REPO_ROOT,
            )
            assert result.returncode == 0, result.stderr
            # Only the lookup GET happened - no POST create.
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
        assert "already exists" in result.stderr


class TestSupersede:
    def test_supersedes_older_open_task_then_creates_new(self, real_commits: tuple[str, str]):
        new_sha, old_sha = real_commits
        new_sha7 = new_sha[:7]
        older_fake_sha = "1111111111111111111111111111111111aaaa"
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {
                    "tasks": [
                        {
                            "id": "existing-older-sha",
                            "status": "open",
                            "title": "chore(deps): bump scaffoldkit to 1111111",
                            "description": f"Commit: {older_fake_sha} (1111111)\n",
                        }
                    ]
                },
            ),
            ("POST", "/api/tasks/existing-older-sha/respec"): (
                200,
                {"task": {"id": "existing-older-sha"}, "confidence": {"score": 40}},
            ),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-2"}, "confidence": {"score": 40}},
            ),
        }
        with MockPlanforgeServer(routes=routes) as server:
            result = _run_script(
                {
                    "PLANFORGE_BOT_TOKEN": TOKEN,
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "LanNguyenSi/scaffoldkit",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                },
                cwd=REPO_ROOT,
            )
            assert result.returncode == 0, result.stderr
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
                ("POST", "/api/tasks/existing-older-sha/respec"),
                ("POST", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
            _, respec_req, create_req = server.requests
            assert f"Superseded by {new_sha7}" in respec_req.json_body["description"]
            assert older_fake_sha in respec_req.json_body["description"]
            assert create_req.json_body["externalRef"] == f"scaffoldkit-bump/{new_sha}"


class TestHttpErrorHandling:
    def test_fails_loudly_on_unexpected_error(self, real_commits: tuple[str, str]):
        new_sha, old_sha = real_commits
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                500,
                {"error": "internal", "message": "boom"},
            ),
        }
        with MockPlanforgeServer(routes=routes) as server:
            result = _run_script(
                {
                    "PLANFORGE_BOT_TOKEN": TOKEN,
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "LanNguyenSi/scaffoldkit",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                },
                cwd=REPO_ROOT,
            )
            assert result.returncode != 0
        assert "500" in result.stderr
        assert TOKEN not in result.stdout
        assert TOKEN not in result.stderr

    def test_tolerates_dedupe_conflict_as_idempotent(self, real_commits: tuple[str, str]):
        new_sha, old_sha = real_commits
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                409,
                {"error": "conflict", "message": "externalRef already exists"},
            ),
        }
        with MockPlanforgeServer(routes=routes) as server:
            result = _run_script(
                {
                    "PLANFORGE_BOT_TOKEN": TOKEN,
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "LanNguyenSi/scaffoldkit",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                },
                cwd=REPO_ROOT,
            )
            assert result.returncode == 0, result.stderr
        assert "already has a task" in result.stderr


class TestRevertTitlePrefix:
    def test_revert_commit_gets_revert_prefixed_title(self, tmp_path: Path):
        # Isolated throwaway git repo so we control the commit subject
        # precisely, without touching this checkout's real history.
        repo = tmp_path / "repo"
        repo.mkdir()
        _git("init", "-q", cwd=repo)
        _git("config", "user.email", "ci@example.com", cwd=repo)
        _git("config", "user.name", "CI", cwd=repo)
        _git("commit", "--allow-empty", "-q", "-m", "Initial commit", cwd=repo)
        old_sha = _git("rev-parse", "HEAD", cwd=repo)
        _git(
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            'Revert "chore: something that broke"',
            cwd=repo,
        )
        new_sha = _git("rev-parse", "HEAD", cwd=repo)
        new_sha7 = new_sha[:7]

        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-3"}, "confidence": {"score": 40}},
            ),
        }
        with MockPlanforgeServer(routes=routes) as server:
            result = _run_script(
                {
                    "PLANFORGE_BOT_TOKEN": TOKEN,
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "acme/demo",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                },
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            create_req = server.requests[-1]
            expected_title = f"revert: chore(deps): bump scaffoldkit to {new_sha7}"
            assert create_req.json_body["title"] == expected_title

"""Dry-run proof for scripts/notify-planforge.sh.

Runs the real script as a subprocess against a local HTTP mock (no network,
never touches the live agent-tasks backend) and inspects the request(s) it
sends: method, path, auth header presence, JSON body shape (title,
externalRef, description contents), and the idempotency/supersede/no-op
control flow.

Every test drives the script against a throwaway two-commit git repo built
fresh under ``tmp_path`` (see ``_make_hermetic_repo``/``hermetic_repo``)
rather than this checkout's own history. That keeps the suite independent of
how much history the checkout that runs it has - it passes the same way in a
full local clone and in CI's shallow (``fetch-depth: 1``) checkout, where
``git rev-parse HEAD~1`` against the real repo would fail.
"""

from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "notify-planforge.sh"
PROJECT_ID = "5ff50a9c-de7b-4cfe-a2b5-22cd7fb0b109"
TOKEN = "test-planforge-bot-token"
ALL_ZERO_SHA = "0000000000000000000000000000000000000000"


@dataclass
class RecordedRequest:
    method: str
    path: str
    headers: dict
    json_body: dict | None


class MockPlanforgeServer:
    """A tiny local HTTP server that records requests and replays canned
    responses keyed by (method, path-without-querystring).

    A route's payload is normally a dict/list, JSON-encoded on the way out.
    Pass ``bytes`` instead to send a raw, non-JSON body (e.g. an HTML error
    page) so tests can exercise the script's jq-parse-failure handling."""

    def __init__(self, routes: dict[tuple[str, str], tuple[int, dict | bytes]]):
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
                if isinstance(payload, (bytes, bytearray)):
                    data = bytes(payload)
                    content_type = "text/html"
                else:
                    data = json.dumps(payload).encode("utf-8")
                    content_type = "application/json"
                self.send_response(status)
                self.send_header("Content-Type", content_type)
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


def _make_hermetic_repo(
    tmp_path: Path, second_commit_message: str = "feat: second commit"
) -> tuple[Path, str, str]:
    """Build a throwaway two-commit git repo under ``tmp_path`` and return
    ``(repo_dir, new_sha, old_sha)``.

    This never touches REPO_ROOT's real git history, so it behaves
    identically whether the checkout running the suite is a full clone or a
    CI shallow (depth-1) checkout.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "ci@example.com", cwd=repo)
    _git("config", "user.name", "CI", cwd=repo)
    _git("commit", "--allow-empty", "-q", "-m", "Initial commit", cwd=repo)
    old_sha = _git("rev-parse", "HEAD", cwd=repo)
    _git("commit", "--allow-empty", "-q", "-m", second_commit_message, cwd=repo)
    new_sha = _git("rev-parse", "HEAD", cwd=repo)
    return repo, new_sha, old_sha


@pytest.fixture
def hermetic_repo(tmp_path: Path) -> tuple[Path, str, str]:
    return _make_hermetic_repo(tmp_path)


class TestMissingToken:
    def test_noop_when_token_absent(self, hermetic_repo: tuple[Path, str, str]):
        repo, new_sha, old_sha = hermetic_repo
        with MockPlanforgeServer(routes={}) as server:
            result = _run_script(
                {
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "LanNguyenSi/scaffoldkit",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                },
                cwd=repo,
            )
            assert result.returncode == 0
            assert server.requests == []
        assert "PLANFORGE_BOT_TOKEN is not set" in result.stderr


class TestCreatesTask:
    def test_creates_task_with_expected_shape(self, hermetic_repo: tuple[Path, str, str]):
        repo, new_sha, old_sha = hermetic_repo
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
                cwd=repo,
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


class TestNoCompareDescription:
    """OLD_SHA sentinel / unreachable-commit paths both fall back to the
    documented no-compare description instead of trying (and failing) to
    diff against a commit that isn't there."""

    def test_initial_push_all_zero_old_sha(self, hermetic_repo: tuple[Path, str, str]):
        repo, new_sha, _old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-initial-push"}},
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
                    "OLD_SHA": ALL_ZERO_SHA,
                },
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            create_req = server.requests[-1]
            description = create_req.json_body["description"]
            assert "no prior commit to diff against" in description
            assert "(initial push; no prior commit to diff against)" in description

    def test_unreachable_old_sha(self, hermetic_repo: tuple[Path, str, str]):
        repo, new_sha, _old_sha = hermetic_repo
        unreachable_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-unreachable"}},
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
                    "OLD_SHA": unreachable_sha,
                },
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            create_req = server.requests[-1]
            description = create_req.json_body["description"]
            assert "no prior commit to diff against" in description
            assert "(initial push; no prior commit to diff against)" in description


class TestIdempotentSkip:
    def test_skips_when_open_task_for_same_sha_exists(self, hermetic_repo: tuple[Path, str, str]):
        repo, new_sha, old_sha = hermetic_repo
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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            # Only the lookup GET happened - no POST create.
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
        assert "already exists" in result.stderr

    def test_skips_when_same_sha_task_is_not_first_in_array(
        self, hermetic_repo: tuple[Path, str, str]
    ):
        """The same-sha match must be found anywhere in the filtered
        array, not just at index 0."""
        repo, new_sha, old_sha = hermetic_repo
        new_sha7 = new_sha[:7]
        older_fake_sha = "2222222222222222222222222222222222bbbb"
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {
                    "tasks": [
                        {
                            "id": "existing-older-sha-first",
                            "status": "open",
                            "title": "chore(deps): bump scaffoldkit to 2222222",
                            "description": f"Commit: {older_fake_sha} (2222222)\n",
                        },
                        {
                            "id": "existing-same-sha-second",
                            "status": "open",
                            "title": f"chore(deps): bump scaffoldkit to {new_sha7}",
                            "description": f"Commit: {new_sha} ({new_sha7})\n",
                        },
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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            # Same-sha match found (even though not first) -> skip
            # entirely, no respec/create calls fired.
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
        assert "existing-same-sha-second" in result.stderr
        assert "already exists" in result.stderr


class TestSupersede:
    def test_supersedes_older_open_task_then_creates_new(
        self, hermetic_repo: tuple[Path, str, str]
    ):
        repo, new_sha, old_sha = hermetic_repo
        new_sha7 = new_sha[:7]
        older_fake_sha = "1111111111111111111111111111111111aaaa"
        older_description = f"Commit: {older_fake_sha} (1111111)\n"
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {
                    "tasks": [
                        {
                            "id": "existing-older-sha",
                            "status": "open",
                            "title": "chore(deps): bump scaffoldkit to 1111111",
                            "description": older_description,
                        }
                    ]
                },
            ),
            ("GET", "/api/tasks/existing-older-sha"): (
                200,
                {"task": {"id": "existing-older-sha", "description": older_description}},
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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
                ("GET", "/api/tasks/existing-older-sha"),
                ("POST", "/api/tasks/existing-older-sha/respec"),
                ("POST", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
            _, _fetch_req, respec_req, create_req = server.requests
            assert f"Superseded by {new_sha7}" in respec_req.json_body["description"]
            assert older_fake_sha in respec_req.json_body["description"]
            assert create_req.json_body["externalRef"] == f"scaffoldkit-bump/{new_sha}"

    def test_supersedes_all_older_open_tasks(self, hermetic_repo: tuple[Path, str, str]):
        """Multiple open bump tasks (all older than NEW_SHA) must each be
        re-fetched and respec'd, not just the first one."""
        repo, new_sha, old_sha = hermetic_repo
        older_shas = [
            "1111111111111111111111111111111111aaaa",
            "2222222222222222222222222222222222bbbb",
            "3333333333333333333333333333333333cccc",
        ]
        task_ids = ["older-1", "older-2", "older-3"]
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {
                    "tasks": [
                        {
                            "id": task_id,
                            "status": "open",
                            "title": f"chore(deps): bump scaffoldkit to {sha[:7]}",
                            "description": f"Commit: {sha} ({sha[:7]})\n",
                        }
                        for task_id, sha in zip(task_ids, older_shas, strict=True)
                    ]
                },
            ),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-multi"}},
            ),
        }
        for task_id, sha in zip(task_ids, older_shas, strict=True):
            routes[("GET", f"/api/tasks/{task_id}")] = (
                200,
                {"task": {"id": task_id, "description": f"Commit: {sha} ({sha[:7]})\n"}},
            )
            routes[("POST", f"/api/tasks/{task_id}/respec")] = (
                200,
                {"task": {"id": task_id}},
            )

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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            fetch_calls = [
                r.path for r in server.requests if r.method == "GET" and "/api/tasks/" in r.path
            ]
            respec_calls = [
                r.path for r in server.requests if r.method == "POST" and r.path.endswith("/respec")
            ]
            assert sorted(fetch_calls) == sorted(f"/api/tasks/{tid}" for tid in task_ids)
            assert sorted(respec_calls) == sorted(f"/api/tasks/{tid}/respec" for tid in task_ids)
            # The new task is still created after all supersede attempts.
            assert server.requests[-1].method == "POST"
            assert server.requests[-1].path == f"/api/projects/{PROJECT_ID}/tasks"

    def test_respec_failure_degrades_to_warning_and_still_creates(
        self, hermetic_repo: tuple[Path, str, str]
    ):
        repo, new_sha, old_sha = hermetic_repo
        older_fake_sha = "1111111111111111111111111111111111aaaa"
        older_description = f"Commit: {older_fake_sha} (1111111)\n"
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {
                    "tasks": [
                        {
                            "id": "existing-older-sha",
                            "status": "open",
                            "title": "chore(deps): bump scaffoldkit to 1111111",
                            "description": older_description,
                        }
                    ]
                },
            ),
            ("GET", "/api/tasks/existing-older-sha"): (
                200,
                {"task": {"id": "existing-older-sha", "description": older_description}},
            ),
            ("POST", "/api/tasks/existing-older-sha/respec"): (
                403,
                {"error": "forbidden", "message": "not the task creator"},
            ),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-despite-403"}},
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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
                ("GET", "/api/tasks/existing-older-sha"),
                ("POST", "/api/tasks/existing-older-sha/respec"),
                ("POST", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
        assert "Could not mark task existing-older-sha as superseded" in result.stderr
        assert "403" in result.stderr

    def test_empty_fetched_description_skips_respec_and_still_creates(
        self, hermetic_repo: tuple[Path, str, str]
    ):
        """If the re-fetch of an older task comes back 200 with an empty
        description, the script must not POST /respec for it at all (to
        avoid clobbering the task with just the supersede note) - it
        should warn and move on, and the new task must still be created."""
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {
                    "tasks": [
                        {
                            "id": "existing-older-sha",
                            "status": "open",
                            "title": "chore(deps): bump scaffoldkit to 1111111",
                            "description": (
                                "Commit: 1111111111111111111111111111111111aaaa (1111111)\n"
                            ),
                        }
                    ]
                },
            ),
            ("GET", "/api/tasks/existing-older-sha"): (
                200,
                {"task": {"id": "existing-older-sha", "description": ""}},
            ),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-despite-empty-description"}},
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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            # No /respec call for this task - only the list, the re-fetch,
            # and the create.
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
                ("GET", "/api/tasks/existing-older-sha"),
                ("POST", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
        assert "fetched description is empty" in result.stderr
        assert "skipping supersede" in result.stderr


class TestTransportFailure:
    """A curl *transport* failure (DNS, connection refused, --max-time
    firing, etc. - no HTTP response at all) must not abort the whole
    script under `set -euo pipefail`. Every api_call site already has a
    non-200/201 handling path; api_call must reach it instead of letting
    the failing `status="$(curl ...)"` assignment kill the script."""

    def test_respec_transport_failure_still_creates(
        self, hermetic_repo: tuple[Path, str, str], tmp_path: Path
    ):
        repo, new_sha, old_sha = hermetic_repo
        older_fake_sha = "1111111111111111111111111111111111aaaa"
        older_description = f"Commit: {older_fake_sha} (1111111)\n"
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {
                    "tasks": [
                        {
                            "id": "existing-older-sha",
                            "status": "open",
                            "title": "chore(deps): bump scaffoldkit to 1111111",
                            "description": older_description,
                        }
                    ]
                },
            ),
            ("GET", "/api/tasks/existing-older-sha"): (
                200,
                {"task": {"id": "existing-older-sha", "description": older_description}},
            ),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-despite-transport-failure"}},
            ),
        }

        real_curl = shutil.which("curl")
        assert real_curl is not None, "curl must be on PATH to build the shim"

        # A curl shim on PATH that fails (transport-style, no HTTP response)
        # only for the /respec request and delegates everything else to the
        # real curl - proves the create still fires even though the
        # supersede attempt never got an HTTP status at all.
        shim_dir = tmp_path / "fake-bin"
        shim_dir.mkdir()
        curl_shim = shim_dir / "curl"
        curl_shim.write_text(
            "#!/usr/bin/env bash\n"
            'for arg in "$@"; do\n'
            '  case "$arg" in\n'
            "    */respec)\n"
            "      exit 7\n"
            "      ;;\n"
            "  esac\n"
            "done\n"
            f'exec "{real_curl}" "$@"\n'
        )
        curl_shim.chmod(0o755)

        with MockPlanforgeServer(routes=routes) as server:
            result = _run_script(
                {
                    "PLANFORGE_BOT_TOKEN": TOKEN,
                    "PLANFORGE_BASE_URL": server.base_url,
                    "PLANFORGE_PROJECT_ID": PROJECT_ID,
                    "GITHUB_REPOSITORY": "LanNguyenSi/scaffoldkit",
                    "NEW_SHA": new_sha,
                    "OLD_SHA": old_sha,
                    "PATH": f"{shim_dir}:{os.environ['PATH']}",
                },
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
            # The respec call never reached the mock server at all (curl
            # failed before making the request); the create still fires.
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
                ("GET", "/api/tasks/existing-older-sha"),
                ("POST", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
        assert "Could not mark task existing-older-sha as superseded" in result.stderr
        assert "000" in result.stderr


class TestHttpErrorHandling:
    def test_fails_loudly_on_unexpected_error(self, hermetic_repo: tuple[Path, str, str]):
        repo, new_sha, old_sha = hermetic_repo
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
                cwd=repo,
            )
            assert result.returncode != 0
        assert "500" in result.stderr
        assert TOKEN not in result.stdout
        assert TOKEN not in result.stderr

    def test_tolerates_dedupe_conflict_as_idempotent(self, hermetic_repo: tuple[Path, str, str]):
        repo, new_sha, old_sha = hermetic_repo
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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
        assert "already has a task" in result.stderr

    def test_200_create_with_task_id_is_treated_as_success(
        self, hermetic_repo: tuple[Path, str, str]
    ):
        """A plausible dedupe-by-returning-the-existing-task shape: HTTP
        200 with a real task id must succeed, not fall through to the
        loud-failure branch (the openapi spec only documents 201/403)."""
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {"task": {"id": "existing-deduped-task"}},
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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
        assert "existing-deduped-task" in result.stderr
        assert "treating as success" in result.stderr

    def test_200_create_without_task_id_still_fails(self, hermetic_repo: tuple[Path, str, str]):
        """A 200 create response with no `.task.id` in the body must NOT
        be treated as success - only a real task id makes the 200 arm
        exit 0; otherwise it must fall through to the loud-failure path."""
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                {"confidence": {"score": 40}},
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
                cwd=repo,
            )
            assert result.returncode != 0
        assert "Failed to create agent-planforge bump task" in result.stderr
        assert "200" in result.stderr

    def test_400_with_externalref_in_body_still_fails(self, hermetic_repo: tuple[Path, str, str]):
        """A 400 whose body happens to mention 'externalRef' must NOT be
        tolerated - only 409 alone, or 409/422 with a matching body, may
        be treated as idempotent."""
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                400,
                {"error": "bad_request", "message": "externalRef must be a non-empty string"},
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
                cwd=repo,
            )
            assert result.returncode != 0
        assert "400" in result.stderr
        assert "Failed to create agent-planforge bump task" in result.stderr

    def test_500_with_duplicate_in_body_still_fails(self, hermetic_repo: tuple[Path, str, str]):
        """A 500 whose body happens to contain the word 'duplicate' must
        NOT be tolerated as idempotent."""
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                500,
                {"error": "internal", "message": "duplicate key value violates constraint"},
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
                cwd=repo,
            )
            assert result.returncode != 0
        assert "500" in result.stderr
        assert "Failed to create agent-planforge bump task" in result.stderr

    def test_422_with_duplicate_in_body_tolerated_as_idempotent(
        self, hermetic_repo: tuple[Path, str, str]
    ):
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                422,
                {"error": "unprocessable", "message": "externalRef is a duplicate"},
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
                cwd=repo,
            )
            assert result.returncode == 0, result.stderr
        assert "already has a task" in result.stderr

    def test_422_with_non_matching_body_still_fails(self, hermetic_repo: tuple[Path, str, str]):
        """A 422 whose body does NOT mention externalRef/duplicate (some
        other validation error) must fall through to the loud-failure
        path, not be swallowed as idempotent."""
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                422,
                {"error": "unprocessable", "message": "title must not be empty"},
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
                cwd=repo,
            )
            assert result.returncode != 0
        assert "422" in result.stderr
        assert "Failed to create agent-planforge bump task" in result.stderr

    def test_fails_loudly_when_list_call_is_non_200(self, hermetic_repo: tuple[Path, str, str]):
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                503,
                {"error": "unavailable"},
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
                cwd=repo,
            )
            assert result.returncode != 0
            # No create call was attempted.
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
        assert "Failed to list existing agent-planforge tasks" in result.stderr
        assert "503" in result.stderr

    def test_fails_loudly_when_list_body_is_unparseable(self, hermetic_repo: tuple[Path, str, str]):
        """A 200 list response whose body jq cannot parse into the
        expected shape (e.g. an HTML error page slipped past the status
        check) must hit the same loud-failure path as a non-200 status,
        not die with a bare jq error under `set -e`."""
        repo, new_sha, old_sha = hermetic_repo
        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (
                200,
                b"<html><body>not json</body></html>",
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
                cwd=repo,
            )
            assert result.returncode != 0
            assert [(r.method, r.path.split("?")[0]) for r in server.requests] == [
                ("GET", f"/api/projects/{PROJECT_ID}/tasks"),
            ]
        assert "Failed to list existing agent-planforge tasks" in result.stderr


class TestRevertTitlePrefix:
    def test_revert_commit_gets_revert_prefixed_title(self, tmp_path: Path):
        repo, new_sha, old_sha = _make_hermetic_repo(
            tmp_path, second_commit_message='Revert "chore: something that broke"'
        )
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

    def test_lowercase_conventional_revert_gets_prefixed_title(self, tmp_path: Path):
        repo, new_sha, old_sha = _make_hermetic_repo(
            tmp_path, second_commit_message="revert: something that broke"
        )
        new_sha7 = new_sha[:7]

        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-lowercase-revert"}},
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

    def test_merge_wrapped_revert_gets_prefixed_title(self, tmp_path: Path):
        repo, new_sha, old_sha = _make_hermetic_repo(
            tmp_path,
            second_commit_message="Merge pull request #42 from acme/revert-bad-change",
        )
        new_sha7 = new_sha[:7]

        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-merge-revert"}},
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

    def test_reverting_prose_does_not_get_prefixed_title(self, tmp_path: Path):
        """'reverting the CSS tweak' must NOT be mislabeled as a revert -
        the loose `[Rr]evert*` pattern used to match this; the tightened
        delimiter-requiring pattern must not."""
        repo, new_sha, old_sha = _make_hermetic_repo(
            tmp_path, second_commit_message="reverting the CSS tweak"
        )
        new_sha7 = new_sha[:7]

        routes = {
            ("GET", f"/api/projects/{PROJECT_ID}/tasks"): (200, {"tasks": []}),
            ("POST", f"/api/projects/{PROJECT_ID}/tasks"): (
                201,
                {"task": {"id": "created-task-not-a-revert"}},
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
            expected_title = f"chore(deps): bump scaffoldkit to {new_sha7}"
            assert create_req.json_body["title"] == expected_title

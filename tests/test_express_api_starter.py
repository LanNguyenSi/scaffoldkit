"""Tests for the express-api blueprint runnable starter code."""

from pathlib import Path

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"

_DEFAULTS = {
    "project_name": "my-api",
    "display_name": "My API",
    "description": "A TypeScript REST API",
    "db_provider": "postgresql",
    "auth_strategy": "jwt",
    "use_docker": True,
    "use_redis": False,
    "use_websockets": False,
    "use_queue": False,
    "ai_context": True,
}


def _generate(tmp_path: Path, variables: dict) -> Path:
    bp_path = BLUEPRINTS_DIR / "express-api"
    bp = load_blueprint(bp_path)
    output = tmp_path / "output"
    ctx = GenerationContext(
        blueprint=bp,
        blueprint_path=bp_path,
        variables=variables,
        target_dir=output,
    )
    result = generate(ctx)
    assert result.success, f"Generation failed: {result.errors}"
    return output


def _assert_non_empty(path: Path) -> None:
    assert path.exists(), f"expected file missing: {path}"
    assert path.read_text().strip(), f"expected non-empty file: {path}"


class TestExpressApiStarter:
    def test_emits_runnable_source_files(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        # The starter source the implementer builds on. Before this change the
        # src/ tree was empty and tsc failed with TS18003 (no inputs).
        _assert_non_empty(output / "src" / "index.ts")
        _assert_non_empty(output / "src" / "routes" / "health.ts")
        _assert_non_empty(output / "src" / "middleware" / "error.ts")
        _assert_non_empty(output / "prisma" / "schema.prisma")
        _assert_non_empty(output / "tests" / "health.test.ts")
        _assert_non_empty(output / ".env.example")

    def test_entry_point_wires_router_and_error_handler(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        index = (output / "src" / "index.ts").read_text()

        # Entry point must export an app factory, mount the health router,
        # register the error handler, and listen on PORT (default 3000).
        assert "export function createApp" in index
        assert "healthRouter" in index
        assert "errorHandler" in index
        assert "process.env.PORT" in index

    def test_health_route_returns_status_ok(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        route = (output / "src" / "routes" / "health.ts").read_text()

        assert "healthRouter" in route
        assert '{ status: "ok" }' in route

    def test_prisma_schema_uses_selected_provider(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        schema = (output / "prisma" / "schema.prisma").read_text()

        assert 'provider = "postgresql"' in schema
        assert 'url      = env("DATABASE_URL")' in schema
        assert "generator client" in schema
        assert "model Example" in schema

        # The provider tracks the db_provider variable so `prisma generate` works.
        sqlite_output = _generate(tmp_path / "sqlite", {**_DEFAULTS, "db_provider": "sqlite"})
        sqlite_schema = (sqlite_output / "prisma" / "schema.prisma").read_text()
        assert 'provider = "sqlite"' in sqlite_schema

    def test_smoke_test_uses_declared_node_test_runner(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        test_file = (output / "tests" / "health.test.ts").read_text()
        package_json = (output / "package.json").read_text()

        # Smoke test runs under Node's built-in test runner (the declared
        # runner), loaded via the tsx devDep so TS test files execute.
        assert 'from "node:test"' in test_file
        assert "GET /health returns status ok" in test_file
        assert "node --import tsx --test" in package_json

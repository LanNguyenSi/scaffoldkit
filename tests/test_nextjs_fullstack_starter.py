"""Tests for the nextjs-fullstack blueprint runnable starter code."""

import json
from pathlib import Path

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"

_DEFAULTS = {
    "project_name": "my-next-app",
    "display_name": "My Next App",
    "description": "A modern full-stack web application",
    "language": "de",
    "db_provider": "postgresql",
    "auth_strategy": "jwt",
    "use_docker": True,
    "use_email": False,
    "use_analytics": False,
    "use_csv_export": False,
    "use_waitlist": False,
    "use_markdown": True,
    "use_og_tags": True,
    "ai_context": True,
}


def _generate(tmp_path: Path, variables: dict) -> Path:
    bp_path = BLUEPRINTS_DIR / "nextjs-fullstack"
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


def _read_nonempty(path: Path) -> str:
    assert path.exists(), f"Expected file missing: {path}"
    text = path.read_text()
    assert text.strip(), f"Expected non-empty file: {path}"
    return text


class TestNextjsFullstackStarter:
    def test_emits_runnable_app_and_api(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        # Config files needed for `next build` to run.
        _read_nonempty(output / "tsconfig.json")
        _read_nonempty(output / "next.config.mjs")
        _read_nonempty(output / "postcss.config.mjs")
        _read_nonempty(output / "eslint.config.mjs")

        # Authored home route + root layout (not framework defaults).
        layout = _read_nonempty(output / "app" / "layout.tsx")
        page = _read_nonempty(output / "app" / "page.tsx")
        assert "My Next App" in layout
        assert 'lang="de"' in layout
        assert "My Next App" in page
        assert "export default function Home" in page

        # Example route handler returning JSON {status: 'ok'}.
        route = _read_nonempty(output / "app" / "api" / "health" / "route.ts")
        assert "export async function GET" in route
        assert '"ok"' in route

    def test_emits_prisma_schema_and_client_singleton(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        schema = _read_nonempty(output / "prisma" / "schema.prisma")
        # Datasource provider tracks the chosen db_provider.
        assert 'provider = "postgresql"' in schema
        # At least one example model ships.
        assert "model Post" in schema

        lib = _read_nonempty(output / "lib" / "prisma.ts")
        assert "PrismaClient" in lib
        assert "globalForPrisma" in lib

    def test_sqlite_provider_threads_through_schema_and_env(self, tmp_path: Path):
        output = _generate(tmp_path, {**_DEFAULTS, "db_provider": "sqlite"})

        schema = _read_nonempty(output / "prisma" / "schema.prisma")
        assert 'provider = "sqlite"' in schema

        env = _read_nonempty(output / ".env.example")
        assert "file:./dev.db" in env

    def test_emits_smoke_test_and_declares_runner(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        _read_nonempty(output / "vitest.config.mts")
        test = _read_nonempty(output / "tests" / "health.test.ts")
        assert "GET" in test
        assert "status" in test

        # The declared test runner + scripts the Makefile relies on must exist.
        pkg = json.loads((output / "package.json").read_text())
        scripts = pkg["scripts"]
        assert scripts["test"] == "vitest run"
        assert "type-check" in scripts
        assert "format" in scripts
        assert "format:check" in scripts
        assert "vitest" in pkg["devDependencies"]
        assert "tailwindcss" in pkg["devDependencies"]
        assert "@tailwindcss/postcss" in pkg["devDependencies"]

    def test_next_pinned_off_known_cve(self, tmp_path: Path):
        # next 15.2.4 is affected by CVE-2025-66478; the blueprint must ship a
        # patched pin (kept in lockstep with eslint-config-next).
        output = _generate(tmp_path, _DEFAULTS)

        pkg = json.loads((output / "package.json").read_text())
        assert pkg["dependencies"]["next"] != "15.2.4"
        assert pkg["devDependencies"]["eslint-config-next"] != "15.2.4"
        assert pkg["dependencies"]["next"] == pkg["devDependencies"]["eslint-config-next"]

    def test_package_json_is_valid_across_option_combos(self, tmp_path: Path):
        # The conditional dependency/script blocks must render valid JSON for
        # every option combination, not just the default path.
        combos = [
            {"auth_strategy": "none", "use_docker": False, "use_og_tags": False},
            {"db_provider": "sqlite", "auth_strategy": "next-auth"},
            {
                "auth_strategy": "next-auth",
                "use_email": True,
                "use_analytics": True,
                "use_csv_export": True,
                "use_waitlist": True,
            },
        ]
        for i, overrides in enumerate(combos):
            output = _generate(tmp_path / f"combo{i}", {**_DEFAULTS, **overrides})
            pkg = json.loads((output / "package.json").read_text())
            # jwt-only deps must be absent when a different auth strategy is chosen.
            if overrides.get("auth_strategy") != "jwt":
                assert "jsonwebtoken" not in pkg["dependencies"]
                assert "bcrypt" not in pkg["dependencies"]

    def test_ships_prettierignore_excluding_markdown(self, tmp_path: Path):
        # format:check enforces code formatting, not the templated narrative docs.
        output = _generate(tmp_path, _DEFAULTS)

        prettierignore = _read_nonempty(output / ".prettierignore")
        assert "*.md" in prettierignore

    def test_optional_doc_bullets_stay_on_their_own_line(self, tmp_path: Path):
        # Inline {% if %}...{% endif %} bullets used to concatenate under
        # trim_blocks (e.g. "Docker + Traefik- **SEO:**"). Block-form keeps
        # each bullet on its own line.
        output = _generate(tmp_path, _DEFAULTS)

        for name in ("AI_CONTEXT.md", "README.md"):
            text = _read_nonempty(output / name)
            assert "Traefik- **" not in text
            assert "- **Deployment:** Docker + Traefik\n" in text

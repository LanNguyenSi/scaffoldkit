"""Tests for the symfony-nextjs blueprint runnable starter."""

import json
from pathlib import Path

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"

_DEFAULTS = {
    "project_name": "verify-symfony-nextjs",
    "display_name": "Verify symfony-nextjs",
    "description": "A fullstack application with Symfony API and Next.js frontend",
    "php_version": "8.3",
    "node_version": "22",
    "api_style": "api-platform",
    "database": "postgresql",
    "use_ddd": False,
    "use_auth": True,
    "auth_method": "jwt",
    "styling": "tailwind",
    "ui_library": "shadcn-ui",
    "use_docker": True,
    "use_ci": True,
    "use_rabbitmq": False,
    "use_redis": False,
    "test_strategy": "unit-and-integration",
    "design_style": "minimal-clean",
    "ai_context": True,
}


def _generate(tmp_path: Path, variables: dict) -> Path:
    bp_path = BLUEPRINTS_DIR / "symfony-nextjs"
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


class TestSymfonyNextjsStarter:
    def test_emits_runnable_api_source(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        api_files = [
            output / "apps" / "api" / "public" / "index.php",
            output / "apps" / "api" / "bin" / "console",
            output / "apps" / "api" / "src" / "Kernel.php",
            output / "apps" / "api" / "src" / "Controller" / "HealthController.php",
            output / "apps" / "api" / "config" / "bundles.php",
            output / "apps" / "api" / "config" / "routes.yaml",
            output / "apps" / "api" / "config" / "services.yaml",
            output / "apps" / "api" / "config" / "packages" / "framework.yaml",
            output / "apps" / "api" / ".env.example",
            output / "apps" / "api" / "phpunit.dist.xml",
            output / "apps" / "api" / "tests" / "Unit" / "Controller" / "HealthControllerTest.php",
        ]
        for f in api_files:
            assert f.exists(), f"missing {f}"
            assert f.read_text().strip(), f"empty {f}"

        controller = (
            output / "apps" / "api" / "src" / "Controller" / "HealthController.php"
        ).read_text()
        assert "#[Route('/health'" in controller
        assert "'status' => 'ok'" in controller

    def test_emits_runnable_web_source(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        web_files = [
            output / "apps" / "web" / "src" / "app" / "layout.tsx",
            output / "apps" / "web" / "src" / "app" / "page.tsx",
            output / "apps" / "web" / "src" / "services" / "health.ts",
            output / "apps" / "web" / "src" / "services" / "health.test.ts",
            output / "apps" / "web" / "next.config.mjs",
            output / "apps" / "web" / "tsconfig.json",
            output / "apps" / "web" / ".env.example",
            output / "packages" / "shared-types" / "src" / "index.ts",
        ]
        for f in web_files:
            assert f.exists(), f"missing {f}"
            assert f.read_text().strip(), f"empty {f}"

        page = (output / "apps" / "web" / "src" / "app" / "page.tsx").read_text()
        assert "Verify symfony-nextjs" in page
        assert "getApiHealth" in page

        shared = (output / "packages" / "shared-types" / "src" / "index.ts").read_text()
        assert "interface HealthStatus" in shared

    def test_composer_psr4_and_runtime_plugin_are_correct(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        composer = json.loads((output / "apps" / "api" / "composer.json").read_text())

        # PSR-4 prefix must be a single namespace separator. Regression: the
        # template double-escaped it to "App\\\\" which Composer reads as a
        # double separator, so autoload resolves nothing (ClassNotFoundError).
        assert composer["autoload"]["psr-4"] == {"App\\": "src/"}
        assert composer["autoload-dev"]["psr-4"] == {"App\\Tests\\": "tests/"}

        # symfony/runtime ships a Composer plugin generating
        # vendor/autoload_runtime.php (required by public/index.php + bin/console);
        # it must be allow-listed or Composer 2.2+ blocks it.
        assert composer["config"]["allow-plugins"].get("symfony/runtime") is True
        assert "phpunit/phpunit" in composer["require-dev"]

    def test_web_package_has_vitest_smoke_test(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        pkg = json.loads((output / "apps" / "web" / "package.json").read_text())

        assert pkg["scripts"]["test"] == "vitest run"
        assert "vitest" in pkg["devDependencies"]

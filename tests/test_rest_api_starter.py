"""Regression tests for the rest-api blueprint runnable starters.

Asserts that each framework path that the blueprint claims to support emits a
real, non-empty entry point + example route + smoke test instead of empty src/
directories. Mirrors the bar set by the fastapi starter (scaffoldkit #48) and
the symfony-backend starter (PR #52).
"""

import ast
from pathlib import Path

import pytest

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext
from scaffoldkit.planforge import default_variables_for_blueprint

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"


def _generate(tmp_path: Path, variables: dict) -> Path:
    bp_path = BLUEPRINTS_DIR / "rest-api"
    bp = load_blueprint(bp_path)
    # Seed declared defaults the way the CLI does, then apply the test overrides.
    merged = {**default_variables_for_blueprint(bp), **_BASE, **variables}
    output = tmp_path / "output"
    ctx = GenerationContext(
        blueprint=bp,
        blueprint_path=bp_path,
        variables=merged,
        target_dir=output,
    )
    result = generate(ctx)
    assert result.success, f"Generation failed: {result.errors}"
    return output


_BASE = {
    "project_name": "verify-rest-api",
    "display_name": "Verify rest-api",
    "description": "A test REST API",
}


def _assert_nonempty(path: Path) -> str:
    assert path.exists(), f"expected file missing: {path}"
    text = path.read_text()
    assert text.strip(), f"expected non-empty file: {path}"
    assert "{{" not in text, f"unrendered Jinja in {path}: {text[:200]}"
    return text


class TestFastapiStarter:
    """The default (fastapi) path must keep shipping its runnable starter."""

    def test_emits_runnable_python_source(self, tmp_path: Path):
        output = _generate(tmp_path, {**_BASE, "framework": "fastapi"})
        main = _assert_nonempty(output / "src" / "main.py")
        route = _assert_nonempty(output / "src" / "routes" / "health.py")
        smoke = _assert_nonempty(output / "tests" / "test_health.py")
        for source in (main, route, smoke):
            ast.parse(source)
        assert "FastAPI" in main
        assert "/health" in route
        assert "Verify rest-api" in main


class TestExpressStarter:
    """The express path must emit a runnable TypeScript starter, not empty src/."""

    def test_emits_runnable_typescript_source(self, tmp_path: Path):
        output = _generate(tmp_path, {**_BASE, "framework": "express"})
        app = _assert_nonempty(output / "src" / "app.ts")
        index = _assert_nonempty(output / "src" / "index.ts")
        route = _assert_nonempty(output / "src" / "routes" / "health.ts")
        smoke = _assert_nonempty(output / "tests" / "health.test.ts")
        pkg = _assert_nonempty(output / "package.json")
        _assert_nonempty(output / "tsconfig.json")

        assert "createApp" in app
        assert "express" in app
        assert "createApp" in index
        assert "/health" in route
        assert "createApp" in smoke
        assert "verify-rest-api" in app
        # The package wires the declared scripts to the emitted source.
        assert '"build"' in pkg
        assert '"test"' in pkg
        assert '"type": "module"' in pkg

    def test_no_orphan_python_starter_on_express(self, tmp_path: Path):
        output = _generate(tmp_path, {**_BASE, "framework": "express"})
        assert not (output / "src" / "main.py").exists()
        assert not (output / "tests" / "test_health.py").exists()
        assert not (output / "requirements.txt").exists()


class TestDjangoRestStarter:
    """The django-rest path must emit a bootable Django project, not empty src/."""

    def test_emits_runnable_django_project(self, tmp_path: Path):
        output = _generate(tmp_path, {**_BASE, "framework": "django-rest"})
        settings = _assert_nonempty(output / "config" / "settings.py")
        urls = _assert_nonempty(output / "config" / "urls.py")
        _assert_nonempty(output / "config" / "wsgi.py")
        _assert_nonempty(output / "config" / "__init__.py")
        views = _assert_nonempty(output / "api" / "views.py")
        api_urls = _assert_nonempty(output / "api" / "urls.py")
        _assert_nonempty(output / "api" / "apps.py")
        smoke = _assert_nonempty(output / "tests" / "test_health.py")
        manage = _assert_nonempty(output / "manage.py")
        _assert_nonempty(output / "requirements.txt")

        for source in (settings, urls, views, api_urls, smoke, manage):
            ast.parse(source)
        # The manage.py settings module and the urlconf must agree.
        assert "config.settings" in manage
        assert "config.settings" in settings or "ROOT_URLCONF" in settings
        assert "api.urls" in urls
        assert "/health" in smoke
        assert "health" in views
        assert "django" in (output / "requirements.txt").read_text().lower()

    def test_no_orphan_fastapi_starter_on_django(self, tmp_path: Path):
        output = _generate(tmp_path, {**_BASE, "framework": "django-rest"})
        assert not (output / "src" / "main.py").exists()
        assert not (output / "package.json").exists()


class TestSpringBootScopedOut:
    """spring-boot is intentionally left as a manifest-only shell here.

    A runnable spring-boot starter is redundant with the dedicated
    springboot-backend blueprint and is not buildable in the CI toolchain
    (no JDK/Maven). The path still emits pom.xml + docs, just no src/.
    """

    def test_no_partial_java_source(self, tmp_path: Path):
        output = _generate(tmp_path, {**_BASE, "framework": "spring-boot"})
        assert (output / "pom.xml").exists()
        java_sources = list(output.rglob("*.java"))
        assert java_sources == [], f"unexpected half-built java starter: {java_sources}"


@pytest.mark.parametrize("framework", ["fastapi", "express", "django-rest", "spring-boot"])
def test_every_framework_path_renders(tmp_path: Path, framework: str):
    """No framework choice leaves orphan or unrendered template files."""
    output = _generate(tmp_path, {**_BASE, "framework": framework})
    assert (output / "README.md").exists()
    for rendered in output.rglob("*"):
        if rendered.is_file():
            assert "{{" not in rendered.read_text(errors="ignore"), (
                f"unrendered Jinja in {rendered}"
            )

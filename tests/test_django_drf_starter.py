"""Regression tests for the django-drf runnable starter.

These assert that the blueprint emits real, non-empty Django + DRF source (a
runnable manage.py, a config package, an apps/api DRF app wired into the root
URLconf, and a pytest-django smoke test), not just empty config/ and apps/
directories. Companion to the runtime verification (`manage.py check` + the
generated smoke test) recorded in PHASE3_LANE_A_REPORT_2026-06-02.md.
"""

import ast
from pathlib import Path

import pytest

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"

_DEFAULTS = {
    "project_name": "verify-django-drf",
    "display_name": "Verify django-drf",
    "description": "A Django REST Framework backend",
    "python_version": "3.12",
    "package_manager": "uv",
    "database": "postgresql",
    "auth_strategy": "jwt",
    "use_docker": True,
    "use_celery": False,
    "use_channels": False,
    "use_drf_spectacular": True,
    "test_strategy": "pytest-django-and-integration",
    "ai_context": True,
}


def _generate(tmp_path: Path, variables: dict) -> Path:
    bp_path = BLUEPRINTS_DIR / "django-drf"
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


# Source files the starter must emit, relative to the generated project root.
_SOURCE_FILES = (
    "manage.py",
    "config/__init__.py",
    "config/settings/__init__.py",
    "config/urls.py",
    "config/wsgi.py",
    "config/asgi.py",
    "apps/__init__.py",
    "apps/api/__init__.py",
    "apps/api/apps.py",
    "apps/api/serializers.py",
    "apps/api/views.py",
    "apps/api/urls.py",
    "apps/users/__init__.py",
    "apps/users/apps.py",
    "tests/__init__.py",
    "tests/test_health.py",
)


class TestDjangoDrfStarter:
    def test_emits_runnable_source_files(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        for rel in _SOURCE_FILES:
            path = output / rel
            assert path.exists(), f"missing starter file: {rel}"
            # Non-empty and valid Python (catches accidental empty/garbled output).
            text = path.read_text()
            assert text.strip(), f"empty starter file: {rel}"
            ast.parse(text)
            # Jinja must be fully substituted, not left as literal {{ ... }}.
            assert "{{" not in text, f"unrendered jinja in {rel}"

    def test_manage_py_is_runnable_entry_point(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        manage = (output / "manage.py").read_text()
        assert "execute_from_command_line" in manage
        assert 'DJANGO_SETTINGS_MODULE", "config.settings"' in manage

    def test_health_endpoint_is_wired_into_root_urlconf(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        root_urls = (output / "config" / "urls.py").read_text()
        api_urls = (output / "apps" / "api" / "urls.py").read_text()
        views = (output / "apps" / "api" / "views.py").read_text()
        assert 'include("apps.api.urls")' in root_urls
        assert 'path("api/"' in root_urls
        assert "HealthView" in api_urls and "health" in api_urls
        assert "class HealthView(APIView)" in views

    def test_smoke_test_asserts_health_200(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        smoke = (output / "tests" / "test_health.py").read_text()
        assert "/api/health" in smoke
        assert "status_code == 200" in smoke
        # The project name is interpolated into the expected response body.
        assert "verify-django-drf" in smoke

    def test_settings_default_to_sqlite_for_runnability(self, tmp_path: Path):
        # Local/test DB must be SQLite so the starter runs with no live server,
        # regardless of the declared production database engine.
        output = _generate(tmp_path, _DEFAULTS)
        settings = (output / "config" / "settings" / "__init__.py").read_text()
        assert "django.db.backends.sqlite3" in settings
        assert '"apps.api"' in settings and '"apps.users"' in settings

    def test_drf_spectacular_gating_leaves_no_orphans(self, tmp_path: Path):
        # With drf-spectacular disabled, the dep is not installed, so the
        # settings/urls must not reference it (else the project fails to import).
        output = _generate(tmp_path, {**_DEFAULTS, "use_drf_spectacular": False})
        settings = (output / "config" / "settings" / "__init__.py").read_text()
        root_urls = (output / "config" / "urls.py").read_text()
        assert "drf_spectacular" not in settings
        assert "spectacular" not in root_urls.lower()
        # Source still parses and the app list is intact.
        ast.parse(settings)
        ast.parse(root_urls)

    @pytest.mark.parametrize("auth_strategy", ["session", "jwt", "token", "oauth2", "none"])
    def test_source_renders_for_all_auth_strategies(self, tmp_path: Path, auth_strategy: str):
        output = _generate(tmp_path, {**_DEFAULTS, "auth_strategy": auth_strategy})
        # The starter source is auth-agnostic and must always render cleanly.
        for rel in ("config/settings/__init__.py", "apps/api/views.py", "manage.py"):
            ast.parse((output / rel).read_text())

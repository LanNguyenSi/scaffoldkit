"""Tests for planforge.py — load_planforge_export, default_target_name, infer_* helpers."""

import json
from pathlib import Path

import pytest

from scaffoldkit.planforge import (
    PlanforgeExport,
    default_target_name,
    infer_auth_strategy,
    infer_database_choice,
    load_planforge_export,
)


def _minimal_export(**kwargs) -> PlanforgeExport:
    """Return a PlanforgeExport with only the required fields plus any overrides."""
    base = {"projectName": "Test Project", "blueprint": "rest-api"}
    base.update(kwargs)
    return PlanforgeExport.model_validate(base)


class TestLoadPlanforgeExport:
    def test_file_not_found_raises_value_error(self, tmp_path: Path):
        missing = tmp_path / "does-not-exist.json"
        with pytest.raises(ValueError, match="not found"):
            load_planforge_export(missing)

    def test_invalid_json_raises_value_error(self, tmp_path: Path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("this is not json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_planforge_export(bad_json)

    def test_missing_required_fields_raises_value_error(self, tmp_path: Path):
        # Valid JSON but missing projectName and blueprint (both required by PlanforgeExport)
        incomplete = tmp_path / "incomplete.json"
        incomplete.write_text(json.dumps({"summary": "no required fields"}), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid planforge export"):
            load_planforge_export(incomplete)

    def test_valid_export_loads_correctly(self, tmp_path: Path):
        payload = {"projectName": "My App", "blueprint": "rest-api", "summary": "A test app"}
        export_file = tmp_path / "scaffoldkit-input.json"
        export_file.write_text(json.dumps(payload), encoding="utf-8")
        result = load_planforge_export(export_file)
        assert result.projectName == "My App"
        assert result.blueprint == "rest-api"


class TestDefaultTargetName:
    def test_normal_project_name_slugified(self):
        export = _minimal_export(projectName="My Cool App")
        assert default_target_name(export) == "my-cool-app"

    def test_empty_project_name_returns_fallback(self):
        export = _minimal_export(projectName="")
        assert default_target_name(export) == "generated-project"

    def test_whitespace_only_project_name_returns_fallback(self):
        export = _minimal_export(projectName="   ")
        assert default_target_name(export) == "generated-project"

    def test_special_chars_are_slugified(self):
        export = _minimal_export(projectName="Hello World 2024!")
        assert default_target_name(export) == "hello-world-2024"


class TestInferDatabaseChoice:
    def test_sqlite_signal_in_constraints(self):
        export = _minimal_export(constraints=["prefer sqlite for local dev"])
        assert infer_database_choice(export, "db_provider") == "sqlite"

    def test_mysql_signal_in_constraints(self):
        export = _minimal_export(constraints=["must use mysql 8"])
        assert infer_database_choice(export, "db_provider") == "mysql"

    def test_mongodb_signal_with_database_variable(self):
        export = _minimal_export(stack={"dataStore": "mongodb"})
        assert infer_database_choice(export, "database") == "mongodb"

    def test_mongodb_signal_ignored_for_non_database_variable(self):
        # "mongo" in text but variable_name != "database" — falls through to postgresql
        export = _minimal_export(stack={"dataStore": "mongodb"})
        assert infer_database_choice(export, "db_provider") == "postgresql"

    def test_no_signal_defaults_to_postgresql(self):
        export = _minimal_export()
        assert infer_database_choice(export, "db_provider") == "postgresql"


class TestInferAuthStrategy:
    def test_public_only_signal_returns_none(self):
        export = _minimal_export(constraints=["public-only, no login required"])
        assert infer_auth_strategy(export, "rest-api") == "none"

    def test_anonymous_signal_returns_none(self):
        export = _minimal_export(summary="anonymous read-only API")
        assert infer_auth_strategy(export, "rest-api") == "none"

    def test_api_key_signal_returns_api_key_for_non_django(self):
        export = _minimal_export(features=["api-key authentication"])
        assert infer_auth_strategy(export, "rest-api") == "api-key"

    def test_api_key_signal_returns_token_for_django_drf(self):
        export = _minimal_export(features=["api-key authentication"])
        assert infer_auth_strategy(export, "django-drf") == "token"

    def test_oauth2_signal_returns_oauth2(self):
        export = _minimal_export(features=["oauth2 social login"])
        assert infer_auth_strategy(export, "rest-api") == "oauth2"

    def test_no_signal_defaults_to_jwt(self):
        export = _minimal_export()
        assert infer_auth_strategy(export, "rest-api") == "jwt"

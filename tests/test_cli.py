"""Tests for CLI commands."""

import json

from typer.testing import CliRunner

from scaffoldkit.cli import app

runner = CliRunner()


class TestListCommand:
    def test_lists_blueprints(self):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "saas-dashboard" in result.output
        assert "SaaS Dashboard" in result.output

    def test_lists_with_custom_dir_empty(self, tmp_path):
        result = runner.invoke(app, ["list", "--blueprints-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "No blueprints found" in result.output


class TestNewCommand:
    def test_invalid_blueprint_name(self, tmp_path):
        result = runner.invoke(app, ["new", "nonexistent", "--target", str(tmp_path)])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_help(self):
        result = runner.invoke(app, ["new", "--help"])
        assert result.exit_code == 0
        assert "blueprint" in result.output.lower()


class TestFromPlanforgeCommand:
    def test_generates_project_from_planforge_export(self, tmp_path):
        export_path = tmp_path / "scaffoldkit-input.json"
        target = tmp_path / "generated-app"
        export_path.write_text(
            json.dumps(
                {
                    "version": "1.1",
                    "exportedBy": "agent-planforge",
                    "projectName": "Ops Console",
                    "summary": "Internal operations dashboard with audit-aware workflows.",
                    "blueprint": "nextjs-fullstack",
                    "blueprintCandidates": ["nextjs-fullstack", "saas-dashboard"],
                    "features": ["analytics dashboard", "user authentication"],
                    "constraints": ["must be dockerized", "prefer TypeScript"],
                    "architecture": {"shape": "modular monolith"},
                    "stack": {"hint": "TypeScript web application", "dataStore": "relational"},
                    "suggestedVariables": {
                        "db_provider": "sqlite",
                        "use_docker": True,
                        "use_analytics": True,
                        "auth_strategy": "jwt",
                    },
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["from-planforge", str(export_path), "--target", str(target), "--no-install"],
        )

        assert result.exit_code == 0
        assert (target / "README.md").exists()
        assert (target / "package.json").exists()
        assert (target / ".ai" / "AGENTS.md").exists()

    def test_falls_back_to_candidate_blueprint_when_primary_is_missing(self, tmp_path):
        export_path = tmp_path / "scaffoldkit-input.json"
        target = tmp_path / "generated-app"
        export_path.write_text(
            json.dumps(
                {
                    "projectName": "Worker API",
                    "summary": "Backend worker with queued jobs.",
                    "blueprint": "missing-blueprint",
                    "blueprintCandidates": ["express-api", "rest-api"],
                    "features": ["workflow queue processing"],
                    "stack": {"hint": "TypeScript service stack"},
                    "suggestedVariables": {"use_queue": True},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["from-planforge", str(export_path), "--target", str(target), "--no-install"],
        )

        assert result.exit_code == 0
        assert "using fallback 'express-api'" in result.output
        assert (target / "README.md").exists()

    def test_reports_ignored_suggested_variables_without_failing(self, tmp_path):
        export_path = tmp_path / "scaffoldkit-input.json"
        target = tmp_path / "generated-app"
        export_path.write_text(
            json.dumps(
                {
                    "projectName": "Ops Console",
                    "summary": "Internal operations dashboard.",
                    "blueprint": "nextjs-fullstack",
                    "suggestedVariables": {
                        "db_provider": "sqlite",
                        "nonexistent_flag": True,
                    },
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["from-planforge", str(export_path), "--target", str(target), "--no-install"],
        )

        assert result.exit_code == 0
        assert "Ignoring unsupported suggested variables" in result.output
        assert "nonexistent_flag" in result.output

    def test_partial_planforge_payload_uses_defaults_with_warning(self, tmp_path):
        export_path = tmp_path / "scaffoldkit-input.json"
        target = tmp_path / "generated-app"
        export_path.write_text(
            json.dumps(
                {
                    "projectName": "Minimal Export",
                    "blueprint": "rest-api",
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["from-planforge", str(export_path), "--target", str(target), "--no-install"],
        )

        assert result.exit_code == 0
        assert "Planforge input warning" in result.output
        assert (target / "README.md").exists()

    def test_invalid_blueprint_in_planforge_export_fails_cleanly(self, tmp_path):
        export_path = tmp_path / "scaffoldkit-input.json"
        export_path.write_text(
            json.dumps(
                {
                    "projectName": "Broken Export",
                    "summary": "Invalid blueprint reference.",
                    "blueprint": "missing-blueprint",
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, ["from-planforge", str(export_path), "--no-install"])

        assert result.exit_code == 1
        assert "No compatible blueprint" in result.output
        assert "missing-blueprint" in result.output

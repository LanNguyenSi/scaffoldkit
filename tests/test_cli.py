"""Tests for CLI commands."""

import json
import subprocess
from importlib.metadata import version

from typer.testing import CliRunner

from scaffoldkit.cli import app

runner = CliRunner()


class TestVersionFlag:
    def test_long_flag_prints_package_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip() == f"scaffoldkit {version('scaffoldkit')}"

    def test_short_flag_prints_package_version(self):
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert result.output.strip() == f"scaffoldkit {version('scaffoldkit')}"


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

    def test_non_interactive_skips_confirmation(self, tmp_path):
        target = tmp_path / "sk-noni"
        result = runner.invoke(
            app,
            [
                "new",
                "cli-tool",
                "--target",
                str(target),
                "--non-interactive",
                "--no-install",
                "--var",
                "project_name=sk-noni",
                "--var",
                "display_name=SK NonI",
                "--var",
                "description=non-interactive smoke",
                "--var",
                "ai_context=true",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (target / "README.md").exists()
        assert "Aborted" not in result.output

    def test_yes_flag_skips_confirmation(self, tmp_path):
        target = tmp_path / "sk-yes"
        result = runner.invoke(
            app,
            [
                "new",
                "cli-tool",
                "--target",
                str(target),
                "--yes",
                "--non-interactive",
                "--no-install",
                "--var",
                "project_name=sk-yes",
                "--var",
                "display_name=SK Yes",
                "--var",
                "description=yes flag smoke",
                "--var",
                "ai_context=true",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (target / "README.md").exists()


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

    def test_no_ai_context_suppresses_ai_files_but_keeps_scaffold(self, tmp_path):
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
            [
                "from-planforge",
                str(export_path),
                "--target",
                str(target),
                "--no-install",
                "--no-ai-context",
            ],
        )

        assert result.exit_code == 0, result.output
        # AI-context files are suppressed: the caller (e.g. planforge) owns .ai/.
        # (test_generates_project_from_planforge_export is the negative control:
        # the same export WITHOUT the flag emits .ai/AGENTS.md.)
        assert not (target / ".ai" / "AGENTS.md").exists()
        assert not (target / ".ai" / "ARCHITECTURE.md").exists()
        assert not (target / "AI_CONTEXT.md").exists()
        # The rest of the scaffold is unaffected by the flag.
        assert (target / "README.md").exists()
        assert (target / "package.json").exists()

    def test_no_ai_context_preserves_caller_ai_files_under_overwrite(self, tmp_path):
        # Regression for the agent-planforge contract: planforge writes its own
        # .ai/ into the target first, then invokes from-planforge --overwrite. With
        # --no-ai-context, scaffoldkit must NOT clobber the caller's .ai/ files.
        export_path = tmp_path / "scaffoldkit-input.json"
        target = tmp_path / "generated-app"
        (target / ".ai").mkdir(parents=True)
        sentinel = target / ".ai" / "AGENTS.md"
        sentinel.write_text("PLANFORGE-ORIGINAL", encoding="utf-8")
        export_path.write_text(
            json.dumps(
                {
                    "version": "1.1",
                    "exportedBy": "agent-planforge",
                    "projectName": "Ops Console",
                    "summary": "Internal operations dashboard.",
                    "blueprint": "nextjs-fullstack",
                    "stack": {"hint": "TypeScript web application", "dataStore": "relational"},
                    "suggestedVariables": {"db_provider": "sqlite"},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "from-planforge",
                str(export_path),
                "--target",
                str(target),
                "--no-install",
                "--overwrite",
                "--no-ai-context",
            ],
        )

        assert result.exit_code == 0, result.output
        # The caller's pre-existing .ai/ file survives despite --overwrite.
        assert sentinel.read_text(encoding="utf-8") == "PLANFORGE-ORIGINAL"

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

    def test_prefers_fastapi_backend_for_generic_python_api_exports(self, tmp_path):
        export_path = tmp_path / "scaffoldkit-input.json"
        target = tmp_path / "generated-fastapi"
        export_path.write_text(
            json.dumps(
                {
                    "projectName": "Workflow Service",
                    "summary": "Python API for asynchronous workflow orchestration.",
                    "blueprint": "rest-api",
                    "blueprintCandidates": ["rest-api"],
                    "features": ["background workflow processing", "redis-backed coordination"],
                    "constraints": ["docker deployment", "JWT auth"],
                    "stack": {"hint": "Python application stack", "dataStore": "relational"},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["from-planforge", str(export_path), "--target", str(target), "--no-install"],
        )

        assert result.exit_code == 0
        assert "fallback 'fastapi-backend'" in result.output
        assert (target / "src" / "routes").is_dir()
        # fastapi-backend now shares the src/ layout with the thin rest-api (so the
        # planner's src/ task paths match); its richer layered dirs distinguish it.
        assert (target / "src" / "repositories").is_dir()
        assert (target / "alembic" / "versions").is_dir()

    def test_prefers_django_drf_for_generic_python_api_exports(self, tmp_path):
        export_path = tmp_path / "scaffoldkit-input.json"
        target = tmp_path / "generated-django"
        export_path.write_text(
            json.dumps(
                {
                    "projectName": "Case Management",
                    "summary": "Django REST API for internal case administration.",
                    "blueprint": "rest-api",
                    "blueprintCandidates": ["rest-api"],
                    "features": ["DRF serializers", "admin workflows"],
                    "constraints": ["session auth for internal operators"],
                    "stack": {"hint": "Python application stack", "dataStore": "relational"},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["from-planforge", str(export_path), "--target", str(target), "--no-install"],
        )

        assert result.exit_code == 0
        assert "fallback 'django-drf'" in result.output
        assert (target / "config" / "settings").is_dir()
        assert not (target / "src" / "routes").exists()

    def test_generates_runnable_typescript_cli_from_planforge_export(self, tmp_path):
        export_path = tmp_path / "scaffoldkit-input.json"
        target = tmp_path / "generated-cli"
        export_path.write_text(
            json.dumps(
                {
                    "version": "1.1",
                    "exportedBy": "agent-planforge",
                    "projectName": "agent-memory-sync",
                    "summary": "CLI tool to sync memory files through a central git repository.",
                    "blueprint": "cli-tool",
                    "blueprintCandidates": ["cli-tool", "express-api"],
                    "features": [
                        "push local memory files to remote git repo",
                        "dry-run mode to preview changes before sync",
                    ],
                    "constraints": [
                        "TypeScript only",
                        "no external databases, git is the source of truth",
                    ],
                    "stack": {"hint": "TypeScript CLI tool", "dataStore": "git"},
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["from-planforge", str(export_path), "--target", str(target), "--no-install"],
        )

        assert result.exit_code == 0
        assert (target / "package.json").exists()
        assert (target / "tsconfig.json").exists()
        assert (target / "src" / "main.ts").exists()
        assert (target / "src" / "commands" / "run.ts").exists()
        assert (target / "tests" / "run.test.ts").exists()

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


_NPM_INSTALL_VARS = [
    "--var",
    "project_name=npm-test",
    "--var",
    "display_name=Npm Test",
    "--var",
    "description=npm install test",
    "--var",
    "language=typescript",
    "--var",
    "cli_framework=commander",
    "--var",
    "distribution=binary",
    "--var",
    "ai_context=false",
]


class TestNpmInstall:
    def test_success_calls_npm_install(self, tmp_path, monkeypatch):
        # _run_npm_install only runs when the generated target contains a
        # package.json (the cli.py gate). The cli-tool blueprint with
        # language=typescript emits one, so omitting --no-install reaches the
        # subprocess call below.
        calls = []

        def fake_run(*args, **kwargs):
            calls.append((args, kwargs))

        monkeypatch.setattr("scaffoldkit.cli.subprocess.run", fake_run)

        target = tmp_path / "npm-success"
        result = runner.invoke(
            app,
            [
                "new",
                "cli-tool",
                "--target",
                str(target),
                "--non-interactive",
                "--yes",
                *_NPM_INSTALL_VARS,
            ],
        )

        assert result.exit_code == 0, result.output
        assert (target / "package.json").exists()  # precondition for the npm gate
        assert len(calls) == 1
        call_args, call_kwargs = calls[0]
        assert call_args[0] == ["npm", "install"]
        assert call_kwargs["cwd"] == target
        assert call_kwargs["check"] is True
        assert call_kwargs["capture_output"] is False
        assert "npm install completed" in result.output

    def test_called_process_error_is_swallowed(self, tmp_path, monkeypatch):
        def fake_run(*args, **kwargs):
            raise subprocess.CalledProcessError(returncode=1, cmd=["npm", "install"])

        monkeypatch.setattr("scaffoldkit.cli.subprocess.run", fake_run)

        target = tmp_path / "npm-cpe"
        result = runner.invoke(
            app,
            [
                "new",
                "cli-tool",
                "--target",
                str(target),
                "--non-interactive",
                "--yes",
                *_NPM_INSTALL_VARS,
            ],
        )

        assert result.exit_code == 0, result.output
        assert "npm install failed with exit code 1" in result.output

    def test_file_not_found_is_swallowed(self, tmp_path, monkeypatch):
        def fake_run(*args, **kwargs):
            raise FileNotFoundError

        monkeypatch.setattr("scaffoldkit.cli.subprocess.run", fake_run)

        target = tmp_path / "npm-fnf"
        result = runner.invoke(
            app,
            [
                "new",
                "cli-tool",
                "--target",
                str(target),
                "--non-interactive",
                "--yes",
                *_NPM_INSTALL_VARS,
            ],
        )

        assert result.exit_code == 0, result.output
        assert "npm not found" in result.output

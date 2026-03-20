"""Tests for CLI commands."""

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

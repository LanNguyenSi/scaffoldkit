"""Integration tests - full generation pipeline with content verification."""

from pathlib import Path

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"


def _generate_saas_dashboard(tmp_path: Path, **variable_overrides) -> Path:
    """Helper: generate a saas-dashboard project and return output path."""
    bp_path = BLUEPRINTS_DIR / "saas-dashboard"
    bp = load_blueprint(bp_path)

    variables = {
        "project_name": "test-app",
        "display_name": "Test App",
        "description": "Integration test project",
        "stack": "nextjs-fullstack",
        "architecture_style": "monorepo",
        "use_ddd": False,
        "use_auth": True,
        "use_docker": True,
        "use_ci": True,
        "test_strategy": "unit-and-integration",
        "design_style": "minimal-clean",
        "ai_context": True,
    }
    variables.update(variable_overrides)

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


class TestFullGeneration:
    def test_all_expected_files_exist(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path)

        expected_files = [
            "README.md",
            "AI_CONTEXT.md",
            "docs/architecture.md",
            "docs/ways-of-working.md",
            "docs/adrs/0001-architecture.md",
            "docs/page-templates/dashboard-page.md",
            "docs/page-templates/detail-page.md",
            "docs/page-templates/settings-page.md",
            ".gitignore",
            ".editorconfig",
        ]
        for f in expected_files:
            assert (output / f).exists(), f"Missing: {f}"

    def test_all_expected_directories_exist(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path)

        expected_dirs = [
            "apps/web",
            "apps/api",
            "packages/ui",
            "packages/shared",
            "docs/adrs",
            "docs/page-templates",
        ]
        for d in expected_dirs:
            assert (output / d).is_dir(), f"Missing dir: {d}"

    def test_readme_contains_project_info(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, display_name="Acme Dashboard")
        readme = (output / "README.md").read_text()
        assert "# Acme Dashboard" in readme
        assert "nextjs-fullstack" in readme
        assert "monorepo" in readme

    def test_ai_context_reflects_variables(self, tmp_path: Path):
        output = _generate_saas_dashboard(
            tmp_path,
            use_ddd=True,
            test_strategy="full-pyramid",
            design_style="corporate-professional",
        )
        ai_ctx = (output / "AI_CONTEXT.md").read_text()
        assert "DDD" in ai_ctx
        assert "full-pyramid" in ai_ctx
        assert "corporate-professional" in ai_ctx

    def test_architecture_doc_contains_stack(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, stack="django-htmx")
        arch = (output / "docs" / "architecture.md").read_text()
        assert "django-htmx" in arch

    def test_ways_of_working_contains_test_strategy(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, test_strategy="e2e-focused")
        wow = (output / "docs" / "ways-of-working.md").read_text()
        assert "e2e-focused" in wow
        assert "end-to-end" in wow.lower()

    def test_adr_reflects_architecture_style(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, architecture_style="microservices")
        adr = (output / "docs" / "adrs" / "0001-architecture.md").read_text()
        assert "microservices" in adr.lower()
        assert "Independent deployment" in adr

    def test_no_ai_context_when_disabled(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, ai_context=False)
        assert not (output / "AI_CONTEXT.md").exists()
        # Other files should still exist
        assert (output / "README.md").exists()

    def test_ddd_sections_present_when_enabled(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, use_ddd=True)
        arch = (output / "docs" / "architecture.md").read_text()
        assert "Domain Model" in arch
        assert "bounded contexts" in arch.lower()

    def test_ddd_sections_absent_when_disabled(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, use_ddd=False)
        arch = (output / "docs" / "architecture.md").read_text()
        assert "Domain Model" not in arch

    def test_docker_sections_conditional(self, tmp_path: Path):
        output_with = _generate_saas_dashboard(tmp_path, use_docker=True)
        arch_with = (output_with / "docs" / "architecture.md").read_text()
        assert "Docker" in arch_with

    def test_generates_docker_and_ci_contracts(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, use_docker=True, use_ci=True)
        assert (output / ".dockerignore").exists()
        assert (output / "Dockerfile").exists()
        assert (output / "docker-compose.yml").exists()
        assert (output / ".github" / "workflows" / "ci.yml").exists()

    def test_skips_docker_and_ci_contracts_when_disabled(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, use_docker=False, use_ci=False)
        assert not (output / ".dockerignore").exists()
        assert not (output / "Dockerfile").exists()
        assert not (output / "docker-compose.yml").exists()
        assert not (output / ".github" / "workflows" / "ci.yml").exists()

    def test_page_templates_reference_design_style(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, design_style="playful-modern")
        dashboard = (output / "docs" / "page-templates" / "dashboard-page.md").read_text()
        assert "playful-modern" in dashboard.lower() or "Colorful" in dashboard

    def test_static_files_are_valid(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path)

        gitignore = (output / ".gitignore").read_text()
        assert "node_modules" in gitignore

        editorconfig = (output / ".editorconfig").read_text()
        assert "root = true" in editorconfig

    def test_generated_files_are_nonempty(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path)
        for f in output.rglob("*"):
            if f.is_file():
                assert f.stat().st_size > 0, f"Empty file: {f.relative_to(output)}"


class TestDesignStyleVariations:
    """Verify all design style choices produce valid output."""

    def test_minimal_clean(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, design_style="minimal-clean")
        dashboard = (output / "docs" / "page-templates" / "dashboard-page.md").read_text()
        assert "whitespace" in dashboard.lower() or "subtle" in dashboard.lower()

    def test_corporate_professional(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, design_style="corporate-professional")
        dashboard = (output / "docs" / "page-templates" / "dashboard-page.md").read_text()
        assert len(dashboard) > 100

    def test_playful_modern(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, design_style="playful-modern")
        dashboard = (output / "docs" / "page-templates" / "dashboard-page.md").read_text()
        assert len(dashboard) > 100


class TestStackVariations:
    """Verify all stack choices produce valid output."""

    def test_nextjs_fullstack(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, stack="nextjs-fullstack")
        assert (output / "README.md").exists()

    def test_symfony_api_react(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, stack="symfony-api-react")
        readme = (output / "README.md").read_text()
        assert "symfony-api-react" in readme

    def test_django_htmx(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, stack="django-htmx")
        readme = (output / "README.md").read_text()
        assert "django-htmx" in readme

    def test_rails_hotwire(self, tmp_path: Path):
        output = _generate_saas_dashboard(tmp_path, stack="rails-hotwire")
        readme = (output / "README.md").read_text()
        assert "rails-hotwire" in readme

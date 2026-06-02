"""Tests for the static-site blueprint runnable starter (Astro path)."""

import json
from pathlib import Path

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"

_DEFAULTS = {
    "project_name": "my-site",
    "display_name": "My Site",
    "description": "A static website",
    "site_type": "docs",
    "framework": "astro",
    "styling": "tailwind",
    "use_cms": False,
    "cms_type": "markdown-files",
    "use_i18n": False,
    "use_analytics": False,
    "use_ci": True,
    "deploy_target": "vercel",
    "ai_context": True,
}


def _generate(tmp_path: Path, variables: dict) -> Path:
    bp_path = BLUEPRINTS_DIR / "static-site"
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


class TestStaticSiteStarter:
    def test_emits_runnable_astro_starter(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        # Framework config + a real entry point, layout, and page.
        starter_files = [
            "astro.config.mjs",
            "tsconfig.json",
            "src/layouts/Base.astro",
            "src/pages/index.astro",
            "src/styles/global.css",
            "src/content.config.ts",
            "src/content/docs/index.md",
            "tests/site.test.mjs",
        ]
        for rel in starter_files:
            path = output / rel
            assert path.exists(), f"missing starter file: {rel}"
            assert path.read_text().strip(), f"empty starter file: {rel}"

        # The page uses the base layout, and the layout wraps content.
        index = (output / "src" / "pages" / "index.astro").read_text()
        assert 'import Base from "@/layouts/Base.astro"' in index
        layout = (output / "src" / "layouts" / "Base.astro").read_text()
        assert "<slot />" in layout
        assert 'import "@/styles/global.css"' in layout

    def test_tailwind_dependency_and_integration_are_wired(self, tmp_path: Path):
        # Regression: the blueprint declared styling=tailwind by default but
        # shipped no tailwind dependency or integration, so the build had no
        # working styling pipeline. Both must now be present.
        output = _generate(tmp_path, _DEFAULTS)

        pkg = json.loads((output / "package.json").read_text())
        assert "@astrojs/tailwind" in pkg["dependencies"]
        assert "tailwindcss" in pkg["dependencies"]
        assert pkg["scripts"]["test"] == "node --test"

        config = (output / "astro.config.mjs").read_text()
        assert 'import tailwind from "@astrojs/tailwind"' in config
        assert "integrations: [tailwind()]" in config
        assert (output / "tailwind.config.mjs").exists()
        assert "@tailwind base;" in (output / "src" / "styles" / "global.css").read_text()

    def test_non_tailwind_astro_skips_tailwind_wiring(self, tmp_path: Path):
        output = _generate(tmp_path, {**_DEFAULTS, "styling": "vanilla-css"})

        pkg = json.loads((output / "package.json").read_text())
        assert "@astrojs/tailwind" not in pkg["dependencies"]
        assert "tailwindcss" not in pkg["dependencies"]
        assert not (output / "tailwind.config.mjs").exists()

        config = (output / "astro.config.mjs").read_text()
        assert "tailwind" not in config
        assert "@tailwind base;" not in (output / "src" / "styles" / "global.css").read_text()

    def test_content_collection_matches_site_type(self, tmp_path: Path):
        blog = _generate(tmp_path / "blog", {**_DEFAULTS, "site_type": "blog"})
        assert (blog / "src" / "content" / "blog" / "welcome.md").exists()
        assert not (blog / "src" / "content" / "docs" / "index.md").exists()
        assert "const blog = defineCollection" in (blog / "src" / "content.config.ts").read_text()

        portfolio = _generate(tmp_path / "portfolio", {**_DEFAULTS, "site_type": "portfolio"})
        assert (portfolio / "src" / "content" / "projects" / "example-project.md").exists()
        assert (
            "const projects = defineCollection"
            in (portfolio / "src" / "content.config.ts").read_text()
        )

        landing = _generate(tmp_path / "landing", {**_DEFAULTS, "site_type": "landing-page"})
        assert (landing / "src" / "content" / "sections" / "hero.md").exists()
        assert (
            "const sections = defineCollection"
            in (landing / "src" / "content.config.ts").read_text()
        )

    def test_non_astro_framework_skips_astro_starter(self, tmp_path: Path):
        output = _generate(tmp_path, {**_DEFAULTS, "framework": "eleventy"})

        assert not (output / "astro.config.mjs").exists()
        assert not (output / "src" / "pages" / "index.astro").exists()
        assert not (output / "src" / "content.config.ts").exists()
        assert not (output / "tests" / "site.test.mjs").exists()

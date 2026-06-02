"""Tests for the nextjs-frontend runnable starter (Phase-3 Batch B1)."""

import json
from pathlib import Path

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"

_DEFAULTS = {
    "project_name": "my-frontend",
    "display_name": "My Frontend",
    "description": "A Next.js frontend application",
    "nextjs_version": "15",
    "router": "app-router",
    "language": "typescript",
    "styling": "tailwind",
    "ui_library": "shadcn-ui",
    "state_management": "zustand",
    "api_client": "tanstack-query",
    "use_auth": True,
    "auth_provider": "next-auth",
    "use_i18n": False,
    "use_storybook": False,
    "use_docker": True,
    "use_ci": True,
    "test_strategy": "vitest-only",
    "design_style": "minimal-clean",
    "ai_context": True,
}


def _generate(tmp_path: Path, variables: dict) -> Path:
    bp_path = BLUEPRINTS_DIR / "nextjs-frontend"
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


class TestNextjsFrontendStarter:
    def test_emits_runnable_app_router_starter(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        # The starter must emit a real authored route, not just empty src/ dirs.
        # Regression: the blueprint previously left src/app empty, so `next build`
        # only produced the framework /404 and /500 pages.
        layout = output / "src" / "app" / "layout.tsx"
        page = output / "src" / "app" / "page.tsx"
        component = output / "src" / "components" / "features" / "WelcomeCard.tsx"

        for f in (layout, page, component):
            assert f.exists(), f"expected starter file missing: {f}"
            assert f.read_text().strip(), f"starter file is empty: {f}"

        # The home page is the authored "/" route and renders the example component.
        page_text = page.read_text()
        assert "export default function HomePage" in page_text
        assert "WelcomeCard" in page_text

        # The root layout imports the global stylesheet and sets metadata.
        layout_text = layout.read_text()
        assert 'import "./globals.css";' in layout_text
        assert "export default function RootLayout" in layout_text

    def test_emits_tailwind_wiring(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        globals_css = output / "src" / "app" / "globals.css"
        tailwind_config = output / "tailwind.config.ts"
        postcss_config = output / "postcss.config.mjs"

        assert globals_css.exists() and globals_css.read_text().strip()
        assert "@tailwind base;" in globals_css.read_text()
        assert tailwind_config.exists() and tailwind_config.read_text().strip()
        assert postcss_config.exists()
        assert "tailwindcss: {}" in postcss_config.read_text()

    def test_emits_smoke_test_and_runner_config(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        smoke_test = output / "src" / "app" / "page.test.tsx"
        vitest_config = output / "vitest.config.ts"
        vitest_setup = output / "vitest.setup.ts"

        for f in (smoke_test, vitest_config, vitest_setup):
            assert f.exists(), f"expected test scaffold missing: {f}"
            assert f.read_text().strip(), f"test scaffold file is empty: {f}"

        # The smoke test asserts the authored home page renders.
        test_text = smoke_test.read_text()
        assert "@testing-library/react" in test_text
        assert "HomePage" in test_text

    def test_next_is_pinned_off_the_vulnerable_release(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        pkg = json.loads((output / "package.json").read_text())

        # CVE-2025-66478: next 15.2.4 was vulnerable; bump to a patched 15.x.
        assert pkg["dependencies"]["next"] == "15.5.19"
        assert pkg["devDependencies"]["eslint-config-next"] == "15.5.19"

        # The pnpm packageManager pin was dropped so npm/yarn installs work too.
        assert "packageManager" not in pkg

        # The testing-library + jsdom toolchain ships so the smoke test runs.
        dev = pkg["devDependencies"]
        assert "@testing-library/react" in dev
        assert "jsdom" in dev
        assert "@vitejs/plugin-react" in dev
        assert "tailwindcss" in dev

    def test_jest_strategy_emits_jest_config_not_vitest(self, tmp_path: Path):
        # Regression: vitest.config/setup were gated on is_typescript only, so the
        # jest-and-cypress combo shipped vitest config with a jest-wired test
        # script and no jest config — npm test failed out of the box.
        output = _generate(tmp_path, {**_DEFAULTS, "test_strategy": "jest-and-cypress"})

        jest_config = output / "jest.config.mjs"
        jest_setup = output / "jest.setup.ts"
        for f in (jest_config, jest_setup):
            assert f.exists(), f"expected jest scaffold missing: {f}"
            assert f.read_text().strip(), f"jest scaffold file is empty: {f}"
        assert "next/jest" in jest_config.read_text()
        assert "@testing-library/jest-dom" in jest_setup.read_text()

        # The vitest runner config must NOT ship for the jest strategy.
        assert not (output / "vitest.config.ts").exists()
        assert not (output / "vitest.setup.ts").exists()

        # The package.json test script + deps must match the chosen runner.
        pkg = json.loads((output / "package.json").read_text())
        assert pkg["scripts"]["test"] == "jest --runInBand"
        assert "jest" in pkg["devDependencies"]
        assert "vitest" not in pkg["devDependencies"]

        # The smoke test ships for both runners (jest provides describe/it globally).
        assert (output / "src" / "app" / "page.test.tsx").exists()

    def test_javascript_path_emits_no_orphan_style_or_test_config(self, tmp_path: Path):
        # The runnable starter is TypeScript-only (no .jsx app templates). The JS
        # path must not leave orphan globals.css/postcss/runner configs behind.
        output = _generate(tmp_path, {**_DEFAULTS, "language": "javascript"})

        for orphan in (
            "src/app/globals.css",
            "postcss.config.mjs",
            "vitest.config.ts",
            "vitest.setup.ts",
            "jest.config.mjs",
            "jest.setup.ts",
        ):
            assert not (output / orphan).exists(), f"orphan emitted on JS path: {orphan}"

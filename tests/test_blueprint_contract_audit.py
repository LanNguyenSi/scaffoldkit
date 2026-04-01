"""Audit tests for blueprint feature flags that promise concrete generated files."""

from __future__ import annotations

from pathlib import Path

import yaml

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"

# These flags imply concrete scaffold output, not just conditional prose in README/docs.
_FLAG_CONTRACTS = {
    "use_docker": ("docker", "dockerfile"),
    "use_ci": (".github/workflows/",),
}

_KNOWN_GAPS: set[tuple[str, str]] = set()
_KNOWN_UNUSED_VARIABLES: set[tuple[str, str]] = set()


def _manifest_entries_for_flag(blueprint_dir: Path, flag: str) -> list[str]:
    data = yaml.safe_load((blueprint_dir / "blueprint.yaml").read_text())
    entries: list[str] = []
    for section in ("templates", "static_files"):
        for entry in data.get(section, []):
            if entry.get("condition") == flag:
                entries.append(str(entry.get("target", "")))
    return entries


def _audit_flag_contract_gaps() -> set[tuple[str, str]]:
    gaps: set[tuple[str, str]] = set()
    for blueprint_dir in sorted(p for p in BLUEPRINTS_DIR.iterdir() if p.is_dir()):
        data = yaml.safe_load((blueprint_dir / "blueprint.yaml").read_text())
        variables = {var["name"] for var in data.get("variables", [])}

        for flag, required_markers in _FLAG_CONTRACTS.items():
            if flag not in variables:
                continue

            targets = _manifest_entries_for_flag(blueprint_dir, flag)
            if not any(any(marker in target.lower() for marker in required_markers) for target in targets):
                gaps.add((blueprint_dir.name, flag))

    return gaps


def _audit_unused_variable_gaps() -> set[tuple[str, str]]:
    gaps: set[tuple[str, str]] = set()
    for blueprint_dir in sorted(p for p in BLUEPRINTS_DIR.iterdir() if p.is_dir()):
        data = yaml.safe_load((blueprint_dir / "blueprint.yaml").read_text())
        variables = [var["name"] for var in data.get("variables", [])]

        corpus_parts: list[str] = []
        for root in ("templates", "static"):
            directory = blueprint_dir / root
            if not directory.exists():
                continue
            for file_path in directory.rglob("*"):
                if not file_path.is_file():
                    continue
                try:
                    corpus_parts.append(file_path.read_text())
                except Exception:
                    continue

        corpus = "\n".join(corpus_parts)
        conditioned_variables = {
            entry.get("condition")
            for section in ("templates", "static_files")
            for entry in data.get(section, [])
            if entry.get("condition")
        }

        for variable in variables:
            if variable in conditioned_variables:
                continue
            if variable not in corpus:
                gaps.add((blueprint_dir.name, variable))

    return gaps


class TestBlueprintContractAudit:
    def test_known_infra_contract_gaps_snapshot(self):
        """Track blueprints whose docker/CI flags do not generate matching files yet."""
        assert _audit_flag_contract_gaps() == _KNOWN_GAPS

    def test_known_unused_variable_gaps_snapshot(self):
        """Track variables that are declared in blueprints but not referenced anywhere."""
        assert _audit_unused_variable_gaps() == _KNOWN_UNUSED_VARIABLES

# Contributing to ScaffoldKit

Thank you for your interest in contributing to ScaffoldKit! This document explains how to get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/LanNguyenSi/scaffoldkit.git
cd scaffoldkit

# Create virtual environment and install with dev dependencies
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=scaffoldkit --cov-report=term-missing

# Run a specific test file
pytest tests/test_generator.py -v
```

## Code Quality

We use ruff for linting and formatting, and mypy for type checking.

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/scaffoldkit/
```

All checks run automatically in CI on every pull request. CI also runs `shellcheck scripts/*.sh` and fails below the coverage floor set in `.github/workflows/ci.yml`; run the pytest command from that file to check locally.

## Project Structure

```
src/scaffoldkit/
  cli.py              # Typer CLI entry point
  tui.py              # Interactive prompts (questionary + rich)
  generator.py        # Core generation engine
  blueprint_loader.py # Blueprint discovery and parsing
  renderer.py         # Jinja2 template rendering
  models.py           # Pydantic data models
  validators.py       # Input validation
  variable_conditions.py # Conditional-variable pruning
  filesystem.py       # File system operations
  planforge.py        # agent-planforge export schema and variable mapping
  scaffold_blueprint.py # init-blueprint starter generator

  blueprints/         # Built-in blueprint definitions
tests/                # Test suite
```

See [docs/architecture.md](docs/architecture.md#module-map) for the full module map.

## Adding a New Blueprint

1. Create a new directory under `src/scaffoldkit/blueprints/`:
   ```
   src/scaffoldkit/blueprints/my-blueprint/
   ├── blueprint.yaml
   ├── templates/
   └── static/
   ```

2. Define the blueprint in `blueprint.yaml` (see existing blueprints for reference).

3. Add Jinja2 templates in `templates/` and static files in `static/`.

4. Add a test module for the blueprint, following the existing per-blueprint tests such as `tests/test_static_site_starter.py`, that generates the blueprint into a temporary directory and checks its key files. The blueprint must also pass `tests/test_blueprint_contract_audit.py`, which runs over every blueprint folder: every declared variable is referenced by a template or static file or used as a `condition`; a `use_docker` variable gates a Docker file; a `use_ci` variable gates a `.github/workflows/` file; and generated workflow templates use the action majors that test pins.

5. Run `scaffoldkit list` to verify discovery works.

## Pull Request Process

1. Fork the repository and create a feature branch from `master`.
2. Make your changes with clear, focused commits.
3. Add or update tests for your changes.
4. Run the full test suite and ensure it passes.
5. Run linting and type checks.
6. Open a pull request with a clear description of what and why.

### Commit Messages

Use conventional commit format:

```
feat(generator): add support for conditional directories
fix(tui): handle empty blueprint list gracefully
docs: update blueprint authoring guide
test: add edge case tests for renderer
```

## Releasing

1. Bump `version` in `pyproject.toml`.
2. Move the `[Unreleased]` entries in `CHANGELOG.md` under a new `## [x.y.z]` section.
3. Merge the change to `master`.
4. Push the tag `vx.y.z`.

The Release workflow (`.github/workflows/release.yml`) reruns CI, checks that the tag matches the `pyproject.toml` version and that `CHANGELOG.md` has a section for it, and attaches the wheel and sdist to a GitHub Release. Nothing is published to a package index.

## Design Principles

Keep these in mind when contributing:

- **Declarative over hard-coded**: Prefer YAML configuration and Jinja2 templates over Python logic.
- **Simple over clever**: Code should be easy to read and understand.
- **Tested**: New features need tests. Bug fixes need regression tests.
- **Separated concerns**: Blueprint logic, generation logic, and UI logic stay in their respective layers.

## Reporting Issues

When reporting a bug, please include:

- Python version (`python --version`)
- ScaffoldKit version (`scaffoldkit --version`)
- Steps to reproduce the issue
- Expected vs actual behavior
- Any error output

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

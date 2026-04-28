# Architecture

ScaffoldKit is three layers stacked top to bottom: a Typer CLI / questionary TUI on top, a generation engine in the middle, and a YAML/Pydantic blueprint layer at the bottom. The engine is pure Python with no daemons, no remote services, and no shared state across runs.

## Layer diagram

```
┌─────────────────────────────────┐
│  TUI / CLI Layer                │  Interactive prompts, display
│  (cli.py, tui.py)               │
├─────────────────────────────────┤
│  Generator / Rendering Layer    │  Template rendering, file I/O
│  (generator.py, renderer.py,    │
│   filesystem.py)                │
├─────────────────────────────────┤
│  Blueprint / Data Layer         │  Models, loading, validation
│  (models.py, blueprint_loader.py│
│   validators.py)                │
└─────────────────────────────────┘
```

## Module map

| Module | Responsibility |
|--------|----------------|
| `cli.py` | Typer entry point. Owns the four subcommands (`new`, `from-planforge`, `init-blueprint`, `list`) and the post-generate `npm install` hook. |
| `tui.py` | Interactive prompts (questionary + Rich). Blueprint picker, variable collection, target-dir prompt, confirmation summary, post-generate result printer. |
| `generator.py` | Orchestrates a generation run: validates variables, prunes inactive ones, builds the Jinja context (including derived `is_*` flags), iterates templates and static files, creates declared directories, returns a `GenerationResult`. |
| `renderer.py` | Wraps Jinja2: env construction, string rendering for inline values, template rendering from disk, raises with file context on missing variables. |
| `filesystem.py` | All file I/O: `ensure_directory`, `write_file`, `copy_file`. Honours `dry_run` and `overwrite` from the generation context. |
| `models.py` | Pydantic models: `Blueprint`, `BlueprintVariable`, `VariableType`, `GenerationContext`, `GenerationResult`. |
| `blueprint_loader.py` | Discovery and parsing. Resolves the blueprints directory (env override -> local checkout -> packaged), parses `blueprint.yaml`, validates against the model. |
| `validators.py` | Variable validation: required fields, type coercion, choice membership. |
| `variable_conditions.py` | Prunes variables whose `if` parent is falsy after collection. |
| `planforge.py` | `scaffoldkit-input.json` schema (`PlanforgeExport`), variable mapping, inference rules, blueprint-candidate fallback. See [planforge-integration.md](planforge-integration.md). |
| `scaffold_blueprint.py` | Backs `init-blueprint`: writes a starter `blueprint.yaml`, `templates/`, and `static/` skeleton. |

## Generation pipeline

A `scaffoldkit new` invocation runs the same pipeline whether the variables come from the TUI, `--var` flags, or a planforge export.

1. **Resolve blueprints dir.** `SCAFFOLDKIT_BLUEPRINTS_DIR` env wins. Otherwise the loader walks up from `cwd` looking for a `pyproject.toml` plus `src/scaffoldkit/blueprints/` (so editing inside a checkout just works). Falls back to the packaged blueprints shipped with the wheel.
2. **Load blueprint.** Parse `blueprint.yaml`, validate against the `Blueprint` model.
3. **Collect variables.** Either via the TUI prompts or by merging `--var` flags with blueprint defaults under `--non-interactive`. Required variables without defaults still fail fast.
4. **Validate.** `validators.py` checks required-ness, type coercion, choice membership.
5. **Prune.** `variable_conditions.prune_inactive_variables` drops variables whose `if` parent is now falsy.
6. **Build template context.** `generator.build_template_context` adds the variables, blueprint metadata (`blueprint_name`, `blueprint_display_name`, `blueprint_stack`), plus a fixed set of derived `is_*` flags so templates can branch on language, framework, package manager, config format, build tool, and stack without restating the same string compares.
7. **Render templates.** Each `templates[]` entry is rendered through Jinja2; the optional `condition` field skips entries whose variable is falsy. Both the `source` and `target` paths are themselves Jinja-rendered, so templates can live in `{{ stack }}/...` style folders.
8. **Copy static files.** Each `static_files[]` entry is copied verbatim from `static/` to its `target`.
9. **Create directories.** Each `directories[]` entry is materialised under the target.
10. **Post-generate hook.** If the generated tree has a `package.json` and `--no-install` was not passed, `cli.py` runs `npm install` in the target directory. Missing `npm` is a warning, not a failure.

`--dry-run` short-circuits steps 7-10: paths are computed and printed but no bytes are written.

## Watch and incremental?

There isn't one. Generation is a one-shot operation. There is no daemon, no incremental rebuild, and no shared state between runs. Re-running into the same target directory requires `--overwrite`.

## Design principles

- **Declarative over hard-coded.** Blueprints are YAML, templates are Jinja2. Adding a stack is adding a folder, not editing the engine.
- **Extensible over perfect.** The model is intentionally flat (no nested variables, no remote registry). New blueprints land as folders; new shipped blueprints are committed to `src/scaffoldkit/blueprints/`.
- **Locally runnable.** No external services required. `from-planforge` reads a local file. Embeddings, networks, and daemons are out of scope.
- **AI-friendly by design.** Every blueprint ships an `AI_CONTEXT.md`, an `architecture.md`, an ADR seed, and ways-of-working notes so a downstream Claude Code or Cursor session has real grounding from the first turn.

## Technologies

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| CLI | [Typer](https://typer.tiangolo.com/) |
| TUI Prompts | [questionary](https://github.com/tmbo/questionary) + [Rich](https://rich.readthedocs.io/) |
| Templating | [Jinja2](https://jinja.palletsprojects.com/) |
| YAML | [PyYAML](https://pyyaml.org/) |
| Models | [Pydantic](https://docs.pydantic.dev/) v2 |
| Packaging | [Hatch](https://hatch.pypa.io/) + [uv](https://docs.astral.sh/uv/) |
| Container | Docker (optional) |

## Repository layout

```
scaffoldkit/
├── install.sh                # One-line installer (uv or Docker)
├── Makefile                  # Build, test, install shortcuts
├── Dockerfile                # Container build
├── scaffoldkit-docker        # Docker wrapper script
├── pyproject.toml
├── src/
│   └── scaffoldkit/
│       ├── cli.py
│       ├── tui.py
│       ├── generator.py
│       ├── blueprint_loader.py
│       ├── renderer.py
│       ├── filesystem.py
│       ├── models.py
│       ├── validators.py
│       ├── variable_conditions.py
│       ├── planforge.py
│       ├── scaffold_blueprint.py
│       └── blueprints/        # 13 shipped blueprints
├── tests/                     # 78 tests: models, loader, validators, renderer, filesystem, generator, CLI, integration
├── .github/workflows/ci.yml   # lint, mypy strict, pytest 3.11/3.12/3.13, build+install
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

## Test suite

78 tests cover:

- **Models.** Data model construction and validation.
- **Blueprint loading.** Discovery, parsing, error handling.
- **Validators.** Required fields, type checks, choice validation.
- **Renderer.** String rendering, template rendering, missing-variable errors.
- **Filesystem.** Directory creation, file writing, copy, overwrite protection.
- **Generator.** Full pipeline, dry-run, conditions, overwrite, static files.
- **CLI.** Command help, blueprint listing, error paths.
- **Integration.** End-to-end generation across stack/style/feature variations.

CI runs ruff lint+format, mypy strict, pytest on Python 3.11, 3.12, 3.13, and a build+install verification on every push and PR to `main`.

## Assumptions and limits

- Python 3.11+ on the host (or via the `./install.sh` uv path, or via Docker).
- Blueprints live alongside the source code. There is no remote registry yet.
- Single-user local execution. No concurrency handling.
- Blueprint variables are flat. Nested objects are not supported.

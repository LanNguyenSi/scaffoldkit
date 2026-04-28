# CLI reference

ScaffoldKit ships a single `scaffoldkit` binary built on [Typer](https://typer.tiangolo.com/). Four subcommands: `new`, `from-planforge`, `init-blueprint`, `list`.

## Installation

No Python install required on your host. Pick the path that fits.

### Option A: One-line installer (recommended)

```bash
git clone https://github.com/LanNguyenSi/scaffoldkit.git
cd scaffoldkit
./install.sh
```

Installs [uv](https://docs.astral.sh/uv/) (if missing), then uv handles Python and dependencies. The `scaffoldkit` command lands in `~/.local/bin`.

### Option B: Docker (no Python on host)

```bash
git clone https://github.com/LanNguyenSi/scaffoldkit.git
cd scaffoldkit
./install.sh --docker
```

Builds the image and installs a thin wrapper. Only Docker and Bash required. You can also call the wrapper directly:

```bash
docker build -t scaffoldkit:latest .
./scaffoldkit-docker --output ./my-projects -- new
./scaffoldkit-docker -- list
./scaffoldkit-docker --print -- new saas-dashboard      # show docker command, do not run
./scaffoldkit-docker --build --output ./projects -- new # rebuild before running
```

### Option C: Makefile shortcuts

```bash
make install          # same as ./install.sh
make install-docker   # same as ./install.sh --docker
make dev              # create .venv with dev dependencies
```

### Option D: pipx (isolated installation)

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath

git clone https://github.com/LanNguyenSi/scaffoldkit.git
cd scaffoldkit
pipx install .
scaffoldkit --help
```

Isolated from system Python, no virtualenv activation, easy uninstall via `pipx uninstall scaffoldkit`.

### Option E: venv (development setup)

```bash
git clone https://github.com/LanNguyenSi/scaffoldkit.git
cd scaffoldkit
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
scaffoldkit --help
```

Use this when contributing, or when you need ruff/mypy/pytest installed.

If you hit `externally-managed-environment` on Debian/Ubuntu, the venv path above is the fix.

### Option F: Manual (Python 3.11+ already installed)

```bash
pip install .
# or for development:
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## `scaffoldkit new`

Generate a project from a blueprint.

```bash
scaffoldkit new [BLUEPRINT_NAME] [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `BLUEPRINT_NAME` | Blueprint to use. Omit for the interactive picker. |
| `-t, --target PATH` | Target directory for the generated project. |
| `-n, --dry-run` | Preview without writing files. |
| `--overwrite` | Overwrite existing files at the target. |
| `--no-install` | Skip `npm install` after generation (Node blueprints only). |
| `-b, --blueprints-dir PATH` | Use a custom blueprints directory. |
| `--var KEY=VALUE` | Set a blueprint variable. Repeatable. |
| `--non-interactive` | Use provided values plus blueprint defaults. Required vars without defaults still fail fast. |
| `-y, --yes` | Skip the confirmation prompt. |

`--var` accepts `true`/`false`, `yes`/`no`, `1`/`0` for booleans. Conditional variables are skipped automatically when their parent flag is disabled.

### Interactive

```bash
scaffoldkit new
```

Launches the TUI: pick a blueprint, answer prompts for variables, choose a target directory, review, confirm. Generated files and directories are printed at the end.

### Direct

```bash
scaffoldkit new saas-dashboard --target ./my-project
```

### Non-interactive

```bash
scaffoldkit new symfony-backend \
  --target ./my-symfony-app \
  --non-interactive --yes \
  --var project_name=my-symfony-app \
  --var display_name="My Symfony App" \
  --var description="A Symfony-based API backend" \
  --var php_version=8.3 \
  --var symfony_version=7.2 \
  --var api_style=api-platform \
  --var database=postgresql \
  --var use_ddd=true \
  --var use_cqrs=true \
  --var use_auth=false \
  --var use_docker=true \
  --var use_ci=true \
  --var use_rabbitmq=false \
  --var use_redis=false \
  --var test_strategy=phpunit-only \
  --var ai_context=true
```

### Post-generate npm install

If the generated project contains a `package.json` and `--no-install` is not passed, `scaffoldkit new` runs `npm install` in the target directory after generation. Missing `npm` produces a warning, not a failure.

## `scaffoldkit from-planforge`

Generate from an `agent-planforge` export:

```bash
scaffoldkit from-planforge ./scaffoldkit-input.json --target ./my-project
```

Selects the recommended blueprint (with fallback resolution), maps planforge `suggestedVariables` onto the blueprint contract, and applies a small set of inference rules for things like `database`, `auth_strategy`, and `use_docker`. See [planforge-integration.md](planforge-integration.md) for the full schema and inference rules.

Same `--target`, `--dry-run`, `--overwrite`, `--no-install`, `--blueprints-dir` flags as `new`.

## `scaffoldkit init-blueprint`

Scaffold a new blueprint folder under `blueprints/` with starter files.

```bash
scaffoldkit init-blueprint my-custom-stack
```

Creates `blueprints/my-custom-stack/` with `blueprint.yaml`, `templates/`, and `static/` skeletons. Edit, then `scaffoldkit list` to verify and `scaffoldkit new my-custom-stack` to test.

## `scaffoldkit list`

Print all available blueprints.

```bash
scaffoldkit list
```

Output:

```
Available blueprints:

  cli-tool - CLI Tool
    Command-line tool project skeleton with docs, tests, and AI context

  fastapi-backend - FastAPI Backend
    Production-ready FastAPI backend with layered application structure ...

  ...
```

The blueprints directory is resolved in this order:

1. `SCAFFOLDKIT_BLUEPRINTS_DIR` env var.
2. A local checkout's `src/scaffoldkit/blueprints/` if you are running from inside a scaffoldkit clone.
3. The packaged blueprints shipped with the installed wheel.

`-b, --blueprints-dir PATH` overrides all of the above.

## Docker wrapper

```bash
scaffoldkit-docker --output ./projects -- new                        # interactive
scaffoldkit-docker -- list                                           # list blueprints
scaffoldkit-docker --print -- new saas-dashboard                     # show docker command without running
scaffoldkit-docker --build --output ./projects -- new                # rebuild image then run
```

Anything after `--` is passed straight to `scaffoldkit` inside the container. The `--output` host directory is mounted so generated projects land on your host filesystem.

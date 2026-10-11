# CLI reference

ScaffoldKit ships a single `scaffoldkit` binary built on [Typer](https://typer.tiangolo.com/). Four subcommands: `new`, `from-planforge`, `init-blueprint`, `list`.

## Installation

Options A and B need no Python on your host (uv provides it for option A, the image for option B). Options D to F need Python 3.11 or newer. Pick the path that fits.

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

Builds the `scaffoldkit:latest` image and installs a wrapper named `scaffoldkit` in `~/.local/bin`. The wrapper mounts the current directory at `/workspace` and passes every argument to the container, so you use it like the native command (`scaffoldkit new`, `scaffoldkit list`). Only Docker and Bash are required.

The repository also ships `./scaffoldkit-docker`, a separate script that the installer does not put on your PATH; it takes wrapper options before `--` (see [Docker wrappers](#docker-wrappers)):

```bash
docker build -t scaffoldkit:latest .
./scaffoldkit-docker --output ./my-projects -- new
./scaffoldkit-docker -- list
./scaffoldkit-docker --print -- new saas-dashboard      # show docker command, do not run
./scaffoldkit-docker --build --output ./projects -- new # rebuild before running
```

With Docker Compose, `docker compose run --rm scaffoldkit new` runs the CLI with `./output` mounted as the working directory; pass `--target` as a relative path.

### Option C: Makefile shortcuts

```bash
make install          # same as ./install.sh
make install-docker   # same as ./install.sh --docker
make dev              # create .venv with dev dependencies
```

Run `make help` for the full list (test, lint, typecheck, check, build, docker-build, clean).

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

## Global options

These apply to the top-level `scaffoldkit` command itself, before any subcommand.

| Option | Description |
|--------|-------------|
| `-V, --version` | Print the installed ScaffoldKit version and exit. The version is read from package metadata, so it always matches the installed distribution. |
| `--help` | Show help. With no subcommand, `scaffoldkit` prints help by default. |

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
| `--non-interactive` | Use provided values plus blueprint defaults, and skip the confirmation prompt. Required vars without defaults still fail fast. The target directory is still prompted for unless `--target` is given. |
| `-y, --yes` | Skip the confirmation prompt. |

`--var` turns the values `true`/`false`, `yes`/`no`, `1`/`0` (any case) into booleans for every variable, whatever its declared type, so a string variable cannot be set to one of these literals from the command line. Conditional variables are skipped automatically when their parent flag is disabled.

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

If generation reports no errors, the generated project contains a `package.json`, and neither `--no-install` nor `--dry-run` is passed, `scaffoldkit new` runs `npm install` in the target directory after generation. `npm install` runs the lifecycle scripts of the generated `package.json`, so pass `--no-install` for a blueprint you have not reviewed (see [Path containment](architecture.md#path-containment)). Missing `npm` produces a warning, not a failure.

## `scaffoldkit from-planforge`

Generate from an `agent-planforge` export:

```bash
scaffoldkit from-planforge ./scaffoldkit-input.json --target ./my-project
```

Selects the recommended blueprint (with fallback resolution), maps planforge `suggestedVariables` onto the blueprint contract, and applies a small set of inference rules for things like `database`, `auth_strategy`, and `use_docker`. See [planforge-integration.md](planforge-integration.md) for the full schema and inference rules.

Same `--target`, `--dry-run`, `--overwrite`, `--no-install`, `--blueprints-dir` flags as `new`, plus a `from-planforge`-only `--no-ai-context` flag that suppresses the blueprint's AI-context files (the `.ai/` tree and `AI_CONTEXT.md`) for callers that already provide their own agent context.

## `scaffoldkit init-blueprint`

Scaffold a new blueprint folder in the resolved blueprints directory, with starter files.

```bash
scaffoldkit init-blueprint my-custom-stack
```

| Option | Description |
|--------|-------------|
| `NAME` | Name of the new blueprint folder. |
| `-b, --blueprints-dir PATH` | Create the blueprint in this directory instead of the resolved one. |

Creates `my-custom-stack/` inside the resolved blueprints directory (see [resolution order](#scaffoldkit-list)) with `blueprint.yaml`, `templates/`, and `static/` skeletons. Edit, then `scaffoldkit list` to verify and `scaffoldkit new my-custom-stack` to test.

Outside a scaffoldkit checkout, pass `-b <dir>` (or set `SCAFFOLDKIT_BLUEPRINTS_DIR`) so the blueprint is created in a directory you keep, and use the same `-b` with `list` and `new`. Otherwise it is written into the installed package's blueprints folder, and under Docker into the container, where it is discarded on exit.

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

## Docker wrappers

`./install.sh --docker` installs a wrapper named `scaffoldkit` that mounts the current directory at `/workspace` and forwards every argument to the container. It takes no wrapper options.

The repository-root script `./scaffoldkit-docker` is separate and is not installed on your PATH. Run it from the checkout:

```bash
./scaffoldkit-docker --output ./projects -- new                      # interactive
./scaffoldkit-docker -- list                                         # list blueprints
./scaffoldkit-docker --print -- new saas-dashboard                   # show docker command without running
./scaffoldkit-docker --build --output ./projects -- new              # rebuild image then run
```

| Option | Description |
|--------|-------------|
| `--output DIR` | Mount `DIR` at `/workspace` (default: the current directory). |
| `--build` | Rebuild the image before running. |
| `--print` | Print the `docker run` command without running it. |
| `SCAFFOLDKIT_IMAGE` (env var) | Override the image (default: `scaffoldkit:latest`). |

Anything after `--` is passed straight to `scaffoldkit` inside the container. The `--output` host directory is mounted so generated projects land on your host filesystem.

Inside the container, for either wrapper, pass `--target` as a path under the mounted directory (a relative path works). The image has no `npm`, so the post-generate install step prints a warning and is skipped. The image pins `SCAFFOLDKIT_BLUEPRINTS_DIR` to its bundled blueprints; for custom blueprints, place them under the mounted directory and pass `-b <relative path>`.

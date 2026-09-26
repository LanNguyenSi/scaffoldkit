# ScaffoldKit

AI-aided project scaffolding from declarative blueprints.

[![CI](https://github.com/LanNguyenSi/scaffoldkit/actions/workflows/ci.yml/badge.svg)](https://github.com/LanNguyenSi/scaffoldkit/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

ScaffoldKit generates complete project skeletons (source layout, docs, ways-of-working, ADRs, page templates, AI context files) from a folder of YAML blueprints plus Jinja2 templates. Each invocation resolves the blueprint, validates and prunes its variables, then renders templates and copies static files into the target directory; see [docs/architecture.md](docs/architecture.md) for the full pipeline and module map. It is the scaffolding engine behind [project-forge](https://github.com/LanNguyenSi/project-forge) and consumes the `scaffoldkit-input.json` export from [agent-planforge](https://github.com/LanNguyenSi/agent-planforge), so blueprints written here flow straight into both downstream tools.

## Key features

- Declarative blueprints: a `blueprint.yaml` plus Jinja2 templates; adding a stack is adding a folder, not editing the engine.
- 12 shipped blueprints spanning CLI tools, backend APIs (FastAPI, Express, Django REST, Spring Boot, Symfony), and frontends (Next.js, static sites, SaaS dashboards). Run `scaffoldkit list` to see all of them.
- Interactive TUI, or fully non-interactive generation via `--var`/`--non-interactive` for scripting.
- `from-planforge` consumes an agent-planforge export directly, mapping its suggested variables onto the blueprint contract.
- AI-context output: every blueprint ships `AI_CONTEXT.md`, an architecture doc, and an ADR seed for downstream Claude Code or Cursor sessions.
- Install via a one-line script, Docker, or pipx; Docker needs no Python on the host.
- Path-containment guard rejects generated paths that would escape the target directory.

## Quick start

Prerequisites: git, and either Docker or nothing else (`./install.sh` installs `uv`, which then manages Python).

```bash
git clone https://github.com/LanNguyenSi/scaffoldkit.git
cd scaffoldkit
./install.sh

# generate a CLI tool skeleton from the cli-tool blueprint
scaffoldkit new cli-tool \
  --target ./hello-cli \
  --non-interactive --yes \
  --var project_name=hello-cli \
  --var display_name="Hello CLI" \
  --var description="A demo CLI"
```

Generation prints every file and directory it created; for `cli-tool` that includes `AI_CONTEXT.md` and a `docs/` set with an architecture doc and an ADR seed.

Don't want Python on your host? Use `./install.sh --docker` instead. See [docs/cli.md](docs/cli.md#installation) for every install path.

## Usage

```bash
scaffoldkit new saas-dashboard --target ./my-project
```

Omit the blueprint name for the interactive picker, or add `--dry-run` to preview without writing. Full flag reference, the `from-planforge` and `init-blueprint` commands, and the Docker wrapper are in [docs/cli.md](docs/cli.md).

## Documentation

| If you want to... | Read |
|------|------|
| See every blueprint, its variables, and the YAML/Jinja format | [docs/blueprints.md](docs/blueprints.md) |
| Pipe an agent-planforge export into `scaffoldkit from-planforge` | [docs/planforge-integration.md](docs/planforge-integration.md) |
| Understand how generation works (loader, renderer, filesystem) | [docs/architecture.md](docs/architecture.md) |
| Full CLI reference (`new`, `from-planforge`, `init-blueprint`, `list`) | [docs/cli.md](docs/cli.md) |

## Development

```bash
make dev              # create .venv with dev deps
source .venv/bin/activate
make check            # run lint + typecheck + test
```

CI runs lint, mypy strict, pytest on Python 3.11/3.12/3.13, and a build+install verification on every push and PR to `master`. Pushes to `master` also open a bump task in agent-planforge; see [docs/planforge-integration.md](docs/planforge-integration.md#notifying-agent-planforge-of-new-commits).

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and PR process. Release history lives in [CHANGELOG.md](CHANGELOG.md).

## License

MIT, see [LICENSE](LICENSE).

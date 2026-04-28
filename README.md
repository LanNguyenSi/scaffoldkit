# ScaffoldKit

AI-aided project scaffolding from declarative blueprints.

ScaffoldKit generates complete project skeletons (source layout, docs, ways-of-working, ADRs, page templates, AI context files) from a folder of YAML blueprints plus Jinja2 templates. It is the scaffolding engine behind [project-forge](https://github.com/LanNguyenSi/project-forge) and consumes the `scaffoldkit-input.json` export from [agent-planforge](https://github.com/LanNguyenSi/agent-planforge), so blueprints written here flow straight into both downstream tools.

## Try it in 60 seconds

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

Don't want Python on your host? Use `./install.sh --docker` instead. See [docs/cli.md](docs/cli.md#installation) for every install path.

## What you get

```
Generation completed successfully!

Files created (9):
  README.md
  pyproject.toml
  .github/workflows/ci.yml
  docs/architecture.md
  docs/ways-of-working.md
  docs/adrs/0001-architecture.md
  AI_CONTEXT.md
  .editorconfig
  .gitignore

Directories (6):
  hello-cli/
  hello-cli/src
  hello-cli/src/commands
  hello-cli/src/config
  hello-cli/tests
  hello-cli/docs/adrs
```

`AI_CONTEXT.md` and the `docs/` set are the point: every blueprint ships ways-of-working, an architecture doc, and an ADR seed so a downstream Claude Code or Cursor session has real context from minute one. Run `scaffoldkit list` to see all 13 blueprints.

## Next steps

| If you want to... | Read |
|------|------|
| See every blueprint, its variables, and the YAML/Jinja format | [docs/blueprints.md](docs/blueprints.md) |
| Pipe an agent-planforge export into `scaffoldkit from-planforge` | [docs/planforge-integration.md](docs/planforge-integration.md) |
| Understand how generation works (loader, renderer, filesystem) | [docs/architecture.md](docs/architecture.md) |
| Full CLI reference (`new`, `from-planforge`, `init-blueprint`, `list`) | [docs/cli.md](docs/cli.md) |

## Used by

- [project-forge](https://github.com/LanNguyenSi/project-forge), end-to-end project bootstrapper that invokes ScaffoldKit for blueprint generation.
- [agent-planforge](https://github.com/LanNguyenSi/agent-planforge), planning tool whose `scaffoldkit-input.json` export feeds directly into `scaffoldkit from-planforge`.

Both depend on this repo in production. Changes to blueprint contracts here ripple into those consumers.

## Development

```bash
make dev              # create .venv with dev deps
source .venv/bin/activate
make check            # run lint + typecheck + test
```

Or directly:

```bash
pytest                                              # tests
pytest --cov=scaffoldkit --cov-report=term-missing  # coverage
ruff check src/ tests/                              # lint
ruff format src/ tests/                             # format
mypy src/scaffoldkit/                               # type check
```

CI runs lint, mypy strict, pytest on Python 3.11/3.12/3.13, and a build+install verification on every push and PR to `main`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and PR process. Release history lives in [CHANGELOG.md](CHANGELOG.md).

## License

MIT, see [LICENSE](LICENSE).

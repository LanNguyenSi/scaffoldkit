# Changelog

All notable changes to ScaffoldKit are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-06-02

### Added

- Runnable starter code for the remaining blueprints, so a generated project opens with a working app and a green smoke test instead of an empty `src/`: `express-api` ([#53](https://github.com/LanNguyenSi/scaffoldkit/pull/53)), `nextjs-frontend` ([#54](https://github.com/LanNguyenSi/scaffoldkit/pull/54)), `nextjs-fullstack` ([#55](https://github.com/LanNguyenSi/scaffoldkit/pull/55)), `static-site` (Astro) ([#56](https://github.com/LanNguyenSi/scaffoldkit/pull/56)), `django-drf` ([#57](https://github.com/LanNguyenSi/scaffoldkit/pull/57)), `springboot-backend` ([#59](https://github.com/LanNguyenSi/scaffoldkit/pull/59)), and the `symfony-nextjs` monorepo ([#60](https://github.com/LanNguyenSi/scaffoldkit/pull/60))
- `express` and `django-rest` runnable starters for the generic `rest-api` blueprint, alongside the existing FastAPI path ([#58](https://github.com/LanNguyenSi/scaffoldkit/pull/58))

### Fixed

- `symfony-backend`: corrected a double-escaped PSR-4 prefix and allow-listed the `symfony/runtime` Composer plugin so a generated project's autoload and bootstrap work, plus a runnable HealthController smoke test ([#52](https://github.com/LanNguyenSi/scaffoldkit/pull/52))
- Wheel build: excluded `blueprints/` from the wheel `packages` selection so they ship only via `force-include`, fixing a latent Hatchling duplicate-path collision ([#52](https://github.com/LanNguyenSi/scaffoldkit/pull/52))
- `springboot-backend`: fixed `application.yml` whitespace corruption and added the Maven wrapper ([#59](https://github.com/LanNguyenSi/scaffoldkit/pull/59))
- `nextjs-frontend`: bumped `next` off the vulnerable 15.2.4 to a patched 15.x release ([#54](https://github.com/LanNguyenSi/scaffoldkit/pull/54))

### Removed

- Removed the `reference-php-app` blueprint, an app-less ops/CI/security shell whose `project/` directory was only a placeholder mount. The runnable `symfony-backend` and `symfony-nextjs` blueprints cover real PHP/Symfony app and monorepo scaffolds ([#61](https://github.com/LanNguyenSi/scaffoldkit/pull/61))

## [0.3.0] - 2026-06-01

### Added

- Minimal runnable starter source for the `rest-api` (FastAPI) and `cli-tool` (Python) blueprints, so a generated repo opens with real, runnable code and a smoke test instead of an empty `src/` ([#48](https://github.com/LanNguyenSi/scaffoldkit/pull/48))
- Minimal runnable FastAPI starter for the `fastapi-backend` blueprint, the planforge remap target for python/FastAPI REST intakes ([#49](https://github.com/LanNguyenSi/scaffoldkit/pull/49))

### Changed

- Unified the `fastapi-backend` blueprint on the `src/` layout (`app/` to `src/`, `app/api/routes/` to `src/routes/`) so its scaffold matches the planner's generated task paths and the thin `rest-api` blueprint ([#50](https://github.com/LanNguyenSi/scaffoldkit/pull/50))

## [0.2.0] - 2026-06-01

### Added

- `scaffoldkit from-planforge --no-ai-context` to suppress blueprint AI-context file emission ([#45](https://github.com/LanNguyenSi/scaffoldkit/pull/45))

### Security

- Contain all generated paths under the target directory, blocking path traversal and absolute-path escapes during generation ([#44](https://github.com/LanNguyenSi/scaffoldkit/pull/44))

### Changed

- Documentation and packaging: README 60s hook restructured into `docs/`, completed open source surface (LICENSE holder, Code of Conduct, security policy, issue templates), and `pyproject.toml` authors set to Lan Nguyen Si ([#41](https://github.com/LanNguyenSi/scaffoldkit/pull/41), [#42](https://github.com/LanNguyenSi/scaffoldkit/pull/42), [#43](https://github.com/LanNguyenSi/scaffoldkit/pull/43))

## [0.1.0] - 2026-04-27

First public release.

### Added

#### CLI

- `scaffoldkit new` interactive TUI: blueprint picker, variable prompts, target-directory prompt, confirmation step, generation summary
- Direct mode: `scaffoldkit new <blueprint> --target ...`
- Non-interactive mode: `--non-interactive` plus repeatable `--var key=value` flags for CI / automation use
- `--yes/-y` flag to skip the confirmation prompt
- `--version/-V` flag (reads `importlib.metadata`, stays in sync with `pyproject.toml`) ([#38](https://github.com/LanNguyenSi/scaffoldkit/pull/38))
- `scaffoldkit list` to enumerate available blueprints
- `scaffoldkit from-planforge` to generate directly from an `agent-planforge` `scaffoldkit-input.json` export, with graceful fallback to candidate blueprints when the primary recommendation is unavailable
- `scaffoldkit init-blueprint` to scaffold a new blueprint folder with starter files
- `--dry-run`, `--overwrite`, `--no-install`, `--blueprints-dir` options on `new`
- Automatic `npm install` after generation when a `package.json` is produced (skippable via `--no-install`)

#### Blueprints

Thirteen production-ready blueprints, each with documentation, AI-context files, tests, and a scripted CI workflow:

- `cli-tool` — Command-line tool skeleton (Python or TypeScript)
- `django-drf` — Django REST Framework backend
- `express-api` — TypeScript REST API with Express, Prisma, PostgreSQL
- `fastapi-backend` — FastAPI backend with layered application structure
- `nextjs-frontend` — Next.js frontend
- `nextjs-fullstack` — Full-stack Next.js with Prisma, PostgreSQL, Tailwind
- `reference-php-app` — Symfony / PHP scaffold with Docker, CI, security tooling
- `rest-api` — Generic REST API skeleton with layered architecture
- `saas-dashboard` — Full-stack SaaS dashboard
- `springboot-backend` — Spring Boot Java backend
- `static-site` — Static documentation/marketing site
- `symfony-backend` — Symfony API backend (DDD/CQRS optional)
- `symfony-nextjs` — Symfony backend + Next.js frontend monorepo

Blueprint authoring contract: declarative `blueprint.yaml` (metadata, variables, file mappings) plus Jinja2 templates and static files. Conditional variables, boolean coercion, choice validation, and per-blueprint runtime bootstraps are supported.

#### Distribution & install

Six install paths are supported, all documented in the README:

- `./install.sh` — bootstraps `uv` and installs to `~/.local/bin`
- `./install.sh --docker` — Docker image + thin wrapper (`scaffoldkit-docker`)
- `make install` / `make install-docker` / `make dev` — Makefile shortcuts
- `pipx install .` — isolated global install
- `python3 -m venv .venv && pip install -e ".[dev]"` — development setup
- `pip install .` — manual

A `Dockerfile` and `docker-compose.yml` are shipped for the Docker path.

#### Engineering

- Comprehensive pytest suite covering models, blueprint loading, validators, renderer, filesystem, generator, CLI, and end-to-end integration
- CI on Python 3.11, 3.12, and 3.13: `ruff check`, `ruff format --check`, `mypy --strict`, pytest, package build
- Strict typing throughout `src/scaffoldkit`

### Fixed

- `--non-interactive` now skips the final confirmation prompt; previously it aborted on missing TTY despite documentation promising CI support ([#36](https://github.com/LanNguyenSi/scaffoldkit/pull/36))
- `pyproject.toml` `[project.urls]` corrected from the non-existent `scaffoldkit/scaffoldkit` org to the real `LanNguyenSi/scaffoldkit` repo. README and CONTRIBUTING `git clone` snippets now use the real URL ([#37](https://github.com/LanNguyenSi/scaffoldkit/pull/37))

### Known limitations

- Blueprints live alongside the source code; no remote blueprint registry yet.
- Single-user local execution; no concurrency guards.
- Blueprint variables are flat (no nested objects).

[Unreleased]: https://github.com/LanNguyenSi/scaffoldkit/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/LanNguyenSi/scaffoldkit/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/LanNguyenSi/scaffoldkit/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/LanNguyenSi/scaffoldkit/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/LanNguyenSi/scaffoldkit/releases/tag/v0.1.0

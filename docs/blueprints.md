# Blueprints

A blueprint is a self-contained folder that tells ScaffoldKit how to generate a project: what to ask the user, which files to render, which files to copy as-is, and which directories to create.

## Folder layout

Shipped blueprints live in `src/scaffoldkit/blueprints/`; custom ones live in any directory passed via `--blueprints-dir` or `SCAFFOLDKIT_BLUEPRINTS_DIR`. Each blueprint folder has this layout:

```
<blueprints-dir>/<name>/
├── blueprint.yaml    # Definition: metadata, variables, file mappings
├── templates/        # Jinja2 templates (rendered with variables)
└── static/           # Static files (copied as-is)
```

## `blueprint.yaml` structure

```yaml
name: my-blueprint
display_name: "My Blueprint"
description: "What this blueprint generates"
version: "1.0.0"
stack: "nextjs"

metadata:                 # Optional: free-form keys merged into the template context
  architecture: "layered"

variables:
  - name: project_name
    description: "Project slug"
    type: string          # string | boolean | choice
    default: "my-project"
    required: true

  - name: use_docker
    type: boolean
    default: true

  - name: stack
    type: choice
    choices: ["nextjs", "remix", "astro"]
    default: "nextjs"

templates:
  - source: README.md.j2        # Path inside templates/
    target: README.md           # Path in generated project
    condition: null             # Optional: template-context key (variable or derived is_* flag) that must be truthy

static_files:
  - source: .gitignore
    target: .gitignore
  - source: .dockerignore
    target: .dockerignore
    condition: use_docker       # Optional, same as for templates

directories:
  - src
  - docs
```

### Variable types

- `string`: free-form text, optional `default`.
- `boolean`: `true`/`false`. Inputs like `yes`/`no`/`1`/`0` are normalised by the CLI's `--var` parser and by the planforge input path; the interactive prompt and the blueprint loader itself do no boolean coercion. The `--var` parser converts these literals for every variable, whatever its declared type (see [cli.md](cli.md#scaffoldkit-new)).
- `choice`: must come with `choices: [...]`. When normalising planforge input, a value outside `choices` falls back to the blueprint's default choice, or to the first choice if the default is absent or invalid. A choice variable with no default and no supplied value is not filled in; it fails validation as a missing required variable. `scaffoldkit new` validates strictly instead: for active variables (inactive ones are pruned before validation), an invalid choice value is a hard error.

Variables default to `required: true`. In `--non-interactive` mode declared defaults are used for all variables; only a required variable without a default fails. Variables can also be made conditional via the `condition` field, in which case they are only collected when their parent flag is truthy. Inactive variables are pruned from the rendering context.

### Template variables in Jinja

All collected variables plus blueprint metadata are exposed to templates:

```jinja
# {{ display_name }}

Stack: {{ stack }}
{% if use_auth %}
Authentication is enabled.
{% endif %}
```

The generator also injects derived flags (`is_python`, `is_typescript`, `is_fastapi`, `is_nextjs_fullstack`, `is_uv`, `is_yaml_config`, etc.) so templates can branch on language/framework/package-manager without re-implementing string compares. See [Conditions and derived flags](#conditions-and-derived-flags) for the full list.

Any keys under the blueprint's top-level `metadata` map are also merged into the template context verbatim, so blueprint authors can expose extra template variables (for example an `architecture` label) without adding a user-facing prompt. Metadata is merged last, so a metadata key overrides a variable or derived flag of the same name.

### Conditions and derived flags

`condition` means two different things depending on where it appears:

- On a `templates` or `static_files` entry, `condition` names any key in the template context: a variable, a derived `is_*` flag, a `blueprint_*` identity field (`blueprint_name`, `blueprint_display_name`, `blueprint_stack`), or a `metadata` key. The entry is skipped when that value is missing or falsy.
- On a variable, `condition` names another variable. It is resolved against the collected values and the declared defaults, and the variable is only collected when that parent is truthy.

The derived flags are computed by `generator.build_template_context`, which is the source of truth. Source values are compared case-insensitively.

| Source variable | Derived flags |
|-----------------|---------------|
| `language` | `is_python`, `is_go`, `is_rust`, `is_typescript` |
| `config_format` | `is_json_config`, `is_yaml_config`, `is_toml_config` |
| `package_manager` | `is_uv`, `is_poetry`, `is_pip_tools` |
| `build_tool` | `is_maven`, `is_gradle` |
| `framework` | `is_fastapi`, `is_express`, `is_django_rest`, `is_spring_boot`, `is_astro`, `is_nextjs_static`, `is_hugo`, `is_eleventy` |
| `stack` | `is_nextjs_fullstack`, `is_symfony_api_react`, `is_django_htmx`, `is_rails_hotwire` |
| `api_style` | `is_api_platform`, `is_custom_controllers`, `is_fos_rest`, `is_spring_mvc`, `is_webflux` |
| `api_style` and `use_auth` | `is_spring_mvc_auth`, `is_webflux_auth` |
| `stack` and `use_docker` | `is_nextjs_fullstack_docker`, `is_symfony_api_react_docker`, `is_django_htmx_docker`, `is_rails_hotwire_docker` |
| `stack` and `use_ci` | `is_nextjs_fullstack_ci`, `is_symfony_api_react_ci`, `is_django_htmx_ci`, `is_rails_hotwire_ci` |
| `framework` and `styling` / `site_type` | `is_astro_tailwind`, `is_astro_docs`, `is_astro_blog`, `is_astro_portfolio`, `is_astro_landing_page` |
| `test_strategy` (and `language`) | `is_vitest`, `is_jest`, `is_typescript_vitest`, `is_typescript_jest` |

## Shipped blueprints

ScaffoldKit ships 12 blueprints in `src/scaffoldkit/blueprints/`. `scaffoldkit list` always reflects the current set.

| Name | Stack | Description |
|------|-------|-------------|
| [`cli-tool`](../src/scaffoldkit/blueprints/cli-tool/blueprint.yaml) | cli | Command-line tool project skeleton with docs, tests, and AI context. |
| [`django-drf`](../src/scaffoldkit/blueprints/django-drf/blueprint.yaml) | python-django | Production-ready Django REST Framework backend with project structure, API guidance, and AI context. |
| [`express-api`](../src/scaffoldkit/blueprints/express-api/blueprint.yaml) | express-api | TypeScript REST API with Express, Prisma, PostgreSQL, and AI agent context. |
| [`fastapi-backend`](../src/scaffoldkit/blueprints/fastapi-backend/blueprint.yaml) | python-fastapi | Production-ready FastAPI backend with layered application structure, API guidance, and AI context. |
| [`nextjs-frontend`](../src/scaffoldkit/blueprints/nextjs-frontend/blueprint.yaml) | frontend | Production-ready Next.js frontend project skeleton with docs, conventions, and AI context. |
| [`nextjs-fullstack`](../src/scaffoldkit/blueprints/nextjs-fullstack/blueprint.yaml) | nextjs-fullstack | Full-stack Next.js application with Prisma, PostgreSQL, Tailwind CSS, and AI agent context. |
| [`rest-api`](../src/scaffoldkit/blueprints/rest-api/blueprint.yaml) | backend | REST API project skeleton with layered architecture, docs, and AI context. |
| [`saas-dashboard`](../src/scaffoldkit/blueprints/saas-dashboard/blueprint.yaml) | fullstack | Full-stack SaaS dashboard with monorepo structure, docs, and AI context. |
| [`springboot-backend`](../src/scaffoldkit/blueprints/springboot-backend/blueprint.yaml) | java-spring | Production-ready Spring Boot API backend with docs, architecture patterns, and AI context. |
| [`static-site`](../src/scaffoldkit/blueprints/static-site/blueprint.yaml) | static | Static website or documentation site with framework choice, styling, and deployment config. |
| [`symfony-backend`](../src/scaffoldkit/blueprints/symfony-backend/blueprint.yaml) | php-symfony | Production-ready Symfony API backend with docs, architecture patterns, and AI context. |
| [`symfony-nextjs`](../src/scaffoldkit/blueprints/symfony-nextjs/blueprint.yaml) | fullstack | Production-ready monorepo with Symfony API backend and Next.js frontend. |

Each blueprint's variables (name, type, choices, default and condition) are declared in its `blueprint.yaml`, linked from the table; that file is the reference for `--var` keys. Running `scaffoldkit new <name>` without `--non-interactive` prompts for each variable with its description and choices.

Every blueprint ships an architecture doc and an ADR seed and, unless `ai_context` is false, agent context files (`AI_CONTEXT.md`; `express-api` ships an `.ai/` tree instead). All blueprints except `express-api` also ship ways-of-working notes. A downstream Claude Code or Cursor session has real grounding from the first turn.

## Adding a new blueprint

project-forge and agent-planforge consume these blueprints in production, so changes to blueprint contracts ripple into those consumers.

The fastest path is `scaffoldkit init-blueprint`:

```bash
scaffoldkit init-blueprint my-new-blueprint
```

That creates `my-new-blueprint/` inside the resolved blueprints directory (see [resolution order](cli.md#scaffoldkit-list)) with starter `blueprint.yaml`, `templates/`, and `static/` files. Outside a scaffoldkit checkout, pass `-b <dir>` (or set `SCAFFOLDKIT_BLUEPRINTS_DIR`) so the blueprint lands in a directory you keep, and use the same `-b` with `list` and `new` (see [`scaffoldkit init-blueprint`](cli.md#scaffoldkit-init-blueprint)). From there:

1. Edit `blueprint.yaml` to declare metadata, variables, templates, static files, and directories.
2. Add Jinja2 templates under `templates/`.
3. Drop static files under `static/` and list each one under `static_files` (only listed files are copied, verbatim). The starter's `static/.editorconfig` is not copied until you add an entry for it.
4. `scaffoldkit list` to confirm discovery.
5. `scaffoldkit new my-new-blueprint --dry-run --non-interactive --yes --target ./demo --var project_name=demo` to smoke-test.

If you prefer to start from scratch, just create the folder by hand with the same three children. The blueprint loader picks up any folder in the blueprints directory that contains a valid `blueprint.yaml`.

## Custom blueprint directories

Point ScaffoldKit at a different directory either per-invocation:

```bash
scaffoldkit new --blueprints-dir ./my-blueprints my-custom
scaffoldkit list -b ./my-blueprints
```

or globally via the `SCAFFOLDKIT_BLUEPRINTS_DIR` env var. When you are running from inside a scaffoldkit checkout the loader auto-detects `src/scaffoldkit/blueprints/` so local edits take effect immediately.

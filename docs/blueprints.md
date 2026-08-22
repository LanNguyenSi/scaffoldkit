# Blueprints

A blueprint is a self-contained folder that tells ScaffoldKit how to generate a project: what to ask the user, which files to render, which files to copy as-is, and which directories to create.

## Folder layout

```
blueprints/<name>/
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
    condition: null             # Optional: variable that must be truthy

static_files:
  - source: .gitignore
    target: .gitignore

directories:
  - src
  - docs
```

### Variable types

- `string`: free-form text, optional `default`.
- `boolean`: `true`/`false`. Inputs like `yes`/`no`/`1`/`0` are normalised by the CLI's `--var` parser and by the planforge input path; the interactive prompt and the blueprint loader itself do no boolean coercion.
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

The generator also injects derived flags (`is_python`, `is_typescript`, `is_fastapi`, `is_nextjs_fullstack`, `is_uv`, `is_yaml_config`, etc.) so templates can branch on language/framework/package-manager without re-implementing string compares. See [architecture.md](architecture.md) for the full list.

Any keys under the blueprint's top-level `metadata` map are also merged into the template context verbatim, so blueprint authors can expose extra template variables (for example an `architecture` label) without adding a user-facing prompt.

## Shipped blueprints

ScaffoldKit ships 12 blueprints in `src/scaffoldkit/blueprints/`. `scaffoldkit list` always reflects the current set.

| Name | Stack | Description |
|------|-------|-------------|
| `cli-tool` | cli | Command-line tool project skeleton with docs, tests, and AI context. |
| `django-drf` | python-django | Production-ready Django REST Framework backend with project structure, API guidance, and AI context. |
| `express-api` | express-api | TypeScript REST API with Express, Prisma, PostgreSQL, and AI agent context. |
| `fastapi-backend` | python-fastapi | Production-ready FastAPI backend with layered application structure, API guidance, and AI context. |
| `nextjs-frontend` | frontend | Production-ready Next.js frontend project skeleton with docs, conventions, and AI context. |
| `nextjs-fullstack` | nextjs-fullstack | Full-stack Next.js application with Prisma, PostgreSQL, Tailwind CSS, and AI agent context. |
| `rest-api` | backend | REST API project skeleton with layered architecture, docs, and AI context. |
| `saas-dashboard` | fullstack | Full-stack SaaS dashboard with monorepo structure, docs, and AI context. |
| `springboot-backend` | java-spring | Production-ready Spring Boot API backend with docs, architecture patterns, and AI context. |
| `static-site` | static | Static website or documentation site with framework choice, styling, and deployment config. |
| `symfony-backend` | php-symfony | Production-ready Symfony API backend with docs, architecture patterns, and AI context. |
| `symfony-nextjs` | fullstack | Production-ready monorepo with Symfony API backend and Next.js frontend. |

Every blueprint includes an `AI_CONTEXT.md`, an `architecture.md`, an ADR seed, and ways-of-working notes so a downstream Claude Code or Cursor session has real grounding from the first turn.

## Adding a new blueprint

The fastest path is `scaffoldkit init-blueprint`:

```bash
scaffoldkit init-blueprint my-new-blueprint
```

That creates `my-new-blueprint/` inside the resolved blueprints directory (see [resolution order](cli.md#scaffoldkit-list)) with starter `blueprint.yaml`, `templates/`, and `static/` files. From there:

1. Edit `blueprint.yaml` to declare metadata, variables, templates, static files, and directories.
2. Add Jinja2 templates under `templates/`.
3. Drop static files under `static/` (copied verbatim).
4. `scaffoldkit list` to confirm discovery.
5. `scaffoldkit new my-new-blueprint --dry-run --non-interactive --yes --var project_name=demo` to smoke-test.

If you prefer to start from scratch, just create the folder by hand with the same three children. The blueprint loader picks up any folder in the blueprints directory that contains a valid `blueprint.yaml`.

## Custom blueprint directories

Point ScaffoldKit at a different directory either per-invocation:

```bash
scaffoldkit new --blueprints-dir ./my-blueprints my-custom
scaffoldkit list -b ./my-blueprints
```

or globally via the `SCAFFOLDKIT_BLUEPRINTS_DIR` env var. When you are running from inside a scaffoldkit checkout the loader auto-detects `src/scaffoldkit/blueprints/` so local edits take effect immediately.

# Planforge integration

[agent-planforge](https://github.com/LanNguyenSi/agent-planforge) is a planning tool that turns a project brief into a `scaffoldkit-input.json` export. `scaffoldkit from-planforge` consumes that file and generates a project without re-prompting for variables planforge already decided.

## Usage

```bash
scaffoldkit from-planforge ./scaffoldkit-input.json --target ./my-project
```

Same flags as `scaffoldkit new` except for `--var` / `--non-interactive` / `--yes`: planforge supplies those values. The supported flags are `--target`, `--dry-run`, `--overwrite`, `--no-install`, `--blueprints-dir`.

If the planforge-recommended blueprint isn't installed locally, the resolver walks `blueprintCandidates` in order and falls back to the first match, printing which fallback it picked. If none match, you get the candidate list plus the locally available blueprints in the error output.

## `scaffoldkit-input.json` schema

The export is validated against `PlanforgeExport` (see `src/scaffoldkit/planforge.py`):

```json
{
  "version": "1.0",
  "exportedBy": "agent-planforge",
  "projectName": "Acme Billing API",
  "summary": "Internal billing service for invoices and subscriptions.",
  "blueprint": "fastapi-backend",
  "blueprintCandidates": ["rest-api"],
  "blueprintReason": "Python ecosystem, OpenAPI required.",
  "plannerProfile": "backend-service",
  "architecture": {
    "shape": "layered service with workers",
    "optionId": "layered-v1",
    "phase": "mvp",
    "path": "monolith"
  },
  "stack": {
    "hint": "FastAPI + Postgres + Redis",
    "dataStore": "postgresql",
    "integrations": ["stripe", "sendgrid"]
  },
  "features": ["billing", "invoices", "background jobs"],
  "constraints": ["docker", "openapi"],
  "suggestedVariables": {
    "use_docker": true,
    "use_redis": true,
    "auth_strategy": "jwt"
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `projectName` | yes | Source for `project_name` (slugified) and `display_name`. |
| `blueprint` | yes | Primary blueprint candidate. |
| `version` | no | Free-form. Currently unused. |
| `exportedBy` | no | Free-form. |
| `summary` | no | Drives the inferred `description` and several signal regexes. |
| `blueprintCandidates` | no | Ordered fallbacks if `blueprint` is not installed. |
| `blueprintReason` | no | Surfaced in the error output if no candidate resolves. |
| `plannerProfile` | no | Free-form planner identifier. |
| `architecture.shape` | no | Free-form architecture description, mined for signals. |
| `architecture.optionId` / `phase` / `path` | no | Free-form passthroughs. |
| `stack.hint` | no | Free-form stack description, mined for `language` / `framework` signals. |
| `stack.dataStore` | no | Used for database inference, defaults to `relational`. |
| `stack.integrations` | no | Free-form list of integration tags. |
| `features` | no | Free-form list, mined for queue/notification/realtime signals. |
| `constraints` | no | Free-form list, mined for docker/api-key signals. |
| `suggestedVariables` | no | Direct map onto blueprint variables. Unsupported keys are ignored with a warning. |

Empty `summary`, `features`, `constraints`, or `architecture.shape` print a warning explaining which inference paths fall back to blueprint defaults.

## Variable mapping

`from-planforge` populates blueprint variables in this order:

1. Start with the blueprint's declared defaults.
2. Set `project_name` to a slug of `projectName`. Set `display_name` to `projectName`. Set `description` to `summary` (or `projectName` if blank).
3. Set `ai_context = true` if the blueprint has that variable.
4. Apply every key in `suggestedVariables` that maps to a real blueprint variable. Unsupported keys are listed in a warning.
5. For variables planforge did not set (and the blueprint default is unchanged), apply the inference rules below.
6. Normalise everything through the blueprint's type contract: booleans accept `true`/`yes`/`1`, choices clamp to declared options or fall back to the default.
7. Prune variables whose `if` parent is now falsy.

### Inference rules

The combined text of `projectName`, `summary`, `features`, `constraints`, `architecture.shape`, and `stack.hint` is searched for keywords:

| Variable | Trigger |
|----------|---------|
| `use_docker` | `docker`, `container`, `kubernetes`, `compose`. |
| `language` | `typescript` -> `typescript`, `\bgo\b` -> `go`, `rust` -> `rust`, otherwise `python`. |
| `cli_framework` | Derived from `language`: python -> `typer`, go -> `cobra`, rust -> `clap`, typescript -> `commander`. |
| `distribution` | Compiled languages get `binary`, otherwise `pip-package`. |
| `test_strategy` | `git`/`sync`/`filesystem`/`queue`/`workflow`/`remote` -> `integration-tests`, otherwise `unit-tests`. Blueprint-specific overrides for `fastapi-backend` and `django-drf`. |
| `use_analytics` | `analytics`/`dashboard`/`report`. |
| `use_email` | `email`/`notification`/`invite`. |
| `use_queue` | `background jobs`/`queue`/`workflow`/`notification`. |
| `use_auth` | Forced `false` when `public-only`/`anonymous`/`no auth` appears. |
| `use_openapi` | Default `true`. |
| `db_provider` / `database` | `sqlite`/`mysql`/`mongo` keywords map to the matching choice, default `postgresql`. |
| `framework` | TypeScript hint -> `express`, otherwise `fastapi`. |
| `auth_strategy` | `public-only`/`anonymous` -> `none`, `api key` -> `api-key` (`token` for django-drf), `oauth2` -> `oauth2`, `sso`/`next-auth` (nextjs-fullstack only) -> `next-auth`, otherwise `jwt`. |

Blueprint-specific extras live alongside these rules. See `src/scaffoldkit/planforge.py` for the canonical implementation.

### Generic API fallback

If planforge picks `rest-api` but the brief mentions Django/DRF/serializers, the resolver inserts `django-drf` ahead of `rest-api`. If it mentions FastAPI/Pydantic/uvicorn/Python, it inserts `fastapi-backend`. This keeps planforge from having to know every Python web framework upfront.

## Producing a `scaffoldkit-input.json`

Planforge owns the export contract. From the planforge UI, the "Generate scaffold input" action writes the JSON to your chosen path; from the planforge CLI it lands next to your plan. Once you have the file, point `scaffoldkit from-planforge` at it.

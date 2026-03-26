"""Core generation engine - orchestrates blueprint rendering and file output."""

from __future__ import annotations

from typing import Any

from scaffoldkit.filesystem import copy_file, ensure_directory, write_file
from scaffoldkit.models import Blueprint, GenerationContext, GenerationResult
from scaffoldkit.renderer import create_jinja_env, render_string, render_template
from scaffoldkit.validators import validate_variables


def build_template_context(blueprint: Blueprint, variables: dict[str, Any]) -> dict[str, Any]:
    """Build the full Jinja2 template context from blueprint + user variables."""
    ctx: dict[str, Any] = {}
    ctx.update(variables)
    ctx["blueprint_name"] = blueprint.name
    ctx["blueprint_display_name"] = blueprint.display_name
    ctx["blueprint_stack"] = blueprint.stack
    language = str(variables.get("language", "")).lower()
    config_format = str(variables.get("config_format", "")).lower()
    ctx["is_python"] = language == "python"
    ctx["is_go"] = language == "go"
    ctx["is_rust"] = language == "rust"
    ctx["is_typescript"] = language == "typescript"
    ctx["is_json_config"] = config_format == "json"
    ctx["is_yaml_config"] = config_format == "yaml"
    ctx["is_toml_config"] = config_format == "toml"
    ctx.update(blueprint.metadata)
    return ctx


def generate(context: GenerationContext) -> GenerationResult:
    """Run the full generation pipeline."""
    result = GenerationResult()
    blueprint = context.blueprint
    bp_path = context.blueprint_path

    # 1. Validate
    errors = validate_variables(blueprint, context.variables)
    if errors:
        result.errors.extend(errors)
        return result

    # 2. Build template context
    tpl_context = build_template_context(blueprint, context.variables)

    # 3. Create target directory
    if not context.dry_run:
        ensure_directory(context.target_dir)
    result.directories_created.append(str(context.target_dir))

    # 4. Create explicit directories
    for dir_pattern in blueprint.directories:
        dir_path = context.target_dir / render_string(dir_pattern, tpl_context)
        created = ensure_directory(dir_path) if not context.dry_run else True
        if created:
            result.directories_created.append(str(dir_path.relative_to(context.target_dir)))

    # 5. Render templates
    template_dir = bp_path / "templates"
    if template_dir.is_dir():
        env = create_jinja_env(template_dir)
        for entry in blueprint.templates:
            if entry.condition and not tpl_context.get(entry.condition):
                result.files_skipped.append(entry.target)
                continue

            target_rel = render_string(entry.target, tpl_context)
            target_path = context.target_dir / target_rel

            try:
                content = render_template(env, entry.source, tpl_context)
            except Exception as e:
                result.errors.append(f"Template error '{entry.source}': {e}")
                continue

            if context.dry_run:
                result.files_created.append(target_rel)
            else:
                written = write_file(target_path, content, overwrite=context.overwrite)
                if written:
                    result.files_created.append(target_rel)
                else:
                    result.files_skipped.append(target_rel)

    # 6. Copy static files
    static_dir = bp_path / "static"
    if static_dir.is_dir():
        for entry in blueprint.static_files:
            if entry.condition and not tpl_context.get(entry.condition):
                result.files_skipped.append(entry.target)
                continue

            target_rel = render_string(entry.target, tpl_context)
            source_path = static_dir / entry.source
            target_path = context.target_dir / target_rel

            if not source_path.exists():
                result.errors.append(f"Static file not found: {entry.source}")
                continue

            if context.dry_run:
                result.files_created.append(target_rel)
            else:
                copied = copy_file(source_path, target_path, overwrite=context.overwrite)
                if copied:
                    result.files_created.append(target_rel)
                else:
                    result.files_skipped.append(target_rel)

    return result

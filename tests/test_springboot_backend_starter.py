"""Regression tests for the springboot-backend runnable starter."""

from pathlib import Path

import yaml

from scaffoldkit.blueprint_loader import load_blueprint
from scaffoldkit.generator import generate
from scaffoldkit.models import GenerationContext

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "src" / "scaffoldkit" / "blueprints"

# Mirrors the blueprint defaults (build_tool=maven, api_style=spring-mvc, use_auth=true).
_DEFAULTS = {
    "project_name": "verify-springboot-backend",
    "display_name": "Verify springboot-backend",
    "description": "A Spring Boot API backend",
    "base_package": "com.example.app",
    "java_version": "21",
    "spring_boot_version": "3.4",
    "build_tool": "maven",
    "api_style": "spring-mvc",
    "database": "postgresql",
    "use_ddd": False,
    "use_auth": True,
    "auth_method": "jwt",
    "use_docker": True,
    "use_ci": True,
    "use_kafka": False,
    "use_redis": False,
    "test_strategy": "junit-and-testcontainers",
    "ai_context": True,
}

_PKG_DIR = "src/main/java/com/example/app"
_TEST_PKG_DIR = "src/test/java/com/example/app"


def _generate(tmp_path: Path, variables: dict) -> Path:
    bp_path = BLUEPRINTS_DIR / "springboot-backend"
    bp = load_blueprint(bp_path)
    output = tmp_path / "output"
    ctx = GenerationContext(
        blueprint=bp,
        blueprint_path=bp_path,
        variables=variables,
        target_dir=output,
    )
    result = generate(ctx)
    assert result.success, f"Generation failed: {result.errors}"
    return output


def _assert_nonempty(path: Path) -> str:
    assert path.exists(), f"expected file missing: {path}"
    text = path.read_text()
    assert text.strip(), f"file is empty: {path}"
    return text


class TestSpringbootBackendStarter:
    def test_vertical_slice_files_exist_and_are_nonempty(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        controller = _assert_nonempty(output / _PKG_DIR / "web" / "HealthController.java")
        dto = _assert_nonempty(output / _PKG_DIR / "web" / "dto" / "HealthResponse.java")
        service = _assert_nonempty(output / _PKG_DIR / "service" / "HealthService.java")
        entity = _assert_nonempty(output / _PKG_DIR / "domain" / "Widget.java")
        repository = _assert_nonempty(output / _PKG_DIR / "repository" / "WidgetRepository.java")
        smoke = _assert_nonempty(output / _TEST_PKG_DIR / "HealthControllerSmokeTest.java")

        # Controller wires GET /health to the service and returns the DTO.
        assert '@GetMapping("/health")' in controller
        assert "HealthService" in controller
        # DTO is a real record with the expected fields.
        assert "record HealthResponse" in dto
        # Service touches the repository so the slice is genuinely wired.
        assert "WidgetRepository" in service
        # Entity is a mapped JPA entity, repository is Spring Data.
        assert "@Entity" in entity
        assert "JpaRepository<Widget, Long>" in repository
        # Smoke test boots the app and hits /health.
        assert "@SpringBootTest" in smoke
        assert "/health" in smoke

    def test_rendered_application_yml_is_valid_yaml(self, tmp_path: Path):
        # Regression: the {%- -%} whitespace control mangled the datasource
        # indentation, producing YAML that failed to parse.
        output = _generate(tmp_path, _DEFAULTS)

        main_yml = output / "src" / "main" / "resources" / "application.yml"
        test_yml = output / "src" / "test" / "resources" / "application.yml"

        main_data = yaml.safe_load(_assert_nonempty(main_yml))
        assert main_data["spring"]["application"]["name"] == "verify-springboot-backend"
        assert "jdbc:postgresql" in main_data["spring"]["datasource"]["url"]
        assert main_data["spring"]["datasource"]["driver-class-name"] == "org.postgresql.Driver"

        test_data = yaml.safe_load(_assert_nonempty(test_yml))
        assert "jdbc:h2:mem" in test_data["spring"]["datasource"]["url"]

    def test_java_sources_have_balanced_braces_and_matching_package(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)

        for java_file in sorted(output.rglob("*.java")):
            text = java_file.read_text()
            assert text.count("{") == text.count("}"), f"unbalanced braces: {java_file}"
            assert text.count("(") == text.count(")"), f"unbalanced parens: {java_file}"

            first_pkg_line = next(line for line in text.splitlines() if line.startswith("package "))
            declared = first_pkg_line[len("package ") :].rstrip(";").strip()

            parts = java_file.relative_to(output).parts
            java_idx = parts.index("java")
            expected = ".".join(parts[java_idx + 1 : -1])
            assert declared == expected, (
                f"package mismatch in {java_file}: declared {declared} expected {expected}"
            )

    def test_security_config_permits_health_when_auth_enabled(self, tmp_path: Path):
        output = _generate(tmp_path, _DEFAULTS)
        security = output / _PKG_DIR / "security" / "SecurityConfig.java"
        text = _assert_nonempty(security)
        assert "SecurityFilterChain" in text
        assert '"/health"' in text
        assert "permitAll" in text

    def test_no_security_config_when_auth_disabled(self, tmp_path: Path):
        output = _generate(tmp_path, {**_DEFAULTS, "use_auth": False})
        security = output / _PKG_DIR / "security" / "SecurityConfig.java"
        assert not security.exists()

    def test_maven_wrapper_generated_for_maven_only(self, tmp_path: Path):
        maven_out = _generate(tmp_path / "maven", _DEFAULTS)
        assert (maven_out / "mvnw").exists()
        assert (maven_out / "mvnw.cmd").exists()
        props = maven_out / ".mvn" / "wrapper" / "maven-wrapper.properties"
        props_text = _assert_nonempty(props)
        assert "distributionUrl=" in props_text

        gradle_out = _generate(tmp_path / "gradle", {**_DEFAULTS, "build_tool": "gradle"})
        assert not (gradle_out / "mvnw").exists()
        assert not (gradle_out / ".mvn" / "wrapper" / "maven-wrapper.properties").exists()

    def test_webflux_emits_reactive_slice(self, tmp_path: Path):
        output = _generate(tmp_path, {**_DEFAULTS, "api_style": "webflux"})

        # Single smoke test target, rendered from the reactive variant.
        smoke = _assert_nonempty(output / _TEST_PKG_DIR / "HealthControllerSmokeTest.java")
        assert "WebTestClient" in smoke

        security = _assert_nonempty(output / _PKG_DIR / "security" / "SecurityConfig.java")
        assert "EnableWebFluxSecurity" in security
        assert "SecurityWebFilterChain" in security

    def test_pom_renders_well_formed_xml(self, tmp_path: Path):
        import xml.dom.minidom as minidom

        output = _generate(tmp_path, _DEFAULTS)
        pom_text = _assert_nonempty(output / "pom.xml")
        minidom.parseString(pom_text)
        assert "<artifactId>h2</artifactId>" in pom_text
        assert "spring-security-test" in pom_text

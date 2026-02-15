"""
Template Content Validation Tests (Level 2)

Tests that verify generated files contain the correct content
based on configuration options. Uses YAML parsing to validate
structure and content.
"""

import pytest
import yaml

from conftest import GeneratedProject

# =============================================================================
# YAML Parsing Helper
# =============================================================================


def parse_yaml(content: str) -> dict:
    """Parse YAML content, handling multi-document files."""
    # For multi-document YAML, get all documents
    docs = list(yaml.safe_load_all(content))
    if len(docs) == 1:
        return docs[0]
    return docs


def load_yaml_file(project: GeneratedProject, path: str) -> dict:
    """Load and parse a YAML file from the generated project."""
    content = project.get_file_content(path)
    return parse_yaml(content)


# =============================================================================
# YAML Syntax Validation Tests
# =============================================================================


class TestYamlSyntax:
    """Test that all generated YAML files are syntactically valid."""

    def test_databricks_yml_valid_yaml(self, generated_project: GeneratedProject):
        """databricks.yml should be valid YAML."""
        content = generated_project.get_file_content("databricks.yml")
        try:
            result = parse_yaml(content)
            assert result is not None
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in databricks.yml: {e}")

    def test_variables_yml_valid_yaml(self, generated_project: GeneratedProject):
        """variables.yml should be valid YAML."""
        content = generated_project.get_file_content("variables.yml")
        try:
            result = parse_yaml(content)
            assert result is not None
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in variables.yml: {e}")

    def test_schemas_yml_valid_yaml(self, generated_project: GeneratedProject):
        """schemas.yml should be valid YAML."""
        content = generated_project.get_file_content("resources/schemas.yml")
        try:
            result = parse_yaml(content)
            assert result is not None
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in schemas.yml: {e}")


# =============================================================================
# Environment Target Tests
# =============================================================================


class TestEnvironmentTargets:
    """Test that correct environment targets are generated based on configuration."""

    def test_user_target_always_exists(self, generated_project: GeneratedProject):
        """User target should always exist."""
        data = load_yaml_file(generated_project, "databricks.yml")
        assert "targets" in data
        assert "user" in data["targets"], (
            f"'user' target missing for config: {generated_project.config_name}"
        )

    def test_stage_target_always_exists(self, generated_project: GeneratedProject):
        """Stage target should always exist (both minimal and full modes)."""
        data = load_yaml_file(generated_project, "databricks.yml")
        assert "stage" in data["targets"], (
            f"'stage' target missing for config: {generated_project.config_name}"
        )

    def test_prod_target_only_in_full_mode(self, generated_project: GeneratedProject):
        """Prod target should only exist in full mode."""
        data = load_yaml_file(generated_project, "databricks.yml")

        if generated_project.is_full:
            assert "prod" in data["targets"], (
                f"'prod' target missing in full mode for config: {generated_project.config_name}"
            )
        else:
            assert "prod" not in data["targets"], (
                f"'prod' target should not exist in minimal mode for config: {generated_project.config_name}"
            )

    def test_dev_target_conditional(self, generated_project: GeneratedProject):
        """Dev target should only exist when include_dev_environment=yes."""
        data = load_yaml_file(generated_project, "databricks.yml")

        if generated_project.has_dev_environment:
            assert "dev" in data["targets"], (
                f"'dev' target missing when include_dev_environment=yes for config: {generated_project.config_name}"
            )
        else:
            assert "dev" not in data["targets"], (
                f"'dev' target should not exist when include_dev_environment=no for config: {generated_project.config_name}"
            )


# =============================================================================
# Unity Catalog Configuration Tests
# =============================================================================


class TestUnityCatalogConfig:
    """Test Unity Catalog configuration based on user input."""

    def test_catalog_suffix_in_variables(self, generated_project: GeneratedProject):
        """Catalog suffix should appear in variables.yml."""
        content = generated_project.get_file_content("variables.yml")
        expected_suffix = generated_project.config.get("uc_catalog_suffix", "my_domain")
        assert expected_suffix in content, (
            f"Catalog suffix '{expected_suffix}' not found in variables.yml"
        )

    def test_user_target_uses_dev_catalog(self, generated_project: GeneratedProject):
        """User target should share the dev catalog (not a per-user catalog)."""
        data = load_yaml_file(generated_project, "databricks.yml")
        user_vars = data["targets"]["user"].get("variables", {})
        catalog_name = user_vars.get("catalog_name", "")
        assert catalog_name.startswith("dev_"), (
            f"User target catalog should start with 'dev_', got: {catalog_name}"
        )

    def test_user_target_has_schema_prefix(self, generated_project: GeneratedProject):
        """User target should have schema_prefix with current_user for isolation."""
        data = load_yaml_file(generated_project, "databricks.yml")
        user_vars = data["targets"]["user"].get("variables", {})
        schema_prefix = user_vars.get("schema_prefix", "")
        assert "current_user.short_name" in schema_prefix, (
            f"User target schema_prefix should reference current_user.short_name, got: {schema_prefix}"
        )

    def test_schema_names_include_prefix_variable(self, generated_project: GeneratedProject):
        """Schema definitions should use ${var.schema_prefix} in name field."""
        content = generated_project.get_file_content("resources/schemas.yml")
        assert "${var.schema_prefix}" in content, (
            "Schema names should include ${var.schema_prefix} for per-user isolation"
        )


# =============================================================================
# Service Principal Configuration Tests
# =============================================================================


class TestServicePrincipalConfig:
    """Test service principal configuration based on options."""

    def test_sp_placeholder_when_not_configured(self, generated_project: GeneratedProject):
        """SP_PLACEHOLDER should appear when configure_sp_now=no."""
        if not generated_project.has_sp_configured:
            content = generated_project.get_file_content("variables.yml")
            assert "SP_PLACEHOLDER" in content, (
                f"SP_PLACEHOLDER not found when configure_sp_now=no for config: {generated_project.config_name}"
            )

    def test_sp_values_when_configured(self, full_with_sp_project: GeneratedProject):
        """Actual SP values should appear when configure_sp_now=yes."""
        content = full_with_sp_project.get_file_content("variables.yml")
        # Check that the configured SP values are present
        assert "11111111-1111-1111-1111-111111111111" in content, (
            "Dev SP value not found when configure_sp_now=yes"
        )
        assert "22222222-2222-2222-2222-222222222222" in content, (
            "Stage SP value not found when configure_sp_now=yes"
        )
        assert "33333333-3333-3333-3333-333333333333" in content, (
            "Prod SP value not found when configure_sp_now=yes"
        )

    def test_dev_sp_only_when_dev_included(self, generated_project: GeneratedProject):
        """dev_service_principal variable should only exist when dev environment included."""
        content = generated_project.get_file_content("variables.yml")

        if generated_project.has_dev_environment:
            assert "dev_service_principal:" in content, (
                "dev_service_principal missing when dev environment included"
            )
        else:
            assert "dev_service_principal:" not in content, (
                "dev_service_principal should not exist when dev environment not included"
            )

    def test_prod_sp_only_in_full_mode(self, generated_project: GeneratedProject):
        """prod_service_principal variable should only exist in full mode."""
        content = generated_project.get_file_content("variables.yml")

        if generated_project.is_full:
            assert "prod_service_principal:" in content, (
                "prod_service_principal missing in full mode"
            )
        else:
            assert "prod_service_principal:" not in content, (
                "prod_service_principal should not exist in minimal mode"
            )


# =============================================================================
# Permissions/RBAC Tests
# =============================================================================


class TestPermissionsConfig:
    """Test permissions configuration based on include_permissions option."""

    def test_permissions_blocks_when_enabled(self, generated_project: GeneratedProject):
        """Permissions blocks should exist when include_permissions=yes."""
        content = generated_project.get_file_content("databricks.yml")

        if generated_project.has_permissions:
            assert "permissions:" in content, (
                "permissions: block missing when include_permissions=yes"
            )
        else:
            assert "permissions:" not in content, (
                "permissions: block should not exist when include_permissions=no"
            )

    def test_group_variables_when_permissions_enabled(self, generated_project: GeneratedProject):
        """Group variables should exist when include_permissions=yes."""
        content = generated_project.get_file_content("variables.yml")

        if generated_project.has_permissions:
            assert "developers_group:" in content, (
                "developers_group variable missing when permissions enabled"
            )
            assert "qa_team_group:" in content, (
                "qa_team_group variable missing when permissions enabled"
            )
            assert "analytics_team_group:" in content, (
                "analytics_team_group variable missing when permissions enabled"
            )
        else:
            assert "developers_group:" not in content, (
                "developers_group should not exist when permissions disabled"
            )

    def test_operations_group_only_in_full_mode(self, generated_project: GeneratedProject):
        """operations_group should only exist in full mode with permissions."""
        content = generated_project.get_file_content("variables.yml")

        if generated_project.has_permissions and generated_project.is_full:
            assert "operations_group:" in content, (
                "operations_group missing in full mode with permissions"
            )
        elif generated_project.has_permissions and generated_project.is_minimal:
            assert "operations_group:" not in content, (
                "operations_group should not exist in minimal mode"
            )


# =============================================================================
# Compute Type Tests
# =============================================================================


class TestComputeConfig:
    """Test compute configuration based on compute_type option."""

    def test_serverless_config(self, generated_project: GeneratedProject):
        """Serverless config should be present when compute_type includes serverless."""
        if generated_project.is_serverless or generated_project.is_both_compute:
            # Check pipeline file for serverless
            project_name = generated_project.project_name
            content = generated_project.get_file_content(
                f"resources/{project_name}_pipeline.pipeline.yml"
            )
            assert "serverless:" in content, "serverless config missing for serverless compute type"

    def test_classic_node_type(self, generated_project: GeneratedProject):
        """Node type should appear for classic compute."""
        if generated_project.is_classic or generated_project.is_both_compute:
            cloud = generated_project.config.get("cloud_provider", "azure")
            expected_node_types = {
                "azure": "Standard_DS3_v2",
                "aws": "i3.xlarge",
                "gcp": "n1-standard-4",
            }
            # Node type might be in job files - check ingestion job
            project_name = generated_project.project_name
            content = generated_project.get_file_content(
                f"resources/{project_name}_ingestion.job.yml"
            )
            # For classic, we expect node_type_id somewhere
            if generated_project.is_classic:
                assert "node_type_id:" in content or expected_node_types[cloud] in content, (
                    "Node type configuration missing for classic compute"
                )


# =============================================================================
# Documentation Content Tests
# =============================================================================


class TestDocumentationContent:
    """Test that documentation reflects the configuration."""

    def test_readme_mentions_environments(self, generated_project: GeneratedProject):
        """README should mention the configured environments."""
        content = generated_project.get_file_content("README.md")

        # Always should have user and stage
        assert "user" in content.lower(), "README should mention user environment"
        assert "stage" in content.lower(), "README should mention stage environment"

        if generated_project.is_full:
            assert "prod" in content.lower(), "README should mention prod in full mode"

    def test_quickstart_deployment_steps(self, generated_project: GeneratedProject):
        """QUICKSTART should have appropriate deployment steps."""
        content = generated_project.get_file_content("QUICKSTART.md")

        # Should always have stage deployment
        assert "stage" in content, "QUICKSTART should mention stage deployment"

        if generated_project.is_full:
            assert "prod" in content, "QUICKSTART should mention prod deployment in full mode"

    def test_groups_doc_matches_config(self, generated_project: GeneratedProject):
        """SETUP_GROUPS.md should list correct groups for configuration."""
        content = generated_project.get_file_content("docs/SETUP_GROUPS.md")

        # Core groups should always be mentioned when permissions enabled
        if generated_project.has_permissions:
            assert "developers" in content
            assert "qa_team" in content
            assert "analytics_team" in content

            if generated_project.is_full:
                assert "operations_team" in content, (
                    "operations_team should be in SETUP_GROUPS.md for full mode"
                )


# =============================================================================
# Workspace Configuration Tests
# =============================================================================


class TestWorkspaceConfig:
    """Test workspace configuration based on workspace_setup option."""

    def test_user_target_never_uses_variable_host(self, generated_project: GeneratedProject):
        """User target should never use a variable-based workspace host."""
        data = load_yaml_file(generated_project, "databricks.yml")
        user_host = data["targets"]["user"]["workspace"]["host"]
        assert "${var." not in str(user_host), (
            f"User target should use current workspace, not a variable. "
            f"Got: {user_host} for config: {generated_project.config_name}"
        )

    def test_multi_workspace_stage_uses_variable(self, generated_project: GeneratedProject):
        """Stage target should use PLACEHOLDER in multi_workspace mode."""
        if not generated_project.is_multi_workspace:
            pytest.skip("Single workspace mode")
        data = load_yaml_file(generated_project, "databricks.yml")
        stage_host = data["targets"]["stage"]["workspace"]["host"]
        assert "WORKSPACE_HOST_PLACEHOLDER_STAGE" in stage_host, (
            f"Stage host should contain WORKSPACE_HOST_PLACEHOLDER_STAGE, got: {stage_host}"
        )

    def test_multi_workspace_prod_uses_variable(self, generated_project: GeneratedProject):
        """Prod target should use PLACEHOLDER in multi_workspace mode."""
        if not generated_project.is_multi_workspace or not generated_project.is_full:
            pytest.skip("Not multi_workspace full mode")
        data = load_yaml_file(generated_project, "databricks.yml")
        prod_host = data["targets"]["prod"]["workspace"]["host"]
        assert "WORKSPACE_HOST_PLACEHOLDER_PROD" in prod_host, (
            f"Prod host should contain WORKSPACE_HOST_PLACEHOLDER_PROD, got: {prod_host}"
        )

    def test_multi_workspace_dev_uses_variable(self, generated_project: GeneratedProject):
        """Dev target should use PLACEHOLDER in multi_workspace mode."""
        if not generated_project.is_multi_workspace or not generated_project.has_dev_environment:
            pytest.skip("Not multi_workspace with dev")
        data = load_yaml_file(generated_project, "databricks.yml")
        dev_host = data["targets"]["dev"]["workspace"]["host"]
        assert "WORKSPACE_HOST_PLACEHOLDER_DEV" in dev_host, (
            f"Dev host should contain WORKSPACE_HOST_PLACEHOLDER_DEV, got: {dev_host}"
        )

    def test_single_workspace_no_host_variables(self, generated_project: GeneratedProject):
        """Single workspace mode should not have workspace host variables."""
        if not generated_project.is_single_workspace:
            pytest.skip("Multi workspace mode")
        content = generated_project.get_file_content("variables.yml")
        assert "workspace_host:" not in content, (
            "Single workspace should not have workspace_host variables in variables.yml"
        )
        assert "WORKSPACE_HOST_PLACEHOLDER" not in content, (
            "Single workspace should not have WORKSPACE_HOST_PLACEHOLDER in variables.yml"
        )

    def test_multi_workspace_has_stage_host_variable(self, generated_project: GeneratedProject):
        """Multi workspace mode should have stage workspace host placeholder in databricks.yml."""
        if not generated_project.is_multi_workspace:
            pytest.skip("Single workspace mode")
        content = generated_project.get_file_content("databricks.yml")
        assert "WORKSPACE_HOST_PLACEHOLDER_STAGE" in content, (
            "Multi workspace should have WORKSPACE_HOST_PLACEHOLDER_STAGE in databricks.yml"
        )

    def test_multi_workspace_prod_variable_only_in_full(self, generated_project: GeneratedProject):
        """Prod workspace host placeholder should only exist in full mode."""
        if not generated_project.is_multi_workspace:
            pytest.skip("Single workspace mode")
        content = generated_project.get_file_content("databricks.yml")
        if generated_project.is_full:
            assert "WORKSPACE_HOST_PLACEHOLDER_PROD" in content, (
                "Full mode multi_workspace should have WORKSPACE_HOST_PLACEHOLDER_PROD in databricks.yml"
            )
        else:
            assert "WORKSPACE_HOST_PLACEHOLDER_PROD" not in content, (
                "Minimal mode multi_workspace should not have WORKSPACE_HOST_PLACEHOLDER_PROD in databricks.yml"
            )

    def test_workspace_setup_in_bundle_config(self, generated_project: GeneratedProject):
        """bundle_init_config.json should preserve workspace_setup value."""
        content = generated_project.get_file_content("bundle_init_config.json")
        workspace_setup = generated_project.config.get("workspace_setup", "single_workspace")
        assert f'"workspace_setup": "{workspace_setup}"' in content, (
            f"workspace_setup '{workspace_setup}' not found in bundle_init_config.json"
        )


# =============================================================================
# Cross-File Consistency Tests
# =============================================================================


class TestCrossFileConsistency:
    """Test that configuration is consistent across generated files."""

    def test_project_name_consistent(self, generated_project: GeneratedProject):
        """Project name should be consistent across files."""
        project_name = generated_project.project_name

        # Check databricks.yml
        db_content = generated_project.get_file_content("databricks.yml")
        assert f"name: {project_name}" in db_content, (
            "Project name not in databricks.yml bundle name"
        )

        # Check README
        readme_content = generated_project.get_file_content("README.md")
        assert project_name in readme_content, "Project name not in README.md"

    def test_catalog_suffix_consistent(self, generated_project: GeneratedProject):
        """Catalog suffix should be consistent across files."""
        suffix = generated_project.config.get("uc_catalog_suffix", "my_domain")

        # Check variables.yml
        vars_content = generated_project.get_file_content("variables.yml")
        assert suffix in vars_content, f"Catalog suffix '{suffix}' not in variables.yml"

        # Check databricks.yml
        db_content = generated_project.get_file_content("databricks.yml")
        assert suffix in db_content, f"Catalog suffix '{suffix}' not in databricks.yml"

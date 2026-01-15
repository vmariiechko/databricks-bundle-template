"""
CI/CD Template Generation Tests

Tests that verify CI/CD pipeline templates are correctly generated
based on configuration options.
"""

import pytest
import yaml

from conftest import GeneratedProject

# =============================================================================
# Azure DevOps CI/CD Tests
# =============================================================================


class TestAzureDevOpsPipelineGeneration:
    """Test Azure DevOps pipeline files are generated correctly."""

    def test_ado_pipeline_generated_when_enabled(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should be generated when cicd_platform=azure_devops."""
        if generated_project.has_cicd and generated_project.is_azure_devops:
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            assert generated_project.file_exists(pipeline_path), (
                f"Azure DevOps pipeline not found at {pipeline_path} "
                f"for config: {generated_project.config_name}"
            )

    def test_ado_pipeline_empty_when_disabled(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should be empty when cicd is disabled."""
        if not generated_project.has_cicd:
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            if generated_project.file_exists(pipeline_path):
                content = generated_project.get_file_content(pipeline_path).strip()
                assert content == "", (
                    f"Azure DevOps pipeline should be empty when CI/CD is disabled "
                    f"for config: {generated_project.config_name}, but got content: {content[:100]}"
                )

    def test_ado_pipeline_empty_for_other_platforms(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should be empty for non-ADO platforms."""
        if generated_project.has_cicd and not generated_project.is_azure_devops:
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            if generated_project.file_exists(pipeline_path):
                content = generated_project.get_file_content(pipeline_path).strip()
                assert content == "", (
                    f"Azure DevOps pipeline should be empty for platform {generated_project.cicd_platform} "
                    f"for config: {generated_project.config_name}"
                )


class TestAzureDevOpsPipelineContent:
    """Test Azure DevOps pipeline content is correct."""

    def test_ado_pipeline_valid_yaml(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should be valid YAML."""
        if generated_project.has_cicd and generated_project.is_azure_devops:
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            # Should parse without errors
            try:
                parsed = yaml.safe_load(content)
                assert parsed is not None, "Pipeline YAML is empty"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in pipeline: {e}")

    def test_ado_pipeline_cli_version_not_hardcoded(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should use templated CLI version, not hardcoded."""
        if generated_project.has_cicd and generated_project.is_azure_devops:
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            # CLI version should be present (from helper template)
            assert "setup-cli/v0." in content, "CLI version reference not found in pipeline"
            # All CLI installs should use same version pattern
            import re

            cli_versions = re.findall(r"setup-cli/(v[\d.]+)/", content)
            assert len(set(cli_versions)) == 1, f"Multiple CLI versions found: {set(cli_versions)}"

    def test_ado_pipeline_validate_prod_has_condition(self, generated_project: GeneratedProject):
        """ValidateProd job should have explicit condition to only run on success."""
        if (
            generated_project.has_cicd
            and generated_project.is_azure_devops
            and generated_project.is_full
        ):
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            # ValidateProd should have both dependsOn and condition: succeeded()
            assert "dependsOn: ValidateAndTest" in content, (
                "ValidateProd should depend on ValidateAndTest"
            )
            assert "condition: succeeded()" in content, (
                "ValidateProd should have condition: succeeded()"
            )

    def test_ado_pipeline_has_required_stages(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should have BundleCI and StagingBundleCD stages."""
        if generated_project.has_cicd and generated_project.is_azure_devops:
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            # Check for required stages
            assert "stage: BundleCI" in content, "BundleCI stage not found in pipeline"
            assert "stage: StagingBundleCD" in content, (
                "StagingBundleCD stage not found in pipeline"
            )

    def test_ado_pipeline_has_prod_stage_for_full_mode(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should have ProdBundleCD stage for full environment setup."""
        if (
            generated_project.has_cicd
            and generated_project.is_azure_devops
            and generated_project.is_full
        ):
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            assert "stage: ProdBundleCD" in content, (
                "ProdBundleCD stage not found in pipeline for full environment setup"
            )

    def test_ado_pipeline_no_prod_stage_for_minimal_mode(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should NOT have ProdBundleCD stage for minimal environment setup."""
        if (
            generated_project.has_cicd
            and generated_project.is_azure_devops
            and generated_project.is_minimal
        ):
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            assert "stage: ProdBundleCD" not in content, (
                "ProdBundleCD stage should not exist in pipeline for minimal environment setup"
            )

    def test_ado_pipeline_uses_correct_branches(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should reference correct branch names."""
        if generated_project.has_cicd and generated_project.is_azure_devops:
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            default_branch = generated_project.default_branch
            assert default_branch in content, (
                f"Default branch '{default_branch}' not found in pipeline"
            )

            if generated_project.is_full:
                release_branch = generated_project.release_branch
                assert release_branch in content, (
                    f"Release branch '{release_branch}' not found in pipeline for full mode"
                )

    def test_ado_pipeline_uses_correct_auth_for_azure(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should use ARM_* variables for Azure cloud."""
        if (
            generated_project.has_cicd
            and generated_project.is_azure_devops
            and generated_project.cloud_provider == "azure"
        ):
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            assert "ARM_TENANT_ID" in content, "ARM_TENANT_ID not found for Azure cloud"
            assert "ARM_CLIENT_ID" in content, "ARM_CLIENT_ID not found for Azure cloud"
            assert "ARM_CLIENT_SECRET" in content, "ARM_CLIENT_SECRET not found for Azure cloud"

    def test_ado_pipeline_uses_correct_auth_for_aws(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should use OAuth credentials for AWS cloud."""
        if (
            generated_project.has_cicd
            and generated_project.is_azure_devops
            and generated_project.cloud_provider == "aws"
        ):
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            # OAuth M2M credentials for AWS/GCP
            assert "DATABRICKS_HOST" in content, "DATABRICKS_HOST not found for AWS cloud"
            assert "DATABRICKS_CLIENT_ID" in content, "DATABRICKS_CLIENT_ID not found for AWS cloud"
            assert "DATABRICKS_CLIENT_SECRET" in content, (
                "DATABRICKS_CLIENT_SECRET not found for AWS cloud"
            )
            # Should NOT have ARM_* variables for AWS
            assert "ARM_TENANT_ID:" not in content, (
                "ARM_TENANT_ID should not be in pipeline for AWS"
            )

    def test_ado_pipeline_includes_unit_tests(self, generated_project: GeneratedProject):
        """Azure DevOps pipeline should include unit test step."""
        if generated_project.has_cicd and generated_project.is_azure_devops:
            project_name = generated_project.project_name
            pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(pipeline_path)

            assert "pytest" in content.lower(), "pytest not found in pipeline"
            assert "Run unit tests" in content, "Unit test step not found in pipeline"


# =============================================================================
# CI/CD Documentation Tests
# =============================================================================


class TestCICDDocumentation:
    """Test CI/CD documentation is generated correctly."""

    def test_cicd_setup_doc_generated_when_enabled(self, generated_project: GeneratedProject):
        """CI_CD_SETUP.md should be generated when CI/CD is enabled."""
        if generated_project.has_cicd:
            assert generated_project.file_exists("docs/CI_CD_SETUP.md"), (
                f"docs/CI_CD_SETUP.md not found when CI/CD is enabled "
                f"for config: {generated_project.config_name}"
            )

    def test_cicd_setup_doc_generated_when_disabled(self, generated_project: GeneratedProject):
        """CI_CD_SETUP.md should still exist (with minimal content) when CI/CD is disabled."""
        # The doc is always generated, just with different content
        assert generated_project.file_exists("docs/CI_CD_SETUP.md"), (
            f"docs/CI_CD_SETUP.md not found for config: {generated_project.config_name}"
        )

    def test_cicd_setup_doc_references_correct_platform(self, generated_project: GeneratedProject):
        """CI_CD_SETUP.md should reference the correct CI/CD platform."""
        if generated_project.has_cicd:
            content = generated_project.get_file_content("docs/CI_CD_SETUP.md")
            platform = generated_project.cicd_platform

            if platform == "azure_devops":
                assert "Azure DevOps" in content, "Azure DevOps not mentioned in CI_CD_SETUP.md"
            elif platform == "github_actions":
                assert "GitHub Actions" in content, "GitHub Actions not mentioned in CI_CD_SETUP.md"
            elif platform == "gitlab":
                assert "GitLab" in content, "GitLab not mentioned in CI_CD_SETUP.md"

    def test_cicd_setup_doc_has_unity_catalog_section(self, generated_project: GeneratedProject):
        """CI_CD_SETUP.md should have Unity Catalog prerequisites section."""
        if generated_project.has_cicd:
            content = generated_project.get_file_content("docs/CI_CD_SETUP.md")
            assert "Unity Catalog Prerequisites" in content, (
                "Unity Catalog Prerequisites section not found in CI_CD_SETUP.md"
            )
            assert "CREATE CATALOG" in content, "Catalog creation SQL not found in CI_CD_SETUP.md"
            assert "GRANT" in content, "Permission grants not found in CI_CD_SETUP.md"

    def test_cicd_setup_doc_has_variable_mapping_table(self, generated_project: GeneratedProject):
        """CI_CD_SETUP.md should have clear variable mapping table for ADO."""
        if generated_project.has_cicd and generated_project.is_azure_devops:
            content = generated_project.get_file_content("docs/CI_CD_SETUP.md")
            assert "Variable Name" in content, "Variable mapping table header not found"
            assert "Value Source" in content, "Value source column not found in variable table"
            assert "Secret?" in content, "Secret column not found in variable table"

    def test_cicd_setup_doc_has_working_directory_guidance(
        self, generated_project: GeneratedProject
    ):
        """CI_CD_SETUP.md should have workingDirectory guidance for subdirectory scenarios."""
        if generated_project.has_cicd:
            content = generated_project.get_file_content("docs/CI_CD_SETUP.md")
            assert "workingDirectory" in content, (
                "workingDirectory guidance not found in CI_CD_SETUP.md"
            )
            assert "subdirectory" in content.lower(), (
                "Subdirectory guidance not found in CI_CD_SETUP.md"
            )

    def test_cicd_setup_doc_has_git_flow_section(self, generated_project: GeneratedProject):
        """CI_CD_SETUP.md should have Git branching strategy section."""
        if generated_project.has_cicd:
            content = generated_project.get_file_content("docs/CI_CD_SETUP.md")
            assert "Git Branching Strategy" in content, "Git Branching Strategy section not found"
            assert "Workflow Steps" in content, "Workflow Steps section not found"


# =============================================================================
# Test Structure Tests
# =============================================================================


class TestTestStructure:
    """Test that test structure is generated correctly."""

    def test_tests_directory_exists(self, generated_project: GeneratedProject):
        """tests/ directory should always be generated."""
        assert generated_project.dir_exists("tests"), (
            f"tests/ directory not found for config: {generated_project.config_name}"
        )

    def test_tests_init_exists(self, generated_project: GeneratedProject):
        """tests/__init__.py should be generated."""
        assert generated_project.file_exists("tests/__init__.py"), (
            f"tests/__init__.py not found for config: {generated_project.config_name}"
        )

    def test_placeholder_test_exists(self, generated_project: GeneratedProject):
        """tests/test_placeholder.py should be generated."""
        assert generated_project.file_exists("tests/test_placeholder.py"), (
            f"tests/test_placeholder.py not found for config: {generated_project.config_name}"
        )

    def test_requirements_dev_exists(self, generated_project: GeneratedProject):
        """requirements_dev.txt should be generated."""
        assert generated_project.file_exists("requirements_dev.txt"), (
            f"requirements_dev.txt not found for config: {generated_project.config_name}"
        )

    def test_requirements_dev_contains_pytest(self, generated_project: GeneratedProject):
        """requirements_dev.txt should contain pytest."""
        content = generated_project.get_file_content("requirements_dev.txt")
        assert "pytest" in content, "pytest not found in requirements_dev.txt"


# =============================================================================
# README CI/CD Section Tests
# =============================================================================


class TestReadmeCICDSection:
    """Test that README includes CI/CD information when enabled."""

    def test_readme_mentions_cicd_when_enabled(self, generated_project: GeneratedProject):
        """README.md should mention CI/CD when it's enabled."""
        if generated_project.has_cicd:
            content = generated_project.get_file_content("README.md")
            assert "CI/CD" in content, "CI/CD not mentioned in README.md when enabled"

    def test_readme_links_to_cicd_setup(self, generated_project: GeneratedProject):
        """README.md should link to CI_CD_SETUP.md when CI/CD is enabled."""
        if generated_project.has_cicd:
            content = generated_project.get_file_content("README.md")
            assert "CI_CD_SETUP.md" in content, "CI_CD_SETUP.md not linked in README.md"

    def test_readme_shows_testing_section(self, generated_project: GeneratedProject):
        """README.md should have a Testing section."""
        content = generated_project.get_file_content("README.md")
        assert "## Testing" in content, "Testing section not found in README.md"

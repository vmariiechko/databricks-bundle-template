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
            assert "Verify Catalog Access" in content, (
                "Catalog access verification section not found in CI_CD_SETUP.md"
            )
            assert "GRANT" in content, "Permission grants not found in CI_CD_SETUP.md"

    def test_cicd_setup_doc_has_variable_mapping_table(self, generated_project: GeneratedProject):
        """CI_CD_SETUP.md should have clear variable mapping table for ADO."""
        if generated_project.has_cicd and generated_project.is_azure_devops:
            content = generated_project.get_file_content("docs/CI_CD_SETUP.md")
            assert "Variable Name" in content, "Variable mapping table header not found"
            assert "Value Source" in content, "Value source column not found in variable table"
            assert "Secret?" in content, "Secret column not found in variable table"

    def test_cicd_setup_doc_has_repo_root_requirement(self, generated_project: GeneratedProject):
        """CI_CD_SETUP.md should have repository root requirement guidance."""
        if generated_project.has_cicd:
            content = generated_project.get_file_content("docs/CI_CD_SETUP.md")
            assert "repository root" in content.lower(), (
                "Repository root requirement not found in CI_CD_SETUP.md"
            )
            assert (
                "must be at" in content.lower()
                or "must be at the repository root" in content.lower()
            ), "Repo root guidance not found in CI_CD_SETUP.md"

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


# =============================================================================
# GitHub Actions CI/CD Tests
# =============================================================================


class TestGitHubActionsWorkflowGeneration:
    """Test GitHub Actions workflow files are generated correctly."""

    def test_github_workflow_generated_when_enabled(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should be generated when cicd_platform=github_actions."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            assert generated_project.file_exists(workflow_path), (
                f"GitHub Actions workflow not found at {workflow_path} "
                f"for config: {generated_project.config_name}"
            )

    def test_github_workflow_empty_when_disabled(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should be empty when cicd is disabled."""
        if not generated_project.has_cicd:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            if generated_project.file_exists(workflow_path):
                content = generated_project.get_file_content(workflow_path).strip()
                assert content == "", (
                    f"GitHub Actions workflow should be empty when CI/CD is disabled "
                    f"for config: {generated_project.config_name}"
                )

    def test_github_workflow_empty_for_other_platforms(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should be empty for non-GitHub platforms."""
        if generated_project.has_cicd and not generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            if generated_project.file_exists(workflow_path):
                content = generated_project.get_file_content(workflow_path).strip()
                assert content == "", (
                    f"GitHub Actions workflow should be empty for platform "
                    f"{generated_project.cicd_platform} for config: {generated_project.config_name}"
                )


class TestGitHubActionsWorkflowContent:
    """Test GitHub Actions workflow content is correct."""

    def test_github_workflow_valid_yaml(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should be valid YAML."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            try:
                parsed = yaml.safe_load(content)
                assert parsed is not None, "Workflow YAML is empty"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in workflow: {e}")

    def test_github_workflow_uses_setup_cli_action(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should use official databricks/setup-cli action."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            assert "databricks/setup-cli@" in content, (
                "databricks/setup-cli action not found in workflow"
            )

    def test_github_workflow_cli_version_consistent(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should use consistent CLI version."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            import re

            cli_versions = re.findall(r"databricks/setup-cli@v?([\d.]+)", content)
            assert len(cli_versions) > 0, "No CLI version found in workflow"
            assert len(set(cli_versions)) == 1, f"Multiple CLI versions found: {set(cli_versions)}"

    def test_github_workflow_has_required_jobs(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should have bundle-ci and staging-cd jobs."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            assert "bundle-ci:" in content, "bundle-ci job not found in workflow"
            assert "staging-cd:" in content, "staging-cd job not found in workflow"

    def test_github_workflow_has_prod_job_for_full_mode(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should have prod-cd job for full environment setup."""
        if (
            generated_project.has_cicd
            and generated_project.is_github_actions
            and generated_project.is_full
        ):
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            assert "prod-cd:" in content, (
                "prod-cd job not found in workflow for full environment setup"
            )

    def test_github_workflow_no_prod_job_for_minimal_mode(
        self, generated_project: GeneratedProject
    ):
        """GitHub Actions workflow should NOT have prod-cd job for minimal environment setup."""
        if (
            generated_project.has_cicd
            and generated_project.is_github_actions
            and generated_project.is_minimal
        ):
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            assert "prod-cd:" not in content, (
                "prod-cd job should not exist in workflow for minimal environment setup"
            )

    def test_github_workflow_uses_correct_branches(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should reference correct branch names."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            default_branch = generated_project.default_branch
            assert default_branch in content, (
                f"Default branch '{default_branch}' not found in workflow"
            )

            if generated_project.is_full:
                release_branch = generated_project.release_branch
                assert release_branch in content, (
                    f"Release branch '{release_branch}' not found in workflow for full mode"
                )

    def test_github_workflow_uses_correct_auth_for_azure(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should use ARM_* variables for Azure cloud."""
        if (
            generated_project.has_cicd
            and generated_project.is_github_actions
            and generated_project.cloud_provider == "azure"
        ):
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            assert "ARM_TENANT_ID" in content, "ARM_TENANT_ID not found for Azure cloud"
            assert "ARM_CLIENT_ID" in content, "ARM_CLIENT_ID not found for Azure cloud"
            assert "ARM_CLIENT_SECRET" in content, "ARM_CLIENT_SECRET not found for Azure cloud"

    def test_github_workflow_uses_correct_auth_for_aws(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should use OAuth credentials for AWS cloud."""
        if (
            generated_project.has_cicd
            and generated_project.is_github_actions
            and generated_project.cloud_provider == "aws"
        ):
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            # OAuth M2M credentials for AWS/GCP
            assert "DATABRICKS_HOST" in content, "DATABRICKS_HOST not found for AWS cloud"
            assert "DATABRICKS_CLIENT_ID" in content, "DATABRICKS_CLIENT_ID not found for AWS"
            assert "DATABRICKS_CLIENT_SECRET" in content, (
                "DATABRICKS_CLIENT_SECRET not found for AWS"
            )
            # Should NOT have ARM_* environment variable assignments for AWS
            assert "ARM_TENANT_ID:" not in content, (
                "ARM_TENANT_ID should not be in workflow for AWS"
            )

    def test_github_workflow_includes_unit_tests(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should include unit test step."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            assert "pytest" in content.lower(), "pytest not found in workflow"
            assert "unit tests" in content.lower(), "Unit test step not found in workflow"

    def test_github_workflow_has_concurrency_controls(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should have concurrency controls."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            assert "concurrency:" in content, "Concurrency controls not found in workflow"

    def test_github_workflow_has_test_reporter(self, generated_project: GeneratedProject):
        """GitHub Actions workflow should use dorny/test-reporter for test results."""
        if generated_project.has_cicd and generated_project.is_github_actions:
            project_name = generated_project.project_name
            workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
            content = generated_project.get_file_content(workflow_path)

            assert "dorny/test-reporter" in content, (
                "dorny/test-reporter not found in workflow for test results"
            )


# =============================================================================
# GitLab CI/CD Tests
# =============================================================================


class TestGitLabPipelineGeneration:
    """Test GitLab CI/CD pipeline files are generated correctly."""

    def test_gitlab_pipeline_generated_when_enabled(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should be generated when cicd_platform=gitlab."""
        if generated_project.has_cicd and generated_project.is_gitlab:
            assert generated_project.file_exists(".gitlab-ci.yml"), (
                f"GitLab CI pipeline not found at .gitlab-ci.yml "
                f"for config: {generated_project.config_name}"
            )

    def test_gitlab_pipeline_empty_when_disabled(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should be empty when cicd is disabled."""
        if not generated_project.has_cicd:
            if generated_project.file_exists(".gitlab-ci.yml"):
                content = generated_project.get_file_content(".gitlab-ci.yml").strip()
                assert content == "", (
                    f"GitLab CI pipeline should be empty when CI/CD is disabled "
                    f"for config: {generated_project.config_name}"
                )

    def test_gitlab_pipeline_empty_for_other_platforms(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should be empty for non-GitLab platforms."""
        if generated_project.has_cicd and not generated_project.is_gitlab:
            if generated_project.file_exists(".gitlab-ci.yml"):
                content = generated_project.get_file_content(".gitlab-ci.yml").strip()
                assert content == "", (
                    f"GitLab CI pipeline should be empty for platform "
                    f"{generated_project.cicd_platform} for config: {generated_project.config_name}"
                )


class TestGitLabPipelineContent:
    """Test GitLab CI/CD pipeline content is correct."""

    def test_gitlab_pipeline_valid_yaml(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should be valid YAML."""
        if generated_project.has_cicd and generated_project.is_gitlab:
            content = generated_project.get_file_content(".gitlab-ci.yml")

            try:
                parsed = yaml.safe_load(content)
                assert parsed is not None, "Pipeline YAML is empty"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in pipeline: {e}")

    def test_gitlab_pipeline_cli_version_consistent(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should use consistent CLI version from helper."""
        if generated_project.has_cicd and generated_project.is_gitlab:
            content = generated_project.get_file_content(".gitlab-ci.yml")

            assert "setup-cli/v0." in content, "CLI version reference not found in pipeline"
            import re

            cli_versions = re.findall(r"setup-cli/(v[\d.]+)/", content)
            assert len(set(cli_versions)) == 1, f"Multiple CLI versions found: {set(cli_versions)}"

    def test_gitlab_pipeline_has_required_jobs(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should have bundle-ci and staging-cd jobs."""
        if generated_project.has_cicd and generated_project.is_gitlab:
            content = generated_project.get_file_content(".gitlab-ci.yml")

            assert "bundle-ci:" in content, "bundle-ci job not found in pipeline"
            assert "staging-cd:" in content, "staging-cd job not found in pipeline"

    def test_gitlab_pipeline_has_prod_job_for_full_mode(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should have prod-cd job for full environment setup."""
        if generated_project.has_cicd and generated_project.is_gitlab and generated_project.is_full:
            content = generated_project.get_file_content(".gitlab-ci.yml")

            assert "prod-cd:" in content, (
                "prod-cd job not found in pipeline for full environment setup"
            )

    def test_gitlab_pipeline_no_prod_job_for_minimal_mode(
        self, generated_project: GeneratedProject
    ):
        """GitLab CI pipeline should NOT have prod-cd job for minimal environment setup."""
        if (
            generated_project.has_cicd
            and generated_project.is_gitlab
            and generated_project.is_minimal
        ):
            content = generated_project.get_file_content(".gitlab-ci.yml")

            assert "prod-cd:" not in content, (
                "prod-cd job should not exist in pipeline for minimal environment setup"
            )

    def test_gitlab_pipeline_uses_correct_branches(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should reference correct branch names."""
        if generated_project.has_cicd and generated_project.is_gitlab:
            content = generated_project.get_file_content(".gitlab-ci.yml")

            default_branch = generated_project.default_branch
            assert default_branch in content, (
                f"Default branch '{default_branch}' not found in pipeline"
            )

            if generated_project.is_full:
                release_branch = generated_project.release_branch
                assert release_branch in content, (
                    f"Release branch '{release_branch}' not found in pipeline for full mode"
                )

    def test_gitlab_pipeline_uses_correct_auth_for_azure(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should use ARM_* variables for Azure cloud."""
        if (
            generated_project.has_cicd
            and generated_project.is_gitlab
            and generated_project.cloud_provider == "azure"
        ):
            content = generated_project.get_file_content(".gitlab-ci.yml")

            assert "ARM_TENANT_ID" in content, "ARM_TENANT_ID not found for Azure cloud"
            assert "ARM_CLIENT_ID" in content, "ARM_CLIENT_ID not found for Azure cloud"
            assert "ARM_CLIENT_SECRET" in content, "ARM_CLIENT_SECRET not found for Azure cloud"

    def test_gitlab_pipeline_uses_correct_auth_for_aws(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should use OAuth credentials for AWS cloud."""
        if (
            generated_project.has_cicd
            and generated_project.is_gitlab
            and generated_project.cloud_provider == "aws"
        ):
            content = generated_project.get_file_content(".gitlab-ci.yml")

            # OAuth M2M credentials for AWS/GCP
            assert "DATABRICKS_HOST" in content, "DATABRICKS_HOST not found for AWS cloud"
            assert "DATABRICKS_CLIENT_ID" in content, "DATABRICKS_CLIENT_ID not found for AWS"
            assert "DATABRICKS_CLIENT_SECRET" in content, (
                "DATABRICKS_CLIENT_SECRET not found for AWS"
            )
            # Should NOT have ARM_* variables for AWS
            assert "ARM_TENANT_ID:" not in content, (
                "ARM_TENANT_ID should not be in pipeline for AWS"
            )

    def test_gitlab_pipeline_includes_unit_tests(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should include unit test step."""
        if generated_project.has_cicd and generated_project.is_gitlab:
            content = generated_project.get_file_content(".gitlab-ci.yml")

            assert "pytest" in content.lower(), "pytest not found in pipeline"

    def test_gitlab_pipeline_has_environments(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should define environments for deploy jobs."""
        if generated_project.has_cicd and generated_project.is_gitlab:
            content = generated_project.get_file_content(".gitlab-ci.yml")

            assert "environment:" in content, "Environment definition not found in pipeline"
            assert "staging" in content, "staging environment not found in pipeline"

            if generated_project.is_full:
                assert "production" in content, "production environment not found for full mode"

    def test_gitlab_pipeline_has_junit_artifacts(self, generated_project: GeneratedProject):
        """GitLab CI pipeline should have JUnit artifact reporting."""
        if generated_project.has_cicd and generated_project.is_gitlab:
            content = generated_project.get_file_content(".gitlab-ci.yml")

            assert "artifacts:" in content, "artifacts section not found in pipeline"
            assert "junit:" in content, "JUnit artifact reporting not found in pipeline"


# =============================================================================
# Multi-Workspace CI/CD Tests
# =============================================================================


class TestMultiWorkspaceCICD:
    """Test CI/CD templates handle multi-workspace correctly."""

    def test_azure_multi_workspace_ado_has_databricks_host(
        self, generated_project: GeneratedProject
    ):
        """ADO pipeline should include DATABRICKS_HOST for Azure multi-workspace."""
        if not (
            generated_project.has_cicd
            and generated_project.is_azure_devops
            and generated_project.cloud_provider == "azure"
            and generated_project.is_multi_workspace
        ):
            pytest.skip("Not Azure ADO multi-workspace")

        project_name = generated_project.project_name
        pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
        content = generated_project.get_file_content(pipeline_path)

        assert "STAGING_DATABRICKS_HOST" in content, (
            "STAGING_DATABRICKS_HOST not found in ADO pipeline for Azure multi-workspace"
        )
        if generated_project.is_full:
            assert "PROD_DATABRICKS_HOST" in content, (
                "PROD_DATABRICKS_HOST not found in ADO pipeline for Azure multi-workspace full mode"
            )

    def test_azure_single_workspace_ado_no_databricks_host(
        self, generated_project: GeneratedProject
    ):
        """ADO pipeline should NOT include DATABRICKS_HOST for Azure single-workspace."""
        if not (
            generated_project.has_cicd
            and generated_project.is_azure_devops
            and generated_project.cloud_provider == "azure"
            and generated_project.is_single_workspace
        ):
            pytest.skip("Not Azure ADO single-workspace")

        project_name = generated_project.project_name
        pipeline_path = f".azure/devops_pipelines/{project_name}_bundle_cicd.yml"
        content = generated_project.get_file_content(pipeline_path)

        assert "STAGING_DATABRICKS_HOST" not in content, (
            "STAGING_DATABRICKS_HOST should not be in ADO pipeline for Azure single-workspace"
        )

    def test_azure_multi_workspace_github_has_databricks_host(
        self, generated_project: GeneratedProject
    ):
        """GitHub Actions should include DATABRICKS_HOST for Azure multi-workspace."""
        if not (
            generated_project.has_cicd
            and generated_project.is_github_actions
            and generated_project.cloud_provider == "azure"
            and generated_project.is_multi_workspace
        ):
            pytest.skip("Not Azure GitHub Actions multi-workspace")

        project_name = generated_project.project_name
        workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
        content = generated_project.get_file_content(workflow_path)

        assert "STAGING_DATABRICKS_HOST" in content, (
            "STAGING_DATABRICKS_HOST not found in GitHub Actions for Azure multi-workspace"
        )
        if generated_project.is_full:
            assert "PROD_DATABRICKS_HOST" in content, (
                "PROD_DATABRICKS_HOST not found in GitHub Actions for Azure multi-workspace full mode"
            )

    def test_azure_single_workspace_github_no_databricks_host(
        self, generated_project: GeneratedProject
    ):
        """GitHub Actions should NOT include DATABRICKS_HOST for Azure single-workspace."""
        if not (
            generated_project.has_cicd
            and generated_project.is_github_actions
            and generated_project.cloud_provider == "azure"
            and generated_project.is_single_workspace
        ):
            pytest.skip("Not Azure GitHub Actions single-workspace")

        project_name = generated_project.project_name
        workflow_path = f".github/workflows/{project_name}_bundle_cicd.yml"
        content = generated_project.get_file_content(workflow_path)

        assert "STAGING_DATABRICKS_HOST" not in content, (
            "STAGING_DATABRICKS_HOST should not be in GitHub Actions for Azure single-workspace"
        )

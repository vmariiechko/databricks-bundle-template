"""
Template Generation Tests (Level 1)

Tests that verify the template generates the expected file structure
based on configuration options.
"""

from conftest import GeneratedProject

# =============================================================================
# Core File Generation Tests
# =============================================================================


class TestCoreFilesGenerated:
    """Test that core files are always generated regardless of configuration."""

    def test_databricks_yml_exists(self, generated_project: GeneratedProject):
        """databricks.yml should always be generated."""
        assert generated_project.file_exists("databricks.yml"), (
            f"databricks.yml not found for config: {generated_project.config_name}"
        )

    def test_variables_yml_exists(self, generated_project: GeneratedProject):
        """variables.yml should always be generated."""
        assert generated_project.file_exists("variables.yml"), (
            f"variables.yml not found for config: {generated_project.config_name}"
        )

    def test_readme_exists(self, generated_project: GeneratedProject):
        """README.md should always be generated."""
        assert generated_project.file_exists("README.md"), (
            f"README.md not found for config: {generated_project.config_name}"
        )

    def test_quickstart_exists(self, generated_project: GeneratedProject):
        """QUICKSTART.md should always be generated."""
        assert generated_project.file_exists("QUICKSTART.md"), (
            f"QUICKSTART.md not found for config: {generated_project.config_name}"
        )

    def test_gitignore_exists(self, generated_project: GeneratedProject):
        """.gitignore should always be generated."""
        assert generated_project.file_exists(".gitignore"), (
            f".gitignore not found for config: {generated_project.config_name}"
        )


class TestResourceFilesGenerated:
    """Test that resource files are generated with correct naming."""

    def test_ingestion_job_exists(self, generated_project: GeneratedProject):
        """Ingestion job file should be generated with project name prefix."""
        project_name = generated_project.project_name
        expected_file = f"resources/{project_name}_ingestion.job.yml"
        assert generated_project.file_exists(expected_file), (
            f"{expected_file} not found for config: {generated_project.config_name}"
        )

    def test_pipeline_exists(self, generated_project: GeneratedProject):
        """Pipeline file should be generated with project name prefix."""
        project_name = generated_project.project_name
        expected_file = f"resources/{project_name}_pipeline.pipeline.yml"
        assert generated_project.file_exists(expected_file), (
            f"{expected_file} not found for config: {generated_project.config_name}"
        )

    def test_pipeline_trigger_exists(self, generated_project: GeneratedProject):
        """Pipeline trigger job file should be generated with project name prefix."""
        project_name = generated_project.project_name
        expected_file = f"resources/{project_name}_pipeline_trigger.job.yml"
        assert generated_project.file_exists(expected_file), (
            f"{expected_file} not found for config: {generated_project.config_name}"
        )

    def test_schemas_exists(self, generated_project: GeneratedProject):
        """Schemas file should always be generated."""
        assert generated_project.file_exists("resources/schemas.yml"), (
            f"resources/schemas.yml not found for config: {generated_project.config_name}"
        )


class TestSourceFilesGenerated:
    """Test that source code files are generated."""

    def test_src_jobs_directory_exists(self, generated_project: GeneratedProject):
        """src/jobs/ directory should exist."""
        assert generated_project.dir_exists("src/jobs"), (
            f"src/jobs/ not found for config: {generated_project.config_name}"
        )

    def test_src_pipelines_directory_exists(self, generated_project: GeneratedProject):
        """src/pipelines/ directory should exist."""
        assert generated_project.dir_exists("src/pipelines"), (
            f"src/pipelines/ not found for config: {generated_project.config_name}"
        )

    def test_ingest_to_raw_exists(self, generated_project: GeneratedProject):
        """ingest_to_raw.py should be generated."""
        assert generated_project.file_exists("src/jobs/ingest_to_raw.py"), (
            f"src/jobs/ingest_to_raw.py not found for config: {generated_project.config_name}"
        )

    def test_bronze_pipeline_exists(self, generated_project: GeneratedProject):
        """bronze.py pipeline should be generated."""
        assert generated_project.file_exists("src/pipelines/bronze.py"), (
            f"src/pipelines/bronze.py not found for config: {generated_project.config_name}"
        )

    def test_silver_pipeline_exists(self, generated_project: GeneratedProject):
        """silver.py pipeline should be generated."""
        assert generated_project.file_exists("src/pipelines/silver.py"), (
            f"src/pipelines/silver.py not found for config: {generated_project.config_name}"
        )


class TestDocsGenerated:
    """Test that documentation files are generated."""

    def test_docs_directory_exists(self, generated_project: GeneratedProject):
        """docs/ directory should exist."""
        assert generated_project.dir_exists("docs"), (
            f"docs/ not found for config: {generated_project.config_name}"
        )

    def test_permissions_setup_exists(self, generated_project: GeneratedProject):
        """PERMISSIONS_SETUP.md should be generated."""
        assert generated_project.file_exists("docs/PERMISSIONS_SETUP.md"), (
            f"docs/PERMISSIONS_SETUP.md not found for config: {generated_project.config_name}"
        )

    def test_setup_groups_exists(self, generated_project: GeneratedProject):
        """SETUP_GROUPS.md should be generated."""
        assert generated_project.file_exists("docs/SETUP_GROUPS.md"), (
            f"docs/SETUP_GROUPS.md not found for config: {generated_project.config_name}"
        )


class TestTemplatesGenerated:
    """Test that template/example files are generated."""

    def test_templates_directory_exists(self, generated_project: GeneratedProject):
        """templates/ directory should exist."""
        assert generated_project.dir_exists("templates"), (
            f"templates/ not found for config: {generated_project.config_name}"
        )

    def test_cluster_configs_exists(self, generated_project: GeneratedProject):
        """cluster_configs.yml should be generated."""
        assert generated_project.file_exists("templates/cluster_configs.yml"), (
            f"templates/cluster_configs.yml not found for config: {generated_project.config_name}"
        )


# =============================================================================
# Project Name Substitution Tests
# =============================================================================


class TestProjectNameSubstitution:
    """Test that project_name is correctly substituted in generated files."""

    def test_project_directory_name(self, generated_project: GeneratedProject):
        """Generated project directory should match project_name."""
        assert generated_project.project_dir.exists(), (
            f"Project directory {generated_project.project_name} not created"
        )
        assert generated_project.project_dir.name == generated_project.project_name

    def test_bundle_name_in_databricks_yml(self, generated_project: GeneratedProject):
        """Bundle name in databricks.yml should match project_name."""
        content = generated_project.get_file_content("databricks.yml")
        expected = f"name: {generated_project.project_name}"
        assert expected in content, f"Bundle name '{expected}' not found in databricks.yml"


# =============================================================================
# Generation Success Tests
# =============================================================================


class TestGenerationSuccess:
    """Test that template generation completes without errors."""

    def test_no_tmpl_files_in_output(self, generated_project: GeneratedProject):
        """No .tmpl files should remain in the generated output."""
        tmpl_files = list(generated_project.project_dir.rglob("*.tmpl"))
        assert len(tmpl_files) == 0, f"Found unprocessed .tmpl files: {tmpl_files}"

    def test_no_template_syntax_in_output(self, generated_project: GeneratedProject):
        """No Go template syntax should remain in generated files."""
        # Check key files for leftover template syntax
        files_to_check = [
            "databricks.yml",
            "variables.yml",
            "README.md",
        ]

        for file_path in files_to_check:
            if generated_project.file_exists(file_path):
                content = generated_project.get_file_content(file_path)
                # Check for common template syntax patterns
                assert "{{-" not in content, f"Template syntax '{{{{-' found in {file_path}"
                assert "{{." not in content or "{{.project_name}}" not in content, (
                    f"Unprocessed template variable found in {file_path}"
                )

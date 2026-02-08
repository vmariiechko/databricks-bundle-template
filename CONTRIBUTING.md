# Contributing to databricks-bundle-template

Thank you for your interest in contributing! This project is a Databricks Asset Bundles custom template, and contributions of all kinds are welcome: bug reports, feature requests, documentation improvements, and code changes.

## Prerequisites

- **Python** 3.11+
- **Databricks CLI** v0.274.0+ ([installation guide](https://docs.databricks.com/en/dev-tools/cli/install.html))

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/databricks-bundle-template.git
   cd databricks-bundle-template
   ```
3. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate    # Linux/macOS
   venv\Scripts\activate       # Windows
   ```
4. Install development dependencies:
   ```bash
   pip install -r tests/requirements_dev.txt
   ```
5. Run the test suite to verify your setup:
   ```bash
   pytest tests/ -V
   ```

## How the Template Works

This is a **Go template** project consumed by the Databricks CLI via `databricks bundle init`. Key concepts:

- **`databricks_template_schema.json`** defines the 15 interactive prompts users see during initialization
- **`library/helpers.tmpl`** contains custom Go template helper functions
- **`template/{{.project_name}}/`** contains all the Go template files that generate the user's project
- **`template/update_layout.tmpl`** controls conditional file/directory generation (e.g., skip `.azure/` when GitHub Actions is selected)
- Files ending in `.tmpl` are processed by the Go template engine; other files are copied as-is

### Template Parameters

The template has 15 parameters. Seven of these are **configuration axes** that drive conditional logic and produce structurally different outputs:

| Parameter | Options | Effect |
|-----------|---------|--------|
| `environment_setup` | `full` / `minimal` | 3-4 targets vs 2 targets |
| `include_dev_environment` | `yes` / `no` | Adds dev target (full mode only) |
| `compute_type` | `classic` / `serverless` / `both` | Cluster config vs environments |
| `include_permissions` | `yes` / `no` | RBAC blocks in all resources |
| `include_cicd` | `yes` / `no` | CI/CD pipeline templates |
| `cicd_platform` | `azure_devops` / `github_actions` / `gitlab` | Platform-specific pipeline |
| `cloud_provider` | `azure` / `aws` / `gcp` | Auth method (ARM vs OAuth M2M) |

The remaining parameters provide input values:

| Parameter | Purpose |
|-----------|---------|
| `project_name` | Bundle name, folder name, resource prefixes |
| `uc_catalog_suffix` | Unity Catalog naming (`dev_<suffix>`, `stage_<suffix>`, `prod_<suffix>`) |
| `configure_sp_now` | Configure SP IDs during init or defer with `SP_PLACEHOLDER` |
| `dev/stage/prod_service_principal` | SP App IDs per environment (conditional on `configure_sp_now`) |
| `default_branch` | Branch for staging deployments (CI/CD only) |
| `release_branch` | Branch for prod deployments (CI/CD + full mode only) |

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design decisions and conditional logic patterns.

## Making Changes

### Template Files

When modifying template files under `template/{{.project_name}}/`:

- Use Go template syntax: `{{ .variable_name }}`, `{{- if eq .var "value" }}...{{- end }}`
- Use `{{-` to strip preceding whitespace and `-}}` to strip following whitespace
- Use standard `{{ }}` (without dashes) when whitespace must be preserved (e.g., inside sentences)
- Test all affected configuration combinations

### Adding a New Prompt

1. Add the parameter to `databricks_template_schema.json` with appropriate `order`, `pattern`, and `skip_prompt_if`
2. Add conditional logic in the relevant `.tmpl` files
3. Create new test config files in `tests/configs/` if needed
4. Update existing tests or add new ones

### Adding a New Test Configuration

1. Create a JSON file in `tests/configs/` with your parameter values
2. The test suite automatically picks up all config files via parametrized fixtures

## Testing

### Running Tests

```bash
# Run full test suite
pytest tests/ -V

# Run a specific test
pytest tests/test_generation.py::test_no_tmpl_files_remain -v

# Run tests for a specific file
pytest tests/test_content.py -v
```

### Manual Testing

```bash
# Generate a project with a specific config
databricks bundle init . --output-dir ../test-output --config-file tests/configs/full_with_dev.json

# Validate the generated bundle (requires Databricks CLI auth)
cd ../test-output/test_full_with_dev/
databricks bundle validate -t user
```

### Test Requirements

All contributions must:

- Pass the full test suite (`pytest tests/ -V`)
- Include new tests for new functionality
- Not leave any `.tmpl` files in generated output

## Submitting Changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes and run the full test suite
3. Commit with a clear message describing what and why
4. Push to your fork and open a Pull Request against `main`
5. Fill out the PR template with the required information

### Pull Request Guidelines

- Keep PRs focused on a single change
- Include test results in the PR description
- If your change affects generated output, include a sample of the before/after
- Update documentation if behavior changes

## Reporting Issues

- **Bug reports**: Use the [bug report template](https://github.com/vmariiechko/databricks-bundle-template/issues/new?template=1-bug-report.yml)
- **Feature requests**: Use the [feature request template](https://github.com/vmariiechko/databricks-bundle-template/issues/new?template=2-feature-request.yml)
- **Questions**: Use [GitHub Discussions](https://github.com/vmariiechko/databricks-bundle-template/discussions)

## Code Style

- **Go templates**: Follow existing patterns in the codebase. Consistent use of whitespace control (`{{-` / `-}}`)
- **Python (tests)**: Use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- **YAML**: 2-space indentation, consistent with Databricks conventions

## Code of Conduct & License

This project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to abide by its terms.

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

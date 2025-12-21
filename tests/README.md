# Template Testing

This directory contains the automated test suite for the Databricks Multi-Environment Bundle Template.

## Quick Start

```bash
python -m venv venv

# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest tests/ -v
```

## Test Structure

```
tests/
├── conftest.py           # Pytest fixtures and helpers
├── configs/              # Test configuration files
│   ├── minimal_serverless.json
│   ├── minimal_classic.json
│   ├── full_no_dev.json
│   ├── full_with_dev.json
│   ├── full_serverless.json
│   └── full_with_sp.json
├── test_generation.py    # Level 1: File generation tests
├── test_content.py       # Level 2: Content validation tests
└── README.md             # This file
```

## Test Levels

### Level 1: Generation Tests (`test_generation.py`)
- Verifies expected files are created
- Checks project name substitution
- Ensures no `.tmpl` files remain
- Validates file/directory structure

### Level 2: Content Tests (`test_content.py`)
- Validates YAML syntax
- Checks conditional content (dev/prod targets)
- Verifies service principal configuration
- Tests permissions/RBAC settings
- Validates compute type configuration

### Level 3: Schema Validation (Manual Testing, potentially to be automated)
- Verify bundle structure (no workspace)
- Requires Databricks CLI (offline)

### Level 4: Integration Tests
TODO

## Test Configurations

The `configs/` directory contains JSON configuration files for different test scenarios:

| Config | Environment | Dev | Compute | Permissions | SP |
|--------|-------------|-----|---------|-------------|-----|
| `minimal_serverless.json` | minimal | - | serverless | no | no |
| `minimal_classic.json` | minimal | - | classic | yes | no |
| `full_no_dev.json` | full | no | classic | yes | no |
| `full_with_dev.json` | full | yes | classic | yes | no |
| `full_serverless.json` | full | no | serverless | yes | no |
| `full_with_sp.json` | full | yes | classic | yes | yes |

## Manual Testing

You can also use the config files for manual template generation:

```bash
# Generate a project with a specific configuration
databricks bundle init . --output-dir ../test-output --config-file tests/configs/full_with_dev.json

# Review generated files
ls -l ../test-output/test_full_with_dev/

# Validate the bundle (requires Databricks CLI authentication)
cd ../test-output/test_full_with_dev/
databricks bundle validate -t user

# Cleanup
rm -rf ../test-output
```

## Adding New Tests

### Adding a New Configuration

1. Create a new JSON file in `tests/configs/`:
   ```json
   {
     "project_name": "test_my_scenario",
     "environment_setup": "full",
     "include_dev_environment": "no",
     "compute_type": "classic",
     "cloud_provider": "azure",
     "uc_catalog_suffix": "test_domain",
     "include_permissions": "yes",
     "configure_sp_now": "no"
   }
   ```

2. Tests will automatically pick up the new config via the `generated_project` fixture.

### Adding New Test Cases

1. Add tests to `test_generation.py` for file existence checks
2. Add tests to `test_content.py` for content validation

Example test:
```python
def test_my_new_feature(self, generated_project: GeneratedProject):
    """Description of what this tests."""
    if generated_project.is_full:
        content = generated_project.get_file_content("databricks.yml")
        assert "expected_content" in content
```

## Fixtures Reference

### `generated_project`
Parametrized fixture that generates a project for each config file in `tests/configs/`.
Tests using this fixture run once per configuration.

### `full_with_dev_project`, `minimal_serverless_project`, etc.
Individual fixtures for specific configurations, useful for tests that only apply
to certain configurations.

### `GeneratedProject` Class
Helper class with properties and methods for accessing generated project files:

```python
project.file_exists("path/to/file")       # Check file exists
project.get_file_content("path/to/file")  # Read file content
project.is_full                           # True if environment_setup=full
project.has_dev_environment               # True if include_dev_environment=yes
project.has_permissions                   # True if include_permissions=yes
project.is_serverless                     # True if compute_type=serverless
```

## CI/CD Integration

For GitHub Actions:

```yaml
- name: Run Template Tests
  run: |
    pip install -r requirements-dev.txt
    pytest tests/ -v --tb=short
```

## Troubleshooting

### "databricks: command not found"
Install the Databricks CLI ([Docs](https://docs.databricks.com/aws/en/dev-tools/cli/install)):
```bash
pip install databricks-cli
# or
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
```

### Tests fail with "Template generation failed"
- Check that `databricks_template_schema.json` is valid JSON
- Verify all `.tmpl` files have valid Go template syntax
- Run `databricks bundle init . --output-dir /tmp/test` manually to see full error

### YAML parsing errors
- Check generated YAML files for syntax issues
- Look for unescaped special characters or incorrect indentation

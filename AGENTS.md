# AGENTS.md

This file provides guidance to AI coding assistants when working with code in this repository.

## What This Repository Is

A **Databricks Asset Bundles (DABs) custom template** that generates multi-environment data pipeline projects. Users run `databricks bundle init .` to create production-ready bundles with configurable environments, compute, and permissions.

## Commands

Before running any commands, activate the virtual environment:

```bash
# Activate virtual environment
source venv/bin/activate    # Linux/macOS
venv\Scripts\activate       # Windows
```

```bash
# Run template tests
pytest tests/ -V

# Run a single test
pytest tests/test_generation.py::test_no_tmpl_files_remain -v

# Generate project for manual testing
databricks bundle init . --output-dir ../test-output --config-file tests/configs/full_with_dev.json

# Validate generated bundle (requires Databricks CLI auth)
cd ../test-output/<project_name>
databricks bundle validate -t user
```

## Architecture

### Template Structure

```
template/{{.project_name}}/    # Go templates, generates user's project
├── databricks.yml.tmpl        # Bundle config with conditional targets
├── variables.yml.tmpl         # SP, catalog, group variables
├── resources/*.yml.tmpl       # Jobs, pipeline, schemas
└── src/                       # Python code (no templating needed)
```

### Key Files

| File | Purpose |
|------|---------|
| `databricks_template_schema.json` | 15 prompts with `skip_prompt_if` conditionals |
| `library/helpers.tmpl` | Custom Go template helpers (e.g., `node_type_id`, `cli_version`) |
| `template/update_layout.tmpl` | Conditional file/directory skipping for CI/CD platforms |
| `tests/configs/*.json` | Test configurations for pytest parametrization |
| `tests/conftest.py` | `GeneratedProject` class for accessing generated files |
| `tests/test_cicd.py` | CI/CD pipeline template tests |

### Template Parameters

The template has 15 parameters defined in `databricks_template_schema.json`.

#### Configuration Axes

These 7 parameters drive conditional logic and produce structurally different outputs:

| Parameter | Options | Effect |
|-----------|---------|--------|
| `environment_setup` | `full` / `minimal` | 3-4 targets vs 2 targets |
| `include_dev_environment` | `yes` / `no` | Adds dev target (full mode only) |
| `compute_type` | `classic` / `serverless` / `both` | Cluster config vs environments |
| `include_permissions` | `yes` / `no` | RBAC blocks in all resources |
| `include_cicd` | `yes` / `no` | CI/CD pipeline templates |
| `cicd_platform` | `azure_devops` / `github_actions` / `gitlab` | Platform-specific pipeline |
| `cloud_provider` | `azure` / `aws` / `gcp` | Auth method (ARM vs OAuth M2M) |

#### Other Template Parameters

These parameters provide input values or conditionally include content:

| Parameter | Purpose |
|-----------|---------|
| `project_name` | Bundle name, folder name, resource prefixes |
| `uc_catalog_suffix` | Unity Catalog naming (`dev_<suffix>`, `stage_<suffix>`, `prod_<suffix>`) |
| `configure_sp_now` | Configure SP IDs during init or defer with `SP_PLACEHOLDER` |
| `dev/stage/prod_service_principal` | SP App IDs per environment (conditional on `configure_sp_now`) |
| `default_branch` | Branch for staging deployments (CI/CD only) |
| `release_branch` | Branch for prod deployments (CI/CD + full mode only) |

### Conditional Logic Patterns

```go
{{- if eq .environment_setup "full" }}       // prod-only content
{{- if eq .include_dev_environment "yes" }}  // dev-only content
{{- if eq .include_permissions "yes" }}      // RBAC content
{{- if or (eq .compute_type "classic") (eq .compute_type "both") }}  // cluster configs
{{- if and (eq .include_cicd "yes") (eq .cicd_platform "gitlab") }}  // CI/CD conditionals
```

**Note on whitespace control**: `{{-` strips preceding whitespace, `-}}` strips following whitespace. Use standard `{{ }}` to preserve whitespace (e.g., inside sentences).

### Design Decisions

Key architectural decisions (environment structure, SP architecture, schema-per-user isolation, branching strategy, CI/CD pipeline patterns, etc.) are documented in [DEVELOPMENT.md](DEVELOPMENT.md#design-decisions). Consult these before making changes that affect template architecture.

### Service Principal Architecture

User target has **no SP references** - works immediately. SP grants only exist in dev/stage/prod target schema overrides in `databricks.yml.tmpl`.

## Testing

Tests use pytest with parametrized fixtures across 15 config files:
- `full_with_dev.json`, `full_no_dev.json`, `full_serverless.json`, `full_with_sp.json`
- `minimal_classic.json`, `minimal_serverless.json`
- `full_with_cicd_ado.json`, `minimal_with_cicd_ado.json`, `full_cicd_aws.json`
- `full_with_github_actions.json`, `minimal_with_github_actions.json`, `full_github_actions_aws.json`
- `full_with_gitlab.json`, `minimal_with_gitlab.json`, `full_gitlab_aws.json`

**L1 tests**: File existence, directory structure, no `.tmpl` leftovers
**L2 tests**: YAML syntax, environment targets, content validation
**CI/CD tests**: Pipeline generation, YAML validity, auth patterns, branch references

When modifying templates, run the full test suite before committing.

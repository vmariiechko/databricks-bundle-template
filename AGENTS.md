# AGENTS.md

This file provides guidance to AI coding assistants when working with code in this repository.

Always use context7 when I need code generation, setup or configuration steps, or library/API documentation. This means you should automatically use the Context7 MCP tools to resolve library id and get library docs without me having to explicitly ask.

## What This Repository Is

A **Declarative Automation Bundles (DABs) custom template** that generates multi-environment data pipeline projects. Users run `databricks bundle init .` to create production-ready bundles with configurable environments, compute, and permissions.

## Development Process

When implementing features, fixes, or changes, follow this workflow:

1. **Branch**: Create a feature branch from `main` before making changes:
   - `feature/<name>` for features and fixes
   - `docs/<name>` for documentation-only changes
2. **Implement**: Make changes, add/update tests. Run `pytest tests/ -V` and ensure all tests pass.
3. **Update metadata** (as applicable):
   - `CHANGELOG.md` — add entry under `[Unreleased]` following [Keep a Changelog](https://keepachangelog.com/) format
   - `ROADMAP.md` — update feature status if the change relates to a tracked item
   - `DEVELOPMENT.md` — add/update design decisions if architectural choices were made
   - `ARCHITECTURE.md` — update if the change affects project structure or architecture
   - `tests/configs/` — add new test configurations if new configuration axes are introduced
4. **Propose commit message** — output a suggested commit message (imperative mood, free-form, no conventional commit prefixes). Do **not** stage or commit; the maintainer reviews and commits manually.
5. **PR** (on request) — create a pull request via `gh pr create` following `.github/PULL_REQUEST_TEMPLATE.md`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for full contributor guidelines.

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
| `databricks_template_schema.json` | interactive user prompts with `skip_prompt_if` conditionals |
| `library/helpers.tmpl` | Custom Go template helpers (e.g., `node_type_id`, `cli_version`) |
| `template/update_layout.tmpl` | Conditional file/directory skipping for CI/CD platforms |
| `tests/configs/*.json` | Test configurations for pytest parametrization |
| `tests/conftest.py` | `GeneratedProject` class for accessing generated files |
| `tests/test_cicd.py` | CI/CD pipeline template tests |

### Template Parameters

The template keeps user parameters defined in `databricks_template_schema.json`.

#### Configuration Axes

These parameters drive conditional logic and produce structurally different outputs:

| Parameter | Options | Effect |
|-----------|---------|--------|
| `environment_setup` | `full` / `minimal` | 3-4 targets vs 2 targets |
| `include_dev_environment` | `yes` / `no` | Adds dev target (full mode only) |
| `compute_type` | `classic` / `serverless` / `both` | Cluster config vs environments |
| `include_permissions` | `yes` / `no` | RBAC blocks in all resources |
| `include_cicd` | `yes` / `no` | CI/CD pipeline templates |
| `cicd_platform` | `azure_devops` / `github_actions` / `gitlab` | Platform-specific pipeline |
| `cloud_provider` | `azure` / `aws` / `gcp` | Auth method (ARM vs OAuth M2M) |
| `workspace_setup` | `single_workspace` / `multi_workspace` | Workspace topology per environment |


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

## Documentation Conventions

- **No hard line wrap** in Markdown. Write paragraphs as single long lines and let the editor soft-wrap. Do not reflow to 80/100/120 chars. This matches every doc in the repo.
- **Avoid em dashes.** Prefer colons, commas, semicolons, or separate sentences.
- **Pipeline terminology.** The official product name is "Lakeflow Spark Declarative Pipelines" (short form: "SDP" or "Lakeflow SDP"). Never use "LDP" or plain "Lakeflow Declarative Pipelines"; those are outdated.
- **Docstring style: Google convention** (configured in `pyproject.toml` under `[tool.ruff.lint.pydocstyle]`). Do NOT use reStructuredText / Sphinx artifacts in docstrings or Markdown: never use double-backtick (`` ``foo`` ``); use single-backtick (`` `foo` ``) for inline code. Never use `::` to introduce a code block; use a single colon plus a fenced code block in Markdown, or the `Example:` section in Google-style docstrings.

## Asset Library

The repo also hosts an **asset library** under `assets/<name>/`: standalone sub-templates installed individually via `databricks bundle init <repo-url> --template-dir assets/<name>`.

Key facts AI assistants must remember:

- `assets/` is **NOT part of the core template's generated output**. The core template's generator only walks `template/`; `assets/` is invisible to `databricks bundle init .`.
- Every asset is **self-contained**. Never reference `library/helpers.tmpl` from an asset; never import from other assets. Duplication across assets is accepted and intentional.
- Assets install **additively**. The CLI errors on file collisions; assets never modify existing files (no patching `databricks.yml` etc.).
- Framework rules: see [CONTRIBUTING.md — Adding an Asset](CONTRIBUTING.md#adding-an-asset).
- Design rationale: [ARCHITECTURE.md §8](ARCHITECTURE.md#8-asset-library--plugins-layer) and [DEVELOPMENT.md Design Decision #15](DEVELOPMENT.md).
- End-user catalog: [ASSETS.md](ASSETS.md).

Tests:
- `tests/assets/conftest.py` holds the shared `install_asset` helper.
- `tests/assets/test_framework.py` runs framework-level smoke tests parametrized over every `assets/*/` automatically.
- `tests/assets/test_<asset_name>.py` holds asset-specific deep tests (optional).
- `tests/configs/assets/<asset_name>.json` is the default prompt-values config; variants use the pattern `<asset_name>_<variant>.json`.

## Testing

Tests use pytest with parametrized fixtures across config files:
- `full_with_dev.json`, `full_no_dev.json`, `full_serverless.json`, `full_with_sp.json`
- `minimal_classic.json`, `minimal_serverless.json`
- `full_with_cicd_ado.json`, `minimal_with_cicd_ado.json`, `full_cicd_aws.json`
- `full_with_github_actions.json`, `minimal_with_github_actions.json`, `full_github_actions_aws.json`
- `full_with_gitlab.json`, `minimal_with_gitlab.json`, `full_gitlab_aws.json`
- `full_multi_workspace.json`, `full_multi_workspace_cicd_ado.json`, `full_multi_workspace_github.json`, `minimal_multi_workspace.json`

**L1 tests**: File existence, directory structure, no `.tmpl` leftovers
**L2 tests**: YAML syntax, environment targets, content validation
**CI/CD tests**: Pipeline generation, YAML validity, auth patterns, branch references

When modifying templates, run the full test suite before committing.

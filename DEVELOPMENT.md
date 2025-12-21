# Development Notes

## Template Status: Converted to Custom Template

This repository has been converted from a example DABs setup to a reusable DABs custom template.

### How to Use

```bash
# Initialize a new project
databricks bundle init .

# Follow the prompts to configure your project
```

Your generated project includes complete documentation (README.md, QUICKSTART.md).

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the complete technical design, including:
- Parameter map and prompt flow
- Conditional logic design
- File structure

---

## Testing the Template

### Automated Tests (pytest)

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest tests/ -v
```

Tests validate:
- **L1 (Generation)**: File existence, directory structure, no leftover `.tmpl` files
- **L2 (Content)**: YAML syntax, environment targets, SP config, permissions, compute type

### Manual Testing

```bash
# Generate with a specific configuration
databricks bundle init . --output-dir ../test-output --config-file tests/configs/full_with_dev.json

# Validate the generated bundle
cd ../test-output/test_full_with_dev/
databricks bundle validate -t user

# Deploy to verify (optional)
databricks bundle deploy -t user

# Cleanup
databricks bundle destroy -t user
cd ../..
rm -rf test-output
```

See [tests/README.md](tests/README.md) for detailed testing documentation.

---

## Useful Commands

```bash
# Deploy with SP variables via CLI
databricks bundle deploy -t prod \
  --var="dev_service_principal=<app-id>" \
  --var="stage_service_principal=<app-id>" \
  --var="prod_service_principal=<app-id>"
```

---

## Documentation Reference

- Job settings: https://docs.databricks.com/api/azure/workspace/jobs/create
- Custom templates: https://docs.databricks.com/aws/en/dev-tools/bundles/templates#custom-bundle-templates
- Custom Go Template variables: https://github.com/databricks/mlops-stacks/blob/main/library/template_variables.tmpl

---

## Completed Tasks

### Phase 1: Template Conversion
- [x] Multi-environment deployment (user/dev/stage/prod)
- [x] Configurable compute (serverless/classic/both)
- [x] Cloud provider node type selection
- [x] Optional RBAC permissions with environment-aware groups
- [x] Service principal configuration (now or later)
- [x] Unity Catalog suffix configuration
- [x] Template conversion (in-place strategy)
- [x] Optional dev environment (separate prompt)
- [x] Environment-aware group configuration (3 vs 4 groups)
- [x] Multi-workspace documentation

### Phase 1.1: Testing & Documentation
- [x] Pytest test suite (316 tests)
- [x] Test configuration files for all scenarios
- [x] Streamlined documentation (deleted redundant TEMPLATE_USAGE.md)
- [x] SP architecture fix (user target works without SP)
- [x] Clear separation: root repo docs vs generated project docs

---

## Design Decisions (Phase 1)

This section documents key design decisions made during the initial template development. These decisions should guide future enhancements.

### 1. Environment Structure

**Decision**: Three configurations instead of comma-separated selection
- **Minimal mode**: user + stage (for small teams, personal projects)
- **Full mode**: user + stage + prod (standard enterprise)
- **Full + dev**: user + dev + stage + prod (with optional dev environment)

**Rationale**:
- Comma-separated selection was considered but rejected due to complexity (15 combinations vs 3)
- Current approach covers 99% of real-world use cases
- Simpler conditional logic in templates (~50 fewer conditionals)
- Better user experience (dropdown vs free text)

**Key insight**: The `include_dev_environment` prompt is **only shown when `environment_setup=full`** via `skip_prompt_if`. In minimal mode, it defaults to "no" and is never asked.

### 2. Group Configuration

**Decision**: Groups are environment-aware (3 groups in minimal, 4 in full mode)

| Group | Minimal | Full |
|-------|---------|------|
| `developers` | ✓ | ✓ |
| `qa_team` | ✓ | ✓ |
| `operations_team` | ✗ | ✓ |
| `analytics_team` | ✓ | ✓ |

**Rationale**:
- `operations_team` is only used in prod target permissions
- No point asking users to create a group they won't use
- Documentation (`SETUP_GROUPS.md.tmpl`) adapts to show only required groups

### 3. Workspace Configuration

**Decision**: Documentation approach instead of prompts for multi-workspace

**Rationale**:
- Users often don't know prod workspace URL at template init time
- Most teams use single workspace with Unity Catalog isolation
- Simple one-line change when needed
- Keeps prompts focused on essential decisions

**Implementation**:
- Inline comments in `databricks.yml.tmpl` at stage/prod targets
- "Workspace Configuration" section in generated README
- Note in QUICKSTART.md for full mode

### 4. Service Principal Architecture

**Decision**: Per-environment SPs with user target isolation

| Target | SP Required? | Run-As | SP Grants |
|--------|--------------|--------|-----------|
| `user` | No | Current user | None (uses user identity) |
| `dev` | Yes (for CI/CD) | Commented SP | Explicit in target override |
| `stage` | Yes (for CI/CD) | SP | Explicit in target override |
| `prod` | Yes (for CI/CD) | SP | Explicit in target override |

**Key Implementation Details**:
- Base `schemas.yml` has **no SP grants** - only schema definitions
- SP grants are added **per-target** in `databricks.yml` schema overrides
- `user` target works immediately without any SP configuration
- CI/CD targets (dev/stage/prod) require SP setup before deployment

**Rationale**:
- User target must work out-of-the-box for quick testing
- Per-environment SPs provide audit trails and access control
- Enterprise compliance often requires separate SPs per environment
- SP grants only exist where SPs are actually used

**Run-As Configuration**:
```yaml
# dev/stage/prod targets (SP required)
run_as:
  service_principal_name: ${var.stage_service_principal}
```

### 5. Built-in Template Variable

> Source: https://docs.databricks.com/aws/en/dev-tools/bundles/templates#template-helpers-and-variables

**Decision**: Use `{{workspace_host}}` variable to access default Databricks workspace host URL

**Example**: `host: {{workspace_host}}`

### 6. Conditional Logic Patterns

**Standard patterns used throughout templates**:

```go
// Environment checks
{{- if eq .environment_setup "full" }}       // For prod-only content
{{- if eq .include_dev_environment "yes" }}  // For dev-only content

// Feature checks
{{- if eq .include_permissions "yes" }}      // For RBAC content
{{- if eq .configure_sp_now "yes" }}         // For SP values

// Compute checks
{{- if or (eq .compute_type "classic") (eq .compute_type "both") }}
{{- if or (eq .compute_type "serverless") (eq .compute_type "both") }}
```

### 7. Documentation as Templates

**Decision**: Convert static docs to `.tmpl` files when content varies by configuration

| File | Template? | Reason |
|------|-----------|--------|
| `README.md.tmpl` | Yes | Environments, groups, catalogs vary |
| `QUICKSTART.md.tmpl` | Yes | Next steps vary by environment |
| `SETUP_GROUPS.md.tmpl` | Yes | Required groups vary |
| `PERMISSIONS_SETUP.md.tmpl` | Yes | Matrix, SP list vary |
| `templates/cluster_configs.yml` | No | Static reference |

---

## Future Enhancements

### Phase 2: Asset Sub-Templates ("Plugins Layer")

The template can be extended with **asset sub-templates** that add resources to existing projects. This pattern is demonstrated in the Databricks `data-engineering` example template.

**Concept:**
```bash
# Initialize base project
databricks bundle init /path/to/template

# Add an ETL pipeline asset later
cd my_project
databricks bundle init /path/to/template --template-dir assets/etl-pipeline
```

**Potential Asset Types:**

| Asset | Description | Directory |
|-------|-------------|-----------|
| `etl-pipeline` | Add new LDP pipeline with bronze/silver layers | `assets/etl-pipeline/` |
| `ingest-job` | Add data ingestion job | `assets/ingest-job/` |
| `ml-pipeline` | Add ML training pipeline | `assets/ml-pipeline/` |
| `dbt-project` | Add dbt integration | `assets/dbt-project/` |

**Implementation Notes:**
- Each asset has its own `databricks_template_schema.json`
- Assets generate into `assets/<name>/` within the project
- Assets can reference existing variables from `variables.yml`

### Phase 3: CI/CD Templates

Add optional CI/CD configuration generation:

```
Q: Include CI/CD configuration?
Options: github_actions | gitlab_ci | azure_devops | none
```

**Files generated:**
- `.github/workflows/deploy.yml` (GitHub Actions)
- `.gitlab-ci.yml` (GitLab CI)
- `azure-pipelines.yml` (Azure DevOps)

### Phase 4: Advanced Permissions Profiles

Instead of yes/no, offer permission profiles:

```
Q: Permissions configuration?
Options:
  - full (4 groups: developers, qa, operations, analytics)
  - team (2 groups: developers, analytics)
  - minimal (owner only)
  - none
```

---

## Template File Reference

| File | Purpose |
|------|---------|
| `databricks_template_schema.json` | Prompt definitions (11 parameters) |
| `library/helpers.tmpl` | Custom Go template helpers (node_type_id) |
| `template/{{.project_name}}/` | Generated project structure |
| `tests/` | Pytest test suite (316 tests) |
| `tests/configs/` | JSON config files for testing |
| `requirements-dev.txt` | Test dependencies |

---

## Testing Matrix

When testing template changes, validate these combinations:

| # | environment_setup | include_dev | compute_type | include_permissions | Expected Targets |
|---|-------------------|-------------|--------------|---------------------|------------------|
| 1 | full | yes | serverless | yes | user, dev, stage, prod |
| 2 | full | yes | classic | yes | user, dev, stage, prod |
| 3 | full | no | classic | yes | user, stage, prod |
| 4 | full | no | both | no | user, stage, prod |
| 5 | minimal | (skipped) | serverless | no | user, stage |
| 6 | minimal | (skipped) | classic | no | user, stage |

**Test Config Files** (in `tests/configs/`):
- `full_with_dev.json` - Full mode with dev environment
- `full_no_dev.json` - Full mode without dev
- `full_serverless.json` - Full mode with serverless
- `full_with_sp.json` - Full mode with SPs configured
- `minimal_classic.json` - Minimal mode with classic compute
- `minimal_serverless.json` - Minimal mode with serverless

---

## Contributing

1. Make changes to template files in `template/{{.project_name}}/`
2. Update prompts in `databricks_template_schema.json` if needed
3. Add helpers to `library/helpers.tmpl` if needed
4. Run tests: `pytest tests/ -v`
5. Update documentation

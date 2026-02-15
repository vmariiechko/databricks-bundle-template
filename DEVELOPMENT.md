# Development Notes

Internal development notes, design decisions, and historical context for template maintainers. For contributor setup and workflow, see [CONTRIBUTING.md](CONTRIBUTING.md). For technical architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Useful Commands

```bash
# Deploy with SP variables via CLI
databricks bundle deploy -t prod \
  --var="dev_service_principal=<sp-id>" \
  --var="stage_service_principal=<sp-id>" \
  --var="prod_service_principal=<sp-id>"
```

---

## Documentation Reference

- Job settings: https://docs.databricks.com/api/azure/workspace/jobs/create
- Custom templates: https://docs.databricks.com/aws/en/dev-tools/bundles/templates#custom-bundle-templates
- Custom Go Template variables: https://github.com/databricks/mlops-stacks/blob/main/library/template_variables.tmpl

---

## Design Decisions

This section documents key design decisions made during template development. These decisions should guide future enhancements.

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
| `developers` | Yes | Yes |
| `qa_team` | Yes | Yes |
| `operations_team` | No | Yes |
| `analytics_team` | Yes | Yes |

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

**Note on whitespace control**:
- `{{-` strips preceding whitespace
- `-}}` strips following whitespace
- Use standard `{{` and `}}` when you need to preserve whitespace (e.g., inserting variables into markdown sentences).

### 7. Documentation as Templates

**Decision**: Convert static docs to `.tmpl` files when content varies by configuration

| File | Template? | Reason |
|------|-----------|--------|
| `README.md.tmpl` | Yes | Environments, groups, catalogs vary |
| `QUICKSTART.md.tmpl` | Yes | Next steps vary by environment |
| `SETUP_GROUPS.md.tmpl` | Yes | Required groups vary |
| `PERMISSIONS_SETUP.md.tmpl` | Yes | Matrix, SP list vary |
| `templates/cluster_configs.yml` | No | Static reference |

### 8. Schema-Per-User Isolation (Replaces Per-User Catalogs)

**Decision**: User target shares the `dev` catalog with user-prefixed schemas instead of creating per-user catalogs.

**Previous approach** (removed): `user_<username>_<suffix>` per-user catalog. This was an anti-pattern because:
- DABs intentionally don't support catalog creation (only `schemas` are a supported resource type)
- Catalogs are metastore-scoped, polluting the shared namespace across all workspaces
- User-created catalogs inherit the metastore's default storage, risking improperly secured blob storage

**Current approach** (dbt-style schema-per-user):

| Target | Catalog | Schema Prefix | Resulting Schemas |
|--------|---------|---------------|-------------------|
| `user` | `dev_<suffix>` | `${workspace.current_user.short_name}_` | `jsmith_bronze`, `jsmith_silver`, `jsmith_gold` |
| `dev` | `dev_<suffix>` | *(empty)* | `bronze`, `silver`, `gold` |
| `stage` | `stage_<suffix>` | *(empty)* | `bronze`, `silver`, `gold` |
| `prod` | `prod_<suffix>` | *(empty)* | `bronze`, `silver`, `gold` |

**Implementation**: A `schema_prefix` variable is set to `${workspace.current_user.short_name}_` for the user target and empty for all other targets. Schema resource names use `${var.schema_prefix}bronze`, etc.

**Key insight**: `user` and `dev` targets share the same catalog. The toggle `include_dev_environment` only controls whether a shared `dev` deployment target exists - the user target always uses `dev_<suffix>`.

### 9. Release-Based Branching Strategy

**Decision**: Use `default_branch` (main) for staging deployment and `release_branch` for production deployment.

**Rationale**:
- Prevents accidental production deployments
- Staging is continuously updated from main; production only via explicit release merges
- Minimal mode skips the `release_branch` prompt (no prod target)

**Alternative considered**: Branch = target (push to `stage` branch → deploy to stage). Simpler conceptually but riskier for production and less suitable as a template default.

### 10. Single Combined CI/CD Pipeline File

**Decision**: One pipeline file per platform containing all stages (CI validation + staging CD + production CD) rather than separate files per stage.

**Rationale**:
- Simpler to maintain - all CI/CD logic in one place
- Consistent pattern across all 3 platforms (ADO stages, GitHub Actions jobs, GitLab stages)
- Uses platform-native conditions to control execution (ADO `condition:`, GitHub `if:`, GitLab `rules:`)

**Alternative considered**: Separate files per stage (e.g., `bundle_ci.yml`, `bundle_cd_staging.yml`). Valid but adds complexity without benefit for our simpler validate+deploy workflow.

### 11. Cloud-Specific CI/CD Authentication

**Decision**: Authentication mechanism varies by `cloud_provider` parameter.

| Cloud | CI/CD Variables | Method |
|-------|----------------|--------|
| Azure | `ARM_TENANT_ID`, `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET` | Service principal (ARM) |
| AWS/GCP | `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET` | OAuth M2M |

**Key consequence**: The `cloud_provider` prompt is always asked (even for serverless compute) because CI/CD authentication requires it.

### 12. Conditional Directory Generation via `skip` Function

**Decision**: Use Go template `skip` function in `update_layout.tmpl` to exclude unused CI/CD platform directories from generated output.

**Implementation**:
```go
{{ skip (printf "%s/%s" $root_dir ".azure") }}   // when cicd_platform != azure_devops
{{ skip (printf "%s/%s" $root_dir ".github") }}   // when cicd_platform != github_actions
```

**Rationale**: Prevents empty directories/files for unused platforms (e.g., no `.azure/` folder when GitHub Actions is selected).

### 13. Workspace Topology Configuration

**Decision**: Binary prompt `workspace_setup` with options: `single_workspace` (default) and `multi_workspace`.

**Rationale**:
- Binary choice is simple to support and understand
- `single_workspace` preserves current behavior (backwards compatible)
- `multi_workspace` generates variable-based workspace hosts per target
- A three-option approach (e.g., "prod_separate") was considered but rejected: users who share workspaces between environments simply set the same URL for those variables
- Follows the existing SP placeholder pattern (`WORKSPACE_HOST_PLACEHOLDER_*`)

**Implementation**:
- Single workspace: All targets use `{{workspace_host}}` (resolved at init time)
- Multi workspace: User target uses `{{workspace_host}}`; dev/stage/prod targets should provide placeholders `WORKSPACE_HOST_PLACEHOLDER_*` in `databricks.yml.tmpl`
- Cannot parametrize it using variables in `variables.yml` because CLI prohibits variable interpolation in `workspace.host` for fields that configure authentication
- Azure CI/CD pipelines include `DATABRICKS_HOST` per environment (AWS/GCP already has this)

**Key insight**: The user target always uses the current workspace regardless of workspace_setup, since it's for personal development. Only CI/CD deployment targets (dev/stage/prod) get separate workspace hosts.

---

## Testing Matrix

When testing template changes, validate these combinations:

### Core Configurations

| # | environment_setup | include_dev | compute_type | include_permissions | workspace_setup | Expected Targets |
|---|-------------------|-------------|--------------|---------------------|-----------------|------------------|
| 1 | full | yes | serverless | yes | single_workspace | user, dev, stage, prod |
| 2 | full | yes | classic | yes | single_workspace | user, dev, stage, prod |
| 3 | full | no | classic | yes | single_workspace | user, stage, prod |
| 4 | full | no | both | no | single_workspace | user, stage, prod |
| 5 | minimal | (skipped) | serverless | no | single_workspace | user, stage |
| 6 | minimal | (skipped) | classic | no | single_workspace | user, stage |
| 7 | full | no | classic | yes | multi_workspace | user, stage, prod |
| 8 | minimal | (skipped) | classic | yes | multi_workspace | user, stage |

### CI/CD Configurations

| # | cicd_platform | cloud_provider | environment_setup | workspace_setup | Config File |
|---|---------------|----------------|-------------------|-----------------|-------------|
| 9 | azure_devops | azure | full | single_workspace | `full_with_cicd_ado.json` |
| 10 | azure_devops | azure | minimal | single_workspace | `minimal_with_cicd_ado.json` |
| 11 | azure_devops | aws | full | single_workspace | `full_cicd_aws.json` |
| 12 | github_actions | azure | full | single_workspace | `full_with_github_actions.json` |
| 13 | github_actions | azure | minimal | single_workspace | `minimal_with_github_actions.json` |
| 14 | github_actions | aws | full | single_workspace | `full_github_actions_aws.json` |
| 15 | gitlab | azure | full | single_workspace | `full_with_gitlab.json` |
| 16 | gitlab | azure | minimal | single_workspace | `minimal_with_gitlab.json` |
| 17 | gitlab | aws | full | single_workspace | `full_gitlab_aws.json` |
| 18 | azure_devops | azure | full | multi_workspace | `full_multi_workspace_cicd_ado.json` |
| 19 | github_actions | azure | full | multi_workspace | `full_multi_workspace_github.json` |

### Test Config Files (in `tests/configs/`)

**Core:**
- `full_with_dev.json` - Full mode with dev environment
- `full_no_dev.json` - Full mode without dev
- `full_serverless.json` - Full mode with serverless
- `full_with_sp.json` - Full mode with SPs configured
- `minimal_classic.json` - Minimal mode with classic compute
- `minimal_serverless.json` - Minimal mode with serverless

**CI/CD:**
- `full_with_cicd_ado.json` - Full + Azure DevOps (Azure cloud)
- `minimal_with_cicd_ado.json` - Minimal + Azure DevOps
- `full_cicd_aws.json` - Full + Azure DevOps (AWS cloud)
- `full_with_github_actions.json` - Full + GitHub Actions (Azure cloud)
- `minimal_with_github_actions.json` - Minimal + GitHub Actions
- `full_github_actions_aws.json` - Full + GitHub Actions (AWS cloud)
- `full_with_gitlab.json` - Full + GitLab (Azure cloud)
- `minimal_with_gitlab.json` - Minimal + GitLab
- `full_gitlab_aws.json` - Full + GitLab (AWS cloud)

**Multi-Workspace:**
- `full_multi_workspace.json` - Full mode with multi-workspace
- `full_multi_workspace_cicd_ado.json` - Full + multi-workspace + Azure DevOps
- `full_multi_workspace_github.json` - Full + multi-workspace + GitHub Actions
- `minimal_multi_workspace.json` - Minimal mode with multi-workspace

---

## Roadmap

For planned features and future direction, see [ROADMAP.md](ROADMAP.md).

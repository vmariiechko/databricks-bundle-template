
# Template Architecture Solution Document

> **Version:** 2.0
> **Updated:** 2026-01-31
> **Status:** Production Ready

This document captures all architectural decisions for converting the `databricks-bundle-template` repository into a reusable Databricks Asset Bundles custom template.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Template Strategy](#2-template-strategy)
3. [User Prompts & Parameters](#3-user-prompts--parameters)
4. [Conditional Logic Design](#4-conditional-logic-design)
5. [File Structure](#5-file-structure)
6. [Node Type Mapping](#6-node-type-mapping)
7. [Implementation Plan](#7-implementation-plan)

> For planned features and future direction, see [ROADMAP.md](ROADMAP.md).

---

## 1. Executive Summary

### Goal
Convert this "real-world example" DABs repository into a reusable custom template that users can initialize via `databricks bundle init` with an interactive CLI flow.

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Template Strategy | **In-place conversion** | Single source of truth, no version drift, easier maintenance |
| Default Compute | **Classic (resource-specific)** | Not all workspaces support serverless |
| Default Cloud | **Azure** | Current repo uses Azure node types |
| Sample Code | **Always included** | Demonstrates patterns, easy to delete |
| Permissions | **Prompted (yes/no)** | Environment-aware groups (3 or 4) |
| Environment Setup | **Full or Minimal** | Full: user+stage+prod (optional dev), Minimal: user+stage |
| Groups | **Environment-aware** | 3 groups in minimal, 4 in full mode |
| CI/CD | **Optional, 3 platforms** | Azure DevOps, GitHub Actions, GitLab |
| CI/CD Auth | **Cloud-specific** | Azure ARM SP vs OAuth M2M for AWS/GCP |

### Template Consumption

```bash
# Initialize from local path
databricks bundle init /path/to/databricks-bundle-template

# Initialize from GitHub (after publishing)
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template
```

---

## 2. Template Strategy

### Approach: In-Place Conversion

The repository will be converted **in-place** into a template structure:

```
databricks-bundle-template/           # Repository root (IS the template)
├── databricks_template_schema.json     # Prompt definitions
├── library/                            # Custom template helpers
│   └── helpers.tmpl
├── template/                           # Generated output structure
│   └── {{.project_name}}/
│       ├── databricks.yml.tmpl
│       ├── variables.yml.tmpl
│       ├── resources/
│       ├── src/
│       └── docs/
├── ARCHITECTURE.md                     # This document
├── DEVELOPMENT.md                      # Developer notes and roadmap
└── README.md                           # Template description
```

### Why In-Place?

| Benefit | Description |
|---------|-------------|
| **Single source of truth** | No drift between template and example |
| **Easy testing** | `bundle init . --output-dir ../test` |
| **Lower maintenance** | One codebase, one set of changes |
| **Industry standard** | Matches Databricks' own template patterns |

### Testing Workflow

```bash
# From repo root
mkdir ../test-generated
databricks bundle init . --output-dir ../test-generated

# Test the generated bundle
cd ../test-generated/<project_name>
databricks bundle validate -t user
databricks bundle deploy -t user

# Cleanup
databricks bundle destroy -t user
cd ../..
rm -rf test-generated
```

---

## 3. User Prompts & Parameters

### Prompt Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TEMPLATE INITIALIZATION FLOW                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Q1: project_name                                                            │
│      "What is your project name?"                                            │
│      Default: my_data_project                                                │
│      Pattern: ^[A-Za-z][A-Za-z0-9_]*$                                        │
│                                                                              │
│  Q2: environment_setup                                                       │
│      "How many deployment environments do you need?"                         │
│      Options: full (user/stage/prod) | minimal (user/stage)                  │
│      Default: full                                                           │
│                                                                              │
│  Q3: include_dev_environment  [SKIP IF environment_setup = minimal]          │
│      "Include a shared development environment (dev)?"                       │
│      Options: yes | no                                                       │
│      Default: no                                                             │
│                                                                              │
│  Q4: compute_type                                                            │
│      "What compute type should resources use?"                               │
│      Options: classic | serverless | both                                    │
│      Default: classic                                                        │
│                                                                              │
│  Q5: cloud_provider  [SKIP IF compute_type = serverless]                     │
│      "Which cloud provider are you using?"                                   │
│      Options: azure | aws | gcp                                              │
│      Default: azure                                                          │
│                                                                              │
│  Q6: workspace_setup                                                         │
│      "Workspace topology for your environments?"                             │
│      Options: single_workspace | multi_workspace                             │
│      Default: single_workspace                                               │
│                                                                              │
│  Q7: uc_catalog_suffix                                                       │
│      "What suffix should be used for Unity Catalog names?"                   │
│      Catalogs: dev_<suffix>, stage_<suffix>, prod_<suffix> (pre-existing)    │
│      User target shares dev catalog with per-user schema prefixes            │
│      Default: my_domain                                                      │
│                                                                              │
│  Q8: include_permissions                                                     │
│      "Include comprehensive permissions/RBAC configuration?"                 │
│      Options: yes | no                                                       │
│      Default: yes                                                            │
│                                                                              │
│  Q9: configure_sp_now                                                        │
│      "Configure service principal IDs now?"                                  │
│      Options: yes | no (configure later via search-replace)                  │
│      Default: no                                                             │
│                                                                              │
│  Q10-12: Service Principal IDs  [CONDITIONAL]                                │
│      dev_service_principal   [SKIP IF configure_sp_now=no OR dev not incl.]  │
│      stage_service_principal [SKIP IF configure_sp_now=no]                   │
│      prod_service_principal  [SKIP IF configure_sp_now=no OR minimal mode]   │
│      Default: "" (empty, uses SP_PLACEHOLDER_<ENV>)                          │
│                                                                              │
│  Q13: include_cicd                                                           │
│      "Include CI/CD pipeline configuration?"                                 │
│      Options: yes | no                                                       │
│      Default: yes                                                            │
│                                                                              │
│  Q14: cicd_platform  [SKIP IF include_cicd = no]                             │
│      "Which CI/CD platform?"                                                 │
│      Options: azure_devops | github_actions | gitlab                         │
│      Default: azure_devops                                                   │
│                                                                              │
│  Q15: default_branch  [SKIP IF include_cicd = no]                            │
│      "What is the default branch for staging deployments?"                   │
│      Default: main                                                           │
│                                                                              │
│  Q16: release_branch  [SKIP IF include_cicd = no OR minimal mode]            │
│      "What is the release branch for production deployments?"                │
│      Default: release                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Parameter Reference Table

| # | Parameter | Type | Default | Required | Condition | Description |
|---|-----------|------|---------|----------|-----------|-------------|
| 1 | `project_name` | string | - | Yes | - | Bundle name, folder name, resource prefix |
| 2 | `environment_setup` | string | `full` | Yes | - | `full` = user+stage+prod; `minimal` = user+stage |
| 3 | `include_dev_environment` | string | `no` | Yes | environment_setup = full | Add optional dev target |
| 4 | `compute_type` | string | `classic` | Yes | - | `serverless`, `classic`, or `both` |
| 5 | `cloud_provider` | string | `azure` | Yes | compute_type != serverless | For node_type_id selection |
| 6 | `workspace_setup` | string | `single_workspace` | Yes | - | `single_workspace` = shared; `multi_workspace` = separate |
| 7 | `uc_catalog_suffix` | string | `my_domain` | Yes | - | Suffix for pre-existing env catalogs (e.g., `dev_sales`, `stage_sales`) |
| 8 | `include_permissions` | string | `yes` | Yes | - | Include RBAC (3-4 groups based on env) |
| 9 | `configure_sp_now` | string | `no` | Yes | - | Configure SPs during init or later |
| 10 | `dev_service_principal` | string | `""` | No | configure_sp_now = yes AND include_dev = yes | Dev environment SP app ID |
| 11 | `stage_service_principal` | string | `""` | No | configure_sp_now = yes | Stage environment SP app ID |
| 12 | `prod_service_principal` | string | `""` | No | configure_sp_now = yes AND environment_setup = full | Prod environment SP app ID |
| 13 | `include_cicd` | string | `yes` | Yes | - | Include CI/CD pipeline templates |
| 14 | `cicd_platform` | string | `azure_devops` | Yes | include_cicd = yes | CI/CD platform selection |
| 15 | `default_branch` | string | `main` | Yes | include_cicd = yes | Branch for staging deployments |
| 16 | `release_branch` | string | `release` | Yes | include_cicd = yes AND environment_setup = full | Branch for production deployments |

### Validation Patterns

All choice-based parameters use pattern validation instead of enum (avoids terminal rendering issues with dynamic option pickers).

| Parameter | Pattern | Error Message |
|-----------|---------|---------------|
| `project_name` | `^[A-Za-z][A-Za-z0-9_]*$` | "Project name must start with a letter and contain only letters, numbers, and underscores" |
| `environment_setup` | `^(full\|minimal)$` | "Please enter 'full' or 'minimal'" |
| `include_dev_environment` | `^(yes\|no)$` | "Please enter 'yes' or 'no'" |
| `compute_type` | `^(classic\|serverless\|both)$` | "Please enter 'classic', 'serverless', or 'both'" |
| `cloud_provider` | `^(azure\|aws\|gcp)$` | "Please enter 'azure', 'aws', or 'gcp'" |
| `workspace_setup` | `^(single_workspace\|multi_workspace)$` | "Please enter 'single_workspace' or 'multi_workspace'" |
| `uc_catalog_suffix` | `^[a-z][a-z0-9_]*$` | "Catalog suffix must be lowercase, start with a letter, and contain only letters, numbers, and underscores" |
| `include_permissions` | `^(yes\|no)$` | "Please enter 'yes' or 'no'" |
| `configure_sp_now` | `^(yes\|no)$` | "Please enter 'yes' or 'no'" |
| `include_cicd` | `^(yes\|no)$` | "Please enter 'yes' or 'no'" |
| `cicd_platform` | `^(azure_devops\|github_actions\|gitlab)$` | "Please enter 'azure_devops', 'github_actions', or 'gitlab'" |

---

## 4. Conditional Logic Design

### Environment Targets

| Configuration | Targets Generated |
|---------------|-------------------|
| `environment_setup = minimal` | user, stage |
| `environment_setup = full` + `include_dev = no` | user, stage, prod |
| `environment_setup = full` + `include_dev = yes` | user, dev, stage, prod |

### Compute Configuration

| Condition | Jobs Config | Pipeline Config |
|-----------|-------------|-----------------|
| `compute_type = serverless` | `environments` block only | `serverless: true` |
| `compute_type = classic` | `job_clusters` block only | `serverless: false` + `clusters` block |
| `compute_type = both` | Both blocks (classic commented as alt) | `serverless: true` + commented `clusters` |

### Permissions Blocks

| Condition | Effect |
|-----------|--------|
| `include_permissions = yes` | Include all `permissions` blocks in targets, all `grants` in schemas |
| `include_permissions = no` | Omit all `permissions` and `grants` blocks entirely |

### Service Principal Configuration

**Architecture**: Per-environment SPs with user target isolation

| Target | SP Required? | Run-As | SP Grants |
|--------|--------------|--------|-----------|
| `user` | No | Current user | None |
| `dev` | For CI/CD | Commented SP | In target override |
| `stage` | For CI/CD | SP | In target override |
| `prod` | For CI/CD | SP | In target override |

**Key Design**: Base `schemas.yml` has no SP grants. SP grants are added per-target in `databricks.yml` schema overrides. This ensures user target works without any SP configuration.

| Condition | Effect |
|-----------|--------|
| `configure_sp_now = yes` | Prompt for SP IDs, populate in variables.yml |
| `configure_sp_now = no` | Leave as `SP_PLACEHOLDER_<ENV>` with comment for search-replace |

### Workspace Configuration

| Condition | Effect |
|-----------|--------|
| `workspace_setup = single_workspace` | All targets use `{{workspace_host}}` (init-time workspace URL) |
| `workspace_setup = multi_workspace` | Non-user targets use `${var.<env>_workspace_host}` variables |
| `workspace_setup = multi_workspace` + Azure CI/CD | CI/CD includes `DATABRICKS_HOST` per environment |
| `workspace_setup = multi_workspace` + AWS/GCP CI/CD | No change (already has per-env `DATABRICKS_HOST`) |

### CI/CD Pipeline Generation

| Condition | Effect |
|-----------|--------|
| `include_cicd = yes` + `cicd_platform = azure_devops` | Generate `.azure/devops_pipelines/` with pipeline YAML |
| `include_cicd = yes` + `cicd_platform = github_actions` | Generate `.github/workflows/` with workflow YAML |
| `include_cicd = yes` + `cicd_platform = gitlab` | Generate `.gitlab-ci.yml` at project root |
| `include_cicd = no` | Skip all CI/CD directories; pipeline files output empty content |

**Directory skipping** is handled by `template/update_layout.tmpl` using the Go template `skip` function. Non-selected CI/CD directories (`.azure/`, `.github/`) are skipped entirely. GitLab uses a root file (`.gitlab-ci.yml`) with a template guard that outputs empty content when not selected.

**Authentication** is cloud-specific within pipeline templates:

| Cloud Provider | CI/CD Variables |
|----------------|----------------|
| Azure | `ARM_TENANT_ID`, `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET` (Service Principal) |
| Azure + multi_workspace | `ARM_TENANT_ID`, `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `DATABRICKS_HOST` per environment |
| AWS/GCP | `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET` (OAuth M2M) |

### File-Level Conditional Generation

| File/Section | Condition |
|--------------|-----------|
| `targets.dev` in databricks.yml | `include_dev_environment = yes` |
| `targets.stage` in databricks.yml | Always (stage is always present) |
| `targets.prod` in databricks.yml | `environment_setup = full` |
| Dev SP variable | `include_dev_environment = yes` |
| Stage SP variable | Always (stage is always present) |
| Prod SP variable | `environment_setup = full` |
| SP grants in schema overrides | Per-target in CI/CD targets only |
| `operations_group` variable | `environment_setup = full` |
| `job_clusters` sections in jobs | `compute_type = classic` OR `compute_type = both` |
| `environments` sections in jobs | `compute_type = serverless` OR `compute_type = both` |
| `clusters` in pipelines | `compute_type = classic` OR `compute_type = both` |
| All `permissions:` blocks | `include_permissions = yes` |
| All `grants:` blocks in schemas | `include_permissions = yes` (per-target only) |
| `.azure/` directory | `include_cicd = yes` AND `cicd_platform = azure_devops` |
| `.github/` directory | `include_cicd = yes` AND `cicd_platform = github_actions` |
| `.gitlab-ci.yml` content | `include_cicd = yes` AND `cicd_platform = gitlab` |
| CI/CD prod job/stage | `environment_setup = full` |
| `release_branch` in pipeline | `environment_setup = full` |
| `tests/` directory | `include_cicd = yes` |
| `requirements_dev.txt` | `include_cicd = yes` |
| Workspace host variables in variables.yml | `workspace_setup = multi_workspace` |
| `DATABRICKS_HOST` in Azure CI/CD env blocks | `workspace_setup = multi_workspace` AND `cloud_provider = azure` |

---

## 5. File Structure

### Template Repository Structure (Post-Conversion)

```
databricks-bundle-template/
├── databricks_template_schema.json          # Prompt definitions
├── library/
│   └── helpers.tmpl                         # Custom Go template helpers
├── template/
│   ├── update_layout.tmpl                   # Conditional directory/file skipping
│   └── {{.project_name}}/                   # Dynamic folder name
│       ├── databricks.yml.tmpl              # Main bundle config
│       ├── variables.yml.tmpl               # Shared variables
│       ├── .azure/devops_pipelines/         # Azure DevOps CI/CD pipeline
│       │   └── {{.project_name}}_bundle_cicd.yml.tmpl
│       ├── .github/workflows/               # GitHub Actions CI/CD workflow
│       │   └── {{.project_name}}_bundle_cicd.yml.tmpl
│       ├── .gitlab-ci.yml.tmpl              # GitLab CI/CD pipeline (root)
│       ├── resources/
│       │   ├── {{.project_name}}_ingestion.job.yml.tmpl
│       │   ├── {{.project_name}}_pipeline.pipeline.yml.tmpl
│       │   ├── {{.project_name}}_pipeline_trigger.job.yml.tmpl
│       │   └── schemas.yml.tmpl
│       ├── src/
│       │   ├── jobs/
│       │   │   ├── ingest_to_raw.py         # No templating needed (uses runtime vars)
│       │   │   └── transform_to_silver.py
│       │   └── pipelines/
│       │       ├── bronze.py
│       │       └── silver.py
│       ├── tests/                            # Unit test placeholder (for CI)
│       │   ├── __init__.py
│       │   └── test_placeholder.py
│       ├── templates/                        # Cluster config copy-paste templates
│       │   ├── cluster_configs.yml
│       │   └── README.md
│       ├── docs/
│       │   ├── CI_CD_SETUP.md.tmpl          # CI/CD setup guide
│       │   ├── PERMISSIONS_SETUP.md.tmpl    # Conditional RBAC content
│       │   └── SETUP_GROUPS.md.tmpl         # Conditional group setup
│       ├── .gitignore
│       ├── bundle_init_config.json.tmpl     # Preserves template config values
│       ├── requirements_dev.txt             # Dev dependencies (pytest)
│       ├── QUICKSTART.md.tmpl
│       └── README.md.tmpl
├── tests/                                   # Pytest test suite
│   ├── configs/                             # test configurations
│   ├── test_generation.py                   # L1: File generation tests
│   ├── test_content.py                      # L2: Content validation tests
│   └── test_cicd.py                         # CI/CD pipeline tests
├── ARCHITECTURE.md                          # This document
├── DEVELOPMENT.md                           # Developer notes and roadmap
└── README.md                                # Template repository README
```

### Generated Output Structure (Example)

When user runs: `databricks bundle init . --project-name my_etl_project`

```
my_etl_project/
├── databricks.yml
├── variables.yml
├── .azure/devops_pipelines/                 # (if azure_devops selected)
│   └── my_etl_project_bundle_cicd.yml
├── .github/workflows/                       # (if github_actions selected)
│   └── my_etl_project_bundle_cicd.yml
├── .gitlab-ci.yml                           # (if gitlab selected)
├── resources/
│   ├── my_etl_project_ingestion.job.yml
│   ├── my_etl_project_pipeline.pipeline.yml
│   ├── my_etl_project_pipeline_trigger.job.yml
│   └── schemas.yml
├── src/
│   ├── jobs/
│   │   ├── ingest_to_raw.py
│   │   └── transform_to_silver.py
│   └── pipelines/
│       ├── bronze.py
│       └── silver.py
├── tests/                                   # (if CI/CD included)
│   ├── __init__.py
│   └── test_placeholder.py
├── templates/
│   ├── cluster_configs.yml
│   └── README.md
├── docs/
│   ├── CI_CD_SETUP.md              # (content varies by platform)
│   ├── PERMISSIONS_SETUP.md        # (content varies by config)
│   └── SETUP_GROUPS.md             # (content varies by config)
├── .gitignore
├── bundle_init_config.json         # Template config used during generation
├── requirements_dev.txt            # (if CI/CD included)
├── QUICKSTART.md
└── README.md
```

---

## 6. Node Type Mapping

### Auto-Selection Based on Cloud Provider

| Cloud Provider | General Purpose Node | Used For |
|----------------|---------------------|----------|
| **Azure** | `Standard_DS3_v2` | Jobs, Pipelines |
| **AWS** | `i3.xlarge` | Jobs, Pipelines |
| **GCP** | `n1-standard-4` | Jobs, Pipelines |

### Implementation in helpers.tmpl

```go
{{- define "node_type_id" -}}
  {{- if eq .cloud_provider "azure" -}}
    Standard_DS3_v2
  {{- else if eq .cloud_provider "aws" -}}
    i3.xlarge
  {{- else if eq .cloud_provider "gcp" -}}
    n1-standard-4
  {{- end -}}
{{- end -}}
```

### Spark Version

All configurations will use: `17.3.x-scala2.13` (current LTS as of template creation)

---

## 7. Implementation Plan

### Activity 1: Template Infrastructure (Steps 1-3)

| Step | Task | Files | Description |
|------|------|-------|-------------|
| 1 | Create template schema | `databricks_template_schema.json` | Define all prompts, defaults, conditions |
| 2 | Create template helpers | `library/helpers.tmpl` | node_type_id, conditionals, utilities |
| 3 | Restructure folders | `template/{{.project_name}}/` | Move files into template structure |

### Activity 2: Core Configuration (Steps 4-6)

| Step | Task | Files | Description |
|------|------|-------|-------------|
| 4 | Convert databricks.yml | `template/.../databricks.yml.tmpl` | Targets, permissions, compute conditionals |
| 5 | Convert variables.yml | `template/.../variables.yml.tmpl` | SP config, catalog suffix, groups |
| 6 | Convert resources | `template/.../resources/*.tmpl` | Jobs, pipeline, schemas with conditionals |

### Activity 3: Source & Documentation (Steps 7-8)

| Step | Task | Files | Description |
|------|------|-------|-------------|
| 7 | Update source code | `template/.../src/**/*.py` | Update domain placeholder references |
| 8 | Convert documentation | `template/.../README.md.tmpl`, etc. | Project-specific README, guides |

### Activity 4: Template Metadata (Steps 9)

| Step | Task | Files | Description |
|------|------|-------|-------------|
| 9 | Create template docs | Update `DEVELOPMENT.md`, `README.md` | Developer notes, template description |

---

## Appendix A: Template Syntax Reference

### Go Template Basics

```go
{{/* Comment */}}

{{.variable_name}}                    // Access user input
{{template "helper_name" .}}          // Call helper

{{- if eq .var "value" }}             // Conditional
  content
{{- else if eq .var "other" }}
  other content
{{- end }}

{{- if and (eq .var1 "a") (eq .var2 "b") }}  // Multiple conditions
{{- end }}

{{range .list}}                       // Iteration
  {{.}}
{{end}}
```

### Built-in Helpers

| Helper | Description |
|--------|-------------|
| `{{workspace_host}}` | Current authenticated workspace URL |
| `{{user_name}}` | Current user's email/name |
| `{{short_name}}` | User's short name |
| `{{is_service_principal}}` | Boolean: is current identity an SP |
| `{{default_catalog}}` | Workspace's default Unity Catalog |

### Conditional Prompt (skip_prompt_if)

```json
{
  "cloud_provider": {
    "skip_prompt_if": {
      "properties": {
        "compute_type": {
          "const": "serverless"
        }
      }
    }
  }
}
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **DAB** | Databricks Asset Bundle |
| **LDP** | Lakeflow Declarative Pipelines (formerly DLT) |
| **UC** | Unity Catalog |
| **SP** | Service Principal |
| **Classic Compute** | Resource-specific clusters that spin up when job/pipeline runs |
| **Serverless Compute** | Databricks-managed compute, no cluster configuration needed |

---
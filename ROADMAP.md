# Roadmap

This document outlines the planned direction for the Databricks Bundle Template. It is a living document that evolves based on community feedback, real-world usage, and contributor interest.

## Vision

A comprehensive, community-driven Databricks Asset Bundles template that covers the most common real-world configurations for production data engineering projects. The template should be opinionated where it matters (secure defaults, proven patterns) and flexible where teams differ (branching strategies, compute choices, permission models).

## How to Influence the Roadmap

- **Propose ideas**: Open a discussion in [GitHub Discussions (Ideas)](https://github.com/vmariiechko/databricks-bundle-template/discussions/categories/ideas)
- **Request features**: File a [feature request](https://github.com/vmariiechko/databricks-bundle-template/issues/new?template=2-feature-request.yml)
- **Contribute**: Pick up a planned item and submit a PR (see [CONTRIBUTING.md](CONTRIBUTING.md))

Features with the most community interest and contributor champions move forward first.

---

## Feature Description Format

Each planned feature follows this structure:

```
### Feature Title
**Status**: Proposed | Planned | In Progress | Shipped
**Target**: vX.Y

Brief description of what this feature does and why it matters.

**Scope:**
- What's included in this feature

**Open questions:** (optional)
- Unresolved design decisions
```

---

## Planned Features

### Configurable Git Branching Model

**Status**: Proposed
**Target**: v1.2

The template currently uses a fixed branching model: `main` branch for staging deployments and a `release` branch for production deployments. Different teams follow different branching strategies, and the template should accommodate this.

**Scope:**
- New prompt for branching model selection during `bundle init`
- Support for common strategies: trunk-based development, GitFlow, release-branch
- CI/CD templates adapt triggers and branch references based on the selected model
- Generated documentation explains the selected branching strategy

**Open questions:**
- How many branching models to support at launch?
- Should custom/freeform branch mapping be an option?

### Git Flow Diagrams

**Status**: Proposed
**Target**: v1.1

Add visual diagrams illustrating the CI/CD branching strategies for each supported platform. The generated `CI_CD_SETUP.md` already references these diagrams but they have not been created yet.

**Scope:**
- Image-based flow diagrams for Azure DevOps, GitHub Actions, and GitLab
- Diagrams embedded in or linked from `CI_CD_SETUP.md`
- Diagrams adapt to the selected environment setup (full vs minimal)

### Template Version Tracking

**Status**: Proposed
**Target**: v1.1

Add metadata to generated resources so teams can track which template version was used and trace back to the source.

**Scope:**
- Custom tags on generated Databricks resources (jobs, pipelines)
- Template version recorded in `bundle_init_config.json`
- Optional git source info in job parameters

---

## Future Ideas

These are larger features that require more design work and community input before committing to implementation.

### Asset Sub-Templates (Plugins Layer)

**Status**: Proposed
**Target**: v2.0

Modular add-on templates that can be applied to an existing generated project to add new resources. This follows the pattern demonstrated in the Databricks [bundle-examples](https://github.com/databricks/bundle-examples) repo under `contrib/data_engineering` example template.

**Scope:**
- `assets/etl-pipeline/` - Add a new LDP pipeline with bronze/silver layers and DLT expectations
- `assets/ingest-job/` - Add a data ingestion job with error handling
- `assets/ml-pipeline/` - Add an ML training pipeline with experiment tracking
- `assets/dbt-project/` - Add dbt integration with Unity Catalog

**Usage pattern:**
```bash
# Initialize base project first
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template

# Later, add a new pipeline to the existing project
cd my_project
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/etl-pipeline
```

**Open questions:**
- How do asset templates reference existing variables from `variables.yml`?
- Should assets modify `databricks.yml` or create standalone resource files?
- How to handle naming conflicts with existing resources?

### Advanced Permissions Profiles

**Status**: Proposed
**Target**: v2.0

Replace the current yes/no permissions toggle with a set of predefined profiles that cover more organizational patterns.

**Scope:**
- **Full** (4 groups): developers, qa_team, operations_team, analytics_team
- **Team** (2 groups): developers, analytics_team
- **Minimal** (owner only): no group-based permissions, only bundle owner
- **None**: no permissions blocks at all

**Open questions:**
- Should custom group names be configurable?
- How to handle migration from yes/no to profiles without breaking existing users?

### Bundle UUID and Git Source Tracking

**Status**: Proposed
**Target**: v2.0

Enhanced traceability for generated bundles, useful in large organizations managing many bundle deployments.

**Scope:**
- Unique bundle UUID generated at init time
- Git repository URL and commit hash recorded in bundle metadata
- Traceable from deployed resources back to template version and configuration

---

## Completed

### v1.1.0

#### Workspace Topology Configuration

**Status**: Shipped

Configurable workspace topology: single shared workspace (default) or separate workspaces per environment.
Multi-workspace mode generates variable-based hosts in `databricks.yml` and adds `DATABRICKS_HOST` to Azure CI/CD pipelines.

**Scope:**
- New `workspace_setup` prompt (`single_workspace` / `multi_workspace`)
- Placeholder-based workspace hosts pattern `WORKSPACE_HOST_PLACEHOLDER_*` in `databricks.yml.tmpl`
- Azure CI/CD updated with per-environment `DATABRICKS_HOST`
- Updated documentation across README, QUICKSTART, CI_CD_SETUP
- 4 new test configurations for multi-workspace scenarios (19 total configs)

### v1.0.0

See [CHANGELOG.md](CHANGELOG.md) for the full list of features shipped in v1.0.0, including:

- Multi-environment deployment (user/dev/stage/prod)
- Configurable compute (classic/serverless/both)
- Unity Catalog with medallion architecture
- Optional RBAC with environment-aware groups
- Service principal architecture
- CI/CD for Azure DevOps, GitHub Actions, GitLab
- Cloud support for Azure, AWS, GCP
- 1531 tests across 15 configurations

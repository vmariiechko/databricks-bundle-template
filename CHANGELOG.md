# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.1] - 2026-02-25

### Changed

#### Branching Strategy Documentation
- Renamed branching strategy from "hybrid Release Flow tailored for DataOps" to "environment-branch promotion model based on GitLab Flow"
- Added links to [GitLab Flow](https://about.gitlab.com/topics/version-control/what-is-gitlab-flow/), [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow), and [Gitflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) documentation in generated CI/CD setup guide
- Expanded DEVELOPMENT.md Design Decision #9 with strategy comparison, community references, and rationale

### Removed
- Removed "Configurable Git Branching Model" from ROADMAP.md (complexity not justified; rationale documented in DEVELOPMENT.md)

### Fixed
- Updated ROADMAP.md "Git Flow Diagrams" to reflect shipped status (diagrams already exist in template)
- Renamed diagram image files for consistency (`dataops-release-flow-*` → `branching-strategy-*`)

## [1.1.0] - 2026-02-15

### Added

#### Workspace Topology Configuration
- New `workspace_setup` prompt: choose between `single_workspace` (default) and `multi_workspace`
- Multi-workspace mode generates variable-based workspace hosts per target (`${var.stage_workspace_host}`, etc.)
- Workspace host variables with `WORKSPACE_HOST_PLACEHOLDER_*` pattern in `variables.yml`
- Azure CI/CD pipelines include `DATABRICKS_HOST` per environment in multi-workspace mode
- Dedicated "Multi-Workspace Deployment" section in generated CI/CD setup guide
- 4 new test configurations for multi-workspace scenarios (19 total configs)

## [1.0.0] - 2026-02-07

Initial public release.

### Added

#### Template Core
- Multi-environment deployment with two modes:
  - **Full** mode: user, stage, prod targets (with optional dev)
  - **Minimal** mode: user, stage targets
- Configurable compute types: classic clusters, serverless, or both
- Unity Catalog integration with medallion architecture (bronze, silver, gold schemas)
- Per-user schema isolation in the user target (e.g., `jsmith_bronze`)
- Cloud provider support for Azure, AWS, and GCP with auto-selected node types

#### Permissions & Security
- Optional RBAC with environment-aware group permissions (3 or 4 groups)
- Service principal architecture with per-environment isolation
- User target works immediately without any SP configuration
- Configurable SP IDs during init or deferred via `SP_PLACEHOLDER` search-replace

#### CI/CD Pipelines
- Azure DevOps pipeline templates with YAML-based pipelines
- GitHub Actions workflow templates
- GitLab CI/CD pipeline templates
- Cloud-specific authentication (Azure ARM SP vs OAuth M2M for AWS/GCP)
- Configurable default and release branch names
- Unit test execution and JUnit reporting in all pipelines

#### Generated Documentation
- Project README with environment-specific quickstart
- QUICKSTART.md with step-by-step deployment guide
- CI_CD_SETUP.md with platform-specific CI/CD configuration
- PERMISSIONS_SETUP.md with RBAC setup instructions
- SETUP_GROUPS.md with group creation guide

#### Template Infrastructure
- 15 interactive prompts with conditional logic (`skip_prompt_if`)
- Custom Go template helpers (`node_type_id`, `cli_version`)
- Conditional file/directory generation via `update_layout.tmpl`
- `bundle_init_config.json` for preserving template configuration values
- Cluster config copy-paste templates for quick customization

#### Testing
- Pytest test suite with 1531 tests across 15 configurations
- L1 tests: file existence, directory structure, no `.tmpl` leftovers
- L2 tests: YAML syntax, environment targets, content validation
- CI/CD tests: pipeline generation, auth patterns, branch references

[1.1.1]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.1.1
[1.1.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.1.0
[1.0.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.0.0

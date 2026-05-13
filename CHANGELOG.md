# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.7.1] - 2026-05-13

### Fixed
- **Asset `dbx-ro-query` stdout/stderr encoding**: `configure_text_streams()` reconfigures both output streams to UTF-8 with `errors="replace"` at startup, preventing `charmap` codec errors when query results contain non-ASCII characters (Greek, Cyrillic, emoji, etc.).

### Changed
- **Asset `dbx-ro-query` install message**: added a "Set your warehouse ID" step to the post-install `success_message`. First-time users now see the `databricks warehouses list` lookup command and the `DATABRICKS_WAREHOUSE_ID` export pattern immediately after wiring, before the smoke-check step.

## [1.7.0] - 2026-05-10

### Added
- **Asset `dbx-ro-query` per-agent references**: new `<target_dir>/skills/dbx-ro-query/references/` subfolder holding agent-runtime-specific operational tips. Files are loaded on demand by the parent `SKILL.md` when an agent hits a runtime quirk; this matches the [agentskills.io](https://agentskills.io) `references/` convention.
  - `agent-claude-code.md`: 2-minute `Bash` tool default timeout (warehouse cold-start hint) plus an exit-code-echo pattern for parseable rejection evidence.
  - `agent-codex.md`: sandbox `network_access = true` setting; `login: false` on `shell_command` for clean captured output; warning against `Measure-Command` PowerShell wrappers; warehouse env var note. Validated by a live Codex test session against the released v1.6.0 install.
  - `agent-cursor.md`: ready-to-paste `.cursor/rules/dbx-ro-query.mdc` rule snippet (Cursor does NOT auto-discover `.cursor/skills/`); terminal runtime notes confirming exit codes are surfaced natively. Validated by a live Cursor 3.3.x / Composer 2 test session.
- **Asset `dbx-ro-query` README troubleshooting**: documented two install-time pitfalls surfaced by independent Codex and Cursor test runs. The first is a generic Databricks CLI quirk: `bundle init` fails resolving a stale `DATABRICKS_CONFIG_PROFILE`; workaround is to re-point the env var at a valid profile. The second is Codex-specific: sandbox blocks the GitHub URL fetch unless `network_access = true` is set.

### Changed
- **Asset `dbx-ro-query` SKILL.md operational notes**: the runtime-specific bullet that named Codex inline has been replaced with a generic on-demand pointer to the new `references/` folder. The remaining operational notes are agent-agnostic. Keeps `SKILL.md` from drifting toward a multi-vendor compatibility matrix as more agents are documented.
- **Asset `dbx-ro-query` `success_message`**: each per-agent section now points at its `references/agent-<name>.md` file rather than restating wiring inline. The Cursor section explicitly calls out that `.cursor/skills/` is not auto-discovered; users see this at install time, not after their first failed query.

## [1.6.0] - 2026-05-09

### Added
- **Asset `dbx-ro-query`**: dependency-free Python wrapper around `databricks experimental aitools tools query` that gives LLM agents a guarded read-only SQL window into a Databricks workspace. Single file, no third-party dependencies.
- **Asset guard rules**: allow-lists `SELECT` / `WITH` / `SHOW` / `DESCRIBE` / `DESC` / `EXPLAIN`; block-lists every destructive verb; strips block comments, line comments, and quoted strings before validation so smuggling attempts (`SELECT '/* DROP TABLE x */ 1'`, stacked statements like `SELECT 1; DROP TABLE foo`) are rejected.
- **Asset output formats**: `auto` / `scalar` / `lines` / `csv` / `tsv` / `json`. The shape-aware `auto` mode collapses 1x1 results to a scalar value and Nx1 results to one-per-line, saving tokens in agent contexts.
- **Asset layout**: follows the [agentskills.io](https://agentskills.io) canonical layout. `<target_dir>/skills/dbx-ro-query/SKILL.md` is the agent contract; `<target_dir>/skills/dbx-ro-query/scripts/dbx-ro-query.py` is the bundled runner. Default `target_dir` is `.agents` (vendor-neutral); override to `.claude` / `.codex` / `.cursor` / `.gemini` for single-agent auto-discovery. The post-install message prints the exact wiring one-liner per agent.

### Changed
- **Asset `sdp-checkpoint-recovery` documentation**: clarified `startingVersion` behavior in the in-bundle README. After a checkpoint reset, the fresh stream defaults to version 0 of the new Delta table (all historical data); to skip historical data or avoid duplicate Bronze events, add `.option("startingVersion", "latest")` to the source `readStream` before running the reset, since `startingVersion` is only applied when no checkpoint exists.
- **Asset framework smoke test**: `tests/assets/test_framework.py` now accepts `SKILL.md` as installed-tree documentation in addition to `README.md`, so agentskills.io-style skill assets are not forced to ship a redundant README. Renamed `test_target_dir_has_readme` to `test_asset_ships_documentation`.

## [1.5.0] - 2026-04-25

### Added
- **Asset Library framework**: a new `assets/` directory hosting self-contained sub-templates installable via `databricks bundle init <repo-url> --template-dir assets/<asset-name>`. Each asset is standalone (own schema, own README, own tests) and can be installed into any Databricks bundle, not only ones generated by the core template. Framework conventions documented in [CONTRIBUTING.md](CONTRIBUTING.md#adding-an-asset); design rationale in [ARCHITECTURE.md §8](ARCHITECTURE.md#8-asset-library--plugins-layer) and [DEVELOPMENT.md Design Decision #15](DEVELOPMENT.md). End-user catalog at [ASSETS.md](ASSETS.md).
- **First asset: `sdp-checkpoint-recovery`**: Python scripts for recovering a Lakeflow Spark Declarative Pipeline from the `DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE` error by resetting the checkpoint selection for specific flows via the Databricks Pipelines API.
- **Asset test infrastructure**: framework-level smoke tests (`tests/assets/test_framework.py`) auto-discovering every asset; shared install helper in `tests/assets/conftest.py`; per-asset deep tests convention at `tests/assets/test_<asset>.py`; per-asset configs at `tests/configs/assets/<asset>.json` with variants as `<asset>_<variant>.json`.
- **PR and issue templates updated** to recognize asset-related changes as a distinct area from core template changes.
- **Ruff configuration** added to `pyproject.toml`: line length 100, target `py311`, Google docstring convention, and a curated rule set (pycodestyle, pyflakes, isort, bugbear, comprehensions, pyupgrade, naming). Per-file ignores for the workspace-notebook script that interleaves imports between `# COMMAND ----------` cells. Tooling-only change; no behavior impact on generated bundles or the asset.

### Changed
- **Corrected Databricks pipeline terminology** throughout documentation, generated project templates, and asset docs: the official product name is "Lakeflow Spark Declarative Pipelines" (short form SDP or Lakeflow SDP). Replaces the outdated "Lakeflow Declarative Pipelines" / "LDP" usages and updates relevant docs.databricks.com URLs.

## [1.4.0] - 2026-04-08

### Changed
- **Renamed "Databricks Asset Bundles" to "Declarative Automation Bundles"** across all documentation, templates, and metadata — aligns with the [official Databricks rename](https://docs.databricks.com/aws/en/dev-tools/bundles/) announced March 16, 2026. The DABs acronym remains unchanged
- **Bumped minimum Databricks CLI version** from v0.274.0 to v0.296.0 to support the direct deployment engine configuration
- **Enabled direct deployment engine** (`bundle.engine: direct`) in generated bundles, replacing the Terraform-based deployment backend for faster, simpler deployments without external dependencies
- **Removed `*.tfstate` patterns from `.gitignore`** — no longer needed with the direct engine; `.databricks/` already covers state files
- **Updated documentation URLs** to current `docs.databricks.com/aws/en/` format

### Fixed
- **Photon now enabled on user target for serverless compute** — serverless pipelines require `photon: true`; previously the user target hardcoded `false` regardless of compute type, causing deployment failures with serverless and both compute modes

## [1.3.0] - 2026-03-05

### Added
- **`_template_version` field in generated `bundle_init_config.json`** — all generated projects now record which template version was used. Useful for tracking generated project provenance and knowing when to regenerate.
- **`cicd_platform_display` helper in `library/helpers.tmpl`** — reusable helper returning the human-readable CI/CD platform name (e.g. `GitHub Actions` instead of `github_actions`). Used in generated README.
- **Example repository companion** — pre-generated example at [databricks-bundle-template-example](https://github.com/vmariiechko/databricks-bundle-template-example) (AWS + GitHub Actions + classic compute, no RBAC), linked from template README.
- **`scripts/regenerate-example.sh`** — maintainer script to regenerate the example repo from the current template state. Uses Python for cross-platform file sync. See `DEVELOPMENT.md` for usage.
- **`scripts/example_repo_config.json`** — generation config for the example repository.
- **Example repo regeneration runbook** in `DEVELOPMENT.md` — documents when and how to update the example repo, including the release checklist step for `_template_version`.

### Fixed
- **Generated README CI/CD section** now shows human-readable platform name (e.g. `GitHub Actions`) instead of the raw config value (`github_actions`)
- **Generated `databricks.yml` documentation link** updated to current `/aws/en/` URL format

## [1.2.0] - 2026-03-01

### Changed

#### Permissions & Groups Model Revision
- **User target no longer has group-based schema grants** — `databricks bundle deploy -t user` now works immediately without creating groups. Groups are only required for dev/stage/prod targets
- **Analytics team now has read access to all schemas** (bronze, silver, gold) in all non-user targets. Previously analytics_team only had access to silver and gold schemas in dev, stage, and prod targets
- Updated access control matrix in PERMISSIONS_SETUP.md to reflect the user target having no group dependencies
- Updated SETUP_GROUPS.md to clarify that groups are only required for non-user targets and that analytics_team has access to all schemas
- Updated QUICKSTART.md, README.md troubleshooting, and group prerequisite sections to clarify user target has zero group dependencies
- Added multi-workspace group guidance to SETUP_GROUPS.md (account-level groups, SCIM provisioning, identity federation)

### Added
- New `full_no_permissions.json` test configuration (full+dev mode with permissions=no) — 20 total test configs
- New tests: `test_user_target_no_schema_grants`, `test_analytics_team_has_bronze_access`, `test_resources_block_structure`
- Enhanced PERMISSIONS_SETUP.md `include_permissions=no` section with step-by-step manual setup guide, SQL grant examples, and Databricks documentation links
- Conditional skip for `docs/SETUP_GROUPS.md` via `update_layout.tmpl` when `include_permissions=no`

### Fixed
- **YAML structure bug**: When `include_permissions=no`, `resources:` was inside the permissions conditional, causing `jobs:` overrides to be incorrectly nested under `variables:` instead of `resources:` in all targets. Fixed by making `resources:` unconditional with only `schemas:` grants wrapped in the permissions conditional

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

[1.7.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.7.0
[1.6.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.6.0
[1.5.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.5.0
[1.4.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.4.0
[1.3.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.3.0
[1.2.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.2.0
[1.1.1]: https://github.com/vmariiechko/databricks-bundle-template/blob/main/CHANGELOG.md#111---2026-02-25
[1.1.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.1.0
[1.0.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.0.0

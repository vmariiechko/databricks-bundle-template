# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **Asset `sdp-expectation-notifications`**: notification hygiene revision, grounded in a two-day live investigation (2026-07-17/18, serverless SDP on a non-development-mode target). The v1.11.0 hook notified on every qualifying `flow_progress` event, and the platform emits expectation counts once per microbatch, so one failing expectation notified once per file on a multi-file backlog (measured: 4 notifications for one expectation in one update, counts summing exactly to the single-batch total), re-notified everything on full refresh, and fired within ~70s of every arriving file on a continuous pipeline. Wired to a real channel, that floods.
  - **The hook now throttles: at most one notification per (pipeline, dataset, expectation) per `dq_notify.throttle_seconds` (default 3600).** Two time-aware layers, both fail-open (any state error notifies rather than stays silent): an in-memory last-notified map (always on; timestamp-based, not a seen-set, because continuous pipelines keep one Python process alive and a notify-once set would go silent forever; validated live NOTIFY -> SUPPRESS in window -> NOTIFY after window on a continuous Auto Loader pipeline) and optional durable marker files under `<dq_notify.state_dir>/dq_notify_state/<pipeline>/<dataset>__<expectation>.json` in an existing UC Volume (one human-readable JSON per expectation, overwritten on notify, never growing; validated across full refreshes and process restarts: 12 raw events across two consecutive full refreshes reduced to 2 notifications). State scopes per pipeline automatically from the event's own `origin` (`pipeline_name`/`pipeline_id`, observed present in hook events), so the same code serves any number of pipelines and cannot cross-suppress (validated with two pipelines sharing one state root). The asset deliberately ships no volume resource: state that describes operations should outlive any one bundle, so a new `state_volume_path` prompt (placeholder default = in-memory only) points under a volume the user already owns. `dq_notify.throttle_seconds: "0"` restores the old per-microbatch behavior.
  - **Webhook channels and secrets.** `dq_notify.channel_format` selects the hook's payload: `slack` (validated end to end: secret scope -> `dbutils.secrets.get` -> throttled hook -> channel message, HTTP 200), `teams` (documented Workflows Adaptive Card envelope, marked doc-confirmed, not live-tested), or `generic` (plain JSON with the violation fields). Webhook URLs are credentials, so the shipped path resolves them from a secret scope via `dbutils.secrets.get` at module level, which works in serverless SDP pipeline Python (validated live), with two traps documented from observation: `{{secrets/scope/key}}` in pipeline configuration is NOT interpolated (the literal string arrives), and a missing scope raises `IllegalArgumentException`, which the code catches to degrade to print-only without touching the pipeline (validated). Plain `dq_notify.webhook_url` remains as the labeled demo-only fallback.
  - **Backstop alert defaults and documentation.** `notify_on_ok: true` is the new shipped default: Alerts v2 notifies exactly once per state transition (measured: 9 consecutive TRIGGERED evaluations, 1 email), which means persistent failures mask new ones until recovery, and the single OK email (measured: exactly one) closes that loop. `retrigger_seconds` ships commented with measured semantics (re-send at the first evaluation past each window; a deliberate escalation knob, suggested 86400 for critical pipelines) and a commented `destination_id` line documents Slack/Teams/PagerDuty delivery via workspace notification destinations. New measured operational note: a broken sweep query flips the alert to ERROR and emails on EVERY evaluation until fixed (5 emails in 4 minutes observed), so the backstop cannot die silently but its failure mode is itself a flood.
  - **README corrections and additions from measurement:** `hook_progress` records ENABLED, FAILED, and DISABLED transitions (v1.11.0 claimed enable-state only); the post-update teardown grace budget is seconds (a ~1s/event hook drained 5 queued events with zero loss; a 20s/event hook lost 6 of 6 under natural teardown), closing two formerly open questions; the in-hook `spark.sql()` write door is definitively shut (`INSERT INTO` fails with `UNSUPPORTED_SPARK_SQL_COMMAND`; allowlist: SELECT, DESCRIBE, SHOW variants, USE) while UC Volume file I/O from a hook works (create/overwrite/read/exists/listdir/stat; append fails with `OSError Errno 29`), which is exactly the surface the durable throttle uses; an update that processes no new rows emits no expectation events (re-running on static data never re-notified); continuous pipelines auto-start on `bundle deploy`. The skill grows a third non-negotiable rule (the throttle stays time-aware and fail-open), the adaptation reference covers throttle/window/state/channel/secret decisions and multi-pipeline rollout, and self-verify gains a marker-file check (suppression proof: a rerun inside the window must not advance `last_notified_at`).
  - Tests extended accordingly: the throttle decision logic is exercised offline by exec-ing the pure helpers from the installed source against a temp state dir (suppress within window, durable across simulated process restarts, per-pipeline scoping, marker overwrite, `0` disables, empty state dir writes nothing), payload formats and guarded secret resolution are asserted, and the no-`spark.sql()`-calls AST guard still holds over the reworked source.

## [1.11.0] - 2026-07-11

### Added
- **Asset `sdp-expectation-notifications`**: per-expectation data-quality notification for Lakeflow Spark Declarative Pipelines, packaged as the validated pair the pattern requires: a native event hook as the fast path and one DABs-managed Alert v2 as the guaranteed path. Event hook delivery is explicitly best-effort (the platform waits a fixed, non-configurable period before terminating pipeline compute and does not guarantee every hook runs on every event), so neither half ships without the other.
  - The reference pipeline ingests the public `samples.nyctaxi.trips` as a streaming table with one deliberately tight WARN expectation (`demo_short_trip`: `trip_distance < 5`, a tripwire chosen to fail on the healthy sample, not a sensible quality rule), so both notification paths fire on the first run with no extra setup. The `@dp.on_event_hook` notifier filters `flow_progress` events for expectation results with `failed_records > 0` and notifies via `print` plus an optional `requests` webhook (configured through `dq_notify.webhook_url`; failures are caught and printed so a broken endpoint never counts as a hook failure). The hook stays on the platform's supported notification surface: the live validation run proved `spark.sql()` writes are rejected inside SDP pipeline Python (`CREATE TABLE` fails with `UNSUPPORTED_SPARK_SQL_COMMAND`; the patched `spark.sql()` rejects the parameterized-query `args=` kwarg), and the asset's tests assert no `spark.sql(` call exists in the shipped source.
  - The pipeline resource publishes the event log to a queryable UC table (`event_log` block, table `dq_notifications_event_log`); the backstop alert resource (`resources/<pipeline_resource_key>_backstop.alert.yml`, key derived from the pipeline key) sums `failed_records` from `flow_progress` events over a trailing 1-day window (past-time-window aggregation, not latest-row, so violations cannot fall between sweeps when cadences differ), triggers on `GREATER_THAN 0`, emails the configured subscription, and schedules itself daily at 06:00 UTC via quartz cron. `warehouse_id` and `notification_email` prompts default to placeholders replaced before deploy; the README cross-references the `monitoring-sql-warehouse` asset as the cost-correct warehouse for the sweep.
  - Validated end to end on a live serverless SDP workspace (2026-07-11, CLI v0.297.2): hooks run on serverless pipelines (`hook_progress` rows confirmed), the hook's printed counts matched the event log exactly per update (3,003 failed / 18,929 passed on the sample), and the backstop delivered end to end (query value, scheduled execution in query history, `TRIGGERED` state via `alerts-v2 get-alert`, and actual email receipt all agreeing). The docs carry the honest findings: `hook_progress` records only enable/disable state (per-invocation output exists only in the driver log, which has no CLI or SQL surface), `mode: development` keeps pipeline compute warm and masks the teardown that makes hook delivery best-effort, and open questions (automatic drop under default teardown, grace-period size, literal `INSERT` from a hook, full `comparison_operator` enum) are stated as open rather than papered over.
  - **Companion agent skill (dual-door asset).** Alongside the reference, the asset installs an agent skill at `<skill_dir>/skills/sdp-expectation-notifications/` (`SKILL.md` + `references/adapt-the-pattern.md` + `references/self-verify.md`) that instructs a coding agent to wire the hook-plus-backstop pattern into the user's own SDP pipeline. The skill enforces two non-negotiable rules (the hook is never the only notification path; never write Delta from inside a hook), splits the work at a deploy/run trust boundary (Phase A adapt and validate with no workspace changes; Phase B deploy and live-verify, defaulting to human-in-the-middle), covers the SQL-pipeline branch (hooks are Python-only; a SQL pipeline carries the hook in a small Python library file), and ships verification checks that separate what an agent can machine-verify (event-log queries, alert state via CLI) from what only the user can observe (driver-log output, inbox delivery). Eight prompts (`target_dir`, `pipeline_resource_key`, `pipeline_name`, `catalog`, `schema`, `warehouse_id`, `notification_email`, `skill_dir`) with safe defaults.

### Changed
- **Asset `pyspark-test-runner` (docs only)**: reframed the SKILL and README default test strategy so the agent-facing guidance matches what the digest is built for. The broad grouped run (no `-x`) is now the default, since `-x` stops pytest at the first failure and leaves the signature dedup nothing to collapse; `-x` is documented as an opt-in for drilling on a single suspected failure. No wrapper behavior change: `-x` was already off by default and the script is untouched.

## [1.10.0] - 2026-06-20

### Added
- **Asset `pyspark-test-runner`**: single-file Python wrapper around `pytest` for local PySpark suites, packaged as an agentskills.io-style skill (`SKILL.md` + `scripts/run-pyspark-tests.py`) so a coding agent's context window stays bounded when a suite floods with repetitive failures. The wrapper script adds no dependencies of its own (standard library, Python 3.9+); the suite it runs needs pytest and PySpark installed in the project interpreter.
  - The wrapper runs `python -m pytest` from the project root, writes the full stdout and stderr to a log file (`<project-root>/.pyspark-test-logs/` by default, overridable via `PYSPARK_TEST_LOG_DIR`), and prints only a compact digest built from the JUnit XML report rather than scraping interleaved Spark/JVM stderr. The digest carries the result, exit code, counts, runnable pytest node ids (reconstructed from JUnit `file` + `classname` + `name`), and failures deduplicated by a normalized signature: many tests failing with one root cause collapse to a single `SIGNATURE 1 of N (K tests)` block instead of K tracebacks.
  - Output is bounded on every axis: the failing-tests list is capped (`--max-failures-listed`, default 20), the top signatures are shown (`MAX_SIGNATURES`, fixed at 3), each representative traceback is head+tail trimmed so the call site and the final exception line both survive (`--excerpt-lines`, default 40), and a hard total-output backstop clips the whole digest as a last resort. Full detail always stays in the log.
  - Edge cases handled: collection/import errors (exit 2), no tests collected (exit 5), and other pytest exit codes mapped to a readable `Result` plus a one-line hint; hung runs killed after `--timeout-sec` (default 900) with a bounded reap guard so a stuck JVM child cannot make the wrapper hang; missing, empty, or malformed JUnit XML falls back to a bounded log tail without crashing; non-UTF8 output decoded with `errors="replace"`. Interpreter resolution prefers a project `.venv`/`venv` then the current interpreter (`--python` to override), and sets `PYSPARK_PYTHON`/`PYSPARK_DRIVER_PYTHON` so Spark workers match.
  - Single prompt (`target_dir`, default `.agents`) mirroring the `dbx-ro-query` skill+script layout. Local pytest only: no Databricks deploy, run, or workspace auth, and out of scope by design are `pytest-xdist` aggregation, rerun/flaky-plugin outcomes, and coverage.
- **`RELEASING.md`**: canonical release checklist. Documents the two version markers (`pyproject.toml` and the generated bundle's `_template_version`), the changelog finalization step (rename `[Unreleased]` to `[X.Y.Z] - <date>` in the PR before merge), the annotated-tag and GitHub-release steps after merge, and a fill-in release-notes template.
- **`tests/test_release_metadata.py`**: version guard test. Asserts the two version markers and the latest finalized `CHANGELOG.md` version all agree, and that an `[Unreleased]` section is always present. Runs in CI on every pull request, so a partial or forgotten version bump fails before merge.

### Changed
- **`.github/PULL_REQUEST_TEMPLATE.md`**: added an optional "Release" block (changelog finalized, both version markers bumped, guard test passes) so release facts surface at review time instead of being buried in free-text.
- **`CONTRIBUTING.md` and `AGENTS.md`**: clarified that changelog entries stay under `[Unreleased]` until a release finalizes them, and added pointers to `RELEASING.md`. `AGENTS.md` gained a Release Process subsection.

## [1.9.0] - 2026-06-06

### Added
- **Asset `sdp-quarantine-pattern`**: Lakeflow Spark Declarative Pipeline demonstrating the inverse-expectations quarantine pattern on the public `samples.nyctaxi.trips` dataset.
  - `raw_trips` ingests the read-only public sample as a streaming table (bronze schema). `clean_trips` applies the critical (drop) expectations; `quarantine_trips` applies their inverse, capturing exactly the rows the clean table drops; both land in the silver schema, following medallion schema separation. The schemas are the medallion layers; the table names describe content. Advisory (warn) expectations log to the pipeline event log without dropping. The public sample contains naturally invalid rows, so quarantine is populated on the first run.
  - Drop predicates are written NULL-safe (total) so `expect_all_or_drop(drop)` and `expect_all_or_drop(NOT(drop))` partition the input exactly once. The README documents the three-valued-logic trap that breaks naive inverse expectations. Validated live on serverless SDP: the partition invariant held exactly across all cases (21,847 clean + 85 quarantine = 21,932 raw at baseline) and a NULL drop column routed to quarantine without leaking into the clean table.
  - Rules live in a declarative `expectations.json`; a pure helper `expectations.py` (no pyspark import) loads them and derives the clean predicate (`build_silver_expr`) and its inverse (`build_quarantine_expr`). The asset also ships an offline unit-test suite (`<target_dir>/tests/`: a real local-Spark `pytest` that proves the partition invariant and NULL routing on crafted edge rows, modeling `expect_all_or_drop` keep-on-NULL semantics with `IS NOT FALSE`). The pipeline source is a Databricks notebook referenced from `resources/<pipeline_resource_key>.pipeline.yml` via a path relative to the resource file.
  - The resource publishes a queryable event log (`event_log` block, table `quarantine_pipeline_event_log`) and ships `event_log_queries.sql` to parse per-expectation passed/failed counts; cost/trace tags identify the pipeline as created by this asset. In-bundle usage doc at `docs/sdp-quarantine-pattern/README.md`. All three pipeline tables are named with fully qualified `catalog.schema.table` identifiers so the source reads consistently and the in-pipeline dependencies resolve unambiguously; catalog, both schemas, and the source table flow to the pipeline through the resource `configuration` block (`quarantine.source` parameterizes the ingest so a test run can point at a curated dataset).
  - **Companion agent skill (dual-door asset).** Alongside the reference pipeline, the asset installs an agent skill at `<skill_dir>/skills/sdp-quarantine-pattern/` (`SKILL.md` + `references/adapt-the-pattern.md` + `references/self-verify.md`) that instructs a coding agent to apply the quarantine pattern to the user's own dataset and verify it. The skill enforces the NULL-safe drop-predicate rule, splits the work at a deploy/run trust boundary (Phase A adapt + run the offline unit tests with no workspace; Phase B deploy and live-verify, defaulting to human-in-the-middle and delegating deploy/run mechanics to the runtime), and ships a three-tier verification ladder: offline rule unit tests (primary), live read-only audits (partition invariant + a NULL-in-clean check per dropped column), and an optional integration test via source parameterization. It includes a kickoff prompt template, is runtime-neutral about read-only query access (it uses whatever capability the agent's runtime provides), and states its limits: it applies and verifies a pattern, it does not guarantee correctness on arbitrary data. Seven prompts (`target_dir`, `pipeline_resource_key`, `pipeline_name`, `catalog`, `bronze_schema`, `silver_schema`, `skill_dir`) with safe defaults.

## [1.8.0] - 2026-05-30

### Added
- **Asset `monitoring-sql-warehouse`**: Declarative Automation Bundle resource defining a small, dedicated serverless SQL warehouse tuned for bursty workloads (scheduled Databricks Alerts, monitoring queries, ad-hoc health checks).
  - Defaults to `cluster_size: 2X-Small`, `warehouse_type: PRO`, `enable_serverless_compute: true`, and `auto_stop_mins: 1` (the serverless minimum verified end-to-end via DABs deploy; sub-minute values silently revert to the platform default).
  - Channel pinned to `CHANNEL_NAME_CURRENT` so Databricks SQL Preview-channel rollouts cannot change query behavior under monitoring workloads. Cost-attribution tags `workload=monitoring-alerts` and `created_by=dabs-asset/monitoring-sql-warehouse` ship by default for traceability in usage reports.
  - Five prompts (`target_dir`, `warehouse_resource_key`, `warehouse_name`, `cluster_size`, `auto_stop_mins`) with safe defaults; the resource file lands at `<target_dir>/<warehouse_resource_key>.sql_warehouse.yml` and is picked up by the conventional `resources/*.yml` include glob without any `databricks.yml` change.
  - In-bundle usage doc at `docs/monitoring-sql-warehouse/README.md` covers the auto-stop nuance, cross-resource ID reference pattern, and `databricks warehouses edit --auto-stop-mins` / REST API paths for editing warehouses created outside DABs.

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

[1.9.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.9.0
[1.8.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.8.0
[1.7.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.7.0
[1.6.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.6.0
[1.5.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.5.0
[1.4.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.4.0
[1.3.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.3.0
[1.2.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.2.0
[1.1.1]: https://github.com/vmariiechko/databricks-bundle-template/blob/main/CHANGELOG.md#111---2026-02-25
[1.1.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.1.0
[1.0.0]: https://github.com/vmariiechko/databricks-bundle-template/releases/tag/v1.0.0

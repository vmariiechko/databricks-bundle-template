# dbx-ro-query

A single-file Python wrapper around `databricks experimental aitools tools query` that gives LLM agents a safe, token-efficient SQL window into a Databricks workspace. Allow-lists `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `DESC`, `EXPLAIN`. Block-lists every destructive verb. Strips comments and quoted strings before validation so attempts to smuggle a `DROP` past the guard fail.

Packaged as an [agentskills.io](https://agentskills.io)-style skill: `SKILL.md` is the agent contract, `scripts/dbx-ro-query.py` is the bundled runner. The two ship together and copy together.

## Install

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/dbx-ro-query
```

You will be prompted for `target_dir` (default `.agents`). Two files are installed:

- `<target_dir>/skills/dbx-ro-query/SKILL.md`: the agent-facing skill contract
- `<target_dir>/skills/dbx-ro-query/scripts/dbx-ro-query.py`: the bundled wrapper script

## Picking a `target_dir`

The default `.agents` is vendor-neutral and matches the convention used by Codex, the Databricks AI Dev Kit, and any multi-agent project. If you only use one agent CLI and want auto-discovery:

| Agent | Override `target_dir` to | Notes |
|---|---|---|
| Claude Code | `.claude` | Auto-discovered via `.claude/skills/`. No further wiring needed. |
| Codex | `.codex` (or keep `.agents`) | Reference the SKILL.md from `AGENTS.md`. |
| Cursor | `.cursor` | Add a rule under `.cursor/rules/` referencing the SKILL.md. |
| Gemini CLI | `.gemini` | Reference from `.gemini/` configuration. |
| Multi-agent / unsure | `.agents` (default) | Wire each agent manually via its config file. |

The post-install message prints the exact one-liner per agent.

## Usage

After install, point your agent at the SKILL.md and call the script directly:

```bash
python <target_dir>/skills/dbx-ro-query/scripts/dbx-ro-query.py \
  "SELECT 1" \
  "<your-databricks-profile>" \
  "scalar"
```

See `<target_dir>/skills/dbx-ro-query/SKILL.md` for the full argument reference, output formats, supported SQL prefixes, and the rejection list.

## Troubleshooting

### `databricks bundle init` fails with `has no <profile> profile configured`

The CLI tries to resolve a Databricks profile during `bundle init` even though template installation does not need workspace auth. If your shell or IDE has `DATABRICKS_CONFIG_PROFILE` pointing at a profile that no longer exists in `~/.databrickscfg`, install fails with `Error: resolve: <path>/.databrickscfg has no <name> profile configured`.

Workaround: run the install with the env var pointed at a valid profile (or `DEFAULT`):

```bash
DATABRICKS_CONFIG_PROFILE=DEFAULT databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/dbx-ro-query
```

### Codex sandbox blocks the GitHub URL fetch

If `databricks bundle init <github url>` fails inside Codex with `connectex: An attempt was made to access a socket in a way forbidden by its access permissions`, the Codex sandbox is blocking outbound network. Enable network access in `~/.codex/config.toml`:

```toml
[sandbox_workspace_write]
network_access = true
```

Then restart Codex. See `<target_dir>/skills/dbx-ro-query/references/agent-codex.md` for the full Codex runtime checklist.

## What this asset is

A standalone sub-template in the [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template) asset library. It does not depend on the core template; it can be installed into any Databricks bundle, or any project at all that uses the Databricks CLI. See [ASSETS.md](../../ASSETS.md) for the full catalog.

## Background

Read the design rationale: [Two Guardrails for Letting LLM Agents Query Your Databricks Tables](https://vmariiechko.com/short-bytes/two-guardrails-llm-agents-databricks-sql/)


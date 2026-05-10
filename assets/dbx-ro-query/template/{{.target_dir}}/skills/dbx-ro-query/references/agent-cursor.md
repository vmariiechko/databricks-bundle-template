# Cursor runtime tips

Load this file on demand when running `dbx-ro-query` inside Cursor (Composer or any IDE-resident agent). Skip it for other runtimes. Verified against Cursor 3.3.x with the Composer 2 model.

## Wiring: rules live under `.cursor/rules/`, not `.cursor/skills/`

Cursor does not auto-discover arbitrary markdown under `.cursor/skills/`. Project-rule discovery is `.cursor/rules/*.mdc`. After installing this asset with `target_dir: .cursor`, drop a rule file at `.cursor/rules/dbx-ro-query.mdc` so Composer surfaces the skill on every prompt.

Suggested content for `.cursor/rules/dbx-ro-query.mdc`:

````markdown
---
description: Read-only Databricks SQL via the dbx-ro-query skill
alwaysApply: true
---

When you need to query Databricks (schema discovery, row sampling, aggregations, EXPLAIN — anything that reads but must not mutate), follow the skill at `.cursor/skills/dbx-ro-query/SKILL.md`. Invoke the bundled wrapper:

```
python .cursor/skills/dbx-ro-query/scripts/dbx-ro-query.py "<sql>" "<profile>" "<format>"
```

Do not call `databricks experimental aitools tools query` directly; the wrapper enforces a read-only guard.
````

The legacy `.cursorrules` file at the project root may still work in some setups, but `.cursor/rules/` is Cursor's current documented layout. Use `alwaysApply: true` so the rule is in scope without the user having to invoke it manually.

## Terminal runtime

- Cursor's terminal tool surfaces stdout, stderr, and `exit_code` to the model on every command. You do not need to append `; echo "exit=$?"` to detect failures.
- First query against a stopped or cold warehouse takes a few seconds (warm-up). Subsequent queries on a warm warehouse return in ~2-3 seconds. No observed timeout in default Composer settings.
- Output capture is clean. No login-shell or status-decoration noise has been observed.

## Profile mapping

The `<profile>` argument passed to the wrapper is a Databricks CLI profile name from `~/.databrickscfg`, not the `DATABRICKS_CONFIG_PROFILE` env var. The two only intersect when the user has explicitly exported the env var. Pass the profile explicitly to keep behavior deterministic.

# Codex runtime tips

Load this file on demand when running `dbx-ro-query` inside Codex. Skip it for other runtimes.

## Sandbox network access

If `databricks` calls fail with errors like `connectex: An attempt was made to access a socket in a way forbidden by its access permissions`, the Codex sandbox is blocking outbound network. Enable network access in `~/.codex/config.toml`:

```toml
[sandbox_workspace_write]
network_access = true
```

Restart Codex after the config change. The same block can manifest as `databricks bundle init` failing against a GitHub URL or as auth/warehouse calls timing out; both clear once the sandbox is allowed to reach the network.

## Disable the shell login chain for wrapper invocations

If `shell_command` runs through a login shell, captured output may end up polluted with profile noise such as `oh-my-posh`, `Terminal-Icons`, `Set-PSReadLineOption`, `ResourceUnavailable`, or `Export-Clixml` errors. These appear *after* the wrapper's actual output, so the SQL result itself is correct but the captured text is hard to paste cleanly into evidence.

Set `login: false` on `shell_command` for invocations of `dbx-ro-query.py`:

```yaml
shell_command:
  login: false
```

If you see a valid TSV or scalar result followed by such errors, rerun with `login: false` (or your local equivalent) to get clean captured output.

## Exit codes are already visible

Codex surfaces `Exit code: N` directly in `shell_command` results to the model. You do not need to append `; echo "exit=$?"` to detect failures. Only add it when you specifically want the exit code embedded in the captured output text for parseable evidence logs.

Avoid wrapping the wrapper with PowerShell `Measure-Command`. It can hide the child process exit code from Codex.

## Warehouse selection

The CLI auto-detects an available warehouse. For deterministic test matrices across sessions or machines, set `DATABRICKS_WAREHOUSE_ID=<id>` explicitly, either as an env var or via your shell config. First post-cold-start call typically takes 20-30 seconds; subsequent warm calls return in 2-3 seconds.

## Per-command timeout

Codex does not impose a fixed default; tune `timeout_ms` per call. `timeout_ms: 300000` (5 minutes) covers warehouse cold starts comfortably without making fast queries feel sluggish.

# Claude Code runtime tips

Load this file on demand when running `dbx-ro-query` inside Claude Code. Skip it for other runtimes.

## Bash tool default timeout (2 minutes)

The `Bash` tool defaults to a 120 000 ms (2-minute) timeout. Cold-starting a Databricks SQL warehouse can exceed this: serverless warehouses typically take 30 to 60 seconds, classic warehouses 3 to 5 minutes. If the first invocation against a stopped warehouse times out, set the `Bash` tool's `timeout` parameter higher (for example 300 000 ms) for the warm-up call, then drop back to the default for subsequent queries.

## Capturing rejections as parseable evidence

Claude Code's harness already surfaces non-zero exit codes to the model when a `Bash` call fails, so you do not need any extra wiring to *detect* a wrapper rejection. You only need extra wiring to *embed* the exit code in the captured output text, which is useful when logging a rejection as machine-readable evidence in a report.

For evidence captures, append `; echo "exit=$?"` to the invocation:

```bash
python .agents/skills/dbx-ro-query/scripts/dbx-ro-query.py \
  "DROP TABLE foo" "<your-profile>" 2>&1; echo "exit=$?"
```

The captured output then ends with `exit=1` (or whatever the wrapper returned), which downstream consumers can grep without parsing the harness's structured error block.

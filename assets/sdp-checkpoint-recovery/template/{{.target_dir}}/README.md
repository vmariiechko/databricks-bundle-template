# Lakeflow SDP Checkpoint Reset

Two Python scripts for recovering a Lakeflow Spark Declarative Pipeline from the `DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE` error by resetting the checkpoint selection for specific flows, without clearing target table data.

| File | Runs where | Auth |
|---|---|---|
| `sdp_reset_checkpoint_local.py` | Your machine | Databricks CLI profile or env vars |
| `sdp_reset_checkpoint_workspace.py` | Databricks notebook | Notebook ambient identity |

## When to use

The pipeline fails with `DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE` after a source Delta table has been dropped and recreated. The streaming checkpoint references the old table ID; the new table has a new ID. Lakeflow SDP abstracts checkpoint management, so manual deletion is not possible, but the Pipelines API exposes `reset_checkpoint_selection` to reset specific flows.

Downstream consequence: Bronze tables may contain duplicate events until your Silver layer's SCD / CDC logic processes them. Target data is not cleared.

## What happens when you run this

Resetting checkpoint selection requires running a pipeline update. The Pipelines API has no "reset only" mode: `reset_checkpoint_selection` is a parameter on `start_update`, so the call always starts an update. After this script returns the `update_id`, the pipeline transitions from IDLE to RUNNING and processes from the new checkpoint. If you want to keep the pipeline stopped after the reset, cancel the update from the Databricks UI immediately after the script prints the `update_id`. The dry-run path uses `validate_only=True` and does not start a real update; it returns an `update_id` for a validation-only update that completes immediately without mutating state.

By default the fresh stream starts from version 0 of the new Delta table (all historical data). To skip historical data or avoid duplicate Bronze events, add `.option("startingVersion", "latest")` (or a specific version number) to the source `readStream` in your pipeline code before running the reset; `startingVersion` is only applied when no checkpoint exists, so the `reset_checkpoint_selection` call is what makes it take effect.

## Flow naming: Fully Qualified Names are required

Flow names must be the **FQN in Unity Catalog**: `<catalog>.<schema>.<table_name>`. Short table names produce:

> `IllegalArgumentException: Reset checkpoint selection should not contain flow <name>, which does not exist in the graph.`

Both scripts validate flow names locally before calling the API and reject anything that is not a three-part FQN.

To find FQNs: check the pipeline's event log in the Databricks UI or the table's Unity Catalog entry.

## Usage: local

Prerequisite: `pip install -r requirements.txt` (pins `databricks-sdk>=0.100`) and a configured CLI profile.

Always start with `--dry-run` to validate auth and payload without mutating the pipeline. The dry-run issues a `validate_only` update; the API returns an `update_id` and the pipeline remains untouched.

```bash
python sdp_reset_checkpoint_local.py \
  --pipeline-id <your-pipeline-id> \
  --flows <catalog>.<schema>.<table_1> <catalog>.<schema>.<table_2> \
  --profile <your-databricks-profile> \
  --dry-run
```

Once the dry-run succeeds, drop `--dry-run` to apply the reset.

The `--profile` flag is optional; without it the script falls back to the default CLI auth chain (env vars, `DEFAULT` profile, workload identity).

## Usage: workspace notebook

1. Upload `sdp_reset_checkpoint_workspace.py` into your workspace as a notebook.
2. Set the **Pipeline ID** widget with your pipeline ID.
3. Set the **Flows to reset** widget with comma-separated FQNs (e.g., `catalog.schema.table`).
4. Confirm **Dry run** is `true` (the default); the first run is a `validate_only` update that does not start the pipeline. Flip to `false` once the dry-run succeeds, then run again to apply the reset.

The notebook uses the ambient Databricks SDK identity inside the notebook environment; no extra auth setup is needed.

## Alternatives

If resetting checkpoints is not enough:

- **Full refresh specific tables**: wipes Bronze data; reprocesses from scratch. Requires toggling `pipelines.reset.allowed = true` temporarily if your tables are protected. Use the Pipeline UI's "Full refresh all" button or `databricks pipelines start-update PIPELINE_ID --full-refresh`.
- **Destroy and recreate pipeline**: dev/test only. Destructive. `databricks bundle destroy -t <env> && databricks bundle deploy -t <env>`.

## References

1. [Databricks Docs: Recover a pipeline from streaming checkpoint failure](https://docs.databricks.com/aws/en/ldp/recover-streaming)
2. [Databricks API: Start a pipeline update](https://docs.databricks.com/api/workspace/pipelines/startupdate) (`reset_checkpoint_selection` parameter)
3. [Databricks SDK for Python: Pipelines API](https://databricks-sdk-py.readthedocs.io/en/latest/workspace/pipelines/pipelines.html)
4. [Databricks Docs: Run a pipeline update (full refresh and `pipelines.reset.allowed`)](https://docs.databricks.com/aws/en/ldp/updates)

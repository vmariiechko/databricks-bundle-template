# Databricks notebook source
# MAGIC %md
# MAGIC # Reset Lakeflow Spark Declarative Pipeline Checkpoints
# MAGIC
# MAGIC This notebook resets the streaming checkpoints for specific flows in a Lakeflow Spark Declarative Pipeline (SDP). It is useful when recovering from a `DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE` error caused by a source table being recreated.
# MAGIC
# MAGIC **Instructions:**
# MAGIC 1. Set the **Pipeline ID** widget.
# MAGIC 2. Set the **Flows to reset** widget (comma-separated fully-qualified names like `catalog.schema.table_name`).
# MAGIC 3. Confirm **Dry run** is `true` for the first run; flip to `false` once dry-run succeeds.
# MAGIC 4. Run the notebook.
# MAGIC
# MAGIC Calls the Databricks Pipelines API to issue an update with `reset_checkpoint_selection`. Prefers the native SDK signature (`databricks-sdk>=0.100`); falls back to a raw REST call via `WorkspaceClient.api_client.do` on older SDKs (notably Databricks Runtime serverless, which bundles its own SDK).

# COMMAND ----------
# MAGIC %md
# MAGIC ## Inputs
# MAGIC Set the widgets at the top of the notebook before running.

# COMMAND ----------

dbutils.widgets.text("pipeline_id", "", "Pipeline ID")
dbutils.widgets.text("flows", "", "Flows to reset (comma-separated FQNs)")
dbutils.widgets.dropdown("dry_run", "true", ["true", "false"], "Dry run")

# COMMAND ----------

PIPELINE_ID = dbutils.widgets.get("pipeline_id").strip()
FLOWS_TO_RESET = [f.strip() for f in dbutils.widgets.get("flows").split(",") if f.strip()]
DRY_RUN = dbutils.widgets.get("dry_run") == "true"

assert PIPELINE_ID, "Set the 'Pipeline ID' widget at the top of the notebook."
assert FLOWS_TO_RESET, (
    "Set the 'Flows to reset' widget at the top of the notebook (comma-separated FQNs)."
)

# COMMAND ----------

import re

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError

FQN_PATTERN = re.compile(r"^[^.\s]+\.[^.\s]+\.[^.\s]+$")


def validate_flow_fqns(flows: list[str]) -> None:
    """Raise `ValueError` if any flow name is not a three-part catalog.schema.table FQN."""
    bad = [f for f in flows if not FQN_PATTERN.match(f)]
    if bad:
        raise ValueError(
            f"Invalid flow name(s): {bad}. Expected fully qualified names like "
            f"catalog.schema.table."
        )


def _start_update_with_reset(w, pipeline_id, flows, validate_only):
    """Reset specified flow checkpoints and start a pipeline update.

    Tries the native SDK call first (databricks-sdk>=0.100). Falls back to
    the underlying REST endpoint via `api_client.do` when the installed
    SDK predates `reset_checkpoint_selection` on `start_update` (notably
    Databricks Runtime serverless, where the runtime owns the SDK version
    and cannot be upgraded via pip). Both paths return an `update_id`.
    """
    try:
        resp = w.pipelines.start_update(
            pipeline_id=pipeline_id,
            reset_checkpoint_selection=flows,
            validate_only=validate_only,
        )
        return resp.update_id
    except TypeError as e:
        if "reset_checkpoint_selection" not in str(e):
            raise
        body = {
            "reset_checkpoint_selection": flows,
            "validate_only": validate_only,
        }
        resp = w.api_client.do(
            method="POST",
            path=f"/api/2.0/pipelines/{pipeline_id}/updates",
            body=body,
        )
        return resp.get("update_id")


validate_flow_fqns(FLOWS_TO_RESET)

w = WorkspaceClient()

print(f"Workspace: {w.config.host}")
print(f"Pipeline:  {PIPELINE_ID}")
print(f"Flows:     {FLOWS_TO_RESET}")
print(f"Mode:      {'DRY-RUN (validate_only=True)' if DRY_RUN else 'APPLY'}")
print("-" * 40)

if not DRY_RUN:
    print(
        "WARNING: this will trigger a pipeline update; the pipeline will start running. "
        "Set DRY_RUN=true to validate without mutating."
    )

try:
    update_id = _start_update_with_reset(w, PIPELINE_ID, FLOWS_TO_RESET, DRY_RUN)
    print("Success! Pipeline update started.")
    print(f"Update ID: {update_id}")
    print("You can monitor the progress in the Pipeline UI.")
except DatabricksError as e:
    print(f"Databricks API error [{e.error_code}]: {e.message}")
    raise

# COMMAND ----------

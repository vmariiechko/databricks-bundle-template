"""Reset checkpoint selection for specific flows in a Lakeflow Spark Declarative Pipeline.

Recovers a pipeline from `DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE` after a
source table has been dropped and recreated, without clearing target table data.

Calls the Databricks Pipelines API to issue an update with `reset_checkpoint_selection`.
Prefers the native SDK signature (`databricks-sdk>=0.100`); falls back to a raw REST
call via `WorkspaceClient.api_client.do` on older SDKs (notably Databricks Runtime
serverless, which bundles its own SDK). Run with `--dry-run` first to issue a
`validate_only` update that exercises the payload without mutating the pipeline.
"""

import argparse
import logging
import re
import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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


def reset_checkpoint(
    pipeline_id: str,
    flows: list[str],
    profile: str = None,
    dry_run: bool = False,
):
    """Call the Databricks Pipelines API to reset checkpoints for specified flows."""
    try:
        validate_flow_fqns(flows)

        logger.info("Initializing Databricks WorkspaceClient...")
        w = WorkspaceClient(profile=profile) if profile else WorkspaceClient()
        logger.info(f"Connected to workspace: {w.config.host}")

        if dry_run:
            logger.info(
                "DRY-RUN mode: calling start_update with validate_only=True; "
                "the pipeline will not be mutated."
            )
        else:
            logger.warning(
                "This will trigger a pipeline update; the pipeline will start running "
                "after this command returns. Use --dry-run to validate without mutating."
            )
        logger.info(f"Resetting checkpoints for flows: {flows}")

        update_id = _start_update_with_reset(w, pipeline_id, flows, dry_run)

        logger.info(f"Success! Pipeline update started. Update ID: {update_id}")

    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except DatabricksError as e:
        logger.error(f"Databricks API error [{e.error_code}]: {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reset checkpoint for specific flows in a Databricks Pipeline."
    )
    parser.add_argument("--pipeline-id", required=True, help="The ID of the Databricks Pipeline.")
    parser.add_argument(
        "--flows",
        required=True,
        nargs="+",
        help=(
            "Space-separated list of fully qualified flow names to reset "
            "(e.g., finance.bronze.transactions_cdf)."
        ),
    )
    parser.add_argument(
        "--profile",
        required=False,
        help="Optional Databricks CLI profile to use for authentication.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Issue a validate_only update; verifies payload and auth without mutating the pipeline."
        ),
    )

    args = parser.parse_args()

    reset_checkpoint(args.pipeline_id, args.flows, args.profile, args.dry_run)

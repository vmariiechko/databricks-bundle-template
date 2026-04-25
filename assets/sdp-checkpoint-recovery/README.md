# sdp-checkpoint-recovery

Reset checkpoint selection on a Lakeflow Spark Declarative Pipeline after a source table has been dropped and recreated (`DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE`). Note: resetting checkpoints triggers a pipeline update; the pipeline will run after the call. Use the dry-run path first.

## Install

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/sdp-checkpoint-recovery
```

You will be prompted for `target_dir` (default `ops/sdp_checkpoint_recovery`). Four files are installed under that directory:

- `sdp_reset_checkpoint_local.py`: run from your machine
- `sdp_reset_checkpoint_workspace.py`: upload as a notebook
- `README.md`: usage instructions
- `requirements.txt`: pinned `databricks-sdk` for the local script

## Usage

After install, open `<target_dir>/README.md` in your project for the command reference, authentication notes, and alternative recovery options.

## What this asset is

A standalone sub-template in the [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template) asset library. It does not depend on the core template; it can be installed into any Databricks bundle. See [ASSETS.md](../../ASSETS.md) for the full catalog.

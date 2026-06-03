# monitoring-sql-warehouse

A small, dedicated serverless SQL warehouse tuned for bursty workloads: scheduled Databricks Alerts, monitoring queries, and ad-hoc health checks. Defaults to `2X-Small` with `auto_stop_mins: 1` so cost stays proportional to actual query time.

## Install

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundle-template \
  --template-dir assets/monitoring-sql-warehouse
```

You will be prompted for:

| Prompt | Default | Notes |
|---|---|---|
| `target_dir` | `resources` | Where the resource YAML lands. Default matches the `resources/*.yml` glob most bundles already include. |
| `warehouse_resource_key` | `monitoring_sql_warehouse` | DABs key under `resources.sql_warehouses.<key>`. Also the resource filename. |
| `warehouse_name` | `Monitoring SQL Warehouse` | Display name in the workspace SQL Warehouses list. |
| `cluster_size` | `2X-Small` | One of: 2X-Small, X-Small, Small, Medium, Large, X-Large, 2X-Large, 3X-Large, 4X-Large. |
| `auto_stop_mins` | `1` | Integer. `1` is the serverless minimum; `0` disables auto-stop; `10+` for Pro/Classic. |

Two files are installed:

- `<target_dir>/<warehouse_resource_key>.sql_warehouse.yml`: the DABs resource definition (serverless PRO, single cluster, channel pinned to `CHANNEL_NAME_CURRENT`, tagged `workload=monitoring-alerts` and `created_by=dabs-asset/monitoring-sql-warehouse`).
- `docs/monitoring-sql-warehouse/README.md`: usage notes, the `auto_stop_mins: 1` serverless nuance, and CLI/API paths for editing existing warehouses outside DABs.

## Usage

After install, open `docs/monitoring-sql-warehouse/README.md` in your project for deploy steps, the cross-resource reference pattern (`${resources.sql_warehouses.<key>.id}`), and the auto-stop behavior reference table.

## What this asset is

A standalone sub-template in the [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template) asset library. It does not depend on the core template; it can be installed into any Databricks bundle. See [ASSETS.md](../../ASSETS.md) for the full catalog.

## Background

Read the story of how it came up: [The SQL Warehouse Cost Trap Behind Short Databricks Alert Jobs](https://vmariiechko.com/short-bytes/sql-warehouse-alert-cost-trap/)

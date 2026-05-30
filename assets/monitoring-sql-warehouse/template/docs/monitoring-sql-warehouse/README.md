# Monitoring SQL Warehouse

A small, dedicated serverless SQL warehouse for scheduled Databricks Alerts, monitoring queries, and ad-hoc health checks. Optimized for bursty, sub-second workloads where idle time would otherwise dominate the bill.

## When to use this

Use a dedicated warehouse like this when:

- You run scheduled Databricks Alerts (every minute, every five minutes, every hour) whose underlying SQL completes in well under a second.
- The default warehouse those queries land on has a long auto-stop window (10 minutes is the platform default for Pro/Classic; serverless allows 1 minute).
- You see the warehouse staying warm for the full auto-stop window after a single sub-second query, inflating monthly cost.

A separate `2X-Small` serverless warehouse with `auto_stop_mins: 1` keeps cost proportional to actual query time: the warehouse starts on the Alert run, executes in under a second, and stops one minute after the last query.

## What this asset installs

| Path | Purpose |
|---|---|
| `<target_dir>/<warehouse_resource_key>.sql_warehouse.yml` | The DABs SQL warehouse resource definition. |
| `docs/monitoring-sql-warehouse/README.md` | This file. |

Default install paths:

- Resource: `resources/monitoring_sql_warehouse.sql_warehouse.yml`
- Docs: `docs/monitoring-sql-warehouse/README.md`

## Bundle integration

Most generated bundles already include `resources/*.yml` from `databricks.yml`:

```yaml
include:
  - resources/*.yml
```

If your bundle uses that pattern and you accepted the default `target_dir`, the warehouse is picked up automatically. No `databricks.yml` change is needed.

If you installed to a custom subdirectory (e.g., `resources/sql_warehouses/`), add the matching glob to `databricks.yml`:

```yaml
include:
  - resources/sql_warehouses/*.yml
```

## Deploy

```bash
databricks bundle validate -t <your-target>
databricks bundle deploy -t <your-target>
```

After deploy, the warehouse appears in the workspace SQL Warehouses list under the display name you chose at install time.

## Referencing the warehouse from other bundle resources

Other resources (Alerts, jobs, dashboards) can pin to this warehouse by ID:

```yaml
${resources.sql_warehouses.<warehouse_resource_key>.id}
```

For example, an Alert resource:

```yaml
resources:
  alerts:
    my_alert:
      warehouse_id: ${resources.sql_warehouses.monitoring_sql_warehouse.id}
      # ... rest of the alert definition
```

## The `auto_stop_mins: 1` nuance

The proven configuration was verified by deploying this asset to a real workspace (Databricks SQL channel v2026.10). The notes below capture behavior that contradicts or refines parts of the public API reference.

| Setting | Behavior |
|---|---|
| `auto_stop_mins: 0` | Disables auto-stop entirely. The warehouse runs until manually stopped. Does NOT mean "stop immediately." |
| `auto_stop_mins: 1` | Valid and effective on serverless via DABs/API. The workspace UI shows "After 1 minute of inactivity." This is the recommended value for Alerts and monitoring workloads. |
| `auto_stop_mins: 0.5` (or any sub-minute value) | Not supported. The field is modeled as an integer; the bundle CLI emits an integer-coercion warning and the workspace silently reverts to the platform default (120 minutes). |
| `auto_stop_mins: 10+` | Per the public [Warehouses API reference][create-warehouse-api], the documented contract is `auto_stop_mins` must be `0` or `>= 10`. This floor applies to Pro/Classic warehouses. Safe upper bound for serverless too. |

The public [Warehouses API reference][create-warehouse-api] states that `auto_stop_mins` must be `0` or `>= 10`. That floor applies to Pro/Classic warehouses; the serverless path accepts `1` end-to-end via DABs and via the CLI (confirmed by deploying this resource and inspecting the workspace UI).

The manual UI editor for an existing warehouse may enforce a higher floor on serverless than 1 minute. If you see that, fall back to the DABs path or the `databricks warehouses edit` CLI path, both of which apply `1` on serverless.

[create-warehouse-api]: https://docs.databricks.com/api/workspace/warehouses/create
[edit-warehouse-api]: https://docs.databricks.com/api/workspace/warehouses/edit

## Applying the same tuning to a warehouse created outside DABs

If you have an existing warehouse that you do not want to recreate as a DABs resource, you can edit it in place to the same auto-stop behavior.

### Via the Databricks CLI

```bash
databricks warehouses edit <warehouse-id> --auto-stop-mins 1
```

The full flag set is visible via `databricks warehouses edit --help`. For serverless, also ensure `--enable-serverless-compute` is on and `--warehouse-type PRO` is set.

### Via the REST API

Use the [Edit Warehouse endpoint][edit-warehouse-api] (`POST /api/2.0/sql/warehouses/{id}/edit`) with `auto_stop_mins: 1`. For serverless, include `enable_serverless_compute: true` and `warehouse_type: PRO` in the request body. The endpoint reference still documents the `0 or >= 10` contract; the serverless `1` value is accepted in practice and is what DABs and the CLI emit.

```bash
curl -X POST \
  -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  -H "Content-Type: application/json" \
  https://$DATABRICKS_HOST/api/2.0/sql/warehouses/<warehouse-id>/edit \
  -d '{
        "auto_stop_mins": 1,
        "enable_serverless_compute": true,
        "warehouse_type": "PRO"
      }'
```

### Via the workspace UI

The "Edit warehouse" form may enforce a higher minimum than 1 minute for serverless. If the UI rejects `1`, use the CLI or DABs path.

## Cost intuition

A `2X-Small` serverless warehouse billed per second of running time, kept warm by a 1-minute auto-stop after each sub-second query, costs a small constant per scheduled run plus the query duration itself. Compared to a 10-minute auto-stop window on the same size warehouse, the per-run dwell time drops by an order of magnitude. Apply this to dozens of scheduled Alerts and the monthly delta is meaningful.

## References

1. [Databricks Docs: Configure SQL warehouse settings (auto-stop)](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-behavior)
2. [Declarative Automation Bundles: `sql_warehouses` resource reference](https://docs.databricks.com/aws/en/dev-tools/bundles/resources.html#sql_warehouse)
3. [Databricks API: Create Warehouse][create-warehouse-api] (`auto_stop_mins` contract)
4. [Databricks API: Edit Warehouse][edit-warehouse-api] (in-place edits to an existing warehouse)
5. [Databricks CLI: `databricks warehouses edit`](https://docs.databricks.com/aws/en/dev-tools/cli/reference/warehouses-commands.html#edit)
6. [Databricks Alerts overview](https://docs.databricks.com/aws/en/sql/user/alerts/)

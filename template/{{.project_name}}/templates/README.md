# Configuration Templates

This folder contains reusable configuration templates that you can copy and paste into your Databricks Asset Bundle resource files.

## Why Templates?

YAML anchors (`&anchor` and `*anchor`) only work within a single YAML file. Since Databricks bundles spread configurations across multiple files, we provide these templates as copy-paste references instead.

## Available Templates

### Cluster Configurations (`cluster_configs.yml`)

Contains 6 ready-to-use cluster configurations:

**For Jobs:**
- `small_cluster` - Development/testing (1 worker)
- `medium_cluster` - Standard workloads (2 workers)
- `autoscale_cluster` - Variable workloads (auto-scaling)
- `photon_cluster` - High-performance workloads (Photon-enabled)

**For DLT Pipelines:**
- `pipeline_cluster_small` - Development (1 worker)
- `pipeline_cluster_autoscale` - Production (auto-scaling)

## How to Use

1. **Open** the template file (e.g., `cluster_configs.yml`)
2. **Find** the configuration that matches your needs
3. **Copy** the entire configuration block (without the anchor name like `small_cluster:`)
4. **Paste** into your resource file at the appropriate location:
   - For jobs: under `job_clusters[].new_cluster` or at the job_cluster definition
   - For pipelines: under `clusters[]`
5. **Customize** as needed (node types, worker counts, spark configs, etc.)

## Future Template Ideas

The following configuration patterns could be added as templates in future:

### 1. **Schedule Templates** (`schedule_configs.yml`)
Common cron schedule patterns:
- Hourly, daily, weekly, monthly schedules
- Business hours only
- Weekend processing
- End-of-month patterns
- Timezone considerations

### 2. **Notification Templates** (`notification_configs.yml`)
Different notification strategies:
- Email notifications (success/failure/start)
- Webhook integrations
- Slack/Teams notifications
- PagerDuty integration patterns
- Alert escalation patterns

### 3. **Permission Templates** (`permission_configs.yml`)
Role-based access patterns:
- Developer access patterns
- Data engineer vs. data analyst roles
- Production lockdown patterns
- Service principal configurations
- Group-based permissions

### 4. **Retry Strategy Templates** (`retry_configs.yml`)
Different retry behaviors:
- Fast-fail (development)
- Standard retry (production)
- Aggressive retry (critical workloads)
- Exponential backoff patterns
- Timeout configurations

### 5. **Library Configuration Templates** (`library_configs.yml`)
Common library patterns:
- PyPI packages
- Maven/JAR libraries
- Wheel files from DBFS/Volumes
- Requirements.txt patterns
- Poetry/uv configurations

### 6. **Storage Templates** (`storage_configs.yml`)
Volume and path patterns:
- Volume mount configurations
- DBFS path patterns
- External location patterns
- Cloud storage integrations (S3, ADLS, GCS)

### 7. **Task Configuration Templates** (`task_configs.yml`)
Common task patterns:
- Python wheel tasks
- Notebook tasks
- SQL tasks
- DLT pipeline tasks
- JAR tasks
- Run job tasks (job chaining)
- For-each tasks (parallel processing)

### 8. **Environment Templates** (`environment_configs.yml`)
Environment variable patterns:
- Databricks-specific variables
- Cloud provider credentials (via secrets)
- Feature flags
- Configuration per environment

### 9. **Health Check Templates** (`health_configs.yml`)
Job health monitoring:
- Health rules for jobs
- SLA configurations
- Data quality checks
- Freshness checks

## Contributing Templates

When adding new templates:

1. Create a new `.yml` file in this folder
2. Add clear comments explaining each configuration
3. Update this README with the new template
4. Consider cloud provider differences (AWS/Azure/GCP)

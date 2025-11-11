# Permissions Configuration Guide

## Overview

This guide explains how to configure permissions in Databricks Asset Bundles for the multi-environment deployment template. Proper permission configuration ensures secure, role-based access to your data platform resources.

## 📚 Table of Contents

1. [Permission Levels](#permission-levels)
2. [Configuration Approaches](#configuration-approaches)
3. [Environment-Specific Strategy](#environment-specific-strategy)
4. [Setup Instructions](#setup-instructions)
5. [Common Patterns](#common-patterns)
6. [Troubleshooting](#troubleshooting)

---

## Permission Levels

### For Jobs, Pipelines, and General Resources

| Level | Capabilities | Recommended For |
|-------|--------------|-----------------|
| `CAN_VIEW` | View configuration and run history | All users, auditors, read-only access |
| `CAN_RUN` | View + trigger runs | Analysts, operators who need to execute |
| `CAN_MANAGE_RUN` | View + run + cancel runs + modify parameters | Team members actively working with resources |
| `CAN_MANAGE` | Full control: view, run, modify, delete | Resource owners, team leads, admins |

### For MLflow Experiments

| Level | Capabilities |
|-------|--------------|
| `CAN_READ` | View experiments and runs |
| `CAN_EDIT` | Read + create runs and log metrics |
| `CAN_MANAGE` | Edit + delete experiments |

### For Secret Scopes

| Level | Capabilities |
|-------|--------------|
| `READ` | Read secret values |
| `WRITE` | Read + create/update secrets |
| `MANAGE` | Write + manage ACLs |

### For Unity Catalog Schemas

| Privilege | Capabilities |
|-----------|--------------|
| `SELECT` | Query tables |
| `MODIFY` | Modify table data |
| `CREATE_TABLE` | Create new tables |
| `ALL_PRIVILEGES` | Full schema control |

---

## Configuration Approaches

Databricks Asset Bundles support **three levels** of permission configuration with a merging strategy:

### 1. Bundle-Level Permissions (Global)

Apply to **all resources** across **all targets**.

```yaml
bundle:
  name: my-bundle

permissions:
  - level: CAN_VIEW
    group_name: all_users
```

**When to use**: Rarely. Only for organization-wide policies (e.g., security auditors need view access to everything).

### 2. Target-Level Permissions (Recommended) ⭐

Apply to **all resources** within a **specific target** (user, dev, stage, prod).

```yaml
targets:
  prod:
    mode: production
    permissions:
      - level: CAN_VIEW
        group_name: analytics_team
      - level: CAN_MANAGE
        service_principal_name: ${var.prod_service_principal}
```

**When to use**: This is the **recommended approach** for most cases. It keeps permissions organized by environment and reduces duplication.

### 3. Resource-Level Permissions

Apply to **individual resources** (specific job, pipeline, experiment).

```yaml
resources:
  jobs:
    critical_job:
      name: Critical Production Job
      permissions:
        - level: CAN_MANAGE
          group_name: platform_team
        - level: CAN_VIEW
          group_name: executives
      tasks:
        # ... task configuration
```

**When to use**: For exceptions or special cases where a specific resource needs different permissions than the target default.

### Permission Merging

When permissions are defined at multiple levels, they are **merged**:

```yaml
# Bundle-level
permissions:
  - level: CAN_VIEW
    group_name: all_users

targets:
  prod:
    # Target-level
    permissions:
      - level: CAN_RUN
        group_name: operations

    resources:
      jobs:
        my_job:
          # Resource-level
          permissions:
            - level: CAN_MANAGE
              user_name: owner@company.com
```

**Result**: The job `my_job` will have:
- `CAN_VIEW` for `all_users` (from bundle)
- `CAN_RUN` for `operations` (from target)
- `CAN_MANAGE` for `owner@company.com` (from resource)

---

## Environment-Specific Strategy

Here's the recommended permission strategy for each environment in this template:

### 🧑‍💻 User Environment (Local Development)

**Goal**: Individual isolation, developer owns everything

```yaml
targets:
  user:
    mode: development
    default: true

    # No explicit permissions needed - developer owns all resources
    # Resources are prefixed with [user <name>] for isolation
```

**Why**: Development mode automatically grants the deploying user full access. No shared access needed.

### 🔧 Dev Environment (Shared Development)

**Goal**: Team collaboration, transparency, safe experimentation

```yaml
targets:
  dev:
    mode: production

    permissions:
      # Everyone can see what's deployed
      - level: CAN_VIEW
        group_name: users

      # Development team can run and manage
      - level: CAN_MANAGE_RUN
        group_name: developers

      # Service principal or lead for deployment
      - level: CAN_MANAGE
        service_principal_name: ${var.dev_service_principal}
```

### 🎭 Stage Environment (Pre-Production)

**Goal**: Controlled testing, production-like access restrictions

```yaml
targets:
  stage:
    mode: production

    permissions:
      # Limited visibility
      - level: CAN_VIEW
        group_name: engineering_team

      # QA team can test
      - level: CAN_RUN
        group_name: qa_team

      # Deployment via service principal only
      - level: CAN_MANAGE
        service_principal_name: ${var.stage_service_principal}

    run_as:
      service_principal_name: ${var.stage_service_principal}
```

### 🚀 Production Environment

**Goal**: Maximum security, audit trail, minimal manual access

```yaml
targets:
  prod:
    mode: production

    permissions:
      # Read-only for monitoring and analytics
      - level: CAN_VIEW
        group_name: analytics_team

      # Operations team can run for incident response
      - level: CAN_RUN
        group_name: operations_team

      # Only service principal can manage
      - level: CAN_MANAGE
        service_principal_name: ${var.prod_service_principal}

    run_as:
      service_principal_name: ${var.prod_service_principal}
```

---

## Setup Instructions

### Step 1: Define Variables

Add service principal configuration to `variables.yml`:

```yaml
variables:
  # ... existing variables ...

  # Service Principals for deployment
  dev_service_principal:
    description: Service principal application ID for dev environment
    default: ""  # Set via environment variable or override

  stage_service_principal:
    description: Service principal application ID for stage environment
    default: ""

  prod_service_principal:
    description: Service principal application ID for production environment
    default: ""

  # Group names (customize for your organization)
  developers_group:
    description: Group name for developers with access to dev resources
    default: "developers"

  qa_team_group:
    description: Group name for QA team with access to stage
    default: "qa_team"

  operations_group:
    description: Group name for operations team with prod run access
    default: "operations_team"
```

### Step 2: Include Permissions Configuration

Update `databricks.yml` to include the permissions file:

```yaml
bundle:
  name: realworld_example

include:
  - resources/*.yml
  - variables.yml
  - cluster_configs.yml
  - permissions.yml  # Add this line
```

### Step 3: Apply Permissions to Targets

Update your target configurations in `databricks.yml`:

```yaml
targets:
  # User target - no changes needed (development mode)
  user:
    mode: development
    # ... existing configuration ...

  # Dev target - add target-level permissions
  dev:
    mode: production
    permissions:
      - level: CAN_VIEW
        group_name: users
      - level: CAN_MANAGE_RUN
        group_name: ${var.developers_group}
    # ... existing configuration ...

  # Stage target - restricted access
  stage:
    mode: production
    permissions:
      - level: CAN_VIEW
        group_name: ${var.developers_group}
      - level: CAN_RUN
        group_name: ${var.qa_team_group}
    run_as:
      service_principal_name: ${var.stage_service_principal}
    # ... existing configuration ...

  # Prod target - minimal access
  prod:
    mode: production
    permissions:
      - level: CAN_VIEW
        group_name: ${var.operations_group}
      - level: CAN_RUN
        group_name: ${var.operations_group}
    run_as:
      service_principal_name: ${var.prod_service_principal}
    # ... existing configuration ...
```

### Step 4: Configure Resource-Level Permissions (Optional)

For resources that need special permissions, add them to the resource definition:

```yaml
# resources/critical_job.job.yml
resources:
  jobs:
    critical_pipeline_job:
      name: Critical Data Pipeline

      # Special permissions for this job only
      permissions:
        - level: CAN_VIEW
          group_name: executives
        - level: CAN_MANAGE
          group_name: platform_engineering

      tasks:
        # ... task configuration
```

### Step 5: Set Up Service Principals

1. **Create Service Principals** in Azure AD / AWS IAM / GCP IAM
2. **Add to Databricks Workspace**:
   ```bash
   databricks service-principals create \
     --application-id <your-app-id> \
     --display-name "Bundle Deployment - Prod"
   ```
3. **Grant Workspace Access**:
   - Add to appropriate groups
   - Grant Unity Catalog permissions
   - Assign cluster policies if needed

4. **Store Credentials**:
   - In CI/CD secrets (GitHub Actions, GitLab CI)
   - Or in Azure Key Vault / AWS Secrets Manager
   - Set as environment variables during deployment

---

## Common Patterns

### Pattern 1: Progressive Access Restriction

```yaml
# More open in dev → more restricted in prod
targets:
  dev:
    permissions:
      - level: CAN_MANAGE_RUN
        group_name: all_developers

  stage:
    permissions:
      - level: CAN_RUN
        group_name: senior_developers

  prod:
    permissions:
      - level: CAN_VIEW
        group_name: senior_developers
      - level: CAN_MANAGE
        service_principal_name: ${var.prod_sp}
```

### Pattern 2: Resource Owner Override

```yaml
# Target gives team access, resource gives owner full control
targets:
  prod:
    permissions:
      - level: CAN_VIEW
        group_name: data_team

resources:
  jobs:
    analytics_pipeline:
      name: Analytics Pipeline
      permissions:
        - level: CAN_MANAGE
          user_name: analytics-lead@company.com
```

### Pattern 3: Compliance and Audit

```yaml
# Ensure auditors always have view access
bundle:
  name: my-bundle

  permissions:
    - level: CAN_VIEW
      group_name: security_auditors
    - level: CAN_VIEW
      group_name: compliance_team

# This applies to ALL targets and resources
```

### Pattern 4: On-Call Support Access

```yaml
# Production resources with emergency access
targets:
  prod:
    permissions:
      - level: CAN_VIEW
        group_name: all_engineers
      - level: CAN_RUN
        group_name: oncall_engineers  # Can trigger reruns
      - level: CAN_MANAGE
        service_principal_name: ${var.prod_sp}
```

---

## Troubleshooting

### Issue: "Permission denied" during deployment

**Cause**: The deploying user/service principal lacks permissions to create resources.

**Solution**:
1. Verify the user/SP has workspace admin or contributor role
2. Check Unity Catalog permissions (`USE CATALOG`, `USE SCHEMA`, `CREATE TABLE`)
3. Verify cluster policies allow the requested configuration

```bash
# Check current user permissions
databricks current-user me

# Validate bundle before deploying
databricks bundle validate -t prod
```

### Issue: Users can't see deployed resources

**Cause**: Permissions not applied or incorrect group names.

**Solution**:
1. Verify group names exist in workspace:
   ```bash
   databricks groups list
   ```
2. Check if permissions are included in deployment:
   ```bash
   databricks bundle deploy -t dev --debug
   ```
3. Confirm users are members of specified groups

### Issue: Service principal deployment fails

**Cause**: Service principal not configured or lacks permissions.

**Solution**:
1. Verify SP exists and has correct application ID
2. Grant SP necessary workspace permissions
3. Set authentication in environment:
   ```bash
   export DATABRICKS_CLIENT_ID=<app-id>
   export DATABRICKS_CLIENT_SECRET=<secret>
   export DATABRICKS_HOST=<workspace-url>
   ```

### Issue: Permissions not merging as expected

**Cause**: Syntax errors or conflicting permission levels.

**Solution**:
1. Validate YAML syntax:
   ```bash
   databricks bundle validate -t <target>
   ```
2. Check bundle output with:
   ```bash
   databricks bundle deploy -t <target> --debug
   ```
3. Review [official docs on permission merging](https://docs.databricks.com/dev-tools/bundles/permissions)

---

## Best Practices Summary

✅ **DO:**
- Use target-level permissions as your primary approach
- Use service principals with `run_as` for prod/stage
- Give developers full access in dev, restricted in prod
- Document your permission strategy
- Use variables for group names and service principals
- Test permission changes in dev first

❌ **DON'T:**
- Don't use bundle-level permissions unless truly global
- Don't hardcode application IDs or user emails
- Don't give broad permissions in production
- Don't mix user-based deployment with SP permissions
- Don't forget to set `run_as` when using service principals

---

## Additional Resources

- [Databricks Asset Bundles Permissions Documentation](https://docs.databricks.com/dev-tools/bundles/permissions)
- [Unity Catalog Privileges](https://docs.databricks.com/data-governance/unity-catalog/manage-privileges/)
- [Service Principals Setup](https://docs.databricks.com/administration-guide/users-groups/service-principals.html)
- [Deployment Modes](https://docs.databricks.com/dev-tools/bundles/deployment-modes.html)

---

## Questions or Issues?

If you encounter issues with permissions configuration:
1. Check the [Troubleshooting](#troubleshooting) section above
2. Review the [Databricks Community Forums](https://community.databricks.com/)
3. Consult your organization's platform team or Databricks account team





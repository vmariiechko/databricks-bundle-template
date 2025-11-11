# Permissions Quick Reference

Quick lookup guide for Databricks Asset Bundle permissions configuration.



## Permission Levels by Resource Type

### Jobs & Pipelines

```yaml
# View only
- level: CAN_VIEW
  group_name: all_users

# Run only (can trigger)
- level: CAN_RUN
  group_name: operators

# Run and manage runs (cancel, modify parameters)
- level: CAN_MANAGE_RUN
  group_name: developers

# Full control (edit, delete, manage permissions)
- level: CAN_MANAGE
  group_name: admins
```

### MLflow Experiments

```yaml
# View experiments and runs
- level: CAN_READ
  group_name: data_scientists

# Create runs and log metrics
- level: CAN_EDIT
  group_name: ml_engineers

# Delete experiments and manage permissions
- level: CAN_MANAGE
  user_name: experiment-owner@company.com
```

### Secret Scopes

```yaml
# Read secrets
- level: READ
  group_name: developers

# Create/update secrets
- level: WRITE
  group_name: data_engineers

# Manage ACLs
- level: MANAGE
  service_principal_name: ${var.service_principal}
```

### Unity Catalog Schemas

```yaml
grants:
  # Query tables
  - principal: users
    privileges:
      - SELECT

  # Modify data
  - principal: data_engineers
    privileges:
      - SELECT
      - MODIFY
      - CREATE_TABLE

  # Full control
  - principal: platform_admins
    privileges:
      - ALL_PRIVILEGES
```

---

## 📍 Where to Define Permissions

### 1. Bundle-Level (Global)

**File:** `databricks.yml`
**Applies to:** ALL resources across ALL targets
**Use when:** Organization-wide policies (rare)

```yaml
bundle:
  name: my-bundle

  permissions:
    - level: CAN_VIEW
      group_name: security_auditors
```

### 2. Target-Level (Recommended)

**File:** `databricks.yml`
**Applies to:** All resources in a specific target
**Use when:** Environment-specific access control

```yaml
targets:
  prod:
    mode: production

    permissions:
      - level: CAN_VIEW
        group_name: all_engineers
      - level: CAN_MANAGE
        service_principal_name: ${var.prod_sp}
```

### 3. Resource-Level

**File:** `resources/<resource_name>.yml`
**Applies to:** Individual resource only
**Use when:** Exceptions to target-level permissions

```yaml
resources:
  jobs:
    critical_job:
      name: Critical Job

      permissions:
        - level: CAN_MANAGE
          user_name: owner@company.com

      tasks:
        # ... task config
```

---

## Principal Types

### User

```yaml
permissions:
  - level: CAN_MANAGE
    user_name: user@company.com
```

⚠️ **Warning:** Use sparingly. Prefer groups for scalability.

### Group

```yaml
permissions:
  - level: CAN_RUN
    group_name: data_engineers
```

✅ **Recommended:** Best practice for team-based access.

### Service Principal

```yaml
permissions:
  - level: CAN_MANAGE
    service_principal_name: abc-123-def-456  # Application ID
```

✅ **Recommended:** Required for production automation.

---

## Permission Merging

Permissions from different levels are **merged** (not overridden):

```yaml
# Bundle level
permissions:
  - level: CAN_VIEW
    group_name: all_users

# Target level
targets:
  prod:
    permissions:
      - level: CAN_RUN
        group_name: operators

# Resource level
resources:
  jobs:
    my_job:
      permissions:
        - level: CAN_MANAGE
          user_name: owner@company.com
```

**Resulting permissions for `my_job` in `prod` target:**
- `all_users`: CAN_VIEW
- `operators`: CAN_RUN
- `owner@company.com`: CAN_MANAGE

---

## Setup Checklist

### Initial Setup

- [ ] Create service principals in Azure AD/AWS/GCP
- [ ] Add service principals to Databricks workspace
- [ ] Create user groups in Databricks workspace
- [ ] Add users to appropriate groups
- [ ] Specify service principals in `variables.yml`
- [ ] Specify group names in `variables.yml`

### Development Environment

- [ ] Set target-level permissions in `databricks.yml` (dev target)
- [ ] Uncomment and configure permission entries
- [ ] Test deployment: `databricks bundle deploy -t dev`
- [ ] Verify permissions in Databricks UI

### Production Environment

- [ ] Configure service principal for `run_as`
- [ ] Grant Unity Catalog permissions to SP
- [ ] Set restrictive target-level permissions
- [ ] Test deployment: `databricks bundle deploy -t prod`
- [ ] Verify only SP can manage resources

---

## Troubleshooting

### "Permission denied" during deployment

**Check:**
- [ ] User/SP has workspace contributor role
- [ ] Unity Catalog permissions (USE CATALOG, CREATE SCHEMA)
- [ ] Cluster policy allows requested configuration

```bash
# Verify current user
databricks current-user me

# Validate bundle
databricks bundle validate -t prod
```

### Users can't see deployed resources

**Check:**
- [ ] Group names match exactly in workspace
- [ ] Users are members of specified groups
- [ ] Permissions deployed correctly

```bash
# List groups
databricks groups list

# Check group members
databricks groups get <group-id>

# Debug deployment
databricks bundle deploy -t dev --debug
```

### Service principal deployment fails

**Check:**
- [ ] SP exists in Azure AD/AWS/GCP
- [ ] SP added to Databricks workspace
- [ ] SP has required permissions
- [ ] Authentication configured correctly

```bash
# Set SP credentials
export DATABRICKS_CLIENT_ID=<app-id>
export DATABRICKS_CLIENT_SECRET=<secret>
export DATABRICKS_HOST=<workspace-url>

# Test deployment
databricks bundle deploy -t prod
```

---

## Learn More

- **Comprehensive Guide:** [`PERMISSIONS_GUIDE.md`](./PERMISSIONS_GUIDE.md)
- **Configuration Templates:** [`permissions.yml`](./permissions.yml)
- **Schema Example:** [`resources/example_schema.schema.yml`](./resources/example_schema.schema.yml)
- **Official Docs:** https://docs.databricks.com/dev-tools/bundles/permissions

---

## Best Practices

✅ **DO:**
- Use target-level permissions as primary approach
- Use service principals with `run_as` for prod/stage
- Use groups instead of individual users
- Document your permission strategy
- Test in dev before applying to prod
- Use variables for group names and SPs

❌ **DON'T:**
- Hardcode application IDs or emails
- Give broad permissions in production
- Mix user deployment with SP permissions
- Grant individual user permissions (use groups)
- Forget to set `run_as` when using SPs




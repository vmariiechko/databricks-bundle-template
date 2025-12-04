# Permissions Setup Guide

Quick guide to configure permissions in your Databricks Asset Bundle for secure, role-based access across environments.

---

## Table of Contents

- [🚀 Quick Start](#-quick-start)
- [📊 Access Control Matrix](#-access-control-matrix)
- [🔐 Permission Levels Explained](#-permission-levels-explained)
- [🎯 Common Scenarios](#-common-scenarios)
- [🛠️ Configuration Details](#️-configuration-details)
- [📖 Additional Resources](#-additional-resources)
- [💡 Best Practices](#-best-practices)

---

## 🚀 Quick Start

**Prerequisites:**
- Service principals created in Azure AD/AWS IAM/GCP
- Service principals added to Databricks workspace

**Step 1: Add Service Principal IDs**

Update `variables.yml`:

```yaml
variables:
  dev_service_principal:
    default: "abc-123-def-456"  # Your SP application ID

  stage_service_principal:
    default: "def-456-ghi-789"

  prod_service_principal:
    default: "ghi-789-jkl-012"
```

**Step 2: Create Required Groups**

Create these groups in your Databricks workspace:
- **Settings → Identity and access → Groups → Add group**

Required groups:
- `developers` - Data engineers and developers
- `qa_team` - QA engineers (for stage)
- `operations_team` - Operations/SRE team (for prod)
- `analytics_team` - Analytics and BI users

```bash
# Or use CLI
databricks groups create --display-name developers
databricks groups create --display-name qa_team
databricks groups create --display-name operations_team
databricks groups create --display-name analytics_team
```

> See [Setup Groups Guide](./SETUP_GROUPS.md) for more details on managing groups and members.

**Step 3: Configure Group Names (Optional)**

If your organization uses different names, update `variables.yml`:

```yaml
variables:
  developers_group:
    default: "your_custom_dev_group"  # Change here

  qa_team_group:
    default: "your_custom_qa_group"

  operations_group:
    default: "your_custom_ops_group"

  analytics_team_group:
    default: "your_custom_analytics_group"
```

**Step 4: Deploy & Verify Your User Environment Locally**

```bash
databricks bundle deploy -t user
```

**Step 5: Set Up CI/CD**

```yaml
# GitHub Actions / GitLab CI environment secrets
DATABRICKS_CLIENT_ID: <service-principal-app-id>
DATABRICKS_CLIENT_SECRET: <service-principal-secret>
DATABRICKS_HOST: https://your-workspace.cloud.databricks.com
```

**Step 6: Deploy Other Environments via Automation in CI/CD**

```bash
databricks bundle deploy -t <dev/stage/prod>
```

---

## 📊 Access Control Matrix

### Who Has Access to What?

| Role/Group | User (Local) | Dev | Stage | Prod |
|------------|-------------|-----|-------|------|
| **Developers** | Full access | CAN_MANAGE (all resources) | CAN_VIEW | - |
| **QA Team** | - | - | CAN_RUN (testing) | - |
| **Operations** | - | - | - | CAN_RUN (incidents) |
| **Analytics Team** | - | READ (silver/gold schemas) | READ (silver/gold) | READ (silver/gold) |
| **Service Principal** | - | CAN_MANAGE | CAN_MANAGE | CAN_MANAGE |

### Unity Catalog Schema Permissions

#### Development (`dev` target)
* Bronze: Full access for developers
  * `developers` → ALL_PRIVILEGES

* Silver: Developers write, Analytics read
  * `developers` → ALL_PRIVILEGES
  * `analytics_team` → USE_SCHEMA, SELECT

* Gold: Developers write, Analytics read
  * `developers` → ALL_PRIVILEGES
  * `analytics_team` → USE_SCHEMA, SELECT

#### Stage (`stage` target)
* Bronze: Read-only for testing
  * `developers`, `qa_team` → USE_SCHEMA, SELECT

* Silver: Read-only for all
  * `developers`, `qa_team`, `analytics_team` → USE_SCHEMA, SELECT

* Gold: Read-only for all
  * `developers`, `qa_team`, `analytics_team` → USE_SCHEMA, SELECT


#### Production (`prod` target)
* Bronze: Operations only (incident investigation)
  * `operations_team` → USE_SCHEMA, SELECT

* Silver: Read-only for analytics and operations
  * `analytics_team`, `operations_team` → USE_SCHEMA, SELECT

* Gold: Read-only for analytics and operations
  * `analytics_team`, `operations_team` → USE_SCHEMA, SELECT


---

## 🔐 Permission Levels Explained

### For Jobs, Pipelines, and Resources

| Level | View | Run | Cancel Runs | Edit/Delete |
|-------|------|-----|-------------|-------------|
| `CAN_VIEW` | ✓ | ✗ | ✗ | ✗ |
| `CAN_RUN` | ✓ | ✓ | ✗ | ✗ |
| `CAN_MANAGE_RUN` | ✓ | ✓ | ✓ | ✗ |
| `CAN_MANAGE` | ✓ | ✓ | ✓ | ✓ |

### For Unity Catalog Schemas

| Privilege | Description |
|-----------|-------------|
| `USE_SCHEMA` | Access schema (required for any operation) |
| `SELECT` | Query tables in schema |
| `MODIFY` | Insert/update/delete data |
| `CREATE_TABLE` | Create new tables |
| `CREATE_FUNCTION` | Create functions |
| `CREATE_VOLUME` | Create volumes |
| `CREATE_MODEL` | Create ML models |
| `ALL_PRIVILEGES` | Full control (includes all above) |

---

## 🎯 Common Scenarios

### Scenario 1: New Developer Joins Team

**What to do:** Add the user to the `developers` group in your Databricks workspace.

**Options:**
- Via UI: **Settings → Identity and access → Groups → developers → Add member**
- Via [Account SCIM](https://docs.databricks.com/aws/en/admin/users-groups/scim/) to add members automatically
- Via Terraform: Manage group membership in your infrastructure-as-code

> See [Setup Groups Guide](./SETUP_GROUPS.md) for instructions on managing groups and members.

### Covered Scenarios

1. Analytics team needs access to prod data => they have read-only access to silver and gold schemas.
2. Emergency: need to rerun failed prod job => operations team can trigger reruns (but cannot modify jobs).
3. QA engineer needs to test stage pipeline => QA team can run jobs in stage.

---

## 🛠️ Configuration Details

### Two Permission Systems

Databricks Asset Bundles use **two separate permission systems**:

#### 1. Resource Permissions (Jobs, Pipelines)
- Defined in `databricks.yml` under `targets.<env>.permissions`
- Controls who can view/run/manage resources
- Applied at target level (all resources in environment)

```yaml
targets:
  dev:
    permissions:
      - level: CAN_MANAGE
        group_name: ${var.developers_group}
```

#### 2. Unity Catalog Grants (Schemas)
Controls who can query/modify data in Unity Catalog schemas.

**Base grants** (environment-agnostic):
- Defined in `resources/medalion_architecture.schemas.yml`
- Applied to all environments
- Grants `ALL_PRIVILEGES` to service principal for automation

```yaml
resources:
  schemas:
    bronze_schema:
      grants:
        - principal: ${var.default_service_principal}
          privileges:
            - ALL_PRIVILEGES
```

**Environment-specific grants**:
- Defined in `databricks.yml` under `targets.<env>.resources.schemas.<schema>.grants`
- Applied per environment to control team access
- Merged with base grants

```yaml
targets:
  dev:
    resources:
      schemas:
        bronze_schema:
          grants:
            - principal: ${var.developers_group}
              privileges:
                - ALL_PRIVILEGES
```

---

## 📖 Additional Resources

- [Permissions Reference](./PERMISSIONS_REFERENCE.md) - Comprehensive details and examples
- [Setup Groups Guide](../SETUP_GROUPS.md) - Detailed group creation instructions
- [Bundles permission docs](https://docs.databricks.com/dev-tools/bundles/permissions)
- [Unity Catalog privileges](https://docs.databricks.com/data-governance/unity-catalog/manage-privileges/)

---

## 💡 Best Practices

✅ **DO:**
- Use groups for all permissions (never individual users)
- Use service principals for stage/prod deployments
- Grant least privilege (start with `CAN_VIEW`, add more as needed)
- Test permission changes in dev first
- Document why specific permissions exist

❌ **DON'T:**
- Don't hardcode user emails or application IDs
- Don't give `ALL_PRIVILEGES` in production unless necessary
- Don't rely on system groups like "users" or "admins"
- Don't skip creating groups before deployment
- Don't deploy to prod without service principal

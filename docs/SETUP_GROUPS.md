# Setting Up User Groups

Before deploying this bundle with permissions enabled, you must create the required groups in your Databricks workspace. These are custom groups you create, not system groups.

---

## Table of Contents

- [How to Create Groups](#how-to-create-groups)
- [Required Groups by Environment](#required-groups-by-environment)
- [Validation](#validation)
- [Adding Members to Groups](#adding-members-to-groups)
- [Customizing Group Names](#customizing-group-names)

---

## How to Create Groups

### Option 1: Via Databricks UI
1. Go to **Settings** → **Identity and access** → **Groups**
2. Click **Manage** button → **Add group**
3. Enter group name and click **Save**
4. Click on the group and add users

### Option 2: Via Databricks CLI
```bash
# Create groups
databricks groups create --display-name developers
databricks groups create --display-name qa_team
databricks groups create --display-name operations_team
databricks groups create --display-name analytics_team
```

### Option 3: Via SCIM Provisioning (Recommended for automation)
Use [SCIM provisioning](https://docs.databricks.com/aws/en/admin/users-groups/scim/) to automatically sync groups from your identity provider (Azure AD, Okta, etc.). This ensures groups and memberships stay in sync with your organization's identity system.

### Option 4: Via Terraform
Manage groups as infrastructure-as-code using the [Databricks Terraform provider](https://registry.terraform.io/providers/databricks/databricks/latest/docs/resources/group):

---

## Required Groups by Environment

### 1. developers (Required for all environments)
- **Purpose**: Data engineers and developers working on data pipelines
- **Access**:
  - **user**: Full access (ALL_PRIVILEGES) to all schemas
  - **dev**: Full access (ALL_PRIVILEGES) to all schemas
  - **stage**: Read-only (USE_SCHEMA, SELECT) to all schemas
  - **prod**: Not granted direct access (automation via service principal)

**Who to add**: Data engineers, ETL developers, data platform engineers

---

### 2. qa_team (Required for stage)
- **Purpose**: QA engineers testing data quality and pipelines
- **Access**:
  - **stage**: Read-only (USE_SCHEMA, SELECT) to all schemas
- **Who to add**: QA engineers, data quality analysts

---

### 3. operations_team (Required for prod)
- **Purpose**: Operations/SRE team for incident investigation and monitoring
- **Access**:
  - **prod**: Read-only (USE_SCHEMA, SELECT) to all schemas
- **Who to add**: SRE, DevOps, on-call engineers, platform team

---

### 4. analytics_team (Required for dev/stage/prod)
- **Purpose**: Analytics and BI teams consuming curated data
- **Access**:
  - **dev**: Read-only (USE_SCHEMA, SELECT) to silver and gold schemas
  - **stage**: Read-only (USE_SCHEMA, SELECT) to silver and gold schemas
  - **prod**: Read-only (USE_SCHEMA, SELECT) to silver and gold schemas
- **Who to add**: Data analysts, BI developers, business users, data scientists

---

## Validation

After creating groups, verify they exist:

**Via UI:**
- Go to **Settings** → **Identity and access** → **Groups**
- Verify all required groups are listed

**Via CLI:**
```bash
# List all groups
databricks groups list

# Get specific group details with members
databricks groups get <group_id>
```

---

## Adding Members to Groups

Once groups are created, add users to them:

**Via UI:**
- **Settings** → **Identity and access** → **Groups** → Select group → **Add member**

**Via SCIM API:**
Use a PATCH request to add members. See [SCIM API documentation](https://docs.databricks.com/api/workspace/groups) for details.

**Via Terraform:**
```hcl
resource "databricks_group_member" "dev_user" {
  group_id  = databricks_group.developers.id
  member_id = databricks_user.developer.id
}
```

---

## Customizing Group Names

If your organization uses different group names, update `variables.yml`:

```yaml
variables:
  developers_group:
    default: "your_custom_dev_group_name"

  qa_team_group:
    default: "your_custom_qa_group_name"

  operations_group:
    default: "your_custom_ops_group_name"

  analytics_team_group:
    default: "your_custom_analytics_group_name"
```

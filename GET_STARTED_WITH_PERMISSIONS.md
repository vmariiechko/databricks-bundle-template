# 🚀 Getting Started with Permissions

**5-minute guide to understanding and enabling permissions in your Databricks Asset Bundle template.**

---

## ⚡ Quick Start (Choose Your Path)

### Path 1: "I just want to test" 🧪
```bash
# Works immediately - no permissions setup needed!
databricks bundle deploy -t user
databricks bundle run sample_ingestion -t user
```
✅ **Development mode** gives you full access automatically.

---

### Path 2: "I want to enable team access (dev)" 👥

**Step 1:** Configure your team's group name
```yaml
# Edit: variables.yml
developers_group:
  default: "data_engineers"  # Your group name here
```

**Step 2:** Uncomment permissions in databricks.yml
```yaml
# Edit: databricks.yml → targets → dev → permissions
targets:
  dev:
    permissions:
      - level: CAN_VIEW
        group_name: users
      - level: CAN_MANAGE_RUN
        group_name: ${var.developers_group}  # Uncomment this!
```

**Step 3:** Deploy
```bash
databricks bundle deploy -t dev
```

✅ Now your team can view and run jobs in the dev environment!

---

### Path 3: "I need production-ready setup" 🏭

**Prerequisites:**
- [ ] Service principals created in Azure AD / AWS / GCP
- [ ] Service principals added to Databricks workspace
- [ ] User groups created in Databricks

**Step 1:** Configure variables
```yaml
# Edit: variables.yml
prod_service_principal:
  default: "abc-123-def-456"  # Your SP application ID

operations_group:
  default: "ops_team"  # Your ops group
```

**Step 2:** Enable service principal
```yaml
# Edit: databricks.yml → targets → prod
targets:
  prod:
    run_as:
      service_principal_name: ${var.prod_service_principal}  # Uncomment!

    permissions:  # Uncomment all of this
      - level: CAN_VIEW
        group_name: analytics_team
      - level: CAN_RUN
        group_name: ${var.operations_group}
      - level: CAN_MANAGE
        service_principal_name: ${var.prod_service_principal}
```

**Step 3:** Set up CI/CD
```yaml
# GitHub Actions / GitLab CI environment variables
DATABRICKS_CLIENT_ID: <service-principal-app-id>
DATABRICKS_CLIENT_SECRET: <service-principal-secret>
DATABRICKS_HOST: https://your-workspace.cloud.databricks.com
```

**Step 4:** Deploy via automation
```bash
databricks bundle deploy -t prod
```

✅ Production environment now secured with service principal!

---

## 📚 Documentation Navigation

```
START HERE
    ↓
┌───────────────────────────────────────────────────┐
│  GET_STARTED_WITH_PERMISSIONS.md (This file)      │
│  ✓ Quick paths to get going                       │
│  ✓ 5-minute setup                                 │
└───────────────────────────────────────────────────┘
    ↓
Need a quick lookup?
    ↓
┌───────────────────────────────────────────────────┐
│  PERMISSIONS_QUICK_REFERENCE.md                    │
│  ✓ Permission levels cheat sheet                  │
│  ✓ Common patterns                                │
│  ✓ Fast troubleshooting                           │
└───────────────────────────────────────────────────┘
    ↓
Ready to implement fully?
    ↓
┌───────────────────────────────────────────────────┐
│  PERMISSIONS_GUIDE.md                              │
│  ✓ Step-by-step setup                            │
│  ✓ Environment strategies                         │
│  ✓ Detailed troubleshooting                       │
└───────────────────────────────────────────────────┘
    ↓
Want to understand the architecture?
    ↓
┌───────────────────────────────────────────────────┐
│  docs/PERMISSIONS_ARCHITECTURE.md                  │
│  ✓ System design & flow                          │
│  ✓ Visual diagrams                                │
│  ✓ Deep technical details                         │
└───────────────────────────────────────────────────┘
    ↓
Need examples?
    ↓
┌───────────────────────────────────────────────────┐
│  permissions.yml                                   │
│  ✓ Reusable YAML anchors                         │
│  ✓ Copy-paste ready configs                      │
└───────────────────────────────────────────────────┘
│
│  resources/example_schema.schema.yml
│  ✓ Unity Catalog grants example                   │
└───────────────────────────────────────────────────┘
```

---

## 🎯 Common Scenarios

### Scenario 1: "New team member can't see jobs"

**Problem:** New developer can't see deployed jobs in dev environment.

**Solution:**
1. Add user to the group specified in `developers_group` variable
2. Verify group name matches exactly in Databricks
3. Check permissions are uncommented in `databricks.yml`

```bash
# Verify groups
databricks groups list
databricks groups get data_engineers
```

---

### Scenario 2: "I want different people to manage different jobs"

**Problem:** Analytics team should manage analytics jobs, ML team should manage ML jobs.

**Solution:** Use resource-level permissions

```yaml
# resources/analytics_job.job.yml
resources:
  jobs:
    analytics_job:
      permissions:
        - level: CAN_MANAGE
          group_name: analytics_team
      # ... rest of job config

# resources/ml_training_job.job.yml
resources:
  jobs:
    ml_training:
      permissions:
        - level: CAN_MANAGE
          group_name: ml_engineers
      # ... rest of job config
```

---

### Scenario 3: "Deployment fails with permission denied"

**Problem:** `databricks bundle deploy -t prod` fails with permission error.

**Quick Checks:**
```bash
# 1. Verify current user/SP
databricks current-user me

# 2. Validate bundle
databricks bundle validate -t prod

# 3. Check Unity Catalog permissions
# User/SP needs: USE CATALOG, USE SCHEMA, CREATE TABLE
```

**Solution:** Grant required Unity Catalog privileges to deployment identity.

---

### Scenario 4: "On-call engineer needs to rerun failed prod job"

**Problem:** Production job failed at 3 AM, on-call engineer needs to trigger rerun.

**Solution:** Grant `CAN_RUN` to on-call rotation group

```yaml
# databricks.yml → targets → prod → permissions
permissions:
  - level: CAN_VIEW
    group_name: engineering_team

  - level: CAN_RUN
    group_name: oncall_rotation  # Can trigger reruns

  - level: CAN_MANAGE
    service_principal_name: ${var.prod_service_principal}
```

Now on-call can trigger runs but not modify the job configuration.

---

## 🔍 Quick Reference Tables

### Permission Levels

| Level | View | Run | Cancel/Modify Runs | Edit Job | Delete |
|-------|------|-----|-------------------|----------|--------|
| `CAN_VIEW` | ✓ | ✗ | ✗ | ✗ | ✗ |
| `CAN_RUN` | ✓ | ✓ | ✗ | ✗ | ✗ |
| `CAN_MANAGE_RUN` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `CAN_MANAGE` | ✓ | ✓ | ✓ | ✓ | ✓ |

### Where to Define Permissions

| Location | Applies To | When to Use | File |
|----------|------------|-------------|------|
| Bundle-level | All resources, all targets | Rarely (org-wide policies) | `databricks.yml` |
| Target-level | All resources in one target | **Recommended** | `databricks.yml` |
| Resource-level | One specific resource | Exceptions only | `resources/*.yml` |

### Principal Types

| Type | Syntax | Best For | Example |
|------|--------|----------|---------|
| User | `user_name:` | Individual (avoid in prod) | `user@company.com` |
| Group | `group_name:` | **Recommended** for teams | `data_engineers` |
| Service Principal | `service_principal_name:` | **Recommended** for automation | `abc-123-def-456` |

---

## 🎨 Customization Checklist

### Basic Customization (Required)

- [ ] Update `developers_group` in `variables.yml`
- [ ] Update `operations_group` in `variables.yml`
- [ ] Uncomment permissions in `databricks.yml` for dev target
- [ ] Test deployment and verify access

### Intermediate Customization

- [ ] Create service principals for stage/prod
- [ ] Add service principal IDs to `variables.yml`
- [ ] Uncomment `run_as` configurations
- [ ] Uncomment permissions for stage/prod
- [ ] Set up CI/CD with SP credentials

### Advanced Customization

- [ ] Add custom permission sets to `permissions.yml`
- [ ] Configure resource-level permissions for critical jobs
- [ ] Set up Unity Catalog schema grants
- [ ] Define custom access control matrix
- [ ] Document your organization's permission strategy

---

## 💡 Pro Tips

### Tip 1: Start Small
Don't configure everything at once. Start with:
1. User target (no config needed)
2. Dev target (one permission)
3. Gradually add more as you learn

### Tip 2: Use Variables
Always use variables for group names and SPs:
```yaml
# Good ✓
group_name: ${var.developers_group}

# Bad ✗
group_name: data_engineers  # Hard to change later
```

### Tip 3: Test in Dev First
Always test permission changes in dev before applying to prod:
```bash
databricks bundle deploy -t dev
# Verify access with team members
# Then apply to prod
```

### Tip 4: Document Your Decisions
Add comments explaining why certain permissions exist:
```yaml
permissions:
  # On-call rotation needs CAN_RUN for emergency response
  - level: CAN_RUN
    group_name: oncall_rotation
```

### Tip 5: Use Groups for Everything
Even for a single user, create a group:
```yaml
# Good ✓
group_name: analytics_leads

# Bad ✗
user_name: analytics-lead@company.com  # What if they leave?
```

---

## 🆘 Emergency Troubleshooting

### "Everything is broken, I need to deploy NOW"

**Quick Fix:** Comment out all permissions temporarily
```yaml
# databricks.yml
targets:
  dev:
    # permissions:  # Comment this out
    #   - level: ...
```

Then deploy:
```bash
databricks bundle deploy -t dev
```

⚠️ **Remember to fix properly later!**

### "Service principal deployment fails"

**Quick Fix:** Switch back to user deployment temporarily
```yaml
run_as:
  user_name: ${workspace.current_user.userName}  # Use this
  # service_principal_name: ${var.prod_service_principal}  # Comment out
```

⚠️ **Only for emergency! Switch back to SP ASAP.**

---

## ✅ Success Criteria

You'll know permissions are working when:

✓ Team members can see resources they should see
✓ Team members cannot modify resources they shouldn't
✓ Service principal deployments succeed
✓ Audit logs show proper attribution
✓ Emergency access works (on-call can rerun jobs)
✓ No one has more access than needed

---

## 📞 Get More Help

- **Quick answers**: [`PERMISSIONS_QUICK_REFERENCE.md`](./PERMISSIONS_QUICK_REFERENCE.md)
- **Detailed guide**: [`PERMISSIONS_GUIDE.md`](./PERMISSIONS_GUIDE.md)
- **Architecture**: [`docs/PERMISSIONS_ARCHITECTURE.md`](./docs/PERMISSIONS_ARCHITECTURE.md)
- **Summary**: [`PERMISSIONS_SUMMARY.md`](./PERMISSIONS_SUMMARY.md)
- **Official Docs**: https://docs.databricks.com/dev-tools/bundles/permissions

---

**Ready to dive deeper?** → Start with [`PERMISSIONS_QUICK_REFERENCE.md`](./PERMISSIONS_QUICK_REFERENCE.md)

**Just want to deploy?** → Use Path 1 above (works immediately!)

**Need production setup?** → Follow Path 3 above, then read the full guide.


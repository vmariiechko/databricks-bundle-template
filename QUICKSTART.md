# Quick Start Guide

**5-Minute Test on Databricks Free Edition**

## ✅ Prerequisites

- Databricks workspace (free tier works!)
- Databricks CLI: `pip install databricks-cli`

## 🚀 Deploy & Test

```bash
# 1. Configure authentication
databricks configure --token

# 2. Validate the bundle
databricks bundle validate -t user

# 3. Deploy to your workspace
databricks bundle deploy -t user

# 4. Run the sample job
databricks bundle run sample_ingestion -t user

# 5. Trigger the sample pipeline
databricks bundle run sample_pipeline_trigger -t user
```

## 🎉 Success!

If the above commands work, you've successfully:
- ✅ Deployed a multi-environment bundle structure
- ✅ Created isolated user resources with `[user <name>]` prefix
- ✅ Ran a serverless job
- ✅ Triggered a DLT pipeline

## 📝 What's Next?

### 1. Customize for Your Project

**Update bundle name** in `databricks.yml`:
```yaml
bundle:
  name: your_project_name  # Change this
```

**Replace sample code** in `src/`:
- `jobs/run.py` → Your ingestion logic
- `pipelines/bronze.py` → Your bronze transformations
- `pipelines/silver.py` → Your silver transformations

### 2. Test Locally

Make changes and redeploy:
```bash
# After editing code
databricks bundle deploy -t user
databricks bundle run sample_ingestion -t user
```

### 3. Set Up CI/CD

When ready, push to git and deploy to shared environments:

```bash
# Deploy to dev (from dev branch)
git checkout dev
databricks bundle deploy -t dev

# Deploy to stage (from stage branch)
git checkout stage
databricks bundle deploy -t stage

# Deploy to prod (from main branch)
git checkout main
databricks bundle deploy -t prod
```

### 4. Clean Up

Remove test resources:
```bash
databricks bundle destroy -t user
```

## 🔍 Understanding the Structure

**4 Environments** → 4 isolated deployments:
- `user`: Your personal sandbox (development mode)
- `dev`: Shared team development
- `stage`: Pre-production testing
- `prod`: Production workloads

**Key Pattern**: Same code, different configs per environment.

## 💡 Tips

- Start with `user` target (default) for development
- All jobs are **paused by default** in `user` target
- Pipelines run in **development mode** (no optimizations) in `user` target
- **Serverless compute** works on Free Edition

## 📚 Learn More

- See `README.md` for full documentation
- Check `databricks.yml` to understand environment configs
- Explore `resources/*.yml` to see resource definitions

## ❓ Common Issues

**"Catalog not found"**: Update `catalog` in `variables.yml` to match yours

**"Pipeline stuck starting"**: Wait 5-10 minutes on Free Edition (serverless startup)

**"Cluster not supported"**: You're on Free Edition - ensure `serverless: true` is set

**"Resource already exists"**: You may have deployed before - run `databricks bundle destroy -t user` first


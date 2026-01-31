# Databricks Multi-Environment Bundle Template

A custom template for Databricks Asset Bundles that generates production-ready, multi-environment projects.

## Requirements

- Databricks CLI v0.274.0+ (`pip install databricks-cli`)
- Unity Catalog enabled workspace

## Usage

```bash
databricks bundle init https://github.com/vmariiechko/databricks-bundles-realworld
```

Or from a local clone:

```bash
databricks bundle init /path/to/databricks-bundles-realworld
```

The CLI will guide you through configuration options. Your generated project includes complete documentation for deployment and customization.

**Windows users:** Use PowerShell or Command Prompt for interactive prompts. Git Bash is not supported for interactive mode.

### Quick Start with Config File

For a quick, non-interactive setup or if you prefer to skip the prompts:

```bash
# From remote (create config.json with your values first):
databricks bundle init https://github.com/vmariiechko/databricks-bundles-realworld \
  --config-file config.json
```

```bash
# From local clone:
cp tests/configs/full_with_sp.json my-config.json   # Copy and edit with your values
databricks bundle init . --config-file my-config.json
```

See [example configs](./tests/configs/) for options and refer to [Template Options](#template-options) for available values.

## What You Get

- **Multi-environment deployment** (user/stage/prod, optional dev)
- **Unity Catalog integration** with medallion architecture schemas
- **Sample ETL jobs and pipelines**
- **Optional RBAC** with environment-aware group permissions
- **Configurable compute** (classic clusters, serverless, or both)
- **CI/CD pipeline templates** (Azure DevOps, GitHub Actions, GitLab)

## Template Options

| Option | Choices | Default |
|--------|---------|---------|
| Environment setup | `full` (user/stage/prod) / `minimal` (user/stage) | `full` |
| Include dev environment | `yes` / `no` | `no` |
| Compute type | `classic` / `serverless` / `both` | `classic` |
| Cloud provider | `azure` / `aws` / `gcp` | `azure` |
| Include permissions | `yes` / `no` | `yes` |
| Include CI/CD | `yes` / `no` | `yes` |
| CI/CD platform | `azure_devops` / `github_actions` / `gitlab` | `azure_devops` |
| Default branch | string | `main` |
| Release branch | string (full mode only) | `release` |

---

## Template Development

This section is for developers modifying the template itself.

### Repository Structure

```
databricks-bundles-realworld/
├── databricks_template_schema.json   # Prompt definitions
├── library/helpers.tmpl              # Go template helpers
├── template/
│   ├── update_layout.tmpl            # Conditional directory/file skipping
│   └── {{.project_name}}/            # Generated project structure
│       ├── .azure/                   # Azure DevOps CI/CD pipelines
│       ├── .github/                  # GitHub Actions workflows
│       ├── .gitlab-ci.yml.tmpl       # GitLab CI/CD pipeline
│       ├── docs/                     # Setup guides (CI/CD, permissions, groups)
│       └── ...                       # Bundle config, resources, src
├── tests/                            # Pytest test suite
├── ARCHITECTURE.md                   # Technical design
└── DEVELOPMENT.md                    # Developer notes
```

### Testing

```bash
# Install dependencies
pip install -r requirements_dev.txt

# Run automated tests
pytest tests/ -V
```

```bash
# Manual testing
databricks bundle init . --output-dir ../test-output --config-file tests/configs/full_with_dev.json

# Validate (requires Databricks CLI authentication)
cd ../test-output/test_full_with_dev/
databricks bundle validate -t user
```

### Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Design decisions and technical architecture
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development notes and future enhancements
- [tests/README.md](tests/README.md) - Tests setup and guide

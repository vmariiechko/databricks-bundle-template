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

## What You Get

- **Multi-environment deployment** (user/stage/prod, optional dev)
- **Unity Catalog integration** with medallion architecture schemas
- **Sample ETL jobs and pipelines**
- **Optional RBAC** with environment-aware group permissions
- **Configurable compute** (classic clusters, serverless, or both)

## Template Options

| Option | Choices | Default |
|--------|---------|---------|
| Environment setup | `full` (user/stage/prod) / `minimal` (user/stage) | `full` |
| Include dev environment | `yes` / `no` | `no` |
| Compute type | `classic` / `serverless` / `both` | `classic` |
| Cloud provider | `azure` / `aws` / `gcp` | `azure` |
| Include permissions | `yes` / `no` | `yes` |

---

## Template Development

This section is for developers modifying the template itself.

### Repository Structure

```
databricks-bundles-realworld/
├── databricks_template_schema.json   # Prompt definitions
├── library/helpers.tmpl              # Go template helpers
├── template/{{.project_name}}/       # Generated project structure
├── tests/                            # Pytest test suite
├── ARCHITECTURE.md                   # Technical design
└── DEVELOPMENT.md                    # Developer notes
```

### Testing

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run automated tests
pytest tests/ -v
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

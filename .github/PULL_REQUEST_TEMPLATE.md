## Related Issue

Closes #

## Summary

<!-- Brief description of what this PR does and why -->

## Changes

<!-- List the key changes made -->

-

## Configuration Axes Affected

<!-- Check all that apply -->

- [ ] Environment setup (full/minimal, dev environment)
- [ ] Compute type (classic/serverless/both)
- [ ] Permissions / RBAC
- [ ] CI/CD pipelines (Azure DevOps, GitHub Actions, GitLab)
- [ ] Cloud provider (Azure/AWS/GCP)
- [ ] Unity Catalog / schemas
- [ ] Template schema (`databricks_template_schema.json`)
- [ ] Template helpers (`library/helpers.tmpl`)
- [ ] None of the above (docs, tests, infrastructure only)

## Testing

- [ ] All tests pass (`pytest tests/ -V`)
- [ ] Manual template generation tested (`databricks bundle init . --output-dir ../test-output --config-file tests/configs/<config>.json`)
- [ ] New tests added for new functionality (if applicable)

## Checklist

- [ ] Go template syntax is valid (no unclosed `{{ }}` blocks)
- [ ] No `.tmpl` files appear in generated output
- [ ] Generated YAML files are valid
- [ ] Documentation updated (if behavior changed)

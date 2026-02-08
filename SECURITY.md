# Security Policy

## Scope

This security policy covers the **template generation logic** of this repository - the Go template files, schema definitions, and helper functions that produce Databricks Asset Bundle projects.

This policy does **not** cover:
- Security of the generated Databricks projects themselves
- Databricks workspace configuration or access control
- Runtime security of deployed jobs and pipelines

## Reporting a Vulnerability

If you discover a security vulnerability in this template, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Use [GitHub's private vulnerability reporting](https://github.com/vmariiechko/databricks-bundle-template/security/advisories/new) to submit your report
3. Alternatively, email **vmariiechko@gmail.com** with details

Please note: we ask that you do not disclose the vulnerability to the public or any third party until we have had a chance to address it and release a fix. This "Responsible Disclosure" helps protect all users of this template.

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Which template files are affected
- Potential impact on generated projects

## Response Timeline

- **Acknowledgment**: Within 48 hours of report
- **Initial assessment**: Within 1 week
- **Fix or mitigation**: Dependent on severity, targeting 2 weeks for critical issues

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` (branch) | Yes |
| `< 1.0.0` | No |

We recommend always using the latest version of the template.

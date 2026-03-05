#!/usr/bin/env bash
# regenerate-example.sh
#
# Regenerates the example repository from the current template state.
# Run from the template repo root.
#
# Usage:
#   ./scripts/regenerate-example.sh
#   ./scripts/regenerate-example.sh /path/to/databricks-bundle-template-example
#
# Requirements: databricks CLI, Python 3

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
EXAMPLE_REPO="${1:-$(cd "$TEMPLATE_REPO/../databricks-bundle-template-example" 2>/dev/null && pwd || echo "")}"
CONFIG_FILE="$TEMPLATE_REPO/scripts/example_repo_config.json"
PROJECT_NAME="my_data_project"

# Resolve Python executable
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null && "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,7) else 1)" 2>/dev/null; then
    PYTHON="$cmd"
    break
  fi
done

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
if [ -z "$EXAMPLE_REPO" ] || [ ! -d "$EXAMPLE_REPO" ]; then
  echo "ERROR: Example repo not found. Pass path as argument or place it at ../databricks-bundle-template-example"
  echo "Usage: ./scripts/regenerate-example.sh [/path/to/example-repo]"
  exit 1
fi

if ! command -v databricks &>/dev/null; then
  echo "ERROR: databricks CLI not found. Install it first."
  exit 1
fi

if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3.7+ not found. Ensure it is on PATH (or activate the project venv first)."
  exit 1
fi

echo "Template repo : $TEMPLATE_REPO"
echo "Example repo  : $EXAMPLE_REPO"
echo "Python        : $PYTHON ($($PYTHON --version))"
echo ""

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Generating project..."
databricks bundle init "$TEMPLATE_REPO" \
  --output-dir "$TEMP_DIR" \
  --config-file "$CONFIG_FILE"

GENERATED="$TEMP_DIR/$PROJECT_NAME"
if [ ! -d "$GENERATED" ]; then
  echo "ERROR: Expected generated project at $GENERATED"
  exit 1
fi

# ---------------------------------------------------------------------------
# Sync to example repo
# Files listed in EXCLUDE are maintained manually and never overwritten.
# ---------------------------------------------------------------------------
echo "Syncing to example repo..."

GENERATED="$GENERATED" EXAMPLE_REPO="$EXAMPLE_REPO" "$PYTHON" - <<'PYEOF'
import os, shutil, sys

src = os.environ["GENERATED"]
dst = os.environ["EXAMPLE_REPO"]

# Files/dirs to preserve in the example repo (never overwritten or deleted)
PRESERVE = {".git", "LICENSE"}

def is_preserved(rel_path):
    parts = rel_path.replace("\\", "/").split("/")
    return bool(parts and parts[0] in PRESERVE)

# Step 1: delete files in dst that no longer exist in src
for root, dirs, files in os.walk(dst, topdown=True):
    rel_root = os.path.relpath(root, dst)
    if is_preserved(rel_root):
        dirs[:] = []
        continue
    dirs[:] = [d for d in dirs if not is_preserved(os.path.join(rel_root, d).replace("\\", "/"))]
    for f in files:
        rel_file = os.path.join(rel_root, f) if rel_root != "." else f
        if not is_preserved(rel_file) and not os.path.exists(os.path.join(src, rel_file)):
            os.remove(os.path.join(dst, rel_file))
            print(f"  - Removed: {rel_file}")

# Step 2: copy all files from src to dst
for root, dirs, files in os.walk(src):
    rel_root = os.path.relpath(root, src)
    dst_dir = os.path.join(dst, rel_root)
    os.makedirs(dst_dir, exist_ok=True)
    for f in files:
        shutil.copy2(os.path.join(root, f), os.path.join(dst_dir, f))

print("  Sync complete.")
PYEOF

# ---------------------------------------------------------------------------
# Post-processing: inject example-repo-specific content into README
# ---------------------------------------------------------------------------
README="$EXAMPLE_REPO/README.md"

EXAMPLE_REPO="$EXAMPLE_REPO" PROJECT_NAME="$PROJECT_NAME" "$PYTHON" - <<'PYEOF'
import os, re

dst         = os.environ["EXAMPLE_REPO"]
project     = os.environ["PROJECT_NAME"]

# ---- databricks.yml: replace real workspace host with placeholder ----------
databricks_yml = os.path.join(dst, "databricks.yml")
yml_content = open(databricks_yml, encoding="utf-8").read()
yml_new = re.sub(
    r'(host:\s+https://)(?!your-workspace)[^\s]+',
    r'\1your-workspace.cloud.databricks.com',
    yml_content,
)
if yml_new != yml_content:
    open(databricks_yml, "w", encoding="utf-8").write(yml_new)
    print("  + Replaced workspace host with placeholder in databricks.yml")

# ---- README.md patches -----------------------------------------------------
readme_path = os.path.join(dst, "README.md")
content = open(readme_path, encoding="utf-8").read()

# 1. Title: generated README uses project name; example repo needs its own title
content = content.replace(
    f"# {project}\n",
    "# Databricks Bundle Template Example\n",
    1,
)

# 2. Project structure block: generated path uses project name; use repo name
content = content.replace(
    f"```\n{project}/\n",
    "```\ndatabricks-bundle-template-example/\n",
    1,
)

# 3. Workspace host warning — inserted before Quick Deploy
HOST_WARNING = (
    '> **Before you start**: Update the `workspace.host` in `databricks.yml` — '
    'replace `your-workspace.cloud.databricks.com` with your actual Databricks '
    'workspace URL (find it in your browser when logged in).'
)
if "Before you start" not in content:
    content = content.replace("### Quick Deploy", HOST_WARNING + "\n\n### Quick Deploy", 1)
    print("  + Injected workspace host warning into README.md")

# 4. Maintenance note — appended at end
MAINTENANCE_NOTE = """---

## About This Repository

This project is a pre-generated example from [databricks-bundle-template](https://github.com/vmariiechko/databricks-bundle-template).
It is periodically regenerated when the template is updated.

- To report issues with the bundle structure or configuration: open an issue in the **[template repo](https://github.com/vmariiechko/databricks-bundle-template/issues)**
- This repository is not intended for direct contribution — fix the template, then regenerate
"""
if "About This Repository" not in content:
    content = content.rstrip() + "\n\n" + MAINTENANCE_NOTE
    print("  + Appended maintenance note to README.md")

open(readme_path, "w", encoding="utf-8").write(content)
PYEOF

# ---------------------------------------------------------------------------
echo ""
echo "Done. Review changes:"
echo "  cd \"$EXAMPLE_REPO\" && git diff"

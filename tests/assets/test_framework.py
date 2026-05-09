"""Framework-level smoke tests for the Asset Library.

Auto-discovers every directory under `assets/` and runs a generic
installation check against it. Asset-specific assertions live in
`tests/assets/test_<asset_name>.py`.

Rules enforced for every asset:
- `databricks bundle init <asset_dir>` succeeds.
- No `.tmpl` suffix leaks into the generated output.
- The asset's `databricks_template_schema.json` is NOT copied to output.
- The asset ships at least one Markdown documentation file (README.md
  for human-facing assets, SKILL.md for agentskills.io-style skills).

Per-asset test configs live at `tests/configs/assets/<asset_name>.json`.
If an asset needs no prompt values, the config may be `{}`.
"""

import json
from pathlib import Path

import pytest

from .conftest import ASSET_CONFIGS_DIR, discover_assets


def _default_config_name(asset_dir: Path) -> str | None:
    """Return the default config basename for an asset, or `None` if absent."""
    basename = asset_dir.name.replace("-", "_")
    return basename if (ASSET_CONFIGS_DIR / f"{basename}.json").is_file() else None


@pytest.fixture(
    scope="session",
    params=discover_assets(),
    ids=[p.name for p in discover_assets()],
)
def installed_asset(request, install_asset) -> Path:
    """Install each discovered asset into a temp dir once per session."""
    asset_dir: Path = request.param
    config = _default_config_name(asset_dir)
    return install_asset(asset_dir.name, config=config)


def test_asset_install_succeeds(installed_asset: Path):
    files = list(installed_asset.rglob("*"))
    assert any(f.is_file() for f in files), "asset produced no files"


def test_no_tmpl_leftovers(installed_asset: Path):
    leftovers = [str(p.relative_to(installed_asset)) for p in installed_asset.rglob("*.tmpl")]
    assert not leftovers, f".tmpl files leaked into output: {leftovers}"


def test_schema_not_copied_to_output(installed_asset: Path):
    leaked = list(installed_asset.rglob("databricks_template_schema.json"))
    assert not leaked, f"schema leaked into output: {leaked}"


def test_asset_ships_documentation(installed_asset: Path):
    """Every asset must ship at least one Markdown doc file inside the
    installed tree: README.md for human-facing assets, SKILL.md for
    agentskills.io-style skill assets."""
    docs = list(installed_asset.rglob("README.md")) + list(installed_asset.rglob("SKILL.md"))
    assert docs, "asset did not install README.md or SKILL.md"


def test_asset_schema_is_valid_json():
    for asset_dir in discover_assets():
        schema_path = asset_dir / "databricks_template_schema.json"
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert "version" in data, f"{asset_dir.name}: schema missing 'version'"
        assert "min_databricks_cli_version" in data, (
            f"{asset_dir.name}: schema missing 'min_databricks_cli_version'"
        )

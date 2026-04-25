"""Shared fixtures and helpers for asset library tests.

Pytest auto-discovers this conftest for any test under `tests/assets/`.
Both the framework smoke tests (`test_framework.py`) and per-asset deep
tests (`test_<asset_name>.py`) use the `install_asset` fixture defined
here.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
ASSETS_DIR = REPO_ROOT / "assets"
ASSET_CONFIGS_DIR = REPO_ROOT / "tests" / "configs" / "assets"


def discover_assets() -> list[Path]:
    """Return every asset directory under `assets/` that ships a schema."""
    if not ASSETS_DIR.is_dir():
        return []
    return sorted(
        p
        for p in ASSETS_DIR.iterdir()
        if p.is_dir() and (p / "databricks_template_schema.json").is_file()
    )


def _run_install(
    asset_name: str,
    output_dir: Path,
    config_name: str | None = None,
    overrides: dict | None = None,
) -> Path:
    """Run `databricks bundle init` for an asset into `output_dir`.

    Exactly one of `config_name` or `overrides` may be provided. If
    neither is given, the install runs without `--config-file` and the
    asset's schema defaults must be acceptable for unattended install.
    Raises `RuntimeError` on install failure with captured stdout/stderr.
    """
    if config_name is not None and overrides is not None:
        raise ValueError("pass config_name or overrides, not both")

    asset_dir = ASSETS_DIR / asset_name
    if not asset_dir.is_dir():
        raise FileNotFoundError(f"no such asset: {asset_dir}")

    cmd = [
        "databricks",
        "bundle",
        "init",
        str(asset_dir),
        "--output-dir",
        str(output_dir),
    ]

    if overrides is not None:
        override_path = output_dir.parent / f"_{asset_name}_overrides.json"
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(json.dumps(overrides))
        cmd.extend(["--config-file", str(override_path)])
    elif config_name is not None:
        config_path = ASSET_CONFIGS_DIR / f"{config_name}.json"
        if not config_path.is_file():
            raise FileNotFoundError(f"no such config: {config_path}")
        cmd.extend(["--config-file", str(config_path)])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(
            f"Asset install failed for {asset_name}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return output_dir


@pytest.fixture(scope="session")
def install_asset(tmp_path_factory):
    """Factory fixture: install an asset and return its output directory.

    Usage (default config):

        def test_x(install_asset):
            out = install_asset("sdp-checkpoint-recovery", config="sdp_checkpoint_recovery")

    Usage (ad-hoc prompt values):

        def test_y(install_asset):
            out = install_asset("sdp-checkpoint-recovery", overrides={"target_dir": "foo"})

    `config` is the basename (without `.json`) of a file under
    `tests/configs/assets/`. Each call produces a fresh temp directory.
    """

    def _install(
        asset_name: str,
        *,
        config: str | None = None,
        overrides: dict | None = None,
    ) -> Path:
        output_dir = Path(tempfile.mkdtemp(prefix=f"asset_{asset_name}_"))
        return _run_install(asset_name, output_dir, config_name=config, overrides=overrides)

    return _install

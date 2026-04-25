"""Asset-specific tests for `assets/sdp-checkpoint-recovery`.

Framework-level smoke checks (no .tmpl leftovers, schema validity, etc.)
live in `tests/assets/test_framework.py`. This file asserts behavior
unique to this asset: exact files installed under the chosen
`target_dir`, plus the FQN-validation function exposed by the local
script.
"""

import importlib.util
from pathlib import Path

import pytest

ASSET_NAME = "sdp-checkpoint-recovery"
DEFAULT_CONFIG = "sdp_checkpoint_recovery"
DEFAULT_TARGET = "ops/sdp_checkpoint_recovery"

EXPECTED_FILES = (
    "sdp_reset_checkpoint_local.py",
    "sdp_reset_checkpoint_workspace.py",
    "README.md",
    "requirements.txt",
)


@pytest.fixture(scope="module")
def installed(install_asset) -> Path:
    """Install the asset once per module using the default target_dir."""
    return install_asset(ASSET_NAME, config=DEFAULT_CONFIG)


def test_installs_expected_files(installed: Path):
    target = installed / Path(DEFAULT_TARGET)
    for name in EXPECTED_FILES:
        assert (target / name).is_file(), f"missing expected file: {name}"


def test_no_extra_files_installed(installed: Path):
    """Asset should install exactly the three expected files, nothing more."""
    installed_files = sorted(
        p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()
    )
    expected = sorted(f"{DEFAULT_TARGET}/{name}" for name in EXPECTED_FILES)
    assert installed_files == expected, f"unexpected files: {set(installed_files) - set(expected)}"


def test_custom_target_dir(install_asset):
    """A user-provided `target_dir` value is honored."""
    out = install_asset(ASSET_NAME, overrides={"target_dir": "custom/path"})
    target = out / "custom" / "path"
    assert target.is_dir()
    for name in EXPECTED_FILES:
        assert (target / name).is_file(), f"missing expected file under custom target: {name}"


@pytest.mark.parametrize(
    "flows,should_raise",
    [
        (["a.b.c"], False),
        (["catalog.schema.table", "c2.s2.t2"], False),
        (["bad"], True),
        (["a.b"], True),
        ([""], True),
        (["a..c"], True),
        (["  .  .  "], True),
    ],
)
def test_validate_flow_fqns(installed: Path, flows, should_raise):
    """Load the installed local script and exercise its FQN validator directly."""
    script = installed / DEFAULT_TARGET / "sdp_reset_checkpoint_local.py"
    spec = importlib.util.spec_from_file_location("sdp_local", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if should_raise:
        with pytest.raises(ValueError):
            mod.validate_flow_fqns(flows)
    else:
        mod.validate_flow_fqns(flows)

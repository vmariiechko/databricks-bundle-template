"""
Pytest configuration and fixtures for template testing.

This module provides fixtures for generating template outputs and
accessing test configurations.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest

# =============================================================================
# Path Constants
# =============================================================================

TESTS_DIR = Path(__file__).parent
REPO_ROOT = TESTS_DIR.parent
TEMPLATE_DIR = REPO_ROOT / "template"
CONFIGS_DIR = TESTS_DIR / "configs"


# =============================================================================
# Configuration Fixtures
# =============================================================================


def get_config_files() -> list[Path]:
    """Get all config JSON files from the configs directory."""
    return list(CONFIGS_DIR.glob("*.json"))


def load_config(config_path: Path) -> dict[str, Any]:
    """Load a configuration JSON file."""
    with open(config_path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository root directory."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def template_dir() -> Path:
    """Return the template directory."""
    return TEMPLATE_DIR


@pytest.fixture(scope="session")
def configs_dir() -> Path:
    """Return the configs directory."""
    return CONFIGS_DIR


# =============================================================================
# Template Generation Fixtures
# =============================================================================


class GeneratedProject:
    """Represents a generated project from the template."""

    def __init__(self, output_dir: Path, config: dict[str, Any], config_name: str):
        self.output_dir = output_dir
        self.config = config
        self.config_name = config_name
        self.project_name = config["project_name"]
        self.project_dir = output_dir / self.project_name

    @property
    def databricks_yml(self) -> Path:
        return self.project_dir / "databricks.yml"

    @property
    def variables_yml(self) -> Path:
        return self.project_dir / "variables.yml"

    @property
    def readme_md(self) -> Path:
        return self.project_dir / "README.md"

    @property
    def quickstart_md(self) -> Path:
        return self.project_dir / "QUICKSTART.md"

    def get_file_content(self, relative_path: str) -> str:
        """Read and return content of a file in the generated project."""
        file_path = self.project_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return file_path.read_text(encoding="utf-8")

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists in the generated project."""
        return (self.project_dir / relative_path).exists()

    def dir_exists(self, relative_path: str) -> bool:
        """Check if a directory exists in the generated project."""
        return (self.project_dir / relative_path).is_dir()

    # Configuration helpers
    @property
    def is_minimal(self) -> bool:
        return self.config.get("environment_setup") == "minimal"

    @property
    def is_full(self) -> bool:
        return self.config.get("environment_setup") == "full"

    @property
    def has_dev_environment(self) -> bool:
        return self.config.get("include_dev_environment") == "yes"

    @property
    def has_permissions(self) -> bool:
        return self.config.get("include_permissions") == "yes"

    @property
    def is_serverless(self) -> bool:
        return self.config.get("compute_type") == "serverless"

    @property
    def is_classic(self) -> bool:
        return self.config.get("compute_type") == "classic"

    @property
    def is_both_compute(self) -> bool:
        return self.config.get("compute_type") == "both"

    @property
    def has_sp_configured(self) -> bool:
        return self.config.get("configure_sp_now") == "yes"


def generate_project(config_path: Path, output_dir: Path) -> GeneratedProject:
    """Generate a project from the template using a config file."""
    config = load_config(config_path)
    config_name = config_path.stem

    # Run databricks bundle init
    result = subprocess.run(
        [
            "databricks",
            "bundle",
            "init",
            str(REPO_ROOT),
            "--output-dir",
            str(output_dir),
            "--config-file",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Template generation failed for {config_name}:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return GeneratedProject(output_dir, config, config_name)


@pytest.fixture(scope="session")
def temp_output_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test outputs that persists across all tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="template_test_"))
    yield temp_dir
    # Cleanup after all tests
    shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# Parametrized Fixtures for All Configurations
# =============================================================================


@pytest.fixture(
    scope="session",
    params=[p.stem for p in get_config_files()],
    ids=[p.stem for p in get_config_files()],
)
def generated_project(request, temp_output_dir: Path) -> GeneratedProject:
    """
    Generate a project for each configuration file.

    This fixture is parametrized over all config files in tests/configs/,
    so tests using this fixture will run once per configuration.
    """
    config_name = request.param
    config_path = CONFIGS_DIR / f"{config_name}.json"
    project_output_dir = temp_output_dir / config_name

    return generate_project(config_path, project_output_dir)


# =============================================================================
# Individual Configuration Fixtures (for specific tests)
# =============================================================================


@pytest.fixture(scope="session")
def minimal_serverless_project(temp_output_dir: Path) -> GeneratedProject:
    """Generate a minimal serverless project."""
    config_path = CONFIGS_DIR / "minimal_serverless.json"
    return generate_project(config_path, temp_output_dir / "minimal_serverless_specific")


@pytest.fixture(scope="session")
def full_with_dev_project(temp_output_dir: Path) -> GeneratedProject:
    """Generate a full project with dev environment."""
    config_path = CONFIGS_DIR / "full_with_dev.json"
    return generate_project(config_path, temp_output_dir / "full_with_dev_specific")


@pytest.fixture(scope="session")
def full_no_dev_project(temp_output_dir: Path) -> GeneratedProject:
    """Generate a full project without dev environment."""
    config_path = CONFIGS_DIR / "full_no_dev.json"
    return generate_project(config_path, temp_output_dir / "full_no_dev_specific")


@pytest.fixture(scope="session")
def full_with_sp_project(temp_output_dir: Path) -> GeneratedProject:
    """Generate a full project with service principals configured."""
    config_path = CONFIGS_DIR / "full_with_sp.json"
    return generate_project(config_path, temp_output_dir / "full_with_sp_specific")

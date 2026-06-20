"""Asset-specific tests for `assets/pyspark-test-runner`.

Framework-level smoke checks (no .tmpl leftovers, schema validity,
documentation present, etc.) live in `tests/assets/test_framework.py`.
This file covers two things:

1. Generation: the exact files installed under the chosen `target_dir`,
   custom-target honoring, SKILL.md frontmatter, and that the installed
   script compiles.
2. Wrapper logic: the pure functions that build the bounded digest -
   JUnit parsing, node-id reconstruction, signature normalization,
   failure grouping, excerpt trimming, exit-code mapping, the digest
   budget, and interpreter / log-dir resolution.

The wrapper logic is tested against the *installed* script (loaded as a
module) so the tests exercise exactly what ships. No Spark and no
pytest-in-pytest: every input is a static fixture string or XML file.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ASSET_NAME = "pyspark-test-runner"
DEFAULT_CONFIG = "pyspark_test_runner"
DEFAULT_TARGET = ".agents"
SKILL_REL = "skills/pyspark-test-runner"

EXPECTED_FILES = (
    f"{SKILL_REL}/SKILL.md",
    f"{SKILL_REL}/scripts/run-pyspark-tests.py",
)


@pytest.fixture(scope="module")
def installed(install_asset) -> Path:
    """Install the asset once per module using the default target_dir."""
    return install_asset(ASSET_NAME, config=DEFAULT_CONFIG)


@pytest.fixture(scope="module")
def script_module(installed: Path):
    """Load the installed wrapper as a module so we can call its functions."""
    script = installed / DEFAULT_TARGET / SKILL_REL / "scripts" / "run-pyspark-tests.py"
    spec = importlib.util.spec_from_file_location("run_pyspark_tests_under_test", script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_pyspark_tests_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def test_installs_expected_files(installed: Path):
    target = installed / DEFAULT_TARGET
    for relative in EXPECTED_FILES:
        assert (target / relative).is_file(), f"missing expected file: {relative}"


def test_no_extra_files_installed(installed: Path):
    installed_files = sorted(
        p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()
    )
    expected = sorted(f"{DEFAULT_TARGET}/{name}" for name in EXPECTED_FILES)
    assert installed_files == expected, f"unexpected files: {set(installed_files) - set(expected)}"


def test_custom_target_dir(install_asset):
    out = install_asset(ASSET_NAME, overrides={"target_dir": ".claude"})
    target = out / ".claude"
    assert target.is_dir()
    for relative in EXPECTED_FILES:
        assert (target / relative).is_file(), f"missing under custom target: {relative}"


def test_skill_frontmatter_well_formed(installed: Path):
    skill = installed / DEFAULT_TARGET / SKILL_REL / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md missing opening frontmatter delimiter"
    end = text.find("\n---", 4)
    assert end != -1, "SKILL.md missing closing frontmatter delimiter"
    front = text[4:end]
    assert "name: pyspark-test-runner" in front, "frontmatter missing `name: pyspark-test-runner`"
    assert "description:" in front, "frontmatter missing `description`"


def test_installed_script_compiles(installed: Path):
    script = installed / DEFAULT_TARGET / SKILL_REL / "scripts" / "run-pyspark-tests.py"
    compile(script.read_text(encoding="utf-8"), str(script), "exec")


def test_script_exposes_tested_functions(script_module):
    for name in (
        "parse_junit",
        "node_id_from_case",
        "normalize_signature",
        "group_failures",
        "trim_excerpt",
        "result_for_exit_code",
        "build_digest",
        "resolve_python",
        "writable_log_dir",
    ):
        assert hasattr(script_module, name), f"wrapper missing function: {name}"


# --------------------------------------------------------------------------- #
# Node-id reconstruction
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "file_attr,classname,name,expected",
    [
        # file attribute present (some pytest configs / record_xml_attribute)
        ("tests/test_x.py", "tests.test_x.TestC", "test_m", "tests/test_x.py::TestC::test_m"),
        ("tests/test_x.py", "tests.test_x", "test_f", "tests/test_x.py::test_f"),
        (
            "tests/unit/test_x.py",
            "tests.unit.test_x.TestC",
            "test_m",
            "tests/unit/test_x.py::TestC::test_m",
        ),
        (
            "tests/test_x.py",
            "tests.test_x.TestC.TestNested",
            "test_m",
            "tests/test_x.py::TestC::TestNested::test_m",
        ),
        (
            "tests/test_x.py",
            "tests.test_x.TestC",
            "test_m[param-1]",
            "tests/test_x.py::TestC::test_m[param-1]",
        ),
        # file attribute absent (pytest's DEFAULT junit output) - rebuild path
        # from the dotted classname using the lowercase/TitleCase convention.
        ("", "tests.test_x.TestC", "test_m", "tests/test_x.py::TestC::test_m"),
        (
            "",
            "tests.test_cleaning_utils.TestCleanStr",
            "test_a",
            "tests/test_cleaning_utils.py::TestCleanStr::test_a",
        ),
        ("", "tests.test_x", "test_f", "tests/test_x.py::test_f"),
        (
            "",
            "tests.unit.test_x.TestC.TestNested",
            "test_m",
            "tests/unit/test_x.py::TestC::TestNested::test_m",
        ),
        # no usable attributes at all
        ("", "", "test_orphan", "test_orphan"),
    ],
)
def test_node_id_from_case(script_module, file_attr, classname, name, expected):
    assert script_module.node_id_from_case(file_attr, classname, name) == expected


# --------------------------------------------------------------------------- #
# JUnit parsing
# --------------------------------------------------------------------------- #
def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "report.xml"
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_junit_missing_file_returns_none(script_module, tmp_path):
    assert script_module.parse_junit(tmp_path / "nope.xml") is None


def test_parse_junit_counts_and_failures(script_module, tmp_path):
    # Real pytest JUnit output omits the `file` attribute (only classname,
    # name, time): node ids must be rebuilt from the dotted classname.
    xml = """<?xml version="1.0"?>
    <testsuites>
      <testsuite name="pytest" tests="4" failures="1" errors="1" skipped="1" time="2.5">
        <testcase classname="tests.test_a" name="test_ok" time="0.1"/>
        <testcase classname="tests.test_a.TestX" name="test_bad" time="0.1">
          <failure message="AssertionError: boom">trace\nAssertionError: boom</failure>
        </testcase>
        <testcase classname="tests.test_a" name="test_err" time="0.1">
          <error message="RuntimeError: nope">trace\nRuntimeError: nope</error>
        </testcase>
        <testcase classname="tests.test_a" name="test_skip" time="0.0">
          <skipped message="skip"/>
        </testcase>
      </testsuite>
    </testsuites>"""
    result = script_module.parse_junit(_write(tmp_path, xml))
    counts = result["counts"]
    assert counts["tests"] == 4
    assert counts["failures"] == 1
    assert counts["errors"] == 1
    assert counts["skipped"] == 1
    assert counts["passed"] == 1
    assert counts["time"] == 2.5
    assert len(result["failures"]) == 2
    node_ids = {f["node_id"] for f in result["failures"]}
    assert "tests/test_a.py::TestX::test_bad" in node_ids
    assert "tests/test_a.py::test_err" in node_ids


def test_parse_junit_single_testsuite_root(script_module, tmp_path):
    xml = """<testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0" time="0.1">
      <testcase classname="tests.test_a" file="tests/test_a.py" name="test_ok" time="0.1"/>
    </testsuite>"""
    result = script_module.parse_junit(_write(tmp_path, xml))
    assert result["counts"]["tests"] == 1
    assert result["counts"]["passed"] == 1


def test_parse_junit_malformed_returns_parse_error(script_module, tmp_path):
    result = script_module.parse_junit(_write(tmp_path, "<testsuite> not closed"))
    assert "parse_error" in result
    assert result["counts"]["tests"] == 0


def test_parse_junit_failure_without_message_uses_body_last_line(script_module, tmp_path):
    xml = """<testsuite tests="1" failures="1" errors="0" skipped="0" time="0.1">
      <testcase classname="tests.test_a" file="tests/test_a.py" name="test_bad">
        <failure>line one\nValueError: the real cause</failure>
      </testcase>
    </testsuite>"""
    result = script_module.parse_junit(_write(tmp_path, xml))
    assert result["failures"][0]["reason"] == "ValueError: the real cause"


# --------------------------------------------------------------------------- #
# Signature normalization + grouping
# --------------------------------------------------------------------------- #
def test_normalize_collapses_numbers(script_module):
    a = script_module.normalize_signature("AssertionError: expected 5 got 7")
    b = script_module.normalize_signature("AssertionError: expected 91 got 3")
    assert a == b


def test_normalize_strips_hex_addresses(script_module):
    out = script_module.normalize_signature("<obj at 0x7f3abc> failed")
    assert "0x7f3abc" not in out
    assert "HEXADDR" in out


def test_normalize_strips_paths(script_module):
    nix = script_module.normalize_signature("error in /tmp/abc/def.py here")
    win = script_module.normalize_signature(r"error in C:\temp\abc\def.py here")
    assert "PATH" in nix
    assert "PATH" in win


def test_normalize_empty_message(script_module):
    assert script_module.normalize_signature("") == "<no message>"


def test_group_failures_collapses_same_signature(script_module):
    failures = [
        {"reason": "AssertionError: expected 1", "node_id": "a", "body": "ta"},
        {"reason": "AssertionError: expected 2", "node_id": "b", "body": "tb"},
        {"reason": "AssertionError: expected 3", "node_id": "c", "body": "tc"},
        {"reason": "ValueError: other", "node_id": "d", "body": "td"},
    ]
    groups = script_module.group_failures(failures)
    assert len(groups) == 2
    assert groups[0]["count"] == 3  # sorted most-frequent first
    assert groups[0]["node_ids"] == ["a", "b", "c"]
    assert groups[1]["count"] == 1


# --------------------------------------------------------------------------- #
# Excerpt trimming
# --------------------------------------------------------------------------- #
def test_trim_excerpt_short_unchanged(script_module):
    text = "line1\nline2\nline3"
    assert script_module.trim_excerpt(text, 40) == ["line1", "line2", "line3"]


def test_trim_excerpt_keeps_head_and_tail(script_module):
    text = "\n".join(f"L{i}" for i in range(100))
    out = script_module.trim_excerpt(text, 40)
    assert len(out) == 40
    assert out[0] == "L0"
    assert out[-1] == "L99"
    assert any("trimmed" in line for line in out)


# --------------------------------------------------------------------------- #
# Exit-code mapping
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "code,expected",
    [
        (0, "PASSED"),
        (1, "FAILED"),
        (2, "ERROR"),
        (3, "INTERNAL ERROR"),
        (4, "USAGE ERROR"),
        (5, "NO TESTS"),
        (6, "WARNINGS"),
        (99, "EXIT 99"),
    ],
)
def test_result_for_exit_code(script_module, code, expected):
    result, _hint = script_module.result_for_exit_code(code)
    assert result == expected


# --------------------------------------------------------------------------- #
# Digest assembly + budget
# --------------------------------------------------------------------------- #
def _digest(script_module, **kwargs):
    defaults = {
        "result": "FAILED",
        "hint": "",
        "exit_code": 1,
        "junit": None,
        "project_root": "/p",
        "target": "tests/",
        "command": "py -m pytest",
        "log_path": "/p/.pyspark-test-logs/x.log",
        "junit_path": "/p/.pyspark-test-logs/x.xml",
        "log_tail": None,
        "excerpt_lines": 40,
        "max_failures_listed": 20,
    }
    defaults.update(kwargs)
    return script_module.build_digest(**defaults)


def test_digest_passed_header_only(script_module):
    junit = {
        "counts": {"tests": 5, "failures": 0, "errors": 0, "skipped": 0, "passed": 5, "time": 1.0},
        "failures": [],
    }
    out = _digest(script_module, result="PASSED", exit_code=0, junit=junit)
    assert "Result: PASSED" in out
    assert "Collected: 5" in out
    assert "FAILING TESTS" not in out


def test_digest_flood_collapses_to_one_signature(script_module):
    failures = [
        {
            "node_id": f"tests/test_x.py::TestA::test_{i}",
            "reason": f"AssertionError: expected {i}",
            "body": "Traceback\nAssertionError: expected X",
        }
        for i in range(50)
    ]

    junit = {
        "counts": {
            "tests": 50,
            "failures": 50,
            "errors": 0,
            "skipped": 0,
            "passed": 0,
            "time": 9.0,
        },
        "failures": failures,
    }
    out = _digest(script_module, junit=junit)
    lines = out.splitlines()
    assert "SIGNATURE 1 of 1  (50 tests)" in out
    assert "... and 30 more (see log)" in out  # 50 listed-capped at 20
    assert len(lines) <= script_module.MAX_OUTPUT_LINES


def test_digest_respects_output_budget_with_many_signatures(script_module):
    failures = [
        {
            "node_id": f"tests/test_x.py::test_{i}",
            "reason": f"Error number {i}: {'x' * 50}",
            "body": "\n".join(f"frame {j}" for j in range(200)),
        }
        for i in range(1000)
    ]
    junit = {
        "counts": {
            "tests": 1000,
            "failures": 1000,
            "errors": 0,
            "skipped": 0,
            "passed": 0,
            "time": 1.0,
        },
        "failures": failures,
    }
    out = _digest(script_module, junit=junit)
    assert len(out.splitlines()) <= script_module.MAX_OUTPUT_LINES


def test_digest_falls_back_to_log_tail_without_junit(script_module):
    out = _digest(
        script_module,
        result="ERROR",
        exit_code=2,
        junit=None,
        log_tail=["ImportError: no module named foo", "during collection"],
    )
    assert "LOG TAIL" in out
    assert "ImportError: no module named foo" in out


def test_digest_reports_parse_error(script_module):
    junit = {
        "counts": {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "passed": 0, "time": 0.0},
        "failures": [],
        "parse_error": "mismatched tag",
    }
    out = _digest(script_module, junit=junit, log_tail=["some tail"])
    assert "unparseable" in out.lower()


def test_digest_handles_non_ascii_in_failure(script_module):
    junit = {
        "counts": {"tests": 1, "failures": 1, "errors": 0, "skipped": 0, "passed": 0, "time": 0.1},
        "failures": [
            {
                "node_id": "tests/test_x.py::test_a",
                "reason": "AssertionError: Αθήνα",
                "body": "Αθήνα",
            }
        ],
    }
    out = _digest(script_module, junit=junit)
    assert "Αθήνα" in out


# --------------------------------------------------------------------------- #
# Interpreter + log-dir resolution
# --------------------------------------------------------------------------- #
def test_resolve_python_explicit_must_exist(script_module, tmp_path):
    with pytest.raises(SystemExit):
        script_module.resolve_python(tmp_path, tmp_path / "no-such-python")


def test_resolve_python_explicit_honored(script_module, tmp_path):
    fake = tmp_path / "python"
    fake.write_text("", encoding="utf-8")
    assert script_module.resolve_python(tmp_path, fake) == fake


def test_resolve_python_falls_back_to_current(script_module, tmp_path):
    assert script_module.resolve_python(tmp_path, None) == Path(sys.executable)


def test_writable_log_dir_anchors_to_project(script_module, tmp_path):
    out = script_module.writable_log_dir(tmp_path)
    assert out == tmp_path / ".pyspark-test-logs"
    assert out.is_dir()


def test_writable_log_dir_env_override(script_module, tmp_path, monkeypatch):
    override = tmp_path / "custom-logs"
    monkeypatch.setenv("PYSPARK_TEST_LOG_DIR", str(override))
    out = script_module.writable_log_dir(tmp_path / "project")
    assert out == override
    assert out.is_dir()

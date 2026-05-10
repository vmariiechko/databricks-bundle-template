"""Asset-specific tests for `assets/dbx-ro-query`.

Framework-level smoke checks (no .tmpl leftovers, schema validity,
documentation present, etc.) live in `tests/assets/test_framework.py`.
This file asserts behavior unique to this asset: exact files installed
under the chosen `target_dir`, custom-target honoring, and the
read-only SQL guard exposed by the installed script.

The asset follows the agentskills.io canonical layout: SKILL.md and a
sibling `scripts/` directory both inside `<target_dir>/skills/<name>/`.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ASSET_NAME = "dbx-ro-query"
DEFAULT_CONFIG = "dbx_ro_query"
DEFAULT_TARGET = ".agents"

EXPECTED_FILES = (
    "skills/dbx-ro-query/SKILL.md",
    "skills/dbx-ro-query/scripts/dbx-ro-query.py",
    "skills/dbx-ro-query/references/agent-claude-code.md",
    "skills/dbx-ro-query/references/agent-codex.md",
    "skills/dbx-ro-query/references/agent-cursor.md",
)


@pytest.fixture(scope="module")
def installed(install_asset) -> Path:
    """Install the asset once per module using the default target_dir."""
    return install_asset(ASSET_NAME, config=DEFAULT_CONFIG)


@pytest.fixture(scope="module")
def script_module(installed: Path):
    """Load the installed script as a module so we can call its functions."""
    script = installed / DEFAULT_TARGET / "skills" / "dbx-ro-query" / "scripts" / "dbx-ro-query.py"
    spec = importlib.util.spec_from_file_location("dbx_ro_query_under_test", script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dbx_ro_query_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_installs_expected_files(installed: Path):
    target = installed / Path(DEFAULT_TARGET)
    for relative in EXPECTED_FILES:
        assert (target / relative).is_file(), f"missing expected file: {relative}"


def test_no_extra_files_installed(installed: Path):
    """Asset should install exactly the two expected files, nothing more."""
    installed_files = sorted(
        p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()
    )
    expected = sorted(f"{DEFAULT_TARGET}/{name}" for name in EXPECTED_FILES)
    assert installed_files == expected, f"unexpected files: {set(installed_files) - set(expected)}"


def test_custom_target_dir(install_asset):
    """A user-provided `target_dir` value is honored."""
    out = install_asset(ASSET_NAME, overrides={"target_dir": ".claude"})
    target = out / ".claude"
    assert target.is_dir()
    for relative in EXPECTED_FILES:
        assert (target / relative).is_file(), f"missing under custom target: {relative}"


def test_skill_frontmatter_well_formed(installed: Path):
    """SKILL.md must start with YAML frontmatter declaring `name` and `description`."""
    skill = installed / DEFAULT_TARGET / "skills" / "dbx-ro-query" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md missing opening frontmatter delimiter"
    end = text.find("\n---", 4)
    assert end != -1, "SKILL.md missing closing frontmatter delimiter"
    front = text[4:end]
    assert "name: dbx-ro-query" in front, "SKILL.md frontmatter missing `name: dbx-ro-query`"
    assert "description:" in front, "SKILL.md frontmatter missing `description`"


def test_skill_references_pointer_present(installed: Path):
    """SKILL.md operational notes must point readers at the references/ folder.

    The references/ subfolder holds per-agent runtime tips (loaded on demand).
    SKILL.md needs to surface this discovery hint so agents know to look there
    when they hit a runtime quirk."""
    skill = installed / DEFAULT_TARGET / "skills" / "dbx-ro-query" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "references/" in text, "SKILL.md missing pointer to references/ folder"


def test_references_files_have_headings(installed: Path):
    """Every references file must start with a Markdown H1 so agents loading
    it on demand see a clear scope title."""
    refs_dir = installed / DEFAULT_TARGET / "skills" / "dbx-ro-query" / "references"
    for ref in refs_dir.glob("agent-*.md"):
        first_line = ref.read_text(encoding="utf-8").splitlines()[0]
        assert first_line.startswith("# "), f"{ref.name} missing H1 heading on first line"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "  SELECT 1",
        "select 1",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "SHOW TABLES",
        "DESCRIBE foo.bar.baz",
        "DESC foo.bar.baz",
        "EXPLAIN SELECT 1",
        "/* leading comment */ SELECT 1",
        "-- leading comment\nSELECT 1",
        "SELECT '/* DROP TABLE foo */ 1' AS x",
        "SELECT 'INSERT' AS x",
        "SELECT 1 -- DROP TABLE foo",
        "SELECT * FROM t WHERE col = 'I will not DROP this'",
    ],
)
def test_validate_accepts_read_only(script_module, sql):
    """These statements are read-only; validate_read_only_sql must not exit."""
    script_module.validate_read_only_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO foo VALUES (1)",
        "UPDATE foo SET x = 1",
        "DELETE FROM foo",
        "MERGE INTO foo USING bar ON foo.id = bar.id",
        "CREATE TABLE foo (x INT)",
        "ALTER TABLE foo ADD COLUMN y INT",
        "DROP TABLE foo",
        "TRUNCATE TABLE foo",
        "OPTIMIZE foo",
        "VACUUM foo",
        "COPY INTO foo FROM 's3://bucket/'",
        "CALL my_proc()",
        "GRANT SELECT ON foo TO bar",
        "REVOKE SELECT ON foo FROM bar",
        "REPAIR TABLE foo",
        "MSCK REPAIR TABLE foo",
        "ANALYZE TABLE foo COMPUTE STATISTICS",
        "CACHE TABLE foo",
        "UNCACHE TABLE foo",
        "SET spark.foo = 'bar'",
        "USE catalog.schema",
        "SELECT 1; DROP TABLE foo",
        "BEGIN; SELECT 1; END",
        "WITH x AS (SELECT 1) INSERT INTO y SELECT * FROM x",
        "REFRESH TABLE foo",
        "EXECUTE IMMEDIATE 'SELECT 1'",
        "",
        "   ",
        "/* comment */",
    ],
)
def test_validate_rejects_destructive_or_unknown(script_module, sql):
    """These statements must be rejected (SystemExit)."""
    with pytest.raises(SystemExit):
        script_module.validate_read_only_sql(sql)


def test_sql_for_inspection_strips_block_comments(script_module):
    cleaned = script_module.sql_for_inspection("SELECT /* DROP TABLE x */ 1")
    assert "DROP" not in cleaned.upper()


def test_sql_for_inspection_strips_line_comments(script_module):
    cleaned = script_module.sql_for_inspection("SELECT 1 -- DROP TABLE x\n")
    assert "DROP" not in cleaned.upper()


def test_sql_for_inspection_strips_string_literals(script_module):
    cleaned = script_module.sql_for_inspection("SELECT 'DROP TABLE x' AS y")
    assert "DROP" not in cleaned.upper()


def test_sql_for_inspection_strips_double_quoted(script_module):
    cleaned = script_module.sql_for_inspection('SELECT "DROP TABLE x" AS y')
    assert "DROP" not in cleaned.upper()


def test_sql_for_inspection_handles_doubled_quote_escape(script_module):
    """SQL escapes single quotes by doubling: 'it''s'. The strip must not break."""
    cleaned = script_module.sql_for_inspection("SELECT 'it''s a DROP test' AS x")
    assert "DROP" not in cleaned.upper()


def test_choose_auto_format_shapes(script_module):
    assert script_module.choose_auto_format([]) == "json"
    assert script_module.choose_auto_format([{"a": 1}]) == "scalar"
    assert script_module.choose_auto_format([{"a": 1}, {"a": 2}]) == "lines"
    assert script_module.choose_auto_format([{"a": 1, "b": 2}]) == "tsv"


def test_format_rows_scalar_requires_one_by_one(script_module):
    with pytest.raises(SystemExit):
        script_module.format_rows([{"a": 1}, {"a": 2}], "scalar")
    with pytest.raises(SystemExit):
        script_module.format_rows([{"a": 1, "b": 2}], "scalar")


def test_format_rows_tsv_has_tab_separators(script_module):
    out = script_module.format_rows([{"a": 1, "b": 2}], "tsv")
    assert "a\tb" in out and "1\t2" in out


def test_format_rows_lines_one_value_per_line(script_module):
    out = script_module.format_rows([{"a": "x"}, {"a": "y"}], "lines")
    assert out.splitlines() == ["x", "y"]


def test_format_rows_csv_quotes_embedded_delimiter(script_module):
    """Cell values containing commas must be quoted in CSV output."""
    out = script_module.format_rows([{"a": "x,y", "b": "1"}], "csv")
    assert '"x,y"' in out


def test_format_rows_unknown_format_rejects(script_module):
    with pytest.raises(SystemExit):
        script_module.format_rows([{"a": 1}], "yaml")

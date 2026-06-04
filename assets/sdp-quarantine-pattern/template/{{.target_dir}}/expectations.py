"""Data quality rules for the quarantine-pattern pipeline.

Pure Python (no pyspark import), so this module is unit-testable offline and
safe to import from the pipeline at runtime. Rules live in `expectations.json`;
this module loads them and derives the inverse predicate the quarantine table
uses.

Every drop predicate is written NULL-safe (each column test guarded by
`IS NOT NULL`) so the silver/quarantine split is a clean partition. The asset
README ("The NULL trap") explains why; do not relax that guard without reading
it.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_HERE, "expectations.json")


def load_rules(action: str, config_path: str = _CONFIG_PATH) -> dict[str, str]:
    """Return `{expectation_name: sql_predicate}` for `"drop"` or `"warn"`."""
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    return {rule["name"]: rule["query"] for rule in config[action]}


def build_quarantine_expr(drop_rules: dict[str, str]) -> str:
    """Build the inverse-of-all-drop-rules predicate for the quarantine table.

    Given `{name: predicate}`, returns `NOT((p1) AND (p2) AND ...)`, which is
    true exactly for rows that fail at least one drop rule.

    Args:
        drop_rules: Mapping of drop expectation name to SQL predicate.

    Returns:
        The inverse SQL predicate as a string.

    Raises:
        ValueError: If `drop_rules` is empty.
    """
    predicates = list(drop_rules.values())
    if not predicates:
        raise ValueError(
            "at least one drop rule is required to build the quarantine expression"
        )
    joined = " AND ".join(f"({p})" for p in predicates)
    return f"NOT({joined})"


DROP_RULES = load_rules("drop")
WARN_RULES = load_rules("warn")

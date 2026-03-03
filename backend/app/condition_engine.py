from __future__ import annotations

from typing import Any, Dict, Iterable, List

from simpleeval import InvalidExpression, NameNotDefined, SimpleEval


ALLOWED_NAMES = {
    "open",
    "high",
    "low",
    "close",
    "volume",
    "pivot",
    "r1",
    "r2",
    "s1",
    "s2",
}


def _normalize_condition(expr: str) -> str:
    text = expr.strip().lower()
    # Remove common filler words so "stock high is greater than close" -> "high greater than close"
    for word in ("stock ", "stocks ", "the ", " price ", " prices "):
        text = text.replace(word, " ")
    for phrase in (" is ", " are ", " was ", " were "):
        text = text.replace(phrase, " ")
    # Phrase -> operator (order matters: longer phrases first)
    replacements = {
        " greater than or equal to ": " >= ",
        " less than or equal to ": " <= ",
        " at least ": " >= ",
        " at most ": " <= ",
        " above r1": " > r1",
        " above r2": " > r2",
        " above pivot": " > pivot",
        " below r1": " < r1",
        " below s1": " < s1",
        " crossed r1": " >= r1",
        " crossed r2": " >= r2",
        " above ": " > ",
        " below ": " < ",
        " less than ": " < ",
        " greater than ": " > ",
        " higher than ": " > ",
        " lower than ": " < ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Collapse multiple spaces and strip
    return " ".join(text.split())


def evaluate_condition(row: Dict[str, Any], condition: str) -> bool:
    expr = _normalize_condition(condition)
    if not expr:
        return True

    # Build whitelist of names from the row
    names = {k: row.get(k) for k in ALLOWED_NAMES}

    s = SimpleEval(names=names, functions={}, operators=None)
    try:
        result = s.eval(expr)
    except (InvalidExpression, NameNotDefined, ZeroDivisionError, TypeError, SyntaxError):
        return False
    return bool(result)


def evaluate_conditions_for_rows(
    rows: Iterable[Dict[str, Any]],
    conditions: List[str],
    combine: str = "and",
) -> List[Dict[str, Any]]:
    clean_conditions = [c for c in conditions if c and c.strip()]
    if not clean_conditions:
        return list(rows)

    mode = combine.lower()
    if mode not in {"and", "or"}:
        mode = "and"

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        results = [evaluate_condition(row, cond) for cond in clean_conditions]
        if not results:
            filtered.append(row)
            continue
        if mode == "and":
            ok = all(results)
        else:
            ok = any(results)
        if ok:
            filtered.append(row)

    return filtered


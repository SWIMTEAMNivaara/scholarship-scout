"""Small product-quality helpers for Scholarship Scout.

These helpers do not determine eligibility or verify scholarship facts. They
support a manual application-readiness checklist and safer CSV exports.
"""
from __future__ import annotations

from typing import Any, Iterable

READINESS_CHECKLIST = (
    ("source_reviewed", "Reviewed the provider's official source"),
    ("eligibility_checked", "Checked eligibility requirements"),
    ("deadline_confirmed", "Confirmed the current deadline and application cycle"),
    ("documents_ready", "Prepared the required documents"),
    ("application_submitted", "Submitted the application (if applying)"),
)


def safe_csv_cell(value: Any) -> str:
    """Convert a value to text and neutralize common spreadsheet formula starts."""
    if value is None:
        return ""
    text = str(value)
    # Excel and similar spreadsheet apps may interpret these leading characters
    # as formulas. Prefix an apostrophe so exported user/source text stays text.
    probe = text.lstrip(" \t\r\n")
    if probe.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def readiness_summary(completed: Iterable[str] | None = None) -> dict[str, Any]:
    """Summarize checked checklist keys without assuming facts about a listing."""
    done = set(completed or ())
    valid_keys = {key for key, _ in READINESS_CHECKLIST}
    done &= valid_keys
    total = len(READINESS_CHECKLIST)
    return {
        "completed": len(done),
        "total": total,
        "percent": round((len(done) / total) * 100) if total else 0,
        "complete_keys": sorted(done),
        "is_complete": len(done) == total,
    }


def readiness_items() -> tuple[tuple[str, str], ...]:
    """Return the stable checklist definitions for rendering in the UI."""
    return READINESS_CHECKLIST

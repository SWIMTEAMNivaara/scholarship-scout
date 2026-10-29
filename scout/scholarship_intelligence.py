"""Deadline review and side-by-side comparison helpers for Scholarship Scout.

These helpers organize extracted information; they do not independently verify
scholarship facts or confirm that a deadline is still open.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

_DATE_FORMATS = (
    "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
    "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %B %Y", "%d %b %Y",
    "%m/%d/%Y",
)


def parse_date(value: Any) -> date | None:
    """Parse common extracted date formats without guessing ambiguous text."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or raw.lower() in {"unknown", "not found", "n/a", "none", "tbd", "to be announced"}:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def assess_deadline(value: Any, today: date | None = None) -> dict[str, Any]:
    """Return a cautious review label for an extracted deadline."""
    today = today or date.today()
    parsed = parse_date(value)
    if parsed is None:
        return {"status": "unknown", "label": "Needs checking", "date": None,
                "days_remaining": None,
                "note": "No recognizable deadline was extracted. Open the provider's page and check the current application cycle."}
    days = (parsed - today).days
    if days < 0:
        return {"status": "past", "label": "Past date — verify status", "date": parsed.isoformat(),
                "days_remaining": days,
                "note": "The extracted date has passed. The scholarship may be closed, extended, or on a new cycle; check the provider's page."}
    if days == 0:
        return {"status": "today", "label": "Date is today", "date": parsed.isoformat(),
                "days_remaining": 0,
                "note": "Check the provider's timezone and exact submission cutoff immediately."}
    if days <= 7:
        return {"status": "urgent", "label": "Due within 7 days", "date": parsed.isoformat(),
                "days_remaining": days,
                "note": "Confirm the deadline and time cutoff on the provider's page before applying."}
    return {"status": "upcoming", "label": "Future date found", "date": parsed.isoformat(),
            "days_remaining": days,
            "note": "This is an extracted date, not a verified open application. Confirm the current cycle with the provider."}


def _text(value: Any) -> str:
    if value is None:
        return "Not found"
    if isinstance(value, (list, tuple, set)):
        cleaned = [str(v).strip() for v in value if str(v).strip()]
        return "; ".join(cleaned) if cleaned else "Not found"
    text = str(value).strip()
    return text if text and text.lower() not in {"none", "null", "n/a"} else "Not found"


def _domain(value: Any) -> str:
    try:
        parsed = urlparse(str(value or ""))
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            return parsed.hostname.lower()
    except (ValueError, TypeError):
        pass
    return "Unknown"


def build_comparison_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Create presentation-ready comparison rows with missing values explicit."""
    rows = []
    for record in records[:4]:
        if not isinstance(record, dict):
            continue
        match = record.get("match") if isinstance(record.get("match"), dict) else {}
        deadline = assess_deadline(record.get("deadline"))
        rows.append({
            "Scholarship": _text(record.get("name") or record.get("title")),
            "Provider": _text(record.get("provider") or record.get("source_name")),
            "Preliminary fit": f"{_text(match.get('status'))} ({match.get('score', 0)}/100)",
            "Deadline": deadline["date"] or "Unknown",
            "Deadline review": deadline["label"],
            "Benefits / award": _text(record.get("benefits")),
            "Income condition": _text(record.get("income_limit")),
            "Academic criteria": _text(record.get("academic_criteria")),
            "Application link": _text(record.get("application_url") or record.get("url")),
            "Source domain": _domain(record.get("url") or record.get("source_url")),
        })
    return rows

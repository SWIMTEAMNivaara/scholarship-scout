"""Reliability helpers for Scholarship Scout.

These helpers are intentionally independent of the app's database schema so they
can be added without risking existing user data.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Iterable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

VALID_STATUSES = {"Interested", "Planning", "Applied", "Rejected", "Awarded"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_text(value: Any) -> str:
    """Convert an arbitrary value into a normalized, whitespace-collapsed string."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_url(value: Any) -> str:
    """Normalize a URL for matching; remove common tracking parameters and fragments."""
    raw = normalize_text(value)
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.I):
        return ""
    try:
        parsed = urlparse(raw)
        if not parsed.netloc:
            return ""
        host = parsed.netloc.lower()
        path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/") or "/"
        # Ignore tracking/query parameters for duplicate detection.
        return f"{parsed.scheme.lower()}://{host}{path}".rstrip("/")
    except (ValueError, TypeError):
        return ""


def scholarship_key(item: dict[str, Any]) -> str:
    """Return a stable duplicate-detection key, preferring normalized application/source URL."""
    if not isinstance(item, dict):
        return ""
    for field in ("application_url", "application_link", "source_url", "url", "link"):
        url = normalize_url(item.get(field))
        if url:
            return "url:" + url
    name = normalize_text(item.get("name") or item.get("title")).casefold()
    provider = normalize_text(item.get("provider") or item.get("organization")).casefold()
    if name:
        return f"name:{name}|provider:{provider}"
    return ""


def deduplicate_scholarships(items: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep first occurrence of each scholarship, preferring URL-based identity."""
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            logger.warning("Skipping malformed scholarship record of type %s", type(item).__name__)
            continue
        key = scholarship_key(item)
        if not key:
            # Preserve records with no usable identity rather than silently dropping them.
            output.append(item)
        elif key not in seen:
            seen.add(key)
            output.append(item)
        else:
            logger.info("Skipped duplicate scholarship record: %s", normalize_text(item.get("name") or item.get("title"))[:100])
    return output


def validate_scholarship(item: Any) -> tuple[bool, list[str]]:
    """Lightweight sanity checks; this does not certify eligibility or factual accuracy."""
    issues: list[str] = []
    if not isinstance(item, dict):
        return False, ["Record must be an object/dictionary."]

    name = normalize_text(item.get("name") or item.get("title"))
    if len(name) < 3:
        issues.append("Missing or unusually short scholarship name.")

    for field in ("application_url", "application_link", "source_url", "url", "link"):
        if normalize_text(item.get(field)):
            if not normalize_url(item.get(field)):
                issues.append(f"{field} is not a valid HTTP(S) URL.")
            break

    amount = item.get("amount")
    if amount is not None and normalize_text(amount):
        amount_text = normalize_text(amount)
        if len(amount_text) > 120:
            issues.append("Amount field is unusually long; verify extracted data.")

    deadline = normalize_text(item.get("deadline"))
    if deadline and deadline.casefold() not in {"not specified", "unknown", "varies", "rolling", "not available", "n/a"}:
        # Accept common textual deadlines; only flag malformed ISO-looking dates.
        if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", deadline) and not DATE_RE.fullmatch(deadline):
            issues.append("Deadline looks date-like but is not in YYYY-MM-DD format.")
        elif DATE_RE.fullmatch(deadline):
            from datetime import date
            try:
                date.fromisoformat(deadline)
            except ValueError:
                issues.append("Deadline is not a valid calendar date.")
    return not issues, issues


def deduplicate_and_validate(items: Iterable[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return deduplicated records and validation reports for records with issues."""
    unique = deduplicate_scholarships(items)
    reports: list[dict[str, Any]] = []
    for item in unique:
        valid, issues = validate_scholarship(item)
        if not valid:
            reports.append({
                "name": normalize_text(item.get("name") or item.get("title")) or "(unnamed record)",
                "issues": issues,
            })
    return unique, reports


def configuration_status(environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Return safe configuration diagnostics without revealing secrets."""
    env = environ if environ is not None else os.environ
    tinyfish_key = bool(normalize_text(env.get("TINYFISH_API_KEY")))
    gemini_key = bool(normalize_text(env.get("GEMINI_API_KEY")))
    model = normalize_text(env.get("GEMINI_MODEL")) or "gemini-3.6-flash"
    return {
        "tinyfish_configured": tinyfish_key,
        "gemini_configured": gemini_key,
        "gemini_model": model,
        "notes": [
            "API keys are never included in this report.",
            "A configured key does not guarantee that the provider is reachable.",
            "Eligibility matches are preliminary and must be verified with the official provider.",
        ],
    }


def safe_parse_json(payload: Any) -> tuple[Any | None, str | None]:
    """Parse a JSON string or pass through already-decoded JSON data safely."""
    import json
    if isinstance(payload, (dict, list)):
        return payload, None
    if not isinstance(payload, (str, bytes, bytearray)):
        return None, "Response was not JSON text or a decoded JSON object."
    try:
        return json.loads(payload), None
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        logger.warning("Could not parse provider response as JSON: %s", type(exc).__name__)
        return None, "Provider returned malformed JSON."


def validate_tracking_status(status: Any) -> tuple[bool, str]:
    """Validate a saved scholarship status before writing it to SQLite."""
    normalized = normalize_text(status)
    if normalized in VALID_STATUSES:
        return True, normalized
    return False, f"Unsupported status. Expected one of: {', '.join(sorted(VALID_STATUSES))}."

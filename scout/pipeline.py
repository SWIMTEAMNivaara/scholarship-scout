"""Safe, additive discovery-pipeline helpers for Scholarship Scout."""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

from scout.reliability import deduplicate_and_validate

logger = logging.getLogger(__name__)


def prepare_discovered_scholarships(
    records: Any,
    *,
    source_label: str = "discovery",
) -> dict[str, Any]:
    """Normalize provider output into records, deduplicate, and report quality issues.

    Accepts a list of dictionaries, or a dictionary containing one of the common
    result keys: scholarships, results, items, or data. Malformed entries are
    skipped by the reliability layer. It never writes to the database.
    """
    extracted: list[dict[str, Any]] = []
    container_keys = ("scholarships", "results", "items", "data")

    if isinstance(records, list):
        candidates = records
    elif isinstance(records, dict):
        candidates = None
        for key in container_keys:
            value = records.get(key)
            if isinstance(value, list):
                candidates = value
                break
        if candidates is None:
            # A single scholarship-shaped dictionary is accepted as one record.
            if any(k in records for k in ("name", "title")):
                candidates = [records]
            else:
                candidates = []
                logger.warning("%s response had no recognized list field", source_label)
    else:
        candidates = []
        if records is not None:
            logger.warning("%s response had unexpected type %s", source_label, type(records).__name__)

    for candidate in candidates:
        if isinstance(candidate, dict):
            extracted.append(candidate)
        else:
            logger.warning("%s contained a non-object record; skipped", source_label)

    unique, issues = deduplicate_and_validate(extracted)
    return {
        "scholarships": unique,
        "validation_issues": issues,
        "input_count": len(candidates),
        "output_count": len(unique),
        "duplicates_removed": max(0, len(extracted) - len(unique)),
        "source_label": source_label,
    }


def safe_provider_call(
    call: Callable[..., Any],
    *args: Any,
    provider_name: str = "provider",
    **kwargs: Any,
) -> dict[str, Any]:
    """Call a provider function safely and return a stable result envelope."""
    try:
        response = call(*args, **kwargs)
    except TimeoutError:
        logger.warning("%s call timed out", provider_name)
        return {"ok": False, "data": None, "error": f"{provider_name} request timed out."}
    except Exception as exc:  # provider boundaries must not crash the UI
        logger.exception("%s call failed (%s)", provider_name, type(exc).__name__)
        return {"ok": False, "data": None, "error": f"{provider_name} request failed. Check configuration and logs."}

    if response is None:
        return {"ok": False, "data": None, "error": f"{provider_name} returned no response."}
    return {"ok": True, "data": response, "error": None}


def official_source_reminder(record: dict[str, Any]) -> str:
    """Return a concise verification reminder for any scholarship record."""
    name = str(record.get("name") or record.get("title") or "this scholarship").strip()
    return (
        f"Verify {name} on the official provider website before applying. "
        "Eligibility and deadline information may be incomplete or outdated."
    )

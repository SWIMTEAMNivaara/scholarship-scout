"""Heuristic source-origin signals for Scholarship Scout; never certifies factual accuracy."""
from __future__ import annotations
from typing import Any
from urllib.parse import urlparse

GOV_SUFFIXES = (".gov", ".gov.in", ".nic.in", ".gov.uk", ".gov.au")
EDU_SUFFIXES = (".edu", ".edu.in", ".ac.in", ".ac.uk", ".edu.au")


def _host(url: Any) -> str:
    raw = str(url or "").strip()
    try:
        parsed = urlparse(raw if "://" in raw else "")
        host = (parsed.hostname or "").lower().strip(".")
        # reject malformed or hostless URLs; never infer trust from plain text
        return host if parsed.scheme in {"http", "https"} and host and "." in host else ""
    except (ValueError, TypeError):
        return ""


def assess_source(record: dict[str, Any] | None) -> dict[str, Any]:
    """Assess domain-origin signals only. This is not a verification or safety guarantee."""
    record = record if isinstance(record, dict) else {}
    url = record.get("url") or record.get("source_url") or record.get("link") or record.get("application_url") or record.get("application_link")
    host = _host(url)
    if not host:
        return {"domain": "Unknown", "label": "Source unavailable", "level": "unknown", "score": 0,
                "note": "No valid source URL was found. Find the original provider page before relying on this listing."}
    if host == "gov.in" or host.endswith(".gov.in") or host.endswith(".nic.in") or any(host == s.lstrip(".") or host.endswith(s) for s in (".gov", ".gov.uk", ".gov.au")):
        return {"domain": host, "label": "Government-domain signal", "level": "strong", "score": 90,
                "note": "The URL uses a government-domain pattern. This does not prove the page is current, genuine, or that the scholarship details are accurate."}
    if any(host == s.lstrip(".") or host.endswith(s) for s in EDU_SUFFIXES):
        return {"domain": host, "label": "Education-domain signal", "level": "institutional", "score": 75,
                "note": "The URL uses an education-domain pattern. Confirm the institution and the specific scholarship page independently."}
    if host.endswith(".org") or host.endswith(".org.in"):
        return {"domain": host, "label": "Organisation-domain signal", "level": "organisation", "score": 55,
                "note": "An organisation-style domain is not proof of official status. Check the organisation identity and application terms."}
    return {"domain": host, "label": "General web source", "level": "general", "score": 35,
            "note": "The domain alone does not establish official status. Cross-check the scholarship on the provider's official website."}


def annotate_source(record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy annotated with transparent source-origin signals."""
    result = dict(record)
    result["source_assessment"] = assess_source(result)
    return result


def prioritize_official_sources(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by domain-origin signal, preserving original order within each level."""
    annotated = [annotate_source(r) for r in records if isinstance(r, dict)]
    return sorted(annotated, key=lambda r: -r["source_assessment"]["score"])

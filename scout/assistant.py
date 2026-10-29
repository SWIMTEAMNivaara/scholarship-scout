"""Source-grounded scholarship Q&A with optional Gemini API and local fallback.

This module:
- Uses only scholarship records supplied by the app as evidence.
- Retries a small number of transient Gemini failures.
- Produces a structured local answer when Gemini is unavailable.
- Never prints or returns API keys or raw provider error bodies.
"""
import os
import re
import time

import requests


_STOP_WORDS = {
    "the", "and", "for", "with", "what", "when", "where", "how", "can",
    "does", "this", "that", "are", "you", "about", "tell", "please", "from",
    "have", "will", "which", "would", "could", "should", "these", "those",
    "your", "their", "there", "then", "than", "into", "some", "any",
    "based", "current", "available", "source", "sources", "scholarship",
    "scholarships", "explain", "list", "show", "find", "information",
}

_TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}
_MAX_SOURCES = 5


def _safe_string(value, limit=3000):
    """Convert a value to a bounded, display-safe string."""
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _item_text(item):
    """Build searchable text from a scholarship record."""
    fields = (
        "name", "title", "provider", "source_name", "summary", "snippet",
        "eligibility_text", "academic_criteria", "income_limit", "benefits",
        "documents", "deadline", "application_cycle", "page_text_excerpt",
    )
    parts = []
    for field in fields:
        value = item.get(field, "")
        if value:
            parts.append(_safe_string(value, 3000 if field == "page_text_excerpt" else 1000))
    return " ".join(parts).strip()


def _rank_items(question, items):
    """Rank records by question-term overlap, preserving original order for ties."""
    words = {
        word for word in re.findall(r"[a-zA-Z0-9₹]+", question.lower())
        if len(word) > 2 and word not in _STOP_WORDS
    }
    if not words:
        return list(items[:_MAX_SOURCES])

    ranked = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        text = _item_text(item).lower()
        item_words = set(re.findall(r"[a-zA-Z0-9₹]+", text))
        overlap = len(words & item_words)

        # Give extra weight to matching the specific field being asked about.
        q = question.lower()
        field_bonus = 0
        if any(term in q for term in ("document", "certificate", "paperwork", "proof")) and item.get("documents"):
            field_bonus += 2
        if any(term in q for term in ("deadline", "last date", "due date", "closing")) and item.get("deadline"):
            field_bonus += 2
        if any(term in q for term in ("income", "family income")) and (item.get("income_limit") or item.get("eligibility_text")):
            field_bonus += 2
        if any(term in q for term in ("eligible", "eligibility", "qualify", "criteria", "requirement")):
            if item.get("eligibility_text") or item.get("academic_criteria"):
                field_bonus += 2
        if any(term in q for term in ("amount", "benefit", "award", "funding", "how much")) and item.get("benefits"):
            field_bonus += 2

        score = overlap + field_bonus
        if score:
            ranked.append((score, -index, item))

    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for _, _, item in ranked[:_MAX_SOURCES]]


def _requested_fields(question):
    """Return the scholarship fields most relevant to the question."""
    q = question.lower()
    requested = []

    if any(term in q for term in ("eligible", "eligibility", "qualify", "qualification", "criteria", "requirement", "marks", "category", "who can apply")):
        requested.extend([
            ("Eligibility", "eligibility_text"),
            ("Academic criteria", "academic_criteria"),
        ])
    if any(term in q for term in ("income", "family income", "earn", "financial condition")):
        requested.append(("Income limit / income condition", "income_limit"))
    if any(term in q for term in ("document", "certificate", "paperwork", "proof", "upload")):
        requested.append(("Documents", "documents"))
    if any(term in q for term in ("deadline", "last date", "due date", "when to apply", "closing", "application date")):
        requested.extend([
            ("Deadline", "deadline"),
            ("Application cycle", "application_cycle"),
        ])
    if any(term in q for term in ("amount", "benefit", "money", "award", "funding", "how much", "stipend")):
        requested.append(("Benefits / award", "benefits"))

    # For broad scholarship questions, show the main useful fields.
    if not requested:
        requested = [
            ("Summary", "summary"),
            ("Eligibility", "eligibility_text"),
            ("Income limit / income condition", "income_limit"),
            ("Documents", "documents"),
            ("Deadline", "deadline"),
        ]

    # Deduplicate while preserving order.
    seen = set()
    return [row for row in requested if not (row[1] in seen or seen.add(row[1]))]


def _fallback_answer(question, profile, sources):
    """Return a useful local answer without inventing missing scholarship facts."""
    if not sources:
        return (
            "I don't have scholarship source records to answer that yet. Open **Discover**, "
            "search for scholarships, and ask again. I won't invent eligibility rules, income "
            "limits, required documents, award amounts, or deadlines."
        )

    fields = _requested_fields(question)
    lines = [
        "**Local source-grounded answer**",
        "",
        "Below are the relevant details present in the records currently available to the app. "
        "A missing field means it was not extracted; it does not mean the provider has no such requirement.",
        "",
    ]

    for item in sources:
        name = _safe_string(item.get("name") or item.get("title") or "Scholarship opportunity", 250)
        lines.append(f"### {name}")

        for label, field in fields:
            value = item.get(field)
            if not value and field == "summary":
                value = item.get("snippet")
            display_value = _safe_string(value, 700) if value else "Not found in the extracted source text; verify on the provider's page."
            lines.append(f"- **{label}:** {display_value}")

        url = _safe_string(item.get("application_url") or item.get("url"), 1000)
        if url.startswith(("https://", "http://")):
            lines.append(f"- **Source:** {url}")
        lines.append("")

    lines.extend([
        "**Evidence status:** These are extracted record fields, not independent verification. If a requested field says it was not found, the app has not established that detail.",
        "**Important:** Confirm eligibility, required documents, income rules, award amounts, and the current application cycle on the scheme's official notification/page before applying. A general scholarship roundup may describe multiple schemes and may not identify which rule applies to each one.",
    ])
    return "\n".join(lines)


def _extract_text(payload):
    """Extract visible text from Gemini candidates without assuming a fixed first-part shape."""
    texts = []
    for candidate in payload.get("candidates", []) or []:
        content = candidate.get("content") or {}
        for part in content.get("parts", []) or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    return "\n".join(texts).strip()


def _gemini_model():
    """Read the model from .env; default to the model used in the successful short API test."""
    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"


def _make_context(sources):
    context_blocks = []
    for index, item in enumerate(sources, start=1):
        context_blocks.append(
            f"SOURCE {index}\n"
            f"Name: {_safe_string(item.get('name') or item.get('title') or 'Unknown', 250)}\n"
            f"Provider: {_safe_string(item.get('provider') or item.get('source_name') or 'Unknown', 250)}\n"
            f"URL: {_safe_string(item.get('application_url') or item.get('url') or 'Unknown', 1000)}\n"
            f"Deadline: {_safe_string(item.get('deadline') or 'Not extracted', 300)}\n"
            f"Income limit: {_safe_string(item.get('income_limit') or 'Not extracted', 500)}\n"
            f"Benefits: {_safe_string(item.get('benefits') or 'Not extracted', 700)}\n"
            f"Documents: {_safe_string(item.get('documents') or 'Not extracted', 1000)}\n"
            f"Eligibility text: {_safe_string(item.get('eligibility_text') or 'Not extracted', 1200)}\n"
            f"Academic criteria: {_safe_string(item.get('academic_criteria') or 'Not extracted', 700)}\n"
            f"Application cycle: {_safe_string(item.get('application_cycle') or 'Not extracted', 300)}\n"
            f"Summary: {_safe_string(item.get('summary') or item.get('snippet') or 'Not extracted', 1000)}\n"
            f"Extracted page text: {_safe_string(item.get('page_text_excerpt') or '', 500)}"
        )
    return "\n\n".join(context_blocks)


def _post_gemini(endpoint, api_key, prompt, max_output_tokens=1800):
    """Post to Gemini with limited retries for transient service failures."""
    last_response = None
    for attempt in range(3):
        try:
            response = requests.post(
                endpoint,
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": max_output_tokens,
                    },
                },
                timeout=(10, 45),
            )
            last_response = response
            if response.ok:
                return response, None

            if response.status_code not in _TRANSIENT_HTTP_STATUSES or attempt == 2:
                return response, None

        except requests.Timeout as exc:
            if attempt == 2:
                return None, "timeout"
        except requests.RequestException:
            if attempt == 2:
                return None, "connection"

        # Brief backoff only; avoid long waits in the Streamlit UI.
        time.sleep(1.0 * (attempt + 1))

    return last_response, "connection"


def answer_question(question, profile, items):
    """Answer from supplied scholarship records; use Gemini when configured and available."""
    question = (question or "").strip()
    items = [item for item in (items or []) if isinstance(item, dict)]

    if not question:
        return {"answer": "Enter a question to get started.", "sources": [], "mode": "local"}

    sources = _rank_items(question, items)
    if not sources:
        sources = items[:_MAX_SOURCES]

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "answer": _fallback_answer(question, profile, sources),
            "sources": sources,
            "mode": "local",
        }

    context = _make_context(sources)
    prompt = f"""You are Scholarship Scout, a careful scholarship information assistant for students in India.

Answer the user's question using ONLY the scholarship source records below. Use the student profile only when relevant to compare against criteria explicitly present in the records.
- Do not invent facts, eligibility rules, income limits, documents, award amounts, or deadlines.
- If a requested detail is missing, say "Not found in the extracted source text" and explain what to verify.
- Cover requested fields in a compact table or concise bullets; keep each scholarship brief.
- Distinguish facts in records from details needing verification.
- Never guarantee eligibility or an award.
- If multiple limits (e.g. ₹6 lakh and ₹10 lakh) are not mapped to a named scheme/condition, report both as source wording and say the applicable one is not established.
- A page excerpt is not proof that a field was extracted or verified.
- Name the source URL when available; do not call a third-party page official.
- Keep the complete answer under 600 words. Do not repeat long source excerpts.

Student profile (use only if relevant): {profile}
User question: {question}

Scholarship source records:
{context if context else "No scholarship source records are currently available."}
"""

    model = _gemini_model()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    try:
        response, failure = _post_gemini(endpoint, api_key, prompt)

        if response is None:
            fallback = _fallback_answer(question, profile, sources)
            note = (
                "Gemini timed out after limited retries"
                if failure == "timeout"
                else "Gemini could not be reached after limited retries"
            )
            return {
                "answer": fallback + f"\n\n*{note}; showing the local source-grounded answer instead.*",
                "sources": sources,
                "mode": "local",
            }

        if not response.ok:
            status = response.status_code
            fallback = _fallback_answer(question, profile, sources)
            return {
                "answer": (
                    fallback
                    + f"\n\n*Gemini could not answer this request (HTTP {status}); "
                    "showing the local source-grounded answer instead.*"
                ),
                "sources": sources,
                "mode": "local",
            }

        payload = response.json()
        candidates = payload.get("candidates", []) or []
        candidate_reasons = [
            str(candidate.get("finishReason", "")).upper()
            for candidate in candidates
            if candidate.get("finishReason")
        ]
        answer = _extract_text(payload)

        # Never display a partial answer when Gemini reports its output limit.
        if "MAX_TOKENS" in candidate_reasons:
            compact_context = _make_context(sources[:2])
            compact_prompt = f"""Answer briefly using ONLY these scholarship records.
Do not infer missing facts. If multiple income limits or criteria appear and the record does not say which applies to the named scholarship, state that ambiguity explicitly. For missing fields say "Not found in the extracted source text."
Use at most 5 concise bullets. No long introduction.

Question: {question}

Records:
{compact_context}
"""
            retry_response, _retry_failure = _post_gemini(
                endpoint, api_key, compact_prompt, max_output_tokens=2048
            )
            if retry_response is not None and retry_response.ok:
                retry_payload = retry_response.json()
                retry_candidates = retry_payload.get("candidates", []) or []
                retry_reasons = [
                    str(candidate.get("finishReason", "")).upper()
                    for candidate in retry_candidates
                    if candidate.get("finishReason")
                ]
                retry_answer = _extract_text(retry_payload)
                if retry_answer and "MAX_TOKENS" not in retry_reasons:
                    return {"answer": retry_answer, "sources": sources, "mode": "gemini"}

            fallback = _fallback_answer(question, profile, sources)
            return {
                "answer": (
                    fallback
                    + "\\n\\n*Gemini's response was truncated even after one shorter retry; "
                    "showing the local source-grounded answer instead.*"
                ),
                "sources": sources,
                "mode": "local",
            }

        if answer:
            return {"answer": answer, "sources": sources, "mode": "gemini"}

        reason_text = f" (reason: {', '.join(candidate_reasons)})" if candidate_reasons else ""
        return {
            "answer": (
                _fallback_answer(question, profile, sources)
                + "\\n\\n*Gemini returned no readable answer"
                + reason_text
                + "; showing the local source-grounded answer instead.*"
            ),
            "sources": sources,
            "mode": "local",
        }

    except (ValueError, TypeError):
        return {
            "answer": (
                _fallback_answer(question, profile, sources)
                + "\n\n*Gemini returned an unreadable response; showing the local source-grounded answer instead.*"
            ),
            "sources": sources,
            "mode": "local",
        }

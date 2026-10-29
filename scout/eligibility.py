import re


def _income_to_number(value):
    """Convert extracted income limits such as '₹3,00,000' or '8 lakh' to rupees."""
    if not value:
        return None
    raw = str(value).lower().replace(",", "").strip()
    try:
        match = re.search(r"\d+(?:\.\d+)?", raw)
        if not match:
            return None
        number = float(match.group())
        if any(unit in raw for unit in ("lakh", "lakhs", " lpa")):
            number *= 100_000
        return number
    except (AttributeError, ValueError):
        return None


def _has_explicit_state_restriction(text, state):
    """Only flag a state mismatch when page text clearly associates state with eligibility."""
    if not state or state == "other":
        return None
    state_names = {
        "andhra pradesh": ["andhra pradesh"],
        "karnataka": ["karnataka"],
        "tamil nadu": ["tamil nadu"],
        "telangana": ["telangana"],
        "kerala": ["kerala"],
        "maharashtra": ["maharashtra"],
    }
    mentioned_states = [s for s in state_names if s in text]
    restriction_terms = ("domicile", "resident of", "residents of", "permanent resident", "state of")
    has_residency_language = any(term in text for term in restriction_terms)
    if has_residency_language and mentioned_states and state not in mentioned_states:
        return f"The page mentions a residency/state condition and names {', '.join(mentioned_states)}; confirm whether it excludes your state."
    if has_residency_language and not mentioned_states:
        return "A residency condition appears to exist, but its exact state requirement is unclear."
    return None


def match_eligibility(scholarship, profile):
    """
    Return a transparent preliminary fit score and status.
    The score is a criteria-coverage indicator, not a probability of receiving funding.
    """
    text = (scholarship.get("page_text_excerpt") or "").lower()
    evidence, concerns, hard_mismatches = [], [], []
    score = 0
    checks = 0

    # State / domicile: only score this when the page contains useful evidence.
    state = (profile.get("state") or "").strip().lower()
    state_note = _has_explicit_state_restriction(text, state)
    if state_note:
        checks += 1
        concerns.append(state_note)
    elif state and state in text:
        checks += 1
        score += 1
        evidence.append(f"The page mentions {profile.get('state')}. This alone does not prove domicile eligibility.")

    # Course / study level
    checks += 1
    course = (profile.get("course") or "").lower()
    course_terms = {
        "b.e. / b.tech": ("undergraduate", "bachelor", "b.tech", "b.e.", "engineering", "degree"),
        "b.sc.": ("undergraduate", "bachelor", "b.sc", "science", "degree"),
        "b.com.": ("undergraduate", "bachelor", "b.com", "commerce", "degree"),
        "b.a.": ("undergraduate", "bachelor", "b.a.", "arts", "degree"),
        "diploma": ("diploma",),
        "other undergraduate": ("undergraduate", "bachelor", "degree"),
    }
    terms = course_terms.get(course, ())
    if any(term in text for term in terms):
        score += 1
        evidence.append("The page contains language consistent with your course/study level.")
    else:
        concerns.append("Course or study-level compatibility was not confidently confirmed.")

    # Income: extraction is treated as a candidate limit, not guaranteed official policy.
    income_limit = _income_to_number(scholarship.get("income_limit"))
    checks += 1
    if income_limit is not None:
        user_income = float(profile.get("income", 0))
        if user_income <= income_limit:
            score += 1
            evidence.append("Entered household income is at or below the extracted income figure; verify the official rule and units.")
        else:
            hard_mismatches.append("Entered household income is above the extracted income figure; this may be a mismatch if it is the official cap.")
    else:
        concerns.append("Income limit was not confidently extracted.")

    # Academic marks: only compare against explicit minimum/cutoff wording.
    checks += 1
    marks = profile.get("marks")
    threshold_patterns = [
        r"(?:minimum|at least|aggregate of|not less than|score of)\s*(\d{2,3}(?:\.\d+)?)\s*%",
        r"(\d{2,3}(?:\.\d+)?)\s*%\s*(?:or above|and above|minimum marks|minimum)",
        r"minimum marks(?: required)?\s*(?:of)?\s*(\d{2,3}(?:\.\d+)?)\s*%",
    ]
    threshold = None
    for pattern in threshold_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                threshold = float(match.group(1))
                break
            except (ValueError, IndexError):
                pass
    if threshold is not None and marks is not None:
        if float(marks) >= threshold:
            score += 1
            evidence.append(f"Entered marks meet the extracted {threshold:g}% threshold; verify the relevant exam/year.")
        else:
            hard_mismatches.append(f"Entered marks are below the extracted {threshold:g}% threshold; verify that it is a mandatory minimum.")
    else:
        concerns.append("A relevant academic cutoff was not confidently extracted.")

    # Category: don't infer a requirement merely because a category is mentioned.
    checks += 1
    category = (profile.get("category") or "").strip().lower()
    category_terms = {
        "obc": ("obc", "other backward classes"),
        "sc": ("scheduled caste", "sc category"),
        "st": ("scheduled tribe", "st category"),
        "ews": ("ews", "economically weaker sections"),
        "general": ("general category", "all categories", "all students"),
    }
    if category in category_terms and any(term in text for term in category_terms[category]):
        score += 1
        evidence.append(f"The page mentions wording related to the selected {profile.get('category')} category; exact eligibility still needs checking.")
    elif category and category != "prefer not to say":
        concerns.append("Category-specific eligibility was not confidently confirmed.")

    # Deadline: informational only, not a core eligibility criterion.
    if scholarship.get("deadline"):
        evidence.append("A deadline-like date was extracted; verify that it applies to the current application cycle.")
    else:
        concerns.append("Application deadline is unknown.")

    # Score reflects the number of positively supported profile checks.
    fit_score = round((score / checks) * 100) if checks else 0
    if hard_mismatches:
        status = "Likely ineligible"
    elif checks > 0 and score == checks:
        status = "Strong match"
    elif score >= 2:
        status = "Potential match"
    else:
        status = "Needs verification"

    reason_parts = evidence + concerns + hard_mismatches
    return {
        "status": status,
        "score": fit_score,
        "reason": " ".join(reason_parts) or "Not enough reliable evidence to assess eligibility.",
        "evidence": evidence,
        "concerns": concerns,
        "mismatches": hard_mismatches,
        "score_note": "Preliminary criteria-coverage score only; not a probability of receiving an award.",
    }

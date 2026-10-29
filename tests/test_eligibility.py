from scout.eligibility import match_eligibility


def test_missing_information_requires_verification():
    result = match_eligibility(
        {"page_text_excerpt": "Scholarship for undergraduate students.", "income_limit": "", "deadline": ""},
        {"state": "Karnataka", "course": "B.E. / B.Tech", "income": 300000, "marks": 96.16, "category": "Prefer not to say"}
    )
    assert result["status"] == "Needs verification"
    assert 0 <= result["score"] <= 100
    assert "not a probability" in result["score_note"]


def test_income_mismatch_is_flagged():
    result = match_eligibility(
        {"page_text_excerpt": "Scholarship for undergraduate students. Family income limit ₹200000", "income_limit": "200000", "deadline": ""},
        {"state": "Karnataka", "course": "B.E. / B.Tech", "income": 300000, "marks": 96.16, "category": "Prefer not to say"}
    )
    assert result["status"] == "Likely ineligible"
    assert result["mismatches"]


def test_income_limit_lakh_is_converted():
    result = match_eligibility(
        {"page_text_excerpt": "undergraduate bachelor degree", "income_limit": "8 lakh", "deadline": "30 November 2026"},
        {"state": "Karnataka", "course": "B.E. / B.Tech", "income": 300000, "marks": 80, "category": "Prefer not to say"}
    )
    assert result["status"] != "Likely ineligible"


def test_score_is_not_award_probability():
    result = match_eligibility(
        {"page_text_excerpt": "Karnataka undergraduate bachelor engineering students", "income_limit": "500000", "deadline": "30 November 2026"},
        {"state": "Karnataka", "course": "B.E. / B.Tech", "income": 300000, "marks": 96.16, "category": "Prefer not to say"}
    )
    assert "criteria-coverage" in result["score_note"]

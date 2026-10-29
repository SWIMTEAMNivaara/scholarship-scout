from scout.extraction import build_scholarship_record


def test_extracts_details_conservatively():
    result = build_scholarship_record(
        {"title": "Example STEM Scholarship", "url": "https://example.org/scholarship", "site_name": "Example"},
        {"title": "Example STEM Scholarship", "url": "https://example.org/scholarship", "text": "Eligibility criteria: Undergraduate engineering students. Family income limit: ₹3,00,000. Scholarship amount: ₹50,000 per year. Documents required: marks card, income certificate, bank details. Minimum 75% marks. Last date: 30 November 2026. Academic year: 2026-2027. Provided by Example Foundation."},
        {},
    )
    assert result["name"] == "Example STEM Scholarship"
    assert result["income_limit"]
    assert result["benefits"]
    assert result["documents"]
    assert result["academic_criteria"]
    assert result["application_cycle"]
    assert result["provider"]
    assert result["application_url"] == ""


def test_does_not_invent_application_url():
    result = build_scholarship_record({"title": "Test", "url": "https://example.org"}, {"text": "No apply link available"}, {})
    assert result["application_url"] == ""

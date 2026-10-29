from scout.source_trust import assess_source, annotate_source, prioritize_official_sources


def test_government_domain_signal_is_not_called_verified():
    result = assess_source({"url": "https://scholarships.gov.in/apply"})
    assert result["level"] == "strong"
    assert "does not prove" in result["note"]
    assert "verified" not in result["label"].lower()


def test_education_domain_signal():
    assert assess_source({"url": "https://example.edu.in/scholarship"})["level"] == "institutional"


def test_general_domain_is_not_official():
    assert assess_source({"url": "https://example.com/scholarship"})["level"] == "general"


def test_invalid_or_missing_url_is_unknown():
    assert assess_source({"url": "javascript:alert(1)"})["level"] == "unknown"
    assert assess_source({})["domain"] == "Unknown"


def test_annotation_does_not_mutate_original():
    original = {"name": "Grant", "url": "https://example.gov.in/grant"}
    updated = annotate_source(original)
    assert "source_assessment" not in original
    assert updated["source_assessment"]["level"] == "strong"


def test_prioritize_sorts_by_signal_stably():
    items = [
        {"name": "General", "url": "https://example.com/a"},
        {"name": "Government", "url": "https://example.gov.in/a"},
        {"name": "Education", "url": "https://example.edu.in/a"},
    ]
    result = prioritize_official_sources(items)
    assert [x["name"] for x in result] == ["Government", "Education", "General"]

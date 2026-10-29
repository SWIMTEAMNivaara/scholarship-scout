from scout.reliability import (
    configuration_status,
    deduplicate_and_validate,
    deduplicate_scholarships,
    normalize_url,
    safe_parse_json,
    validate_scholarship,
    validate_tracking_status,
)


def test_normalize_url_removes_tracking_and_fragment():
    assert normalize_url("HTTPS://Example.com/apply/?utm_source=x#form") == "https://example.com/apply"


def test_deduplicate_by_url_and_tracking_params():
    items = [
        {"name": "Scholarship A", "application_url": "https://example.com/apply?utm_source=one"},
        {"name": "Scholarship A duplicate", "application_url": "https://example.com/apply?ref=two"},
    ]
    assert len(deduplicate_scholarships(items)) == 1


def test_deduplicate_by_name_and_provider_when_no_url():
    items = [
        {"name": "Future Scholars", "provider": "ABC Trust"},
        {"title": " future   scholars ", "organization": "abc trust"},
    ]
    assert len(deduplicate_scholarships(items)) == 1


def test_malformed_records_are_skipped():
    assert deduplicate_scholarships([None, "bad", {"name": "Valid Scholarship"}]) == [{"name": "Valid Scholarship"}]


def test_validation_flags_missing_name_and_bad_url():
    valid, issues = validate_scholarship({"name": "A", "application_url": "ftp://example.com"})
    assert not valid
    assert any("name" in issue.lower() for issue in issues)
    assert any("url" in issue.lower() for issue in issues)


def test_valid_iso_deadline():
    valid, issues = validate_scholarship({"name": "Future Scholarship", "deadline": "2027-02-28"})
    assert valid
    assert issues == []


def test_invalid_calendar_deadline():
    valid, issues = validate_scholarship({"name": "Future Scholarship", "deadline": "2027-02-30"})
    assert not valid
    assert any("calendar date" in issue.lower() for issue in issues)


def test_safe_parse_json_handles_invalid_payload():
    parsed, error = safe_parse_json("{broken")
    assert parsed is None
    assert error == "Provider returned malformed JSON."


def test_safe_parse_json_accepts_dict():
    parsed, error = safe_parse_json({"items": []})
    assert parsed == {"items": []}
    assert error is None


def test_config_report_never_returns_secret_values():
    result = configuration_status({
        "TINYFISH_API_KEY": "secret-one",
        "GEMINI_API_KEY": "secret-two",
        "GEMINI_MODEL": "gemini-3.6-flash",
    })
    assert result["tinyfish_configured"] is True
    assert result["gemini_configured"] is True
    assert "secret-one" not in repr(result)
    assert "secret-two" not in repr(result)


def test_tracking_status_validation():
    assert validate_tracking_status("Applied") == (True, "Applied")
    ok, message = validate_tracking_status("Paid")
    assert not ok
    assert "Unsupported status" in message


def test_deduplicate_and_validate_reports_bad_records():
    items, reports = deduplicate_and_validate([
        {"name": "Valid Scholarship", "deadline": "2027-05-10"},
        {"name": ""},
    ])
    assert len(items) == 2
    assert len(reports) == 1

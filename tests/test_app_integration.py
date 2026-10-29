from scout.pipeline import prepare_discovered_scholarships, safe_provider_call
from scout.reliability import configuration_status, deduplicate_and_validate


def test_discovery_pipeline_removes_duplicates_before_display():
    result = prepare_discovered_scholarships([
        {"name": "Scholarship Alpha", "url": "https://example.org/alpha?utm_source=a"},
        {"name": "Alpha duplicate", "url": "https://example.org/alpha?utm_source=b"},
        {"name": "Scholarship Beta", "url": "https://example.org/beta"},
    ], source_label="test")
    assert result["input_count"] == 3
    assert result["output_count"] == 2
    assert result["duplicates_removed"] == 1


def test_fetch_failure_returns_safe_error_and_not_exception_text():
    def fail(_urls):
        raise RuntimeError("private response content")
    result = safe_provider_call(fail, ["https://example.org"], provider_name="TinyFish Fetch")
    assert result["ok"] is False
    assert "private response content" not in result["error"]


def test_extracted_records_are_validated_without_dropping_unknown_deadline():
    records, issues = deduplicate_and_validate([
        {"name": "Scholarship Gamma", "url": "https://example.org/gamma", "deadline": ""},
    ])
    assert len(records) == 1
    assert issues == []


def test_config_diagnostics_do_not_expose_api_keys():
    report = configuration_status({
        "TINYFISH_API_KEY": "not-a-real-key",
        "GEMINI_API_KEY": "also-not-a-real-key",
        "GEMINI_MODEL": "gemini-3.6-flash",
    })
    assert report["tinyfish_configured"]
    assert report["gemini_configured"]
    assert "not-a-real-key" not in repr(report)

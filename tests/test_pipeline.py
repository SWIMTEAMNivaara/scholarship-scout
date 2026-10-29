from scout.pipeline import prepare_discovered_scholarships, safe_provider_call, official_source_reminder


def test_prepare_list_deduplicates_and_reports_counts():
    result = prepare_discovered_scholarships([
        {"name": "Future Scholarship", "application_url": "https://example.com/apply?utm_source=a"},
        {"name": "Duplicate", "application_url": "https://example.com/apply?utm_source=b"},
        {"name": "Another Scholarship"},
    ])
    assert result["input_count"] == 3
    assert result["output_count"] == 2
    assert result["duplicates_removed"] == 1
    assert len(result["scholarships"]) == 2


def test_prepare_common_result_envelope():
    result = prepare_discovered_scholarships({"results": [{"name": "Scholarship One"}]})
    assert result["output_count"] == 1


def test_prepare_single_record():
    result = prepare_discovered_scholarships({"name": "Scholarship One"})
    assert result["output_count"] == 1


def test_prepare_malformed_payload_does_not_crash():
    result = prepare_discovered_scholarships("unexpected")
    assert result["scholarships"] == []
    assert result["output_count"] == 0


def test_prepare_skips_non_object_items():
    result = prepare_discovered_scholarships([{"name": "Scholarship One"}, None, "bad"])
    assert result["output_count"] == 1


def test_provider_call_success():
    result = safe_provider_call(lambda x: {"items": [x]}, "ok", provider_name="test")
    assert result["ok"] is True
    assert result["data"] == {"items": ["ok"]}


def test_provider_call_timeout():
    def timeout():
        raise TimeoutError()
    result = safe_provider_call(timeout, provider_name="test")
    assert result["ok"] is False
    assert "timed out" in result["error"]


def test_provider_call_exception():
    def broken():
        raise RuntimeError("private provider response")
    result = safe_provider_call(broken, provider_name="test")
    assert result["ok"] is False
    assert "private provider response" not in result["error"]


def test_official_source_reminder():
    reminder = official_source_reminder({"name": "Future Scholarship"})
    assert "Future Scholarship" in reminder
    assert "official provider website" in reminder

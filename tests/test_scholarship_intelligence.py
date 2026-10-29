from datetime import date
from scout.scholarship_intelligence import assess_deadline, build_comparison_rows, parse_date


def test_parse_common_dates_and_unknown_values():
    assert parse_date("2027-01-15") == date(2027, 1, 15)
    assert parse_date("15 January 2027") == date(2027, 1, 15)
    assert parse_date("unknown") is None
    assert parse_date("deadline sometime next year") is None


def test_assess_deadline_states_are_cautious():
    assert assess_deadline("2026-10-29", date(2026, 10, 30))["status"] == "past"
    assert assess_deadline("2026-10-30", date(2026, 10, 30))["status"] == "today"
    assert assess_deadline("2026-11-04", date(2026, 10, 30))["status"] == "urgent"
    assert assess_deadline("2027-01-15", date(2026, 10, 30))["status"] == "upcoming"
    assert assess_deadline(None, date(2026, 10, 30))["status"] == "unknown"


def test_past_date_is_not_claimed_closed():
    result = assess_deadline("2026-01-01", date(2026, 10, 30))
    assert "may be closed" in result["note"]
    assert "verify status" in result["label"].lower()


def test_comparison_handles_missing_data_and_limits_to_four():
    records = [{"name": f"Grant {i}", "url": f"https://example{i}.org/apply"} for i in range(6)]
    rows = build_comparison_rows(records)
    assert len(rows) == 4
    assert rows[0]["Benefits / award"] == "Not found"
    assert rows[0]["Deadline"] == "Unknown"
    assert rows[0]["Source domain"] == "example0.org"


def test_comparison_includes_match_and_deadline_details():
    rows = build_comparison_rows([{
        "name": "STEM Grant", "provider": "Example Foundation", "url": "https://example.org/grant",
        "deadline": "2027-01-15", "benefits": "₹25,000", "match": {"status": "Potential match", "score": 72}
    }])
    assert rows[0]["Preliminary fit"] == "Potential match (72/100)"
    assert rows[0]["Benefits / award"] == "₹25,000"
    assert rows[0]["Deadline review"] == "Future date found"

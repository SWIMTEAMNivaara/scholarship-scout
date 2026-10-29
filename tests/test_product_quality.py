from scout.product_quality import readiness_items, readiness_summary, safe_csv_cell


def test_csv_formula_prefixes_are_neutralized():
    assert safe_csv_cell("=1+1") == "'=1+1"
    assert safe_csv_cell("  @SUM(A1:A2)") == "'  @SUM(A1:A2)"
    assert safe_csv_cell("-2") == "'-2"
    assert safe_csv_cell("+cmd") == "'+cmd"


def test_csv_normal_text_is_preserved():
    assert safe_csv_cell("Scholarship for STEM") == "Scholarship for STEM"
    assert safe_csv_cell(None) == ""
    assert safe_csv_cell(123) == "123"


def test_readiness_summary_counts_only_known_keys():
    keys = [key for key, _ in readiness_items()]
    result = readiness_summary([keys[0], keys[1], "not-a-real-key"])
    assert result["completed"] == 2
    assert result["total"] == 5
    assert result["percent"] == 40
    assert result["is_complete"] is False


def test_readiness_complete_only_when_all_steps_checked():
    result = readiness_summary(key for key, _ in readiness_items())
    assert result["completed"] == 5
    assert result["percent"] == 100
    assert result["is_complete"] is True


def test_checklist_definitions_are_stable_and_unique():
    items = readiness_items()
    keys = [key for key, _ in items]
    assert len(items) == 5
    assert len(set(keys)) == 5

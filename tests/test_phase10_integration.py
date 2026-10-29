from pathlib import Path


def test_phase10_app_wires_comparison_and_deadline_review():
    app = Path(__file__).resolve().parents[1] / "app.py"
    source = app.read_text(encoding="utf-8")
    assert "build_comparison_rows" in source
    assert "Select scholarships to compare" in source
    assert "Open source to check deadline" in source
    assert "I checked the deadline on the provider's source page" in source

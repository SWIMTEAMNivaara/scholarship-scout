from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_app_compiles_and_imports_quality_helpers():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert "from scout.product_quality import readiness_items, readiness_summary, safe_csv_cell" in source
    assert "safe_csv_cell(item.get(key, \"\"))" in source


def test_tracker_renders_manual_readiness_checklist():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Application readiness checklist" in source
    assert "st.progress(readiness[\"percent\"] / 100" in source
    assert "does not independently verify facts or save progress" in source

from pathlib import Path
import ast

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_config_disables_usage_stats():
    config = (PACKAGE_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in config


def test_release_checker_is_valid_python():
    source = (PACKAGE_ROOT / "scripts" / "release_check.py").read_text(encoding="utf-8")
    ast.parse(source)


def test_deployment_notes_exist():
    assert (PACKAGE_ROOT / "DEPLOYMENT-PHASE12.txt").is_file()

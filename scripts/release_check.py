"""Basic release-readiness checks for Scholarship Scout.

Run this script from the root of the merged Scholarship Scout project:
    python scripts/release_check.py
It checks filenames and dependency declarations only; it never reads .env or prints secrets.
"""
from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "app.py",
    "requirements.txt",
    "scout",
    "database",
]
CORE_DEPENDENCIES = ["streamlit", "requests"]


def main() -> int:
    errors = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).exists():
            errors.append(f"Missing required project path: {relative}")

    app_path = ROOT / "app.py"
    if app_path.is_file():
        try:
            ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"app.py syntax/read check failed: {exc}")

    requirements_path = ROOT / "requirements.txt"
    if requirements_path.is_file():
        lines = [
            line.strip().lower().split(";")[0].split("=")[0].split("<")[0].split("> ")[0].strip()
            for line in requirements_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        normalized = {line.split("[")[0] for line in lines}
        for dependency in CORE_DEPENDENCIES:
            if dependency not in normalized:
                errors.append(f"requirements.txt does not declare core dependency: {dependency}")

    if errors:
        print("RELEASE CHECK: FAILED")
        for error in errors:
            print(f"- {error}")
        print("Fix the items above, then rerun this check from the project root.")
        return 1

    print("RELEASE CHECK: PASSED")
    print("Required project paths, app.py syntax, and core dependency declarations look present.")
    print("This is a basic preflight check, not a security audit or deployment guarantee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import importlib
from pathlib import Path


def test_reminder_crud(tmp_path, monkeypatch):
    import database.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.init_reminders_table()
    db.create_reminder(1, "Example scholarship", "2026-11-01", "Check documents")
    reminders = db.list_reminders()
    assert len(reminders) == 1
    reminder_id = reminders[0]["id"]
    assert reminders[0]["scholarship_name"] == "Example scholarship"
    db.update_reminder_completed(reminder_id, True)
    assert db.list_reminders()[0]["completed"] == 1
    assert db.list_reminders(include_completed=False) == []
    db.delete_reminder(reminder_id)
    assert db.list_reminders() == []

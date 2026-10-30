import sqlite3

from database import db


def _fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.init_db()
    db.init_reminders_table()


def test_workspaces_do_not_see_each_other(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    a, b = db.workspace_id("alpha-code"), db.workspace_id("beta-code")
    db.save_scholarship({"url": "https://x.org/s", "name": "S"}, workspace=a)
    assert len(db.list_saved_scholarships(workspace=a)) == 1
    assert db.list_saved_scholarships(workspace=b) == []
    # same URL can be saved independently by another workspace
    db.save_scholarship({"url": "https://x.org/s", "name": "S"}, workspace=b)
    assert len(db.list_saved_scholarships(workspace=b)) == 1


def test_cannot_modify_other_workspace_rows(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    a, b = db.workspace_id("alpha-code"), db.workspace_id("beta-code")
    db.save_scholarship({"url": "https://x.org/s", "name": "S"}, workspace=a)
    row = db.list_saved_scholarships(workspace=a)[0]
    db.update_application_status(row["id"], "Applied", workspace=b)
    assert db.list_saved_scholarships(workspace=a)[0]["application_status"] == "Interested"
    db.create_reminder(row["id"], "S", "2026-12-01", workspace=a)
    rid = db.list_reminders(workspace=a)[0]["id"]
    db.delete_reminder(rid, workspace=b)
    assert len(db.list_reminders(workspace=a)) == 1
    assert db.list_reminders(workspace=b) == []
    db.update_reminder_completed(rid, True, workspace=b)
    assert db.list_reminders(workspace=a)[0]["completed"] == 0


def test_blank_code_gives_empty_id():
    assert db.workspace_id("   ") == ""
    assert db.workspace_id("abc") == db.workspace_id("abc") != "abc"


def test_old_database_is_migrated(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE scholarships (
        id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
        deadline TEXT, source_name TEXT, data_json TEXT NOT NULL,
        application_status TEXT NOT NULL DEFAULT 'Interested', last_checked TEXT)""")
    conn.execute("INSERT INTO scholarships(url,name,data_json) VALUES ('https://old.org','Old','{}')")
    conn.commit(); conn.close()
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db(); db.init_reminders_table()
    assert [r["name"] for r in db.list_saved_scholarships(workspace="")] == ["Old"]
    db.save_scholarship({"url": "https://old.org", "name": "Old"}, workspace="w1")
    assert len(db.list_saved_scholarships(workspace="w1")) == 1

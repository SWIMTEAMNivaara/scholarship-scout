import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "scholarships.db"

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def workspace_id(code):
    """Turn a user-chosen workspace code into an opaque, non-reversible id."""
    code = (code or "").strip()
    if not code:
        return ""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:32]


def init_db():
    """Create tables; migrate older single-user databases to per-workspace rows."""
    with _connect() as conn:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(scholarships)")]
        if not cols:
            conn.execute("""
                CREATE TABLE scholarships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL,
                    name TEXT NOT NULL,
                    deadline TEXT,
                    source_name TEXT,
                    data_json TEXT NOT NULL,
                    application_status TEXT NOT NULL DEFAULT 'Interested',
                    last_checked TEXT,
                    UNIQUE(workspace, url)
                )
            """)
        elif "workspace" not in cols:
            # Old schema had UNIQUE(url) only; rebuild so each workspace can save the same URL.
            conn.execute("ALTER TABLE scholarships RENAME TO scholarships_old")
            conn.execute("""
                CREATE TABLE scholarships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL,
                    name TEXT NOT NULL,
                    deadline TEXT,
                    source_name TEXT,
                    data_json TEXT NOT NULL,
                    application_status TEXT NOT NULL DEFAULT 'Interested',
                    last_checked TEXT,
                    UNIQUE(workspace, url)
                )
            """)
            conn.execute("""
                INSERT INTO scholarships(id, url, name, deadline, source_name, data_json, application_status, last_checked)
                SELECT id, url, name, deadline, source_name, data_json, application_status, last_checked
                FROM scholarships_old
            """)
            conn.execute("DROP TABLE scholarships_old")

def save_scholarship(item, workspace=""):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            INSERT INTO scholarships(workspace, url, name, deadline, source_name, data_json, application_status, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, 'Interested', ?)
            ON CONFLICT(workspace, url) DO UPDATE SET
                name=excluded.name,
                deadline=excluded.deadline,
                source_name=excluded.source_name,
                data_json=excluded.data_json,
                last_checked=excluded.last_checked
        """, (
            workspace,
            item.get("url", ""),
            item.get("name") or item.get("title") or "Scholarship opportunity",
            item.get("deadline", ""),
            item.get("source_name", ""),
            json.dumps(item, ensure_ascii=False),
            now,
        ))

def list_saved_scholarships(workspace=""):
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM scholarships WHERE workspace=? ORDER BY id DESC", (workspace,)).fetchall()
    output = []
    for row in rows:
        data = json.loads(row["data_json"])
        data.update({
            "id": row["id"],
            "name": row["name"],
            "deadline": row["deadline"],
            "url": row["url"],
            "source_name": row["source_name"],
            "application_status": row["application_status"],
            "last_checked": row["last_checked"],
        })
        output.append(data)
    return output

def update_application_status(row_id, status, workspace=""):
    with _connect() as conn:
        conn.execute("UPDATE scholarships SET application_status=? WHERE id=? AND workspace=?", (status, row_id, workspace))


def init_reminders_table():
    """Create a separate reminders table without changing existing scholarship rows."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scholarship_id INTEGER,
                scholarship_name TEXT NOT NULL,
                reminder_date TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(scholarship_id) REFERENCES scholarships(id)
            )
        """)
        rcols = [r["name"] for r in conn.execute("PRAGMA table_info(reminders)")]
        if "workspace" not in rcols:
            conn.execute("ALTER TABLE reminders ADD COLUMN workspace TEXT NOT NULL DEFAULT ''")


def create_reminder(scholarship_id, scholarship_name, reminder_date, note="", workspace=""):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            INSERT INTO reminders(scholarship_id, scholarship_name, reminder_date, note, completed, created_at, workspace)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (scholarship_id, scholarship_name, reminder_date, note, now, workspace))


def list_reminders(include_completed=True, workspace=""):
    with _connect() as conn:
        query = "SELECT * FROM reminders WHERE workspace=?"
        if not include_completed:
            query += " AND completed=0"
        query += " ORDER BY reminder_date ASC, id DESC"
        rows = conn.execute(query, (workspace,)).fetchall()
    return [dict(row) for row in rows]


def update_reminder_completed(reminder_id, completed, workspace=""):
    with _connect() as conn:
        conn.execute("UPDATE reminders SET completed=? WHERE id=? AND workspace=?", (1 if completed else 0, reminder_id, workspace))


def delete_reminder(reminder_id, workspace=""):
    with _connect() as conn:
        conn.execute("DELETE FROM reminders WHERE id=? AND workspace=?", (reminder_id, workspace))

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "scholarships.db"

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scholarships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                deadline TEXT,
                source_name TEXT,
                data_json TEXT NOT NULL,
                application_status TEXT NOT NULL DEFAULT 'Interested',
                last_checked TEXT
            )
        """)

def save_scholarship(item):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            INSERT INTO scholarships(url, name, deadline, source_name, data_json, application_status, last_checked)
            VALUES (?, ?, ?, ?, ?, 'Interested', ?)
            ON CONFLICT(url) DO UPDATE SET
                name=excluded.name,
                deadline=excluded.deadline,
                source_name=excluded.source_name,
                data_json=excluded.data_json,
                last_checked=excluded.last_checked
        """, (
            item.get("url", ""),
            item.get("name") or item.get("title") or "Scholarship opportunity",
            item.get("deadline", ""),
            item.get("source_name", ""),
            json.dumps(item, ensure_ascii=False),
            now,
        ))

def list_saved_scholarships():
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM scholarships ORDER BY id DESC").fetchall()
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

def update_application_status(row_id, status):
    with _connect() as conn:
        conn.execute("UPDATE scholarships SET application_status=? WHERE id=?", (status, row_id))


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


def create_reminder(scholarship_id, scholarship_name, reminder_date, note=""):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            INSERT INTO reminders(scholarship_id, scholarship_name, reminder_date, note, completed, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (scholarship_id, scholarship_name, reminder_date, note, now))


def list_reminders(include_completed=True):
    with _connect() as conn:
        query = "SELECT * FROM reminders"
        if not include_completed:
            query += " WHERE completed=0"
        query += " ORDER BY reminder_date ASC, id DESC"
        rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]


def update_reminder_completed(reminder_id, completed):
    with _connect() as conn:
        conn.execute("UPDATE reminders SET completed=? WHERE id=?", (1 if completed else 0, reminder_id))


def delete_reminder(reminder_id):
    with _connect() as conn:
        conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))

```python
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "scholarships.db"


# ==========================================
# DATABASE CONNECTION
# ==========================================

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==========================================
# WORKSPACE MANAGEMENT
# ==========================================

def workspace_id(code):
    code = str(code).strip()

    if not code:
        raise ValueError("Workspace code cannot be empty")

    return hashlib.sha256(
        code.encode("utf-8")
    ).hexdigest()


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

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
                last_checked TEXT,
                workspace TEXT NOT NULL DEFAULT 'legacy'
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(scholarships)"
            ).fetchall()
        }

        if "workspace" not in columns:
            conn.execute("""
                ALTER TABLE scholarships
                ADD COLUMN workspace TEXT NOT NULL DEFAULT 'legacy'
            """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scholarships_workspace
            ON scholarships(workspace)
        """)


# ==========================================
# SAVE SCHOLARSHIP
# ==========================================

def save_scholarship(item, workspace="default"):

    now = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    url = item.get("url", "")

    with _connect() as conn:

        existing = conn.execute("""
            SELECT id, workspace
            FROM scholarships
            WHERE url = ?
        """, (url,)).fetchone()

        if existing:

            if existing["workspace"] != workspace:
                raise ValueError(
                    "This scholarship URL already belongs to another workspace."
                )

            conn.execute("""
                UPDATE scholarships
                SET name = ?,
                    deadline = ?,
                    source_name = ?,
                    data_json = ?,
                    last_checked = ?
                WHERE id = ?
            """, (
                item.get("name") or item.get("title")
                or "Scholarship opportunity",
                item.get("deadline", ""),
                item.get("source_name", ""),
                json.dumps(item, ensure_ascii=False),
                now,
                existing["id"],
            ))

        else:

            conn.execute("""
                INSERT INTO scholarships (
                    url,
                    name,
                    deadline,
                    source_name,
                    data_json,
                    application_status,
                    last_checked,
                    workspace
                )
                VALUES (?, ?, ?, ?, ?, 'Interested', ?, ?)
            """, (
                url,
                item.get("name") or item.get("title")
                or "Scholarship opportunity",
                item.get("deadline", ""),
                item.get("source_name", ""),
                json.dumps(item, ensure_ascii=False),
                now,
                workspace,
            ))


# ==========================================
# LIST SAVED SCHOLARSHIPS
# ==========================================

def list_saved_scholarships(workspace="default"):

    with _connect() as conn:

        rows = conn.execute("""
            SELECT *
            FROM scholarships
            WHERE workspace = ?
            ORDER BY id DESC
        """, (workspace,)).fetchall()

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


# ==========================================
# UPDATE APPLICATION STATUS
# ==========================================

def update_application_status(
    row_id,
    status,
    workspace="default"
):

    with _connect() as conn:

        conn.execute("""
            UPDATE scholarships
            SET application_status = ?
            WHERE id = ? AND workspace = ?
        """, (status, row_id, workspace))


# ==========================================
# REMINDERS INITIALIZATION
# ==========================================

def init_reminders_table():

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
                workspace TEXT NOT NULL DEFAULT 'legacy',
                FOREIGN KEY(scholarship_id)
                    REFERENCES scholarships(id)
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(reminders)"
            ).fetchall()
        }

        if "workspace" not in columns:
            conn.execute("""
                ALTER TABLE reminders
                ADD COLUMN workspace TEXT NOT NULL DEFAULT 'legacy'
            """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_workspace
            ON reminders(workspace)
        """)


# ==========================================
# CREATE REMINDER
# ==========================================

def create_reminder(
    scholarship_id,
    scholarship_name,
    reminder_date,
    note="",
    workspace="default"
):

    now = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    with _connect() as conn:

        conn.execute("""
            INSERT INTO reminders (
                scholarship_id,
                scholarship_name,
                reminder_date,
                note,
                completed,
                created_at,
                workspace
            )
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (
            scholarship_id,
            scholarship_name,
            reminder_date,
            note,
            now,
            workspace,
        ))


# ==========================================
# LIST REMINDERS
# ==========================================

def list_reminders(
    workspace="default",
    include_completed=True
):

    query = """
        SELECT *
        FROM reminders
        WHERE workspace = ?
    """

    params = [workspace]

    if not include_completed:
        query += " AND completed = 0"

    query += " ORDER BY reminder_date ASC, id DESC"

    with _connect() as conn:

        rows = conn.execute(
            query,
            params
        ).fetchall()

    return [dict(row) for row in rows]


# ==========================================
# UPDATE REMINDER
# ==========================================

def update_reminder_completed(
    reminder_id,
    completed,
    workspace="default"
):

    with _connect() as conn:

        conn.execute("""
            UPDATE reminders
            SET completed = ?
            WHERE id = ? AND workspace = ?
        """, (
            1 if completed else 0,
            reminder_id,
            workspace,
        ))


# ==========================================
# DELETE REMINDER
# ==========================================

def delete_reminder(
    reminder_id,
    workspace="default"
):

    with _connect() as conn:

        conn.execute("""
            DELETE FROM reminders
            WHERE id = ? AND workspace = ?
        """, (reminder_id, workspace))
```

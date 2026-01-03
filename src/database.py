"""Database operations for task management."""

import random
import sqlite3
from datetime import datetime

from .config import DB_PATH


def _generate_unique_id() -> int:
    """Generate a random 3-digit ID (100-999) that doesn't exist in database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM tasks")
    existing_ids = {row[0] for row in cur.fetchall()}
    conn.close()

    for _ in range(100):  # Max attempts
        new_id = random.randint(100, 999)
        if new_id not in existing_ids:
            return new_id
    raise RuntimeError("Could not generate unique ID after 100 attempts")


def init_db():
    """Create the tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            frequency_days INTEGER NOT NULL,
            last_done TEXT NOT NULL,
            room TEXT NOT NULL,
            notes TEXT,
            points INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            points_earned INTEGER NOT NULL,
            completed_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def migrate_db():
    """Add points column to existing tasks table if missing."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(tasks)")
    columns = [col[1] for col in cur.fetchall()]
    if "points" not in columns:
        cur.execute("ALTER TABLE tasks ADD COLUMN points INTEGER NOT NULL DEFAULT 1")
        conn.commit()
    conn.close()


def add_task_db(name: str, freq_days: int, room: str, notes: str = "", points: int = 1):
    """Insert a new task with a random 3-digit ID."""
    task_id = _generate_unique_id()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now_iso = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO tasks (id, name, frequency_days, last_done, room, notes, points) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (task_id, name, freq_days, now_iso, room, notes, points),
    )
    conn.commit()
    conn.close()


def list_tasks_db(room: str = None):
    """Fetch all tasks ordered by id, optionally filtered by room."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if room:
        cur.execute(
            "SELECT id, name, frequency_days, last_done, room, notes, points FROM tasks WHERE room = ? ORDER BY id",
            (room,),
        )
    else:
        cur.execute(
            "SELECT id, name, frequency_days, last_done, room, notes, points FROM tasks ORDER BY id"
        )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_task_db(task_id: int):
    """Fetch a single task by id."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, frequency_days, last_done, room, notes, points FROM tasks WHERE id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def update_task_last_done(task_id: int, when: datetime):
    """Update the last_done timestamp for a task."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE tasks SET last_done = ? WHERE id = ?", (when.isoformat(), task_id)
    )
    conn.commit()
    conn.close()


def update_task_field(task_id: int, field: str, value):
    """Update a specific field of a task."""
    if field not in ("name", "frequency_days", "room", "notes", "points"):
        raise ValueError("Invalid field")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"UPDATE tasks SET {field} = ? WHERE id = ?", (value, task_id))
    conn.commit()
    conn.close()


def remove_task_db(task_id: int):
    """Delete a task by id."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def record_task_completion(username: str, task_id: int, task_name: str, points: int):
    """Record a task completion for points tracking."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now_iso = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO completed_tasks (username, task_id, task_name, points_earned, completed_at) VALUES (?, ?, ?, ?, ?)",
        (username, task_id, task_name, points, now_iso),
    )
    conn.commit()
    conn.close()


def get_weekly_points(since_iso: str) -> list[tuple[str, int]]:
    """Get points earned by each user since given date."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT username, SUM(points_earned) as total_points
        FROM completed_tasks
        WHERE completed_at >= ?
        GROUP BY username
        ORDER BY total_points DESC
        """,
        (since_iso,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def save_chat_id(chat_id: int):
    """Save chat ID for scheduled messages."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
        ("chat_id", str(chat_id)),
    )
    conn.commit()
    conn.close()


def get_chat_id() -> int | None:
    """Get saved chat ID for scheduled messages."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM bot_config WHERE key = ?", ("chat_id",))
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else None

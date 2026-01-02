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
    """Create the tasks table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        frequency_days INTEGER NOT NULL,
        last_done TEXT NOT NULL,
        notes TEXT
    )
    """
    )
    conn.commit()
    conn.close()


def add_task_db(name: str, freq_days: int, notes: str = ""):
    """Insert a new task with a random 3-digit ID."""
    task_id = _generate_unique_id()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now_iso = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO tasks (id, name, frequency_days, last_done, notes) VALUES (?, ?, ?, ?, ?)",
        (task_id, name, freq_days, now_iso, notes),
    )
    conn.commit()
    conn.close()


def list_tasks_db():
    """Fetch all tasks ordered by id."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, frequency_days, last_done, notes FROM tasks ORDER BY id"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_task_db(task_id: int):
    """Fetch a single task by id."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, frequency_days, last_done, notes FROM tasks WHERE id = ?",
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
    if field not in ("name", "frequency_days", "notes"):
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

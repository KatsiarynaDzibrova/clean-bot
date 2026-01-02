"""Utility functions for parsing and formatting."""

import re
from datetime import datetime, timedelta

from .database import list_tasks_db


def parse_frequency_to_days(text: str) -> int:
    """
    Parse frequency string to days.

    Accepts:
      - "3d" => 3
      - "1w" => 7
      - "1m" => 30
      - "10" => 10 days
      - "2 days" / "2d" / "2w" / "2months" etc.

    Returns integer days. Raises ValueError on bad input.
    """
    s = text.strip().lower()
    # direct integer
    if re.fullmatch(r"\d+", s):
        return int(s)
    m = re.match(r"^(\d+)\s*(d|day|days)$", s)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)\s*(w|week|weeks)$", s)
    if m:
        return int(m.group(1)) * 7
    m = re.match(r"^(\d+)\s*(m|month|months)$", s)
    if m:
        return int(m.group(1)) * 30
    m = re.match(r"^(\d+)\s*(d|w|m)$", s)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "d":
            return num
        if unit == "w":
            return num * 7
        if unit == "m":
            return num * 30
    raise ValueError(
        "Could not parse frequency. Use e.g. '3d', '1w', '1m' or a number of days."
    )


def next_due_text(last_done_iso: str, freq_days: int) -> tuple[datetime, str]:
    """Calculate next due date and formatted string."""
    last = datetime.fromisoformat(last_done_iso)
    nd = last + timedelta(days=freq_days)
    return nd, nd.strftime("%Y-%m-%d %H:%M UTC")


def tasks_due_now(room: str = None):
    """Get all tasks that are currently due (overdue), optionally filtered by room."""
    now = datetime.utcnow()
    due = []
    for row in list_tasks_db(room=room):
        tid, name, freq, last_iso, task_room, notes = row
        nd, nd_text = next_due_text(last_iso, freq)
        if nd <= now:
            due.append((tid, name, freq, last_iso, task_room, notes, nd))
    return due


def format_task_row(row, show_room=True):
    """Format a task row for display."""
    tid, name, freq, last_iso, room, notes = row
    nd, nd_text = next_due_text(last_iso, freq)
    if show_room:
        return f"{tid}. {name} — {room} — every {freq}d — next due: {nd_text}" + (
            f" — {notes}" if notes else ""
        )
    else:
        return f"{tid}. {name} — every {freq}d — next due: {nd_text}" + (
            f" — {notes}" if notes else ""
        )

"""Pytest configuration and fixtures."""

import os
import sqlite3
import tempfile

import pytest


@pytest.fixture
def test_db(monkeypatch):
    """Create a temporary test database and patch DB_PATH to use it."""
    # Create a temporary file for the test database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Patch the DB_PATH in the config module before importing database functions
    monkeypatch.setattr("src.config.DB_PATH", db_path)

    # Initialize the database schema
    conn = sqlite3.connect(db_path)
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

    yield db_path

    # Cleanup: remove the temporary database file
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def db_connection(test_db):
    """Provide a database connection for direct queries in tests."""
    conn = sqlite3.connect(test_db)
    yield conn
    conn.close()

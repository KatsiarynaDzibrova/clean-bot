"""Integration tests for task lifecycle.

Tests the complete flow: create task -> make it daily -> appears in due ->
complete it -> no longer in due.
"""

from datetime import datetime, timedelta

import pytest


class TestTaskLifecycle:
    """Integration tests for the complete task lifecycle."""

    def test_create_task_and_verify_in_database(self, test_db, monkeypatch):
        """Test that creating a task stores it correctly in the database."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, get_task_db, list_tasks_db

        # Create a task
        add_task_db("Clean bathroom", freq_days=1, notes="Daily cleaning")

        # Verify task exists in database
        tasks = list_tasks_db()
        assert len(tasks) == 1

        task = tasks[0]
        tid, name, freq, last_done, notes = task
        assert name == "Clean bathroom"
        assert freq == 1
        assert notes == "Daily cleaning"

        # Verify we can get task by ID
        task_by_id = get_task_db(tid)
        assert task_by_id is not None
        assert task_by_id[1] == "Clean bathroom"

    def test_newly_created_task_not_in_due_list(self, test_db, monkeypatch):
        """Test that a newly created task is NOT in the due list.

        When a task is created, last_done is set to NOW, so next_due = NOW + freq_days,
        which is in the future.
        """
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db
        from src.utils import tasks_due_now

        # Create a daily task
        add_task_db("Clean kitchen", freq_days=1)

        # Task should NOT be due yet (just created)
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 0

    def test_task_appears_in_due_after_frequency_passes(self, test_db, monkeypatch):
        """Test that a task appears in due list after frequency period passes."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, list_tasks_db, update_task_last_done
        from src.utils import tasks_due_now

        # Create a daily task
        add_task_db("Vacuum floor", freq_days=1)

        # Get the task ID
        tasks = list_tasks_db()
        task_id = tasks[0][0]

        # Simulate that the task was done 2 days ago (so it's overdue for a daily task)
        two_days_ago = datetime.utcnow() - timedelta(days=2)
        update_task_last_done(task_id, two_days_ago)

        # Task should now appear in due list
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 1
        assert due_tasks[0][1] == "Vacuum floor"

    def test_complete_task_removes_from_due_list(self, test_db, monkeypatch):
        """Test that completing a task removes it from the due list."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, list_tasks_db, update_task_last_done
        from src.utils import tasks_due_now

        # Create a daily task
        add_task_db("Wipe counters", freq_days=1)

        # Get the task ID
        tasks = list_tasks_db()
        task_id = tasks[0][0]

        # Make task overdue
        yesterday = datetime.utcnow() - timedelta(days=2)
        update_task_last_done(task_id, yesterday)

        # Verify task is due
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 1

        # Complete the task (update last_done to now)
        update_task_last_done(task_id, datetime.utcnow())

        # Task should no longer be in due list
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 0

    def test_full_daily_task_lifecycle(self, test_db, monkeypatch):
        """Test the complete lifecycle of a daily task.

        1. Create a daily task
        2. Verify not in due (just created)
        3. Simulate time passing (make it overdue)
        4. Verify appears in due
        5. Complete the task
        6. Verify not in due anymore
        """
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, get_task_db, list_tasks_db, update_task_last_done
        from src.utils import tasks_due_now

        # Step 1: Create a daily task
        add_task_db("Daily dusting", freq_days=1)
        tasks = list_tasks_db()
        assert len(tasks) == 1
        task_id = tasks[0][0]

        # Step 2: Verify task is NOT due (just created)
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 0, "Newly created task should not be due"

        # Step 3: Simulate one day passing (set last_done to 1.5 days ago)
        past_time = datetime.utcnow() - timedelta(days=1, hours=12)
        update_task_last_done(task_id, past_time)

        # Step 4: Verify task appears in due list
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 1, "Task should be due after frequency period"
        assert due_tasks[0][0] == task_id
        assert due_tasks[0][1] == "Daily dusting"

        # Step 5: Complete the task
        update_task_last_done(task_id, datetime.utcnow())

        # Step 6: Verify task is no longer in due list
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 0, "Completed task should not be in due list"

        # Verify task still exists in database
        task = get_task_db(task_id)
        assert task is not None
        assert task[1] == "Daily dusting"


class TestMultipleTasks:
    """Tests for handling multiple tasks."""

    def test_multiple_tasks_some_due(self, test_db, monkeypatch):
        """Test that only overdue tasks appear in due list when multiple tasks exist."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, list_tasks_db, update_task_last_done
        from src.utils import tasks_due_now

        # Create multiple tasks with different frequencies
        add_task_db("Daily task", freq_days=1)
        add_task_db("Weekly task", freq_days=7)
        add_task_db("Monthly task", freq_days=30)

        tasks = list_tasks_db()
        # Find tasks by name instead of assuming position (IDs are random)
        task_map = {t[1]: t[0] for t in tasks}  # name -> id
        daily_id = task_map["Daily task"]
        weekly_id = task_map["Weekly task"]
        monthly_id = task_map["Monthly task"]

        # Make only daily and weekly tasks overdue
        two_days_ago = datetime.utcnow() - timedelta(days=2)
        update_task_last_done(daily_id, two_days_ago)

        eight_days_ago = datetime.utcnow() - timedelta(days=8)
        update_task_last_done(weekly_id, eight_days_ago)

        # Monthly task remains not due (just created)

        # Check due list
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 2

        due_names = [t[1] for t in due_tasks]
        assert "Daily task" in due_names
        assert "Weekly task" in due_names
        assert "Monthly task" not in due_names

    def test_complete_one_task_others_remain_due(self, test_db, monkeypatch):
        """Test that completing one task doesn't affect other due tasks."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, list_tasks_db, update_task_last_done
        from src.utils import tasks_due_now

        # Create two tasks
        add_task_db("Task A", freq_days=1)
        add_task_db("Task B", freq_days=1)

        tasks = list_tasks_db()
        # Find tasks by name instead of assuming position (IDs are random)
        task_map = {t[1]: t[0] for t in tasks}  # name -> id
        task_a_id = task_map["Task A"]
        task_b_id = task_map["Task B"]

        # Make both tasks overdue
        yesterday = datetime.utcnow() - timedelta(days=2)
        update_task_last_done(task_a_id, yesterday)
        update_task_last_done(task_b_id, yesterday)

        # Both should be due
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 2

        # Complete Task A
        update_task_last_done(task_a_id, datetime.utcnow())

        # Only Task B should be due now
        due_tasks = tasks_due_now()
        assert len(due_tasks) == 1
        assert due_tasks[0][1] == "Task B"


class TestTaskRemoval:
    """Tests for task removal functionality."""

    def test_remove_task_from_database(self, test_db, monkeypatch):
        """Test that removing a task deletes it from the database."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, get_task_db, list_tasks_db, remove_task_db

        # Create a task
        add_task_db("Task to remove", freq_days=1)
        tasks = list_tasks_db()
        task_id = tasks[0][0]

        # Verify task exists
        assert get_task_db(task_id) is not None

        # Remove the task
        remove_task_db(task_id)

        # Verify task is gone
        assert get_task_db(task_id) is None
        assert len(list_tasks_db()) == 0

    def test_remove_due_task_removes_from_due_list(self, test_db, monkeypatch):
        """Test that removing a due task removes it from due list."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, list_tasks_db, remove_task_db, update_task_last_done
        from src.utils import tasks_due_now

        # Create and make task overdue
        add_task_db("Task to delete", freq_days=1)
        tasks = list_tasks_db()
        task_id = tasks[0][0]

        yesterday = datetime.utcnow() - timedelta(days=2)
        update_task_last_done(task_id, yesterday)

        # Verify task is due
        assert len(tasks_due_now()) == 1

        # Remove the task
        remove_task_db(task_id)

        # Verify task is no longer in due list
        assert len(tasks_due_now()) == 0


class TestFrequencyParsing:
    """Tests for frequency parsing utility."""

    @pytest.mark.parametrize(
        "input_str,expected_days",
        [
            ("1", 1),
            ("7", 7),
            ("30", 30),
            ("1d", 1),
            ("3d", 3),
            ("1 day", 1),
            ("3 days", 3),
            ("1w", 7),
            ("2w", 14),
            ("1 week", 7),
            ("2 weeks", 14),
            ("1m", 30),
            ("2m", 60),
            ("1 month", 30),
            ("2 months", 60),
        ],
    )
    def test_parse_frequency_valid_inputs(self, input_str, expected_days):
        """Test that various frequency formats are parsed correctly."""
        from src.utils import parse_frequency_to_days

        assert parse_frequency_to_days(input_str) == expected_days

    def test_parse_frequency_invalid_input(self):
        """Test that invalid frequency raises ValueError."""
        from src.utils import parse_frequency_to_days

        with pytest.raises(ValueError):
            parse_frequency_to_days("invalid")

        with pytest.raises(ValueError):
            parse_frequency_to_days("abc")

        with pytest.raises(ValueError):
            parse_frequency_to_days("")


class TestRandomIds:
    """Tests for random ID generation."""

    def test_random_ids_no_collision(self, test_db, monkeypatch):
        """Test that multiple tasks get unique random IDs."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)
        from src.database import add_task_db, list_tasks_db

        # Create several tasks
        for i in range(10):
            add_task_db(f"Task {i}", freq_days=1)

        tasks = list_tasks_db()
        ids = [t[0] for t in tasks]

        # All IDs should be unique
        assert len(ids) == len(set(ids))
        # All IDs should be 3-digit (100-999)
        assert all(100 <= tid <= 999 for tid in ids)

    def test_error_when_no_unique_id_available(self, test_db, monkeypatch, db_connection):
        """Test that RuntimeError is raised when no unique ID can be generated."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)
        from src.database import add_task_db

        # Pre-fill database with all possible IDs (100-999)
        cur = db_connection.cursor()
        for i in range(100, 1000):
            cur.execute(
                "INSERT INTO tasks (id, name, frequency_days, last_done, notes) VALUES (?, ?, ?, ?, ?)",
                (i, f"Task {i}", 1, "2024-01-01T00:00:00", ""),
            )
        db_connection.commit()

        # Attempting to add another task should raise RuntimeError
        with pytest.raises(RuntimeError, match="Could not generate unique ID"):
            add_task_db("One more task", freq_days=1)


class TestTaskEditing:
    """Tests for task editing functionality."""

    def test_edit_task_name(self, test_db, monkeypatch):
        """Test editing a task's name."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, get_task_db, list_tasks_db, update_task_field

        add_task_db("Original name", freq_days=1)
        tasks = list_tasks_db()
        task_id = tasks[0][0]

        update_task_field(task_id, "name", "New name")

        task = get_task_db(task_id)
        assert task[1] == "New name"

    def test_edit_task_frequency(self, test_db, monkeypatch):
        """Test editing a task's frequency."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, get_task_db, list_tasks_db, update_task_field

        add_task_db("Some task", freq_days=1)
        tasks = list_tasks_db()
        task_id = tasks[0][0]

        update_task_field(task_id, "frequency_days", 7)

        task = get_task_db(task_id)
        assert task[2] == 7

    def test_edit_task_notes(self, test_db, monkeypatch):
        """Test editing a task's notes."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, get_task_db, list_tasks_db, update_task_field

        add_task_db("Task with notes", freq_days=1, notes="Original notes")
        tasks = list_tasks_db()
        task_id = tasks[0][0]

        update_task_field(task_id, "notes", "Updated notes")

        task = get_task_db(task_id)
        assert task[4] == "Updated notes"

    def test_edit_invalid_field_raises_error(self, test_db, monkeypatch):
        """Test that editing an invalid field raises ValueError."""
        monkeypatch.setattr("src.database.DB_PATH", test_db)

        from src.database import add_task_db, list_tasks_db, update_task_field

        add_task_db("Test task", freq_days=1)
        tasks = list_tasks_db()
        task_id = tasks[0][0]

        with pytest.raises(ValueError):
            update_task_field(task_id, "invalid_field", "value")

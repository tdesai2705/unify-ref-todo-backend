"""Unit tests for bulk_ops.execute_bulk_complete.

Direct import of app.bulk_ops — no Flask app required.
This isolated import is what lets Smart Tests (PTS) map changes
in app/bulk_ops.py exclusively to this test file.
"""
from unittest.mock import MagicMock, call, patch
from app.bulk_ops import execute_bulk_complete


def _make_db():
    db = MagicMock()
    return db


def _make_Todo(existing_ids):
    """Return a mock Todo class whose .query.get returns an obj for known IDs."""
    Todo = MagicMock()
    def get_side_effect(tid):
        if tid in existing_ids:
            return MagicMock(completed=False, id=tid)
        return None
    Todo.query.get.side_effect = get_side_effect
    return Todo


class TestExecuteBulkComplete:
    def test_all_found_marks_completed(self):
        db = _make_db()
        Todo = _make_Todo([1, 2, 3])
        result = execute_bulk_complete([1, 2, 3], db, Todo)
        assert result['count'] == 3
        assert sorted(result['completed']) == [1, 2, 3]
        assert result['skipped'] == []
        assert result['total_requested'] == 3
        assert result['success_rate'] == 100.0
        assert result['processed'] is True
        db.session.commit.assert_called_once()

    def test_partial_found_skips_missing(self):
        db = _make_db()
        Todo = _make_Todo([1, 3])
        result = execute_bulk_complete([1, 2, 3], db, Todo)
        assert result['count'] == 2
        assert sorted(result['completed']) == [1, 3]
        assert result['skipped'] == [2]
        assert result['total_requested'] == 3
        assert result['success_rate'] == 66.7

    def test_none_found_returns_all_skipped(self):
        db = _make_db()
        Todo = _make_Todo([])
        result = execute_bulk_complete([10, 20], db, Todo)
        assert result['count'] == 0
        assert result['completed'] == []
        assert sorted(result['skipped']) == [10, 20]
        assert result['success_rate'] == 0.0

    def test_success_rate_rounds_to_one_decimal(self):
        db = _make_db()
        Todo = _make_Todo([1, 2])
        result = execute_bulk_complete([1, 2, 3], db, Todo)
        assert result['success_rate'] == 66.7

    def test_commit_called_exactly_once(self):
        db = _make_db()
        Todo = _make_Todo([1])
        execute_bulk_complete([1], db, Todo)
        db.session.commit.assert_called_once()

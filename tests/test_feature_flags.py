"""
Tests for feature-flag-gated behaviour.

Each flag has two test classes:
  - FlagOff*  — default state, flag env var not set
  - FlagOn*   — flag enabled via monkeypatch

Smart Tests (PTS) demo value:
  When you change code inside feature_flags.py or the flag-gated block in routes.py,
  PTS selects only the tests in this file — not the full suite.
  When you change auth or core todo code, PTS selects the tests in test_api.py instead.
"""

import os
import pytest
from app import create_app, db
from app.models import User, Todo
from datetime import datetime, timedelta


@pytest.fixture
def app():
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
    del os.environ['DATABASE_URL']


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(username='flaguser', email='flag@example.com')
        u.set_password('pass123')
        db.session.add(u)
        db.session.commit()
        return u.id


# ══════════════════════════════════════════════════════════════
# FLAG: FEATURE_ENHANCED_STATS
# ══════════════════════════════════════════════════════════════

class TestEnhancedStatsFlagOff:
    """Default behaviour — no extra stats fields."""

    @pytest.fixture(autouse=True)
    def disable_flag(self, monkeypatch):
        monkeypatch.setenv('FEATURE_ENHANCED_STATS', 'false')

    def test_stats_no_overdue_count(self, client):
        response = client.get('/todos/stats')
        assert response.status_code == 200
        data = response.get_json()
        assert 'overdue_count' not in data

    def test_stats_no_by_category(self, client):
        response = client.get('/todos/stats')
        data = response.get_json()
        assert 'by_category' not in data

    def test_stats_baseline_fields_present(self, client, user):
        client.post('/todos', json={'title': 'T', 'user_id': user})
        data = client.get('/todos/stats').get_json()
        assert all(k in data for k in ('total', 'completed', 'pending', 'completion_rate', 'by_priority'))


class TestEnhancedStatsFlagOn:
    """Enhanced stats — overdue_count and by_category returned."""

    @pytest.fixture(autouse=True)
    def enable_flag(self, monkeypatch):
        monkeypatch.setenv('FEATURE_ENHANCED_STATS', 'true')

    def test_stats_includes_overdue_count(self, client):
        response = client.get('/todos/stats')
        assert response.status_code == 200
        assert 'overdue_count' in response.get_json()

    def test_stats_includes_by_category(self, client):
        response = client.get('/todos/stats')
        assert 'by_category' in response.get_json()

    def test_overdue_count_correct(self, client, user, app):
        with app.app_context():
            past = datetime.utcnow() - timedelta(days=2)
            future = datetime.utcnow() + timedelta(days=2)
            db.session.add(Todo(user_id=user, title='Overdue', due_date=past, completed=False))
            db.session.add(Todo(user_id=user, title='Not due', due_date=future, completed=False))
            db.session.add(Todo(user_id=user, title='Done', due_date=past, completed=True))
            db.session.commit()

        data = client.get('/todos/stats').get_json()
        # Only the incomplete + past due_date todo counts as overdue
        assert data['overdue_count'] == 1

    def test_by_category_groups_correctly(self, client, user, app):
        with app.app_context():
            db.session.add(Todo(user_id=user, title='W1', category='work'))
            db.session.add(Todo(user_id=user, title='W2', category='work'))
            db.session.add(Todo(user_id=user, title='P1', category='personal'))
            db.session.commit()

        data = client.get('/todos/stats').get_json()
        assert data['by_category']['work'] == 2
        assert data['by_category']['personal'] == 1

    def test_baseline_fields_still_present(self, client, user):
        client.post('/todos', json={'title': 'T', 'user_id': user})
        data = client.get('/todos/stats').get_json()
        assert all(k in data for k in ('total', 'completed', 'pending', 'completion_rate', 'by_priority'))


# ══════════════════════════════════════════════════════════════
# FLAG: FEATURE_DUE_DATE_WARNINGS
# ══════════════════════════════════════════════════════════════

class TestDueDateWarningsFlagOff:
    """Default — todo responses do NOT include overdue or days_until_due."""

    @pytest.fixture(autouse=True)
    def disable_flag(self, monkeypatch):
        monkeypatch.setenv('FEATURE_DUE_DATE_WARNINGS', 'false')

    def test_get_todos_no_overdue_field(self, client, user, app):
        with app.app_context():
            past = datetime.utcnow() - timedelta(days=1)
            db.session.add(Todo(user_id=user, title='Old task', due_date=past))
            db.session.commit()

        todos = client.get('/todos').get_json()
        assert 'overdue' not in todos[0]
        assert 'days_until_due' not in todos[0]

    def test_todo_without_due_date_no_warning_fields(self, client, user):
        client.post('/todos', json={'title': 'No date', 'user_id': user})
        todos = client.get('/todos').get_json()
        assert 'overdue' not in todos[0]


class TestDueDateWarningsFlagOn:
    """Due date warnings enabled — overdue and days_until_due added to responses."""

    @pytest.fixture(autouse=True)
    def enable_flag(self, monkeypatch):
        monkeypatch.setenv('FEATURE_DUE_DATE_WARNINGS', 'true')

    def test_overdue_todo_flagged(self, client, user, app):
        with app.app_context():
            past = datetime.utcnow() - timedelta(days=3)
            db.session.add(Todo(user_id=user, title='Late task', due_date=past))
            db.session.commit()

        todos = client.get('/todos').get_json()
        assert todos[0]['overdue'] is True
        assert todos[0]['days_until_due'] < 0

    def test_future_todo_not_overdue(self, client, user, app):
        with app.app_context():
            future = datetime.utcnow() + timedelta(days=5)
            db.session.add(Todo(user_id=user, title='Upcoming', due_date=future))
            db.session.commit()

        todos = client.get('/todos').get_json()
        assert todos[0]['overdue'] is False
        assert todos[0]['days_until_due'] > 0

    def test_todo_without_due_date_skips_warning_fields(self, client, user):
        client.post('/todos', json={'title': 'No date', 'user_id': user})
        todos = client.get('/todos').get_json()
        assert 'overdue' not in todos[0]

    def test_single_todo_endpoint_includes_warnings(self, client, user, app):
        with app.app_context():
            past = datetime.utcnow() - timedelta(days=1)
            t = Todo(user_id=user, title='Check single', due_date=past)
            db.session.add(t)
            db.session.commit()
            tid = t.id

        data = client.get(f'/todos/{tid}').get_json()
        assert data['overdue'] is True


# ══════════════════════════════════════════════════════════════
# FLAG: FEATURE_BULK_OPERATIONS
# ══════════════════════════════════════════════════════════════

class TestBulkOperationsFlagOff:
    """Default — bulk-complete endpoint returns 404."""

    @pytest.fixture(autouse=True)
    def disable_flag(self, monkeypatch):
        monkeypatch.setenv('FEATURE_BULK_OPERATIONS', 'false')

    def test_bulk_complete_returns_404(self, client, user):
        client.post('/todos', json={'title': 'T1', 'user_id': user})
        response = client.post('/todos/bulk-complete', json={'todo_ids': [1]})
        assert response.status_code == 404

    def test_bulk_complete_without_body_returns_404(self, client):
        response = client.post('/todos/bulk-complete')
        assert response.status_code == 404


class TestBulkOperationsFlagOn:
    """Bulk operations enabled — endpoint marks todos completed."""

    @pytest.fixture(autouse=True)
    def enable_flag(self, monkeypatch):
        monkeypatch.setenv('FEATURE_BULK_OPERATIONS', 'true')

    def test_bulk_complete_marks_all_done(self, client, user):
        t1 = client.post('/todos', json={'title': 'T1', 'user_id': user}).get_json()
        t2 = client.post('/todos', json={'title': 'T2', 'user_id': user}).get_json()

        response = client.post('/todos/bulk-complete', json={'todo_ids': [t1['id'], t2['id']]})
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 2
        assert t1['id'] in data['completed']
        assert t2['id'] in data['completed']

        # Verify in DB
        assert client.get(f'/todos/{t1["id"]}').get_json()['completed'] is True
        assert client.get(f'/todos/{t2["id"]}').get_json()['completed'] is True

    def test_bulk_complete_partial_valid_ids(self, client, user):
        t1 = client.post('/todos', json={'title': 'T1', 'user_id': user}).get_json()
        response = client.post('/todos/bulk-complete', json={'todo_ids': [t1['id'], 9999]})
        assert response.status_code == 200
        data = response.get_json()
        # Only existing todo gets completed
        assert data['count'] == 1
        assert t1['id'] in data['completed']

    def test_bulk_complete_empty_list_returns_400(self, client):
        response = client.post('/todos/bulk-complete', json={'todo_ids': []})
        assert response.status_code == 400

    def test_bulk_complete_missing_body_returns_400(self, client):
        response = client.post('/todos/bulk-complete', json={})
        assert response.status_code == 400

    def test_stats_unchanged_after_bulk_complete(self, client, user):
        t1 = client.post('/todos', json={'title': 'T1', 'user_id': user}).get_json()
        t2 = client.post('/todos', json={'title': 'T2', 'user_id': user}).get_json()
        client.post('/todos/bulk-complete', json={'todo_ids': [t1['id'], t2['id']]})

        stats = client.get('/todos/stats').get_json()
        assert stats['completed'] == 2
        assert stats['pending'] == 0
        assert stats['completion_rate'] == 100.0

"""
Extended real-endpoint (non-mocked) coverage for POST /todos/bulk-complete,
complementing the existing mocked unit tests in test_bulk_complete.py.
"""

import os
import pytest
from app import create_app, db
from app.models import User


@pytest.fixture
def app():
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['FEATURE_BULK_OPERATIONS'] = 'true'
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
    del os.environ['DATABASE_URL']
    del os.environ['FEATURE_BULK_OPERATIONS']


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(username='bulkuser', email='bulk@example.com')
        u.set_password('pass123')
        db.session.add(u)
        db.session.commit()
        return u.id


def _make_todos(client, user_id, n):
    ids = []
    for i in range(n):
        r = client.post('/todos', json={'title': f'Bulk {i}', 'user_id': user_id})
        ids.append(r.get_json()['id'])
    return ids


# ══════════════════════════════════════════════════════════════
# Valid/invalid id count combinations
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('n_valid,n_invalid', [
    (1, 0), (2, 0), (5, 0), (1, 1), (2, 3), (5, 5), (10, 0), (0, 3), (3, 0), (8, 2),
])
def test_bulk_complete_valid_invalid_mix(client, user, n_valid, n_invalid):
    valid_ids = _make_todos(client, user, n_valid)
    invalid_ids = [900000 + i for i in range(n_invalid)]
    all_ids = valid_ids + invalid_ids

    response = client.post('/todos/bulk-complete', json={'todo_ids': all_ids})
    data = response.get_json()

    assert response.status_code == 200
    assert data['count'] == n_valid
    assert data['not_found_count'] == n_invalid
    assert data['total_requested'] == n_valid + n_invalid
    assert data['all_completed'] == (n_invalid == 0)
    assert data['fully_completed'] == (n_invalid == 0 and n_valid > 0)


@pytest.mark.parametrize('n', [1, 5, 10, 20, 50])
def test_bulk_complete_large_batches_all_valid(client, user, n):
    ids = _make_todos(client, user, n)
    response = client.post('/todos/bulk-complete', json={'todo_ids': ids})
    data = response.get_json()
    assert data['count'] == n
    assert data['success_rate'] == 100.0
    assert data['all_completed'] is True


@pytest.mark.parametrize('n_valid,n_invalid,expected_rate', [
    (1, 1, 50.0), (2, 2, 50.0), (1, 3, 25.0), (3, 1, 75.0), (1, 0, 100.0), (0, 1, 0.0),
])
def test_bulk_complete_success_rate(client, user, n_valid, n_invalid, expected_rate):
    valid_ids = _make_todos(client, user, n_valid)
    invalid_ids = [800000 + i for i in range(n_invalid)]
    response = client.post('/todos/bulk-complete', json={'todo_ids': valid_ids + invalid_ids})
    assert response.get_json()['success_rate'] == expected_rate


# ══════════════════════════════════════════════════════════════
# Duplicate ids in the same request
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('n_duplicates', [2, 3, 5])
def test_bulk_complete_duplicate_valid_ids_all_counted(client, user, n_duplicates):
    """Documents real behavior: execute_bulk_complete appends the same id
    once per occurrence in the request, so duplicates inflate the count."""
    todo_id = _make_todos(client, user, 1)[0]
    response = client.post('/todos/bulk-complete', json={'todo_ids': [todo_id] * n_duplicates})
    data = response.get_json()
    assert data['count'] == n_duplicates
    assert data['completed'] == [todo_id] * n_duplicates


def test_bulk_complete_actually_marks_todos_completed_in_db(client, user):
    ids = _make_todos(client, user, 3)
    client.post('/todos/bulk-complete', json={'todo_ids': ids})
    for tid in ids:
        todo = client.get(f'/todos/{tid}').get_json()
        assert todo['completed'] is True


def test_bulk_complete_does_not_affect_other_users_todos(client, user, app):
    with app.app_context():
        other = User(username='bulkother', email='bulkother@example.com')
        other.set_password('pass')
        db.session.add(other)
        db.session.commit()
        other_id = other.id

    mine = _make_todos(client, user, 2)
    theirs_resp = client.post('/todos', json={'title': 'Theirs', 'user_id': other_id})
    theirs_id = theirs_resp.get_json()['id']

    client.post('/todos/bulk-complete', json={'todo_ids': mine})

    theirs = client.get(f'/todos/{theirs_id}').get_json()
    assert theirs['completed'] is False


@pytest.mark.parametrize('n_already_completed', [1, 2, 5])
def test_bulk_complete_on_already_completed_todos_is_idempotent(client, user, n_already_completed):
    ids = _make_todos(client, user, n_already_completed)
    for tid in ids:
        client.put(f'/todos/{tid}', json={'completed': True})

    response = client.post('/todos/bulk-complete', json={'todo_ids': ids})
    data = response.get_json()
    assert data['count'] == n_already_completed
    assert data['all_completed'] is True

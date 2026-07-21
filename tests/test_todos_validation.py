"""
Expanded validation coverage for /todos CRUD endpoints.

Added per engineering's request: the existing suite was too small and too
fast for Smart Tests' confidence model to build a meaningful duration/
signal profile. This file adds broad parametrized coverage of create/update/
delete edge cases against app/routes.py's real (sometimes unhandled-exception)
behavior.
"""

import os
import pytest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Todo


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
        u = User(username='validationuser', email='validation@example.com')
        u.set_password('pass123')
        db.session.add(u)
        db.session.commit()
        return u.id


# ══════════════════════════════════════════════════════════════
# create_todo — title validation
# ══════════════════════════════════════════════════════════════

INVALID_TITLES = [
    '', None,
]

VALID_TITLES = [
    'a',
    'Buy groceries',
    'A' * 200,          # matches String(200) column limit exactly
    'Ünïcödé tïtlé 🎉',
    'Title with "quotes" and \'apostrophes\'',
    '   leading and trailing spaces   ',
    'Line1\nLine2',
    '<script>alert(1)</script>',
    '日本語のタイトル',
    '123456789',
]


@pytest.mark.parametrize('title', INVALID_TITLES)
def test_create_todo_rejects_invalid_title(client, user, title):
    payload = {'user_id': user}
    if title is not None:
        payload['title'] = title
    response = client.post('/todos', json=payload)
    assert response.status_code == 400
    assert response.get_json()['error'] == 'Title is required'


@pytest.mark.parametrize('title', VALID_TITLES)
def test_create_todo_accepts_valid_title(client, user, title):
    response = client.post('/todos', json={'title': title, 'user_id': user})
    assert response.status_code == 201
    assert response.get_json()['title'] == title


def test_create_todo_whitespace_only_title_is_accepted_as_truthy(client, user):
    """Route only checks truthiness, not blank-after-strip -- documents real behavior."""
    response = client.post('/todos', json={'title': '   ', 'user_id': user})
    assert response.status_code == 201
    assert response.get_json()['title'] == '   '


# ══════════════════════════════════════════════════════════════
# create_todo — user_id validation
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('user_id_value', [None, 0, ''])
def test_create_todo_rejects_missing_user_id(client, user_id_value):
    payload = {'title': 'Needs a user'}
    if user_id_value is not None:
        payload['user_id'] = user_id_value
    response = client.post('/todos', json=payload)
    assert response.status_code == 400
    assert response.get_json()['error'] == 'User ID is required'


@pytest.mark.parametrize('nonexistent_id', [9999, 88888, -1, 123456])
def test_create_todo_rejects_nonexistent_user(client, nonexistent_id):
    response = client.post('/todos', json={'title': 'Ghost user todo', 'user_id': nonexistent_id})
    assert response.status_code == 404
    assert response.get_json()['error'] == 'User not found'


# ══════════════════════════════════════════════════════════════
# create_todo — priority values (no validation in route, any string accepted)
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('priority', ['high', 'medium', 'low', 'urgent', 'none', '', 'HIGH', '123'])
def test_create_todo_accepts_any_priority_string(client, user, priority):
    response = client.post('/todos', json={'title': 'Priority test', 'user_id': user, 'priority': priority})
    assert response.status_code == 201
    assert response.get_json()['priority'] == priority


def test_create_todo_defaults_priority_to_medium_when_omitted(client, user):
    response = client.post('/todos', json={'title': 'No priority given', 'user_id': user})
    assert response.status_code == 201
    assert response.get_json()['priority'] == 'medium'


# ══════════════════════════════════════════════════════════════
# create_todo — category (freeform, no validation)
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('category', ['work', 'personal', 'shopping', 'health', '', 'Ünïcödé', None])
def test_create_todo_accepts_any_category(client, user, category):
    payload = {'title': 'Category test', 'user_id': user}
    if category is not None:
        payload['category'] = category
    response = client.post('/todos', json=payload)
    assert response.status_code == 201
    assert response.get_json()['category'] == category


# ══════════════════════════════════════════════════════════════
# create_todo — due_date parsing (real route has NO try/except around
# datetime.fromisoformat, so malformed input raises ValueError, not a 400)
# ══════════════════════════════════════════════════════════════

VALID_ISO_DATES = [
    '2026-08-01T00:00:00',
    '2026-12-31T23:59:59',
    '2027-01-01T00:00:00',
    (datetime.utcnow() + timedelta(days=1)).isoformat(),
    (datetime.utcnow() - timedelta(days=10)).isoformat(),
]

MALFORMED_DUE_DATES = [
    'not-a-date',
    '2026/08/01',
    '31-12-2026',
    'tomorrow',
    '',
]


@pytest.mark.parametrize('due_date', VALID_ISO_DATES)
def test_create_todo_accepts_valid_iso_due_date(client, user, due_date):
    response = client.post('/todos', json={'title': 'Due date test', 'user_id': user, 'due_date': due_date})
    assert response.status_code == 201
    assert response.get_json()['due_date'] is not None


@pytest.mark.parametrize('bad_due_date', MALFORMED_DUE_DATES)
def test_create_todo_malformed_due_date_raises_valueerror(client, user, bad_due_date):
    """Documents real (arguably-a-bug) behavior: routes.py does not catch
    the ValueError from datetime.fromisoformat, so it propagates instead
    of returning a 400. Empty string is falsy so it's the one case that
    short-circuits to None cleanly."""
    if bad_due_date == '':
        response = client.post('/todos', json={'title': 'Empty due date', 'user_id': user, 'due_date': bad_due_date})
        assert response.status_code == 201
        assert response.get_json()['due_date'] is None
    else:
        with pytest.raises(ValueError):
            client.post('/todos', json={'title': 'Bad due date', 'user_id': user, 'due_date': bad_due_date})


def test_create_todo_without_due_date_defaults_to_none(client, user):
    response = client.post('/todos', json={'title': 'No due date', 'user_id': user})
    assert response.status_code == 201
    assert response.get_json()['due_date'] is None


# ══════════════════════════════════════════════════════════════
# create_todo — description (freeform text, optional)
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('description', [
    None, '', 'Short description', 'A' * 5000, 'Multi\nline\ndescription',
    'Emoji 🎉🚀✅', '<b>HTML in description</b>',
])
def test_create_todo_accepts_any_description(client, user, description):
    payload = {'title': 'Description test', 'user_id': user}
    if description is not None:
        payload['description'] = description
    response = client.post('/todos', json=payload)
    assert response.status_code == 201
    assert response.get_json()['description'] == description


# ══════════════════════════════════════════════════════════════
# get_todo / delete_todo — 404 handling for nonexistent ids
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('bad_id', [999999, 424242, 1000000, 55555, 8675309, 111111, 222222, 333333])
def test_get_todo_nonexistent_returns_404(client, bad_id):
    response = client.get(f'/todos/{bad_id}')
    assert response.status_code == 404


@pytest.mark.parametrize('bad_id', [999999, 424242, 1000000, 55555, 8675309])
def test_delete_todo_nonexistent_returns_404(client, bad_id):
    response = client.delete(f'/todos/{bad_id}')
    assert response.status_code == 404


@pytest.mark.parametrize('bad_id', [999999, 424242, 1000000, 55555, 8675309])
def test_update_todo_nonexistent_returns_404(client, bad_id):
    response = client.put(f'/todos/{bad_id}', json={'title': 'Updated ghost'})
    assert response.status_code == 404


# ══════════════════════════════════════════════════════════════
# update_todo — partial field updates, one field at a time
# ══════════════════════════════════════════════════════════════

def _make_todo(client, user):
    resp = client.post('/todos', json={'title': 'Original title', 'user_id': user, 'priority': 'medium'})
    return resp.get_json()['id']


@pytest.mark.parametrize('field,value', [
    ('title', 'New title'),
    ('title', 'A' * 200),
    ('description', 'New description'),
    ('description', ''),
    ('completed', True),
    ('completed', False),
    ('priority', 'high'),
    ('priority', 'low'),
    ('priority', 'critical'),
    ('category', 'work'),
    ('category', 'personal'),
    ('category', None),
])
def test_update_todo_single_field(client, user, field, value):
    todo_id = _make_todo(client, user)
    response = client.put(f'/todos/{todo_id}', json={field: value})
    assert response.status_code == 200
    assert response.get_json()[field] == value


@pytest.mark.parametrize('due_date', VALID_ISO_DATES)
def test_update_todo_due_date(client, user, due_date):
    todo_id = _make_todo(client, user)
    response = client.put(f'/todos/{todo_id}', json={'due_date': due_date})
    assert response.status_code == 200
    assert response.get_json()['due_date'] is not None


def test_update_todo_due_date_to_null_clears_it(client, user):
    todo_id = _make_todo(client, user)
    client.put(f'/todos/{todo_id}', json={'due_date': VALID_ISO_DATES[0]})
    response = client.put(f'/todos/{todo_id}', json={'due_date': None})
    assert response.status_code == 200
    assert response.get_json()['due_date'] is None


@pytest.mark.parametrize('fields', [
    {'title': 'Combo A', 'completed': True},
    {'title': 'Combo B', 'priority': 'high', 'category': 'work'},
    {'description': 'Combo C', 'completed': True, 'priority': 'low'},
    {'title': 'Combo D', 'description': 'D desc', 'priority': 'medium', 'category': 'personal', 'completed': False},
])
def test_update_todo_multiple_fields_at_once(client, user, fields):
    todo_id = _make_todo(client, user)
    response = client.put(f'/todos/{todo_id}', json=fields)
    assert response.status_code == 200
    data = response.get_json()
    for k, v in fields.items():
        assert data[k] == v


def test_update_todo_no_fields_leaves_todo_unchanged(client, user):
    todo_id = _make_todo(client, user)
    response = client.put(f'/todos/{todo_id}', json={})
    assert response.status_code == 200
    assert response.get_json()['title'] == 'Original title'


# ══════════════════════════════════════════════════════════════
# delete_todo — confirms removal and idempotent re-delete behavior
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('n_todos_before_delete', [1, 3, 5, 10])
def test_delete_todo_removes_only_target(client, user, n_todos_before_delete):
    ids = []
    for i in range(n_todos_before_delete):
        r = client.post('/todos', json={'title': f'Todo {i}', 'user_id': user})
        ids.append(r.get_json()['id'])

    target = ids[0]
    response = client.delete(f'/todos/{target}')
    assert response.status_code == 204

    remaining = client.get('/todos').get_json()
    assert len(remaining) == n_todos_before_delete - 1
    assert all(t['id'] != target for t in remaining)


def test_delete_then_get_returns_404(client, user):
    todo_id = _make_todo(client, user)
    client.delete(f'/todos/{todo_id}')
    response = client.get(f'/todos/{todo_id}')
    assert response.status_code == 404


def test_delete_same_todo_twice_second_call_404s(client, user):
    todo_id = _make_todo(client, user)
    first = client.delete(f'/todos/{todo_id}')
    second = client.delete(f'/todos/{todo_id}')
    assert first.status_code == 204
    assert second.status_code == 404

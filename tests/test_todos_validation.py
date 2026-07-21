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

# Explicit ids on every non-trivial value: pytest's auto-generated parametrize
# ids for long/unicode/special-character strings are not guaranteed to
# round-trip identically between two separate `pytest --collect-only`
# invocations (see build #95 -- a 5000-char string's auto-id didn't match
# on re-collection). Smart Tests' subset flow depends on exact node-id
# matching across two such collections, so every "interesting" edge-case
# value here gets a short, stable, plain-ASCII id instead of relying on
# pytest to derive one from the value itself.
VALID_TITLES = [
    pytest.param('a', id='single_char'),
    pytest.param('Buy groceries', id='normal_title'),
    pytest.param('A' * 200, id='max_length_200'),          # matches String(200) column limit exactly
    pytest.param('Ünïcödé tïtlé 🎉', id='unicode_emoji'),
    pytest.param('Title with "quotes" and \'apostrophes\'', id='quotes_and_apostrophes'),
    pytest.param('   leading and trailing spaces   ', id='leading_trailing_spaces'),
    pytest.param('Line1\nLine2', id='embedded_newline'),
    pytest.param('<script>alert(1)</script>', id='script_tag'),
    pytest.param('日本語のタイトル', id='japanese_text'),
    pytest.param('123456789', id='numeric_string'),
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


def test_create_todo_whitespace_only_title_is_rejected(client, user):
    """create_todo now strip()-checks the title, not just truthiness --
    was previously accepted (201), see test_known_issues.py history."""
    response = client.post('/todos', json={'title': '   ', 'user_id': user})
    assert response.status_code == 400


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
# create_todo — priority values (validated against high/medium/low --
# invalid values covered in test_known_issues.py)
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('priority', ['high', 'medium', 'low'])
def test_create_todo_accepts_valid_priority_values(client, user, priority):
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

@pytest.mark.parametrize('category', [
    'work', 'personal', 'shopping', 'health',
    pytest.param('', id='empty_string'),
    pytest.param('Ünïcödé', id='unicode'),
    None,
])
def test_create_todo_accepts_any_category(client, user, category):
    payload = {'title': 'Category test', 'user_id': user}
    if category is not None:
        payload['category'] = category
    response = client.post('/todos', json=payload)
    assert response.status_code == 201
    assert response.get_json()['category'] == category


# ══════════════════════════════════════════════════════════════
# create_todo — due_date parsing (malformed input now returns a clean
# 400, via _parse_due_date() wrapped in try/except ValueError)
# ══════════════════════════════════════════════════════════════

VALID_ISO_DATES = [
    # Fixed, deterministic strings only -- Smart Tests' subset flow runs
    # `pytest --collect-only` once to build subset.txt, then a SECOND,
    # later `pytest <ids>` to actually run it. A value computed from
    # datetime.utcnow() at collection time (e.g. "a day from now") produces
    # a DIFFERENT literal timestamp string on each of those two collections,
    # so the exact node id in subset.txt no longer exists by the second
    # pass, and pytest aborts the whole run with "not found" errors instead
    # of just failing that one test. Never derive a parametrize id from
    # wall-clock time.
    '2026-08-01T00:00:00',
    '2026-12-31T23:59:59',
    '2027-01-01T00:00:00',
    '2026-09-15T12:00:00',
    '2025-06-01T08:30:00',
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
def test_create_todo_malformed_due_date_returns_400(client, user, bad_due_date):
    """Empty string is falsy so it short-circuits to None cleanly (still 201);
    every other malformed value now returns a clean 400 instead of raising
    (see test_known_issues.py for the original failing-test history)."""
    if bad_due_date == '':
        response = client.post('/todos', json={'title': 'Empty due date', 'user_id': user, 'due_date': bad_due_date})
        assert response.status_code == 201
        assert response.get_json()['due_date'] is None
    else:
        response = client.post('/todos', json={'title': 'Bad due date', 'user_id': user, 'due_date': bad_due_date})
        assert response.status_code == 400


def test_create_todo_without_due_date_defaults_to_none(client, user):
    response = client.post('/todos', json={'title': 'No due date', 'user_id': user})
    assert response.status_code == 201
    assert response.get_json()['due_date'] is None


# ══════════════════════════════════════════════════════════════
# create_todo — description (freeform text, optional)
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('description', [
    None,
    pytest.param('', id='empty_string'),
    'Short description',
    pytest.param('A' * 5000, id='max_length_5000'),
    pytest.param('Multi\nline\ndescription', id='embedded_newlines'),
    pytest.param('Emoji 🎉🚀✅', id='emoji'),
    pytest.param('<b>HTML in description</b>', id='html_tag'),
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
    pytest.param('title', 'A' * 200, id='title-max_length_200'),
    ('description', 'New description'),
    pytest.param('description', '', id='description-empty_string'),
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

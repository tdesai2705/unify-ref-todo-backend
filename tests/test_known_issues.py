"""
Known-issue tests — these document REAL gaps in current app behavior and are
EXPECTED TO FAIL against today's code. This is intentional: Smart Tests'
confidence model needs genuine pass/fail diversity tied to real code paths
to build a meaningful confidence curve, not just more passing tests.

Each test below corresponds to an actual, reproducible bug or missing
validation in app/routes.py, found while expanding test coverage. They are
left failing on purpose as a real backlog, not fixed here, so this file
also doubles as a findings list for engineering.

DO NOT silently "fix" these by weakening the assertions -- if the
underlying route behavior is fixed, the test should then pass for real.
"""

import os
import pytest
from app import create_app, db
from app.models import User


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
        u = User(username='knownissueuser', email='knownissue@example.com')
        u.set_password('pass123')
        db.session.add(u)
        db.session.commit()
        return u.id


# ══════════════════════════════════════════════════════════════
# BUG: malformed due_date crashes with an unhandled ValueError
# instead of returning a 400. routes.py calls
# datetime.fromisoformat(data['due_date']) with no try/except.
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('bad_due_date', [
    'not-a-date', '2026/08/01', '31-12-2026', 'tomorrow', '13:45',
])
def test_create_todo_should_return_400_for_malformed_due_date(client, user, bad_due_date):
    """FAILS TODAY: raises ValueError instead of returning 400.
    Expected/desired behavior once fixed: a 400 with a clear error message."""
    response = client.post('/todos', json={'title': 'Bad date', 'user_id': user, 'due_date': bad_due_date})
    assert response.status_code == 400
    assert 'error' in response.get_json()


@pytest.mark.parametrize('bad_due_date', ['not-a-date', 'invalid-format'])
def test_update_todo_should_return_400_for_malformed_due_date(client, user, bad_due_date):
    """FAILS TODAY: same unhandled ValueError bug exists in update_todo()."""
    create = client.post('/todos', json={'title': 'To update', 'user_id': user})
    todo_id = create.get_json()['id']
    response = client.put(f'/todos/{todo_id}', json={'due_date': bad_due_date})
    assert response.status_code == 400


# ══════════════════════════════════════════════════════════════
# BUG: whitespace-only title is accepted as valid (route only
# checks truthiness of the raw string, not stripped content).
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('whitespace_title', ['   ', '\t', '\n', '  \t\n  '])
def test_create_todo_should_reject_whitespace_only_title(client, user, whitespace_title):
    """FAILS TODAY: whitespace-only titles are accepted (201) instead of
    rejected (400) -- 'Title is required' should arguably mean non-blank."""
    response = client.post('/todos', json={'title': whitespace_title, 'user_id': user})
    assert response.status_code == 400


# ══════════════════════════════════════════════════════════════
# BUG: priority accepts any arbitrary string, not just high/medium/low.
# The by_priority stats breakdown silently ignores anything else.
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('invalid_priority', ['urgent', 'critical', 'none', 'HIGH', '5', ''])
def test_create_todo_should_reject_invalid_priority_value(client, user, invalid_priority):
    """FAILS TODAY: any string is accepted for priority with no validation
    against the documented high/medium/low set."""
    response = client.post('/todos', json={'title': 'Priority check', 'user_id': user, 'priority': invalid_priority})
    assert response.status_code == 400


def test_stats_by_priority_should_account_for_all_todos(client, user):
    """FAILS TODAY: a todo created with an invalid/unexpected priority value
    is silently excluded from every by_priority bucket, so
    high + medium + low can under-count the real total."""
    client.post('/todos', json={'title': 'T1', 'user_id': user, 'priority': 'high'})
    client.post('/todos', json={'title': 'T2', 'user_id': user, 'priority': 'urgent'})  # not in high/medium/low
    data = client.get('/todos/stats').get_json()
    accounted_for = data['by_priority']['high'] + data['by_priority']['medium'] + data['by_priority']['low']
    assert accounted_for == data['total']


# ══════════════════════════════════════════════════════════════
# BUG: register() does not validate email format at all.
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('bad_email', [
    'not-an-email', 'missing-at-sign.com', '@no-local-part.com', 'spaces in@email.com', 'double@@at.com',
])
def test_register_should_reject_invalid_email_format(client, bad_email):
    """FAILS TODAY: no email format validation exists in the register route,
    so any string is stored as a user's email."""
    response = client.post('/auth/register', json={
        'username': f'emailtest_{hash(bad_email) % 100000}', 'password': 'pass123', 'email': bad_email,
    })
    assert response.status_code == 400

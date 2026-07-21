"""
Regression tests for real bugs found while expanding test coverage.

These were originally committed as intentionally-failing tests (see git
history) specifically so Smart Tests would have genuine pass/fail
diversity to learn from, not just more passing tests. The underlying
bugs in app/routes.py have since been fixed (strip-checked titles,
validated priority, try/except around due_date parsing, email format
validation), so these now pass for real -- giving Smart Tests a second,
even more useful signal: the same tests flipping from fail to pass tied
to an actual code change, not just a one-off failure.

DO NOT weaken these assertions to make them pass -- if a future change
reintroduces one of these bugs, this file should fail again for real.
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
# FIXED: malformed due_date used to crash with an unhandled ValueError
# instead of returning a 400. create_todo/update_todo now go through
# _parse_due_date() wrapped in try/except ValueError.
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('bad_due_date', [
    'not-a-date', '2026/08/01', '31-12-2026', 'tomorrow', '13:45',
])
def test_create_todo_should_return_400_for_malformed_due_date(client, user, bad_due_date):
    """Was failing (unhandled ValueError) -- now returns a clean 400."""
    response = client.post('/todos', json={'title': 'Bad date', 'user_id': user, 'due_date': bad_due_date})
    assert response.status_code == 400
    assert 'error' in response.get_json()


@pytest.mark.parametrize('bad_due_date', ['not-a-date', 'invalid-format'])
def test_update_todo_should_return_400_for_malformed_due_date(client, user, bad_due_date):
    """Was failing -- same fix applied to update_todo()."""
    create = client.post('/todos', json={'title': 'To update', 'user_id': user})
    todo_id = create.get_json()['id']
    response = client.put(f'/todos/{todo_id}', json={'due_date': bad_due_date})
    assert response.status_code == 400


# ══════════════════════════════════════════════════════════════
# FIXED: whitespace-only title used to be accepted as valid.
# create_todo now checks title.strip() truthiness too.
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('whitespace_title', [
    pytest.param('   ', id='spaces_only'),
    pytest.param('\t', id='tab_only'),
    pytest.param('\n', id='newline_only'),
    pytest.param('  \t\n  ', id='mixed_whitespace'),
])
def test_create_todo_should_reject_whitespace_only_title(client, user, whitespace_title):
    """Was failing (201 accepted) -- now correctly rejected with 400."""
    response = client.post('/todos', json={'title': whitespace_title, 'user_id': user})
    assert response.status_code == 400


# ══════════════════════════════════════════════════════════════
# FIXED: priority used to accept any arbitrary string. create_todo now
# validates against VALID_PRIORITIES = {'high', 'medium', 'low'}.
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('invalid_priority', [
    'urgent', 'critical', 'none', 'HIGH', '5',
    pytest.param('', id='empty_string'),
])
def test_create_todo_should_reject_invalid_priority_value(client, user, invalid_priority):
    """Was failing (any string accepted) -- now returns 400."""
    response = client.post('/todos', json={'title': 'Priority check', 'user_id': user, 'priority': invalid_priority})
    assert response.status_code == 400


def test_stats_by_priority_should_account_for_all_todos(client, user):
    """Was failing when an invalid-priority todo silently vanished from
    every by_priority bucket. Now trivially holds, because invalid
    priorities are rejected at creation time (T2 below never gets
    created) -- still a meaningful regression guard: if priority
    validation is ever removed, this goes back to failing too."""
    client.post('/todos', json={'title': 'T1', 'user_id': user, 'priority': 'high'})
    client.post('/todos', json={'title': 'T2', 'user_id': user, 'priority': 'urgent'})  # rejected, not created
    data = client.get('/todos/stats').get_json()
    accounted_for = data['by_priority']['high'] + data['by_priority']['medium'] + data['by_priority']['low']
    assert accounted_for == data['total']


# ══════════════════════════════════════════════════════════════
# FIXED: register() did not validate email format at all.
# Now checked against EMAIL_RE before uniqueness checks.
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('bad_email', [
    'not-an-email', 'missing-at-sign.com', '@no-local-part.com',
    pytest.param('spaces in@email.com', id='spaces_in_email'),
    'double@@at.com',
])
def test_register_should_reject_invalid_email_format(client, bad_email):
    """Was failing (any string stored as email) -- now returns 400."""
    response = client.post('/auth/register', json={
        'username': f'emailtest_{hash(bad_email) % 100000}', 'password': 'pass123', 'email': bad_email,
    })
    assert response.status_code == 400

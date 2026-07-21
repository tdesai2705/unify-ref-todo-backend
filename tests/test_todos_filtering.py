"""
Combinatorial coverage of GET /todos filtering and sorting.

routes.py's get_todos() supports independent filters (user_id, completed,
priority, category) plus a sort direction -- this file exercises the
combinations directly against a known, seeded dataset so each assertion
verifies real filtering logic, not just a smoke-test 200.
"""

import os
import pytest
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
        u = User(username='filteruser', email='filter@example.com')
        u.set_password('pass123')
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def other_user(app):
    with app.app_context():
        u = User(username='otheruser', email='other@example.com')
        u.set_password('pass123')
        db.session.add(u)
        db.session.commit()
        return u.id


SEED_TODOS = [
    {'title': 'High work incomplete', 'priority': 'high', 'category': 'work', 'completed': False},
    {'title': 'High work complete', 'priority': 'high', 'category': 'work', 'completed': True},
    {'title': 'Medium personal incomplete', 'priority': 'medium', 'category': 'personal', 'completed': False},
    {'title': 'Medium personal complete', 'priority': 'medium', 'category': 'personal', 'completed': True},
    {'title': 'Low shopping incomplete', 'priority': 'low', 'category': 'shopping', 'completed': False},
    {'title': 'Low shopping complete', 'priority': 'low', 'category': 'shopping', 'completed': True},
    {'title': 'High personal incomplete', 'priority': 'high', 'category': 'personal', 'completed': False},
    {'title': 'Medium work complete', 'priority': 'medium', 'category': 'work', 'completed': True},
]


def _seed(client, user_id):
    ids = []
    for t in SEED_TODOS:
        r = client.post('/todos', json={
            'title': t['title'], 'user_id': user_id,
            'priority': t['priority'], 'category': t['category'],
        })
        todo_id = r.get_json()['id']
        if t['completed']:
            client.put(f'/todos/{todo_id}', json={'completed': True})
        ids.append(todo_id)
    return ids


# ══════════════════════════════════════════════════════════════
# Single-filter combinations
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('priority,expected_count', [
    ('high', 3), ('medium', 3), ('low', 2), ('critical', 0),
])
def test_filter_by_priority_alone(client, user, priority, expected_count):
    _seed(client, user)
    response = client.get(f'/todos?priority={priority}')
    todos = response.get_json()
    assert len(todos) == expected_count
    assert all(t['priority'] == priority for t in todos)


@pytest.mark.parametrize('category,expected_count', [
    ('work', 3), ('personal', 3), ('shopping', 2), ('health', 0),
])
def test_filter_by_category_alone(client, user, category, expected_count):
    _seed(client, user)
    response = client.get(f'/todos?category={category}')
    todos = response.get_json()
    assert len(todos) == expected_count
    assert all(t['category'] == category for t in todos)


@pytest.mark.parametrize('completed_str,expected_count', [
    ('true', 4), ('false', 4), ('True', 4), ('yes', 4), ('1', 4), ('nonsense', 4),
])
def test_filter_by_completed_alone(client, user, completed_str, expected_count):
    """completed.lower() == 'true' is the only truthy path -- anything else,
    including 'yes'/'1'/'nonsense', is treated as completed=False."""
    _seed(client, user)
    response = client.get(f'/todos?completed={completed_str}')
    todos = response.get_json()
    assert len(todos) == expected_count
    expected_bool = completed_str.lower() == 'true'
    assert all(t['completed'] == expected_bool for t in todos)


# ══════════════════════════════════════════════════════════════
# Two-filter combinations (priority x category)
# ══════════════════════════════════════════════════════════════

PRIORITY_CATEGORY_COMBOS = [
    ('high', 'work', 2), ('high', 'personal', 1), ('high', 'shopping', 0),
    ('medium', 'work', 1), ('medium', 'personal', 2), ('medium', 'shopping', 0),
    ('low', 'work', 0), ('low', 'personal', 0), ('low', 'shopping', 2),
]


@pytest.mark.parametrize('priority,category,expected_count', PRIORITY_CATEGORY_COMBOS)
def test_filter_by_priority_and_category(client, user, priority, category, expected_count):
    _seed(client, user)
    response = client.get(f'/todos?priority={priority}&category={category}')
    todos = response.get_json()
    assert len(todos) == expected_count
    assert all(t['priority'] == priority and t['category'] == category for t in todos)


# ══════════════════════════════════════════════════════════════
# Two-filter combinations (priority x completed)
# ══════════════════════════════════════════════════════════════

PRIORITY_COMPLETED_COMBOS = [
    ('high', 'true', 1), ('high', 'false', 2),
    ('medium', 'true', 2), ('medium', 'false', 1),
    ('low', 'true', 1), ('low', 'false', 1),
]


@pytest.mark.parametrize('priority,completed_str,expected_count', PRIORITY_COMPLETED_COMBOS)
def test_filter_by_priority_and_completed(client, user, priority, completed_str, expected_count):
    _seed(client, user)
    response = client.get(f'/todos?priority={priority}&completed={completed_str}')
    todos = response.get_json()
    assert len(todos) == expected_count


# ══════════════════════════════════════════════════════════════
# Two-filter combinations (category x completed)
# ══════════════════════════════════════════════════════════════

CATEGORY_COMPLETED_COMBOS = [
    ('work', 'true', 2), ('work', 'false', 1),
    ('personal', 'true', 1), ('personal', 'false', 2),
    ('shopping', 'true', 1), ('shopping', 'false', 1),
]


@pytest.mark.parametrize('category,completed_str,expected_count', CATEGORY_COMPLETED_COMBOS)
def test_filter_by_category_and_completed(client, user, category, completed_str, expected_count):
    _seed(client, user)
    response = client.get(f'/todos?category={category}&completed={completed_str}')
    todos = response.get_json()
    assert len(todos) == expected_count


# ══════════════════════════════════════════════════════════════
# Three-filter combinations (priority x category x completed)
# ══════════════════════════════════════════════════════════════

THREE_WAY_COMBOS = [
    ('high', 'work', 'true', 1), ('high', 'work', 'false', 1),
    ('high', 'personal', 'true', 0), ('high', 'personal', 'false', 1),
    ('medium', 'work', 'true', 1), ('medium', 'work', 'false', 0),
    ('medium', 'personal', 'true', 1), ('medium', 'personal', 'false', 1),
    ('low', 'shopping', 'true', 1), ('low', 'shopping', 'false', 1),
]


@pytest.mark.parametrize('priority,category,completed_str,expected_count', THREE_WAY_COMBOS)
def test_filter_by_priority_category_and_completed(client, user, priority, category, completed_str, expected_count):
    _seed(client, user)
    response = client.get(f'/todos?priority={priority}&category={category}&completed={completed_str}')
    todos = response.get_json()
    assert len(todos) == expected_count


# ══════════════════════════════════════════════════════════════
# Sorting
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('sort_value', ['asc', 'desc', 'invalid', '', 'ASC', None])
def test_sort_order(client, user, sort_value):
    """Only sort=asc triggers ascending; every other value (including
    unrelated strings) falls through to the desc() branch."""
    ids = _seed(client, user)
    url = '/todos' if sort_value is None else f'/todos?sort={sort_value}'
    response = client.get(url)
    todos = response.get_json()
    returned_ids = [t['id'] for t in todos]
    if sort_value == 'asc':
        assert returned_ids == ids
    else:
        assert returned_ids == list(reversed(ids))


# ══════════════════════════════════════════════════════════════
# user_id scoping — ensures filters never leak across users
# ══════════════════════════════════════════════════════════════

def test_user_id_filter_isolates_other_users_todos(client, user, other_user):
    client.post('/todos', json={'title': 'Mine', 'user_id': user})
    client.post('/todos', json={'title': 'Theirs', 'user_id': other_user})

    mine = client.get(f'/todos?user_id={user}').get_json()
    theirs = client.get(f'/todos?user_id={other_user}').get_json()

    assert len(mine) == 1 and mine[0]['title'] == 'Mine'
    assert len(theirs) == 1 and theirs[0]['title'] == 'Theirs'


def test_no_user_id_filter_returns_all_users_todos(client, user, other_user):
    client.post('/todos', json={'title': 'Mine', 'user_id': user})
    client.post('/todos', json={'title': 'Theirs', 'user_id': other_user})
    response = client.get('/todos')
    assert len(response.get_json()) == 2


@pytest.mark.parametrize('n_mine,n_theirs', [(1, 1), (2, 3), (5, 0), (0, 4), (3, 3)])
def test_user_id_filter_counts(client, user, other_user, n_mine, n_theirs):
    for i in range(n_mine):
        client.post('/todos', json={'title': f'Mine {i}', 'user_id': user})
    for i in range(n_theirs):
        client.post('/todos', json={'title': f'Theirs {i}', 'user_id': other_user})

    mine = client.get(f'/todos?user_id={user}').get_json()
    theirs = client.get(f'/todos?user_id={other_user}').get_json()
    assert len(mine) == n_mine
    assert len(theirs) == n_theirs


# ══════════════════════════════════════════════════════════════
# Empty-state and boundary cases
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('query_string', [
    'priority=high', 'category=work', 'completed=true', 'sort=asc',
    'priority=high&category=work', 'user_id=999999',
])
def test_filters_on_empty_dataset_return_empty_list(client, query_string):
    response = client.get(f'/todos?{query_string}')
    assert response.status_code == 200
    assert response.get_json() == []

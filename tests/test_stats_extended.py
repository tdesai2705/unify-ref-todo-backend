"""Expanded coverage for GET /todos/stats, including the enhanced_stats flag path."""

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
        u = User(username='statsuser', email='stats@example.com')
        u.set_password('pass123')
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def other_user(app):
    with app.app_context():
        u = User(username='statsother', email='statsother@example.com')
        u.set_password('pass123')
        db.session.add(u)
        db.session.commit()
        return u.id


# ══════════════════════════════════════════════════════════════
# Baseline fields, various total/completed distributions
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('total,completed,expected_rate', [
    (0, 0, 0), (1, 0, 0.0), (1, 1, 100.0), (2, 1, 50.0),
    (3, 1, 33.33), (4, 1, 25.0), (5, 2, 40.0), (10, 3, 30.0),
    (7, 7, 100.0), (8, 0, 0.0), (3, 2, 66.67), (6, 5, 83.33),
])
def test_stats_completion_rate_calculation(client, user, total, completed, expected_rate):
    ids = []
    for i in range(total):
        r = client.post('/todos', json={'title': f'T{i}', 'user_id': user})
        ids.append(r.get_json()['id'])
    for i in range(completed):
        client.put(f'/todos/{ids[i]}', json={'completed': True})

    response = client.get('/todos/stats')
    data = response.get_json()
    assert data['total'] == total
    assert data['completed'] == completed
    assert data['pending'] == total - completed
    assert data['completion_rate'] == expected_rate


@pytest.mark.parametrize('n_high,n_medium,n_low', [
    (1, 0, 0), (0, 1, 0), (0, 0, 1), (2, 3, 1), (5, 5, 5), (0, 0, 0), (10, 0, 0),
])
def test_stats_by_priority_breakdown(client, user, n_high, n_medium, n_low):
    for i in range(n_high):
        client.post('/todos', json={'title': f'H{i}', 'user_id': user, 'priority': 'high'})
    for i in range(n_medium):
        client.post('/todos', json={'title': f'M{i}', 'user_id': user, 'priority': 'medium'})
    for i in range(n_low):
        client.post('/todos', json={'title': f'L{i}', 'user_id': user, 'priority': 'low'})

    data = client.get('/todos/stats').get_json()
    assert data['by_priority']['high'] == n_high
    assert data['by_priority']['medium'] == n_medium
    assert data['by_priority']['low'] == n_low


# ══════════════════════════════════════════════════════════════
# user_id scoping
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('n_mine,n_theirs', [(1, 1), (3, 2), (0, 5), (5, 0), (4, 4)])
def test_stats_scoped_to_user_id(client, user, other_user, n_mine, n_theirs):
    for i in range(n_mine):
        client.post('/todos', json={'title': f'Mine{i}', 'user_id': user})
    for i in range(n_theirs):
        client.post('/todos', json={'title': f'Theirs{i}', 'user_id': other_user})

    mine_stats = client.get(f'/todos/stats?user_id={user}').get_json()
    theirs_stats = client.get(f'/todos/stats?user_id={other_user}').get_json()
    assert mine_stats['total'] == n_mine
    assert theirs_stats['total'] == n_theirs


def test_stats_without_user_id_includes_all_users(client, user, other_user):
    client.post('/todos', json={'title': 'Mine', 'user_id': user})
    client.post('/todos', json={'title': 'Theirs', 'user_id': other_user})
    data = client.get('/todos/stats').get_json()
    assert data['total'] == 2


# ══════════════════════════════════════════════════════════════
# enhanced_stats flag OFF (default) -- extra fields absent
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('n_todos', [0, 1, 5, 10])
def test_stats_without_enhanced_flag_omits_extra_fields(client, user, monkeypatch, n_todos):
    monkeypatch.setenv('FEATURE_ENHANCED_STATS', 'false')
    for i in range(n_todos):
        client.post('/todos', json={'title': f'T{i}', 'user_id': user})
    data = client.get('/todos/stats').get_json()
    assert 'overdue_count' not in data
    assert 'by_category' not in data
    assert 'overdue_rate' not in data
    assert 'pending_rate' not in data


# ══════════════════════════════════════════════════════════════
# enhanced_stats flag ON -- overdue / category / rate fields
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('n_overdue,n_not_overdue,n_completed_overdue', [
    (1, 0, 0), (0, 1, 0), (2, 3, 0), (0, 0, 1), (3, 0, 2), (5, 5, 5), (0, 5, 0),
])
def test_stats_overdue_count_with_enhanced_flag(client, user, monkeypatch, n_overdue, n_not_overdue, n_completed_overdue):
    monkeypatch.setenv('FEATURE_ENHANCED_STATS', 'true')
    past = (datetime.utcnow() - timedelta(days=2)).isoformat()
    future = (datetime.utcnow() + timedelta(days=2)).isoformat()

    for i in range(n_overdue):
        client.post('/todos', json={'title': f'Overdue{i}', 'user_id': user, 'due_date': past})
    for i in range(n_not_overdue):
        client.post('/todos', json={'title': f'Future{i}', 'user_id': user, 'due_date': future})
    for i in range(n_completed_overdue):
        r = client.post('/todos', json={'title': f'DoneOverdue{i}', 'user_id': user, 'due_date': past})
        client.put(f'/todos/{r.get_json()["id"]}', json={'completed': True})

    data = client.get('/todos/stats').get_json()
    assert data['overdue_count'] == n_overdue


@pytest.mark.parametrize('categories', [
    ['work'], ['work', 'personal'], ['work', 'work', 'personal'],
    ['work', 'personal', 'shopping'], [], ['health', 'health', 'health', 'fitness'],
])
def test_stats_by_category_with_enhanced_flag(client, user, monkeypatch, categories):
    monkeypatch.setenv('FEATURE_ENHANCED_STATS', 'true')
    for i, cat in enumerate(categories):
        client.post('/todos', json={'title': f'T{i}', 'user_id': user, 'category': cat})

    data = client.get('/todos/stats').get_json()
    expected = {}
    for cat in categories:
        expected[cat] = expected.get(cat, 0) + 1
    assert data['by_category'] == expected


@pytest.mark.parametrize('total,overdue,expected_overdue_rate', [
    (4, 1, 25.0), (4, 2, 50.0), (10, 3, 30.0), (2, 0, 0.0), (5, 5, 100.0),
])
def test_stats_overdue_rate_calculation(client, user, monkeypatch, total, overdue, expected_overdue_rate):
    monkeypatch.setenv('FEATURE_ENHANCED_STATS', 'true')
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    for i in range(overdue):
        client.post('/todos', json={'title': f'Overdue{i}', 'user_id': user, 'due_date': past})
    for i in range(total - overdue):
        client.post('/todos', json={'title': f'Fine{i}', 'user_id': user})

    data = client.get('/todos/stats').get_json()
    assert data['overdue_rate'] == expected_overdue_rate


@pytest.mark.parametrize('total,completed,expected_pending_rate', [
    (4, 1, 75.0), (4, 3, 25.0), (10, 5, 50.0), (2, 2, 0.0), (5, 0, 100.0),
])
def test_stats_pending_rate_calculation(client, user, monkeypatch, total, completed, expected_pending_rate):
    monkeypatch.setenv('FEATURE_ENHANCED_STATS', 'true')
    ids = []
    for i in range(total):
        r = client.post('/todos', json={'title': f'T{i}', 'user_id': user})
        ids.append(r.get_json()['id'])
    for i in range(completed):
        client.put(f'/todos/{ids[i]}', json={'completed': True})

    data = client.get('/todos/stats').get_json()
    assert data['pending_rate'] == expected_pending_rate


def test_stats_enhanced_category_scoped_to_user_id(client, user, other_user, monkeypatch):
    monkeypatch.setenv('FEATURE_ENHANCED_STATS', 'true')
    client.post('/todos', json={'title': 'Mine', 'user_id': user, 'category': 'work'})
    client.post('/todos', json={'title': 'Theirs', 'user_id': other_user, 'category': 'personal'})

    data = client.get(f'/todos/stats?user_id={user}').get_json()
    assert data['by_category'] == {'work': 1}

import pytest
from app import create_app, db
from app.models import User, Todo


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(username='testuser', email='test@example.com')
        u.set_password('password123')
        db.session.add(u)
        db.session.commit()
        return u.id


def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'healthy'


def test_register_user(client):
    response = client.post('/auth/register', json={
        'username': 'newuser',
        'password': 'password123',
        'email': 'newuser@example.com'
    })
    assert response.status_code == 201
    assert response.get_json()['username'] == 'newuser'


def test_register_duplicate_username(client, user):
    response = client.post('/auth/register', json={
        'username': 'testuser',
        'password': 'password123'
    })
    assert response.status_code == 409


def test_login_success(client, user):
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'password123'
    })
    assert response.status_code == 200
    assert response.get_json()['message'] == 'Login successful'


def test_login_wrong_password(client, user):
    response = client.post('/auth/login', json={
        'username': 'testuser',
        'password': 'wrongpassword'
    })
    assert response.status_code == 401


def test_create_todo(client, user):
    response = client.post('/todos', json={
        'title': 'Test Todo',
        'user_id': user,
        'priority': 'high'
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'Test Todo'
    assert data['priority'] == 'high'
    assert data['completed'] is False


def test_create_todo_missing_title(client, user):
    response = client.post('/todos', json={'user_id': user})
    assert response.status_code == 400


def test_create_todo_missing_user(client):
    response = client.post('/todos', json={'title': 'No User Todo'})
    assert response.status_code == 400


def test_get_todos(client, user):
    client.post('/todos', json={'title': 'Todo 1', 'user_id': user, 'priority': 'high'})
    client.post('/todos', json={'title': 'Todo 2', 'user_id': user, 'priority': 'low'})
    response = client.get('/todos')
    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_get_todos_filter_by_priority(client, user):
    client.post('/todos', json={'title': 'High', 'user_id': user, 'priority': 'high'})
    client.post('/todos', json={'title': 'Low', 'user_id': user, 'priority': 'low'})
    response = client.get('/todos?priority=high')
    assert response.status_code == 200
    todos = response.get_json()
    assert len(todos) == 1
    assert todos[0]['priority'] == 'high'


def test_update_todo(client, user):
    create = client.post('/todos', json={'title': 'Original', 'user_id': user})
    todo_id = create.get_json()['id']
    response = client.put(f'/todos/{todo_id}', json={'title': 'Updated', 'completed': True})
    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Updated'
    assert data['completed'] is True


def test_delete_todo(client, user):
    create = client.post('/todos', json={'title': 'To Delete', 'user_id': user})
    todo_id = create.get_json()['id']
    response = client.delete(f'/todos/{todo_id}')
    assert response.status_code == 204


def test_stats_empty(client):
    response = client.get('/todos/stats')
    assert response.status_code == 200
    data = response.get_json()
    assert data['total'] == 0
    assert data['completion_rate'] == 0


def test_stats_with_todos(client, user):
    client.post('/todos', json={'title': 'T1', 'user_id': user})
    t2 = client.post('/todos', json={'title': 'T2', 'user_id': user}).get_json()
    client.put(f'/todos/{t2["id"]}', json={'completed': True})
    response = client.get('/todos/stats')
    data = response.get_json()
    assert data['total'] == 2
    assert data['completed'] == 1
    assert data['completion_rate'] == 50.0

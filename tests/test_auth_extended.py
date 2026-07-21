"""Expanded coverage for /auth/register and /auth/login edge cases."""

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
def existing_user(app):
    with app.app_context():
        u = User(username='existinguser', email='existing@example.com')
        u.set_password('correcthorsebatterystaple')
        db.session.add(u)
        db.session.commit()
        return u.id


# ══════════════════════════════════════════════════════════════
# register — required-field validation
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('payload', [
    {},
    {'username': 'onlyusername'},
    {'password': 'onlypassword'},
    {'username': '', 'password': 'pw'},
    {'username': 'user', 'password': ''},
    {'username': '', 'password': ''},
    {'email': 'noname@example.com', 'password': 'pw'},
])
def test_register_rejects_missing_required_fields(client, payload):
    response = client.post('/auth/register', json=payload)
    assert response.status_code == 400
    assert response.get_json()['error'] == 'Username and password are required'


@pytest.mark.parametrize('username,password', [
    ('a', 'p'),
    ('normaluser', 'normalpass'),
    ('user_with_underscore', 'pass123'),
    ('user.with.dots', 'pass123'),
    ('UPPERCASE', 'pass123'),
    ('a' * 80, 'pass123'),
    ('ünïcödé_user', 'pass123'),
    ('123numericstart', 'pass123'),
])
def test_register_accepts_valid_username_formats(client, username, password):
    response = client.post('/auth/register', json={'username': username, 'password': password})
    assert response.status_code == 201
    assert response.get_json()['username'] == username


# ══════════════════════════════════════════════════════════════
# register — duplicate username / email
# ══════════════════════════════════════════════════════════════

def test_register_duplicate_username_returns_409(client, existing_user):
    response = client.post('/auth/register', json={'username': 'existinguser', 'password': 'anything'})
    assert response.status_code == 409
    assert response.get_json()['error'] == 'Username already exists'


def test_register_duplicate_email_returns_409(client, existing_user):
    response = client.post('/auth/register', json={
        'username': 'differentusername', 'password': 'anything', 'email': 'existing@example.com',
    })
    assert response.status_code == 409
    assert response.get_json()['error'] == 'Email already exists'


@pytest.mark.parametrize('n_existing_users', [1, 3, 5, 10])
def test_register_duplicate_check_scales_with_user_count(client, app, n_existing_users):
    with app.app_context():
        for i in range(n_existing_users):
            u = User(username=f'user{i}', email=f'user{i}@example.com')
            u.set_password('pass')
            db.session.add(u)
        db.session.commit()

    response = client.post('/auth/register', json={'username': 'user0', 'password': 'pass'})
    assert response.status_code == 409


# ══════════════════════════════════════════════════════════════
# register — default email generation
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('username', ['alice', 'bob', 'charlie123', 'dave_smith'])
def test_register_without_email_generates_default(client, username):
    response = client.post('/auth/register', json={'username': username, 'password': 'pass123'})
    assert response.status_code == 201
    assert response.get_json()['email'] == f'{username}@example.com'


@pytest.mark.parametrize('email', [
    'custom@domain.com', 'test.user+tag@example.co.uk', 'a@b.io',
])
def test_register_with_explicit_email_is_preserved(client, email):
    response = client.post('/auth/register', json={
        'username': f'user_{hash(email) % 10000}', 'password': 'pass123', 'email': email,
    })
    assert response.status_code == 201
    assert response.get_json()['email'] == email


# ══════════════════════════════════════════════════════════════
# register — password variety (no strength validation in route)
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('password', [
    '1', 'a', 'password', 'P@ssw0rd!', 'a' * 100, '12345678',
    'with spaces in it', 'ünïcödé_pässwörd', '!@#$%^&*()',
])
def test_register_accepts_any_nonempty_password(client, password):
    response = client.post('/auth/register', json={'username': f'pwuser_{hash(password) % 100000}', 'password': password})
    assert response.status_code == 201


@pytest.mark.parametrize('password', [
    '1', 'password', 'P@ssw0rd!', 'ünïcödé_pässwörd',
])
def test_registered_password_is_hashed_not_stored_plaintext(client, app, password):
    client.post('/auth/register', json={'username': f'hashcheck_{hash(password) % 100000}', 'password': password})
    with app.app_context():
        u = User.query.filter_by(username=f'hashcheck_{hash(password) % 100000}').first()
        assert u.password_hash != password
        assert u.check_password(password) is True


# ══════════════════════════════════════════════════════════════
# login — required-field validation
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('payload', [
    {}, {'username': 'onlyusername'}, {'password': 'onlypassword'},
    {'username': '', 'password': 'pw'}, {'username': 'user', 'password': ''},
])
def test_login_rejects_missing_required_fields(client, payload):
    response = client.post('/auth/login', json=payload)
    assert response.status_code == 400
    assert response.get_json()['error'] == 'Username and password are required'


def test_login_success_returns_user_payload(client, existing_user):
    response = client.post('/auth/login', json={
        'username': 'existinguser', 'password': 'correcthorsebatterystaple',
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['message'] == 'Login successful'
    assert data['user']['username'] == 'existinguser'


@pytest.mark.parametrize('wrong_password', [
    'wrong', 'Correcthorsebatterystaple', 'correcthorsebatterystapl', 'password123',
])
def test_login_wrong_password_returns_401(client, existing_user, wrong_password):
    response = client.post('/auth/login', json={'username': 'existinguser', 'password': wrong_password})
    assert response.status_code == 401
    assert response.get_json()['error'] == 'Invalid username or password'


@pytest.mark.parametrize('nonexistent_username', [
    'ghost', 'nosuchuser', 'deleteduser', 'typo_username', 'ExistingUser',
])
def test_login_nonexistent_username_returns_401(client, existing_user, nonexistent_username):
    """Username lookup is case-sensitive -- 'ExistingUser' != 'existinguser'."""
    response = client.post('/auth/login', json={'username': nonexistent_username, 'password': 'correcthorsebatterystaple'})
    assert response.status_code == 401


@pytest.mark.parametrize('n_users,target_index', [
    (2, 0), (2, 1), (5, 2), (10, 9), (10, 0),
])
def test_login_finds_correct_user_among_many(client, app, n_users, target_index):
    with app.app_context():
        for i in range(n_users):
            u = User(username=f'multiuser{i}', email=f'multiuser{i}@example.com')
            u.set_password(f'pass{i}')
            db.session.add(u)
        db.session.commit()

    response = client.post('/auth/login', json={
        'username': f'multiuser{target_index}', 'password': f'pass{target_index}',
    })
    assert response.status_code == 200
    assert response.get_json()['user']['username'] == f'multiuser{target_index}'


# ══════════════════════════════════════════════════════════════
# register -> login round trip
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('username,password,email', [
    ('roundtrip1', 'pass1', 'rt1@example.com'),
    ('roundtrip2', 'pass2', None),
    ('roundtrip3', 'complex!P@ss', 'rt3@example.com'),
    ('roundtrip4', 'ünïcödé', None),
    ('roundtrip5', 'a' * 50, 'rt5@example.com'),
])
def test_register_then_login_round_trip(client, username, password, email):
    reg_payload = {'username': username, 'password': password}
    if email:
        reg_payload['email'] = email
    reg = client.post('/auth/register', json=reg_payload)
    assert reg.status_code == 201

    login = client.post('/auth/login', json={'username': username, 'password': password})
    assert login.status_code == 200
    assert login.get_json()['user']['username'] == username

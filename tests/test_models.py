"""Model-level unit tests for User and Todo -- password hashing, to_dict serialization."""

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


# ══════════════════════════════════════════════════════════════
# User — password hashing
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('password', [
    'simple', 'P@ssw0rd!', 'a' * 200, 'ünïcödé_pässwörd', '12345678',
    'with spaces', '!@#$%^&*()_+-=', '', 'ThisIsAVeryLongPasswordThatShouldStillWork1234567890',
])
def test_user_password_hash_never_equals_plaintext(app, password):
    with app.app_context():
        u = User(username='hashtest', email='hashtest@example.com')
        u.set_password(password)
        assert u.password_hash != password
        assert len(u.password_hash) > 0


@pytest.mark.parametrize('password', [
    'simple', 'P@ssw0rd!', 'ünïcödé_pässwörd', '12345678', 'with spaces',
])
def test_user_check_password_correct(app, password):
    with app.app_context():
        u = User(username='checktest', email='checktest@example.com')
        u.set_password(password)
        assert u.check_password(password) is True


@pytest.mark.parametrize('correct,wrong', [
    ('password1', 'password2'),
    ('CaseSensitive', 'casesensitive'),
    ('trailing ', 'trailing'),
    ('12345', '54321'),
    ('correct', ''),
])
def test_user_check_password_incorrect(app, correct, wrong):
    with app.app_context():
        u = User(username='wrongtest', email='wrongtest@example.com')
        u.set_password(correct)
        assert u.check_password(wrong) is False


@pytest.mark.parametrize('password', ['samepassword', 'another'])
def test_user_same_password_produces_different_hashes(app, password):
    """werkzeug's generate_password_hash salts each call -- two users with
    the same password should not have identical hashes."""
    with app.app_context():
        u1 = User(username='salttest1', email='salttest1@example.com')
        u2 = User(username='salttest2', email='salttest2@example.com')
        u1.set_password(password)
        u2.set_password(password)
        assert u1.password_hash != u2.password_hash
        assert u1.check_password(password) is True
        assert u2.check_password(password) is True


# ══════════════════════════════════════════════════════════════
# User — to_dict serialization
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('username,email', [
    ('alice', 'alice@example.com'),
    ('bob_smith', 'bob@work.io'),
    ('ünïcödé_name', 'unicode@example.com'),
    ('a', 'a@b.co'),
])
def test_user_to_dict_fields(app, username, email):
    with app.app_context():
        u = User(username=username, email=email)
        u.set_password('irrelevant')
        db.session.add(u)
        db.session.commit()
        data = u.to_dict()
        assert data['username'] == username
        assert data['email'] == email
        assert 'password_hash' not in data
        assert 'created_at' in data
        assert isinstance(data['id'], int)


def test_user_to_dict_excludes_password_hash(app):
    with app.app_context():
        u = User(username='secure', email='secure@example.com')
        u.set_password('supersecret')
        db.session.add(u)
        db.session.commit()
        data = u.to_dict()
        assert 'password_hash' not in data
        assert 'password' not in data


# ══════════════════════════════════════════════════════════════
# Todo — to_dict serialization
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('title,description,priority,category', [
    ('T1', 'D1', 'high', 'work'),
    ('T2', None, 'medium', None),
    ('T3', '', 'low', ''),
    ('Ünïcödé', 'Déscríptïön', 'high', 'personal'),
    ('T5', 'A' * 500, 'medium', 'shopping'),
])
def test_todo_to_dict_fields(app, title, description, priority, category):
    with app.app_context():
        u = User(username='tododict', email='tododict@example.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

        t = Todo(user_id=u.id, title=title, description=description, priority=priority, category=category)
        db.session.add(t)
        db.session.commit()

        data = t.to_dict()
        assert data['title'] == title
        assert data['description'] == description
        assert data['priority'] == priority
        assert data['category'] == category
        assert data['completed'] is False
        assert data['due_date'] is None
        assert 'created_at' in data
        assert 'updated_at' in data


@pytest.mark.parametrize('days_offset', [1, -1, 30, -30, 365, -365, 0])
def test_todo_to_dict_due_date_serialization(app, days_offset):
    with app.app_context():
        u = User(username='duedate', email='duedate@example.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

        due = datetime.utcnow() + timedelta(days=days_offset)
        t = Todo(user_id=u.id, title='Due date test', due_date=due)
        db.session.add(t)
        db.session.commit()

        data = t.to_dict()
        assert data['due_date'] == due.isoformat()


def test_todo_to_dict_without_due_date_is_none(app):
    with app.app_context():
        u = User(username='nodue', email='nodue@example.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

        t = Todo(user_id=u.id, title='No due date')
        db.session.add(t)
        db.session.commit()

        assert t.to_dict()['due_date'] is None


# ══════════════════════════════════════════════════════════════
# User <-> Todo relationship / cascade delete
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize('n_todos', [1, 3, 5, 10])
def test_deleting_user_cascades_to_todos(app, n_todos):
    with app.app_context():
        u = User(username='cascadetest', email='cascade@example.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()
        user_id = u.id

        for i in range(n_todos):
            db.session.add(Todo(user_id=user_id, title=f'Todo {i}'))
        db.session.commit()

        assert Todo.query.filter_by(user_id=user_id).count() == n_todos

        db.session.delete(u)
        db.session.commit()

        assert Todo.query.filter_by(user_id=user_id).count() == 0


def test_user_todos_relationship_backref(app):
    with app.app_context():
        u = User(username='backreftest', email='backref@example.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()

        t = Todo(user_id=u.id, title='Backref todo')
        db.session.add(t)
        db.session.commit()

        assert t.user.username == 'backreftest'
        assert len(u.todos) == 1
        assert u.todos[0].title == 'Backref todo'

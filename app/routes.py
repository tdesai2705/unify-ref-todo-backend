from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Todo
from app.feature_flags import FeatureFlags
from datetime import datetime, timezone

bp = Blueprint('api', __name__)


def _todo_dict(todo):
    """Serialize a Todo, adding due-date warning fields when flag is on."""
    data = todo.to_dict()
    if FeatureFlags.due_date_warnings() and todo.due_date:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        delta = (todo.due_date - now).days
        data['overdue'] = delta < 0
        data['days_until_due'] = delta
    return data


# ── Health ────────────────────────────────────────────────────

@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'todo-backend'}), 200


# ── Todos ─────────────────────────────────────────────────────

@bp.route('/todos', methods=['GET'])
def get_todos():
    user_id = request.args.get('user_id', type=int)
    completed = request.args.get('completed', type=str)
    priority = request.args.get('priority', type=str)
    category = request.args.get('category', type=str)

    query = Todo.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if completed is not None:
        query = query.filter_by(completed=completed.lower() == 'true')
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)

    todos = query.order_by(Todo.created_at.desc()).all()
    return jsonify([_todo_dict(t) for t in todos]), 200


@bp.route('/todos/<int:todo_id>', methods=['GET'])
def get_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    return jsonify(_todo_dict(todo)), 200


@bp.route('/todos', methods=['POST'])
def create_todo():
    data = request.get_json()

    if not data or not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
    if not data.get('user_id'):
        return jsonify({'error': 'User ID is required'}), 400

    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    todo = Todo(
        user_id=data['user_id'],
        title=data['title'],
        description=data.get('description'),
        priority=data.get('priority', 'medium'),
        category=data.get('category'),
        due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None
    )
    db.session.add(todo)
    db.session.commit()
    return jsonify(_todo_dict(todo)), 201


@bp.route('/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    data = request.get_json()

    if 'title' in data:
        todo.title = data['title']
    if 'description' in data:
        todo.description = data['description']
    if 'completed' in data:
        todo.completed = data['completed']
    if 'priority' in data:
        todo.priority = data['priority']
    if 'category' in data:
        todo.category = data['category']
    if 'due_date' in data:
        todo.due_date = datetime.fromisoformat(data['due_date']) if data['due_date'] else None

    db.session.commit()
    return jsonify(_todo_dict(todo)), 200


@bp.route('/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    db.session.delete(todo)
    db.session.commit()
    return '', 204


# ── Bulk operations (FEATURE_BULK_OPERATIONS) ─────────────────

@bp.route('/todos/bulk-complete', methods=['POST'])
def bulk_complete():
    """Mark multiple todos as completed in one request.

    Gated by FEATURE_BULK_OPERATIONS flag.
    Body: {"todo_ids": [1, 2, 3]}
    """
    if not FeatureFlags.bulk_operations():
        return jsonify({'error': 'Feature not enabled'}), 404

    data = request.get_json()
    if not data or not isinstance(data.get('todo_ids'), list):
        return jsonify({'error': 'todo_ids list is required'}), 400

    todo_ids = data['todo_ids']
    if not todo_ids:
        return jsonify({'error': 'todo_ids must not be empty'}), 400

    updated = []
    for tid in todo_ids:
        todo = Todo.query.get(tid)
        if todo:
            todo.completed = True
            updated.append(tid)

    db.session.commit()
    return jsonify({'completed': updated, 'count': len(updated)}), 200


# ── Stats ─────────────────────────────────────────────────────

@bp.route('/todos/stats', methods=['GET'])
def get_stats():
    user_id = request.args.get('user_id', type=int)

    query = Todo.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    total = query.count()
    completed = query.filter_by(completed=True).count()

    response = {
        'total': total,
        'completed': completed,
        'pending': total - completed,
        'completion_rate': round((completed / total * 100) if total > 0 else 0, 2),
        'by_priority': {
            'high': query.filter_by(priority='high').count(),
            'medium': query.filter_by(priority='medium').count(),
            'low': query.filter_by(priority='low').count(),
        }
    }

    if FeatureFlags.enhanced_stats():
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        overdue = query.filter(
            Todo.completed == False,
            Todo.due_date != None,
            Todo.due_date < now
        ).count()

        categories = db.session.query(
            Todo.category, db.func.count(Todo.id)
        ).filter(Todo.category != None)
        if user_id:
            categories = categories.filter(Todo.user_id == user_id)
        categories = categories.group_by(Todo.category).all()

        response['overdue_count'] = overdue
        response['by_category'] = {cat: count for cat, count in categories}

    return jsonify(response), 200


# ── Auth ──────────────────────────────────────────────────────

@bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    if data.get('email') and User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409

    user = User(
        username=data['username'],
        email=data.get('email', f"{data['username']}@example.com")
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400

    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401

    return jsonify({'message': 'Login successful', 'user': user.to_dict()}), 200

from flask import Blueprint, request, jsonify
from app import db
from app.models import User, Todo
from datetime import datetime

bp = Blueprint('api', __name__)

# Health Check Endpoint

@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Kubernetes probes"""
    return jsonify({'status': 'healthy', 'service': 'todo-backend'}), 200

# Todo CRUD Endpoints

@bp.route('/todos', methods=['GET'])
def get_todos():
    """Get all todos with optional filters"""
    user_id = request.args.get('user_id', type=int)
    completed = request.args.get('completed', type=str)
    priority = request.args.get('priority', type=str)
    category = request.args.get('category', type=str)

    query = Todo.query

    if user_id:
        query = query.filter_by(user_id=user_id)
    if completed is not None:
        is_completed = completed.lower() == 'true'
        query = query.filter_by(completed=is_completed)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)

    todos = query.order_by(Todo.created_at.desc()).all()
    return jsonify([todo.to_dict() for todo in todos]), 200

@bp.route('/todos/<int:todo_id>', methods=['GET'])
def get_todo(todo_id):
    """Get a single todo by ID"""
    todo = Todo.query.get_or_404(todo_id)
    return jsonify(todo.to_dict()), 200

@bp.route('/todos', methods=['POST'])
def create_todo():
    """Create a new todo"""
    data = request.get_json()

    if not data or not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400

    if not data.get('user_id'):
        return jsonify({'error': 'User ID is required'}), 400

    # Check if user exists
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

    return jsonify(todo.to_dict()), 201

@bp.route('/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """Update an existing todo"""
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
    return jsonify(todo.to_dict()), 200

@bp.route('/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """Delete a todo"""
    todo = Todo.query.get_or_404(todo_id)
    db.session.delete(todo)
    db.session.commit()
    return '', 204

@bp.route('/todos/stats', methods=['GET'])
def get_stats():
    """Get statistics about todos"""
    user_id = request.args.get('user_id', type=int)

    query = Todo.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    total = query.count()
    completed = query.filter_by(completed=True).count()
    high_priority = query.filter_by(priority='high').count()
    medium_priority = query.filter_by(priority='medium').count()
    low_priority = query.filter_by(priority='low').count()

    return jsonify({
        'total': total,
        'completed': completed,
        'pending': total - completed,
        'completion_rate': round((completed / total * 100) if total > 0 else 0, 2),
        'by_priority': {
            'high': high_priority,
            'medium': medium_priority,
            'low': low_priority
        }
    }), 200

# User Endpoints

@bp.route('/auth/register', methods=['POST'])
def register():
    """Register a new user"""
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
    """Authenticate a user"""
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400

    user = User.query.filter_by(username=data['username']).first()

    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict()
    }), 200

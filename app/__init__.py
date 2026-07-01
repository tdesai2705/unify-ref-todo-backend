from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate
import os

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name='default'):
    app = Flask(__name__)

    # Configuration
    database_url = os.getenv('DATABASE_URL', 'postgresql://todouser:todopass@postgres:5432/todos')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['CASK_API_KEY'] = os.getenv('CASK_API_KEY', '')

    # Initialize CloudBees Feature Management SDK
    from app.feature_flags import setup as setup_flags
    setup_flags(app.config['CASK_API_KEY'])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)

    # Register blueprints
    from app.routes import bp as api_bp
    app.register_blueprint(api_bp)

    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'todo-backend'}, 200

    # Seed default demo user so the app works out of the box
    with app.app_context():
        try:
            from app.models import User
            if not User.query.filter_by(id=1).first():
                demo = User(username='demo', email='demo@example.com')
                demo.set_password('demo')
                db.session.add(demo)
                db.session.commit()
        except Exception:
            db.session.rollback()

    return app

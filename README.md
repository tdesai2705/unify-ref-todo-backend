# Backend REST API

Flask-based REST API for the 2-tier to-do application.

**CloudBees Unify CI/CD** - Automated build and deployment pipeline.

## Technology Stack

- **Framework**: Python Flask 3.0
- **ORM**: SQLAlchemy
- **Database**: PostgreSQL 15
- **Authentication**: Werkzeug password hashing
- **CORS**: Flask-CORS

## API Endpoints

### Todo Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/todos` | Get all todos (with filters) |
| GET | `/api/todos/:id` | Get single todo |
| POST | `/api/todos` | Create new todo |
| PUT | `/api/todos/:id` | Update todo |
| DELETE | `/api/todos/:id` | Delete todo |
| GET | `/api/todos/stats` | Get statistics |

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Authenticate user |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python run.py
```

Server runs on `http://localhost:5000`

## Project Structure

```
backend/
├── app/
│   ├── __init__.py       # Flask app factory
│   ├── models.py         # SQLAlchemy models
│   └── routes.py         # API endpoints
├── requirements.txt      # Python dependencies
├── run.py               # Application entry point
└── Dockerfile           # Multi-stage Docker build
```

Part of CloudBees Unify Reference Architecture project.
# develop branch

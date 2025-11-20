# Development Environment Setup Guide

This guide will help you set up your local development environment for the Second Brain Database project.

## Prerequisites

### Required Software

- **Node.js** v20.x or higher ([Download](https://nodejs.org/))
- **Python** 3.11 or higher ([Download](https://www.python.org/))
- **MongoDB** 6.0 or higher ([Download](https://www.mongodb.com/try/download/community))
- **Redis** 7.0 or higher ([Download](https://redis.io/download))
- **Git** ([Download](https://git-scm.com/))

### Optional Tools

- **uv** - Fast Python package manager ([Install](https://docs.astral.sh/uv/))
- **Docker** - For containerized development ([Download](https://www.docker.com/))

## Clone the Repository

```bash
git clone https://github.com/yourusername/second_brain_database.git
cd second_brain_database
```

## Backend Setup

### 1. Install Python Dependencies

Using **uv** (recommended):

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --extra dev
```

Using **pip**:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.development.example .env
```

Edit `.env` and configure:

```env
# Database
MONGODB_URL=mongodb://localhost:27017/second_brain_db
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600

# API
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=true

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:3001"]
```

### 3. Start Backend Services

#### Start MongoDB

```bash
# Using Docker
docker run -d -p 27017:27017 --name mongodb mongo:7

# Or using local installation
mongod --dbpath /path/to/data/db
```

#### Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 --name redis redis:7

# Or using local installation
redis-server
```

#### Start FastAPI Application

```bash
# Using uv
uv run uvicorn src.second_brain_database.main:app --reload

# Or using python
python -m uvicorn src.second_brain_database.main:app --reload
```

Backend will be available at: `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Frontend Setup

### Digital Shop

```bash
cd submodules/sbd-nextjs-digital-shop
npm install
npm run dev
```

Available at: `http://localhost:3000`

### University Clubs Platform

```bash
cd submodules/sbd-nextjs-university-clubs-platform
npm install
npm run dev
```

Available at: `http://localhost:3001`

### Blog Platform

```bash
cd submodules/sbd-nextjs-blog-platform
npm install
npm run dev
```

Available at: `http://localhost:3002`

### Family Hub

```bash
cd submodules/sbd-nextjs-family-hub
npm install
npm run dev
```

Available at: `http://localhost:3003`

## Running Tests

### Backend Tests

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test file
uv run pytest tests/test_auth.py -v
```

### Frontend Tests

```bash
cd submodules/sbd-nextjs-digital-shop

# Unit tests
npm test

# E2E tests
npm run test:e2e

# Storybook
npm run storybook
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write code following project conventions
- Add tests for new features
- Update documentation as needed

### 3. Run Linters

Backend:

```bash
make lint        # Check for issues
make format      # Auto-format code
make check       # Type checking
```

Frontend:

```bash
npm run lint     # ESLint
npm run build    # Verify build works
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

**Commit Message Format**:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `style:` - Code style changes
- `chore:` - Build/tooling changes

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a PR on GitHub.

## Common Issues

### Port Already in Use

**Problem**: Port 8000 or 3000 already in use

**Solution**:
```bash
# Find and kill process using port 8000
lsof -ti:8000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :8000   # Windows

# Or change port in .env or package.json
```

### MongoDB Connection Error

**Problem**: Cannot connect to MongoDB

**Solution**:
1. Verify MongoDB is running: `mongosh`
2. Check connection string in `.env`
3. Ensure port 27017 is not blocked

### Redis Connection Error

**Problem**: Cannot connect to Redis

**Solution**:
1. Verify Redis is running: `redis-cli ping`
2. Check connection string in `.env`
3. Ensure port 6379 is not blocked

### Module Not Found

**Problem**: Python module import errors

**Solution**:
```bash
# Reinstall dependencies
uv sync --extra dev

# Or with pip
pip install -r requirements.txt --force-reinstall
```

### npm Install Fails

**Problem**: Frontend dependency installation fails

**Solution**:
```bash
# Clear npm cache
npm cache clean --force

# Remove node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

## IDE Setup

### VS Code

Recommended extensions:

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss"
  ]
}
```

Settings:

```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  }
}
```

## Database Seeding

Seed the database with sample data:

```bash
# Backend seed data
uv run python scripts/seed_database.py

# Or manually
mongosh second_brain_db < scripts/seed_data.js
```

## Hot Reload

Both backend and frontend support hot reload:

- **Backend**: Uvicorn watches for file changes
- **Frontend**: Next.js development server auto-refreshes

## Browser DevTools

Recommended Chrome extensions:
- React Developer Tools
- Redux DevTools (if using Redux)
- Axe DevTools (for accessibility testing)

## Next Steps

- Read the [Architecture Documentation](/docs/ARCHITECTURE.md)
- Review [API Documentation](/docs/api/)
- Check [Contributing Guidelines](/CONTRIBUTING.md)
- Set up [Pre-commit Hooks](/docs/LINTING.md)

## Getting Help

- **Documentation**: `/docs` folder
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: dev@secondbraindatabase.com

---

**Last Updated**: November 2024  
**Maintained by**: Development Team

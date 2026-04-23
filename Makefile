.PHONY: help install install-dev test test-cov lint lint-fix format type-check security check quality pre-commit commit-check clean docs docker-build docker-run docker-stop

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

#=============================================================================#
#                                Installation                                 #
#=============================================================================#

install: ## Install dependencies
	uv sync

install-dev: ## Install with dev dependencies
	uv sync --all-extras

uv-sync: ## Sync dependencies lock file
	uv sync

#=============================================================================#
#                          Dependency Management                              #
#=============================================================================#

uv-lock: ## Generate/update UV lock file
	uv lock

uv-add: ## Add new dependency
	uv add $(package)

uv-add-dev: ## Add new development dependency
	uv add --dev $(package)

uv-remove: ## Remove dependency
	uv remove $(package)

uv-upgrade: ## Upgrade all dependencies
	uv lock --upgrade

uv-tree: ## Show dependency tree
	uv tree

#=============================================================================#
#                               Development                                   #
#=============================================================================#

run: ## Start the application
	@echo "🚀 Starting server on port $$(uv run python -c "from settings import cfg; print(cfg.app.port)")..."
	@echo "💡 Use Ctrl+C to stop the server properly"
	@echo "💡 Or use 'make kill-server' to stop from another terminal"
	@echo "🧹 Checking for orphaned processes..."
	@make kill-server >/dev/null 2>&1 || true
	uv run python manage.py start-web

#=============================================================================#
#                                Testing                                      #
#=============================================================================#

test: ## Run all tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=. --cov-report=html --cov-report=term-missing

test-unit: ## Run unit tests only
	uv run pytest -m unit

test-integration: ## Run integration tests only
	uv run pytest -m integration

test-fast: ## Run tests excluding slow ones
	uv run pytest -m "not slow"

test-parallel: ## Run tests in parallel
	uv run pytest -n auto

test-watch: ## Run tests in watch mode
	uv run pytest-watch

#=============================================================================#
#                             Code Quality                                    #
#=============================================================================#

# Same scope as pre-commit: web, models, services, settings, manage.py
SRC_DIRS = web models services settings
SRC_FILES = $(SRC_DIRS) manage.py

lint: ## Run linter (ruff check)
	uv run ruff check $(SRC_FILES)

lint-fix: ## Fix linting issues (ruff check --fix)
	@echo "🔧 Fixing linting issues..."
	uv run ruff check $(SRC_FILES) --fix

format: ## Format code (ruff format)
	uv run ruff format $(SRC_FILES)

type-check: ## Run type checking (mypy)
	uv run mypy $(SRC_DIRS)

security: ## Run security checks (bandit)
	uv run bandit -r $(SRC_DIRS) -ll -q

check: lint format type-check security ## Run all checks (lint + format + mypy + bandit)
	@echo "✅ All checks passed!"

quality: check ## Alias for check
	@echo "✅ Quality checks passed!"

pre-commit: ## Run pre-commit on all files (if pre-commit works on your system)
	uv run pre-commit run --all-files --show-diff-on-failure --color always

#=============================================================================#
#                                Database                                     #
#=============================================================================#

confirm-danger: ## Confirm dangerous operation
	@if [ "$(FORCE)" != "true" ]; then \
		echo "⚠️  DANGER ZONE!  ⚠️"; \
		echo "Database URL: "; \
		uv run python -c "from settings import cfg; print(cfg.pg.connection.dsn)"; \
		read -p "❓ Are you sure you want to proceed? Type 'yes' to continue: " confirm; \
		if [ "$$confirm" != "yes" ]; then \
			echo "❌ Cancelled."; \
			exit 1; \
		fi; \
	fi

db-migrate: ## Create new migration
	uv run alembic revision --autogenerate -m "$(message)"

db-upgrade: confirm-danger ## Apply migrations
	uv run alembic upgrade head

db-downgrade: confirm-danger ## Rollback last migration
	uv run alembic downgrade -1

db-history: ## Show migration history
	uv run alembic history

db-reset: confirm-danger ## Reset database (DANGER!)
	uv run alembic downgrade base
	uv run alembic upgrade head

data-migration: confirm-danger ## Apply data migration
	uv run python manage.py apply-sql data.sql


#=============================================================================#
#                                 Docker                                      #
#=============================================================================#

docker-build: ## Build Docker image (use TARGET=development or TARGET=production)
	docker build --target $(or $(TARGET),production) -t stronica_backend:latest .

docker-run: ## Run with Docker Compose
	docker-compose up -d --force-recreate

docker-stop: ## Stop Docker services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

docker-rebuild: ## Rebuild and run Docker services
	docker-compose up --build -d --force-recreate

docker-infra: ## Start only infrastructure (postgres, minio)
	docker-compose up -d postgres minio minio_init


#=============================================================================#
#                               Utilities                                     #
#=============================================================================#

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build

kill-server: ## Kill Python server process on configured port
	@echo "🔍 Finding server process on port $$(uv run python -c "from settings import cfg; print(cfg.app.port)")..."
	@if command -v lsof >/dev/null 2>&1; then \
		PORT=$$(uv run python -c "from settings import cfg; print(cfg.app.port)"); \
		PID=$$(lsof -ti:$$PORT 2>/dev/null); \
		if [ -n "$$PID" ]; then \
			echo "🔄 Killing process $$PID on port $$PORT..."; \
			kill -9 $$PID; \
			echo "✅ Server process killed!"; \
		else \
			echo "ℹ️  No server process found on port $$PORT"; \
		fi; \
	else \
		echo "❌ lsof not found. Please install it or use: pkill -f python"; \
	fi

kill-server-force: ## Force kill all Python server processes (use with caution)
	@echo "⚠️  Force killing all Python server processes..."
	@if command -v pkill >/dev/null 2>&1; then \
		pkill -f "python.*manage.py" || true; \
		pkill -f "uvicorn" || true; \
		pkill -f "python.*start-web" || true; \
		echo "✅ All Python server processes killed!"; \
	else \
		echo "❌ pkill not found. Please install it or manually kill processes."; \
	fi

server-status: ## Show status of server processes
	@echo "🔍 Checking server processes..."
	@PORT=$$(uv run python -c "from settings import cfg; print(cfg.app.port)"); \
	echo "Configured port: $$PORT"; \
	echo ""; \
	if command -v lsof >/dev/null 2>&1; then \
		echo "📊 Processes on port $$PORT:"; \
		lsof -i:$$PORT 2>/dev/null || echo "  No processes found"; \
		echo ""; \
		echo "💾 Resource usage:"; \
		PID=$$(lsof -ti:$$PORT 2>/dev/null); \
		if [ -n "$$PID" ]; then \
			echo "  Process ID: $$PID"; \
			if command -v ps >/dev/null 2>&1; then \
				echo "  CPU/Memory usage:"; \
				ps -p $$PID -o pid,ppid,%cpu,%mem,vsz,rss,command --no-headers 2>/dev/null || echo "    Unable to get resource info"; \
			fi; \
			if command -v top >/dev/null 2>&1; then \
				echo "  Top process info:"; \
				top -pid $$PID -l 1 -stats pid,cpu,mem,time,command 2>/dev/null | tail -n 1 || echo "    Unable to get top info"; \
			fi; \
		else \
			echo "  No active process on port $$PORT"; \
		fi; \
		echo ""; \
		echo "🔍 All Python server processes:"; \
		ps aux | grep -E "(python.*manage.py|uvicorn|python.*start-web)" | grep -v grep || echo "  No Python server processes found"; \
	else \
		echo "❌ lsof not found. Using ps..."; \
		ps aux | grep -E "(python.*manage.py|uvicorn)" | grep -v grep || echo "  No Python server processes found"; \
	fi


#=============================================================================#
#                               Git Hooks                                     #
#=============================================================================#

install-hooks: ## Install pre-commit hooks
	pre-commit install

update-hooks: ## Update pre-commit hooks
	pre-commit autoupdate

#=============================================================================#
#                        Development Workflow                                 #
#=============================================================================#

init: ## Install dependencies and start infrastructure
	@echo "🚀 Initializing project..."
	@echo "1. Installing dependencies..."
	make install-dev
	@echo "2. Creating .env file..."
	make env-example
	@echo "3. Installing Git hooks..."
	make install-hooks
	@echo "4. Starting infrastructure services..."
	make docker-infra
	@echo "5. Waiting for database to be ready..."
	@sleep 5
	@echo "6. Applying database migrations..."
	make db-upgrade FORCE=true
	@echo "7. Applying data migrations..."
	make data-migration FORCE=true
	@echo "✅ Project initialized successfully!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Start the application: make run"
	@echo "2. Run tests: make test"

check-all: test-cov lint type-check security ## Run all checks
	@echo "All checks passed! ✅"

commit-check: check ## Run all checks + tests (use before commit)
	uv run pytest
	@echo "Ready to commit! ✅"

pre-commit-changed: ## Run pre-commit on staged files only (if pre-commit works)
	uv run pre-commit run
	$(MAKE) check
	uv run pytest
	@echo "Ready to commit! ✅"

#=============================================================================#
#                              Environment                                    #
#=============================================================================#

env-example: ## Create example environment file
	@echo "Creating .env file with default settings..."
	@echo "# =====================" > .env
	@echo "# Application Settings" >> .env
	@echo "# =====================" >> .env
	@echo "APP_HOST=0.0.0.0" >> .env
	@echo "APP_PORT=8000" >> .env
	@echo "DEBUG=true" >> .env
	@echo "ENV=development" >> .env
	@echo "" >> .env
	@echo "# =====================" >> .env
	@echo "# Database Configuration" >> .env
	@echo "# =====================" >> .env
	@echo "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fitness" >> .env
	@echo "DB_POOL_SIZE=10" >> .env
	@echo "DB_MAX_OVERFLOW=20" >> .env
	@echo "DB_POOL_TIMEOUT=30" >> .env
	@echo "" >> .env
	@echo "# =====================" >> .env
	@echo "# Security" >> .env
	@echo "# =====================" >> .env
	@echo "SECRET_KEY=your-super-secret-key-change-this-in-production" >> .env
	@echo "JWT_SECRET_KEY=your-jwt-secret-key-change-this-in-production" >> .env
	@echo "JWT_ALGORITHM=HS256" >> .env
	@echo "JWT_EXPIRATION_HOURS=24" >> .env
	@echo "" >> .env
	@echo "# =====================" >> .env
	@echo "# S3 Configuration (MinIO)" >> .env
	@echo "# =====================" >> .env
	@echo "S3_ENDPOINT_URL=http://localhost:9000" >> .env
	@echo "S3_ACCESS_KEY=minioadmin" >> .env
	@echo "S3_SECRET_KEY=minioadmin" >> .env
	@echo "S3_BUCKET=bucket" >> .env
	@echo "" >> .env
	@echo "# =====================" >> .env
	@echo "# Logging" >> .env
	@echo "# =====================" >> .env
	@echo "LOG_LEVEL=INFO" >> .env
	@echo "LOG_FORMAT=json" >> .env
	@echo "LOG_FILE=logs/app.log" >> .env
	@echo "" >> .env
	@echo "# =====================" >> .env
	@echo "# Feature Flags" >> .env
	@echo "# =====================" >> .env
	@echo "ENABLE_SWAGGER=true" >> .env
	@echo "ENABLE_REDOC=true" >> .env
	@echo "ENABLE_METRICS=true" >> .env
	@echo "ENABLE_HEALTH_CHECK=true" >> .env
	@echo "" >> .env
	@echo "# =====================" >> .env
	@echo "# Development Settings" >> .env
	@echo "# =====================" >> .env
	@echo "RELOAD=true" >> .env
	@echo "WORKERS=1" >> .env
	@echo "✅ .env file created with default settings!"
	@echo "Please review and customize the settings for your environment."


#=============================================================================#
#                             Project Reset                                   #
#=============================================================================#

reset: ## Reset project to clean state (stop infra + remove venv + clean all)
	@echo "🧹 Resetting project to clean state..."
	@echo "1. Stopping infrastructure services..."
	docker-compose down -v
	@echo "2. Removing virtual environment..."
	rm -rf .venv
	@echo "3. Cleaning all temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf docs/_build
	rm -rf logs
	mkdir -p logs
	@echo "4. Removing .env file..."
	rm -f .env
	@echo "5. Cleaning Docker..."
	docker system prune -f
	docker image prune -f
	@echo "✅ Project reset completed!"
	@echo ""
	@echo "To start fresh, run: make init"

#=============================================================================#
#                  Comprehensive Quality Checks                               #
#=============================================================================#

quality-all: check ## Run all quality checks and tests
	@echo "🔍 Running all quality checks and tests..."
	uv run pytest

#=============================================================================#
#                     Comprehensive Testing                                   #
#=============================================================================#

test-all: ## Run ALL tests with quality checks (tests + coverage + quality)
	@echo "🧪 Running ALL tests with quality checks..."
	@echo "1. Code quality checks..."
	$(MAKE) quality-all
	@echo "2. Running all tests with coverage..."
	uv run pytest --cov=. --cov-report=html --cov-report=term-missing --cov-fail-under=80
	@echo "3. Running tests in parallel..."
	uv run pytest -n auto
	@echo "4. Running slow tests..."
	uv run pytest -m slow
	@echo "✅ All tests and quality checks completed!"

#=============================================================================#
#                          Release Management                                 #
#=============================================================================#

release: ## Create a new release (update version, tag, push)
	@echo "🚀 Creating new release..."
	@echo "Current version: $(shell grep '^version = ' pyproject.toml | cut -d'"' -f2)"
	@read -p "Enter new version (e.g., 1.0.1): " version; \
	echo "Updating version to $$version..."; \
	sed -i '' 's/^version = ".*"/version = "'$$version'"/' pyproject.toml; \
	git add pyproject.toml; \
	git commit -m "Bump version to $$version"; \
	git tag -a "v$$version" -m "Release $$version"; \
	git push origin main --tags; \
	echo "✅ Release $$version created and pushed!" 
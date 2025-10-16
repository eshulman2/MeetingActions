.PHONY: help install dev build test lint format security clean docker-build docker-up docker-down git-setup
.PHONY: start-mcp start-google-agents start-jira-agents start-workflows start-registry start-all stop-all

# Default target
help:
	@echo "MeetingActions Development Commands"
	@echo "=================================="
	@echo "Development:"
	@echo "  install          - Install dependencies and setup"
	@echo "  dev              - Set up development environment"
	@echo "  git-setup        - Setup Git hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             - Run all linting checks"
	@echo "  format           - Auto-format code"
	@echo "  security         - Run security checks"
	@echo "  test             - Run all tests"
	@echo "  test-cov         - Run tests with coverage"
	@echo ""
	@echo "Services:"
	@echo "  start-mcp        - Start MCP server"
	@echo "  start-jira-agent - Start Jira agent server"
	@echo "  start-google-agents - Start Google agent server"
	@echo "  start-workflows  - Start workflow server"
	@echo "  start-registry   - Start agent registry service"
	@echo "  start-all        - Start all servers"
	@echo "  stop-all         - Stop all running servers"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build     - Build Docker images"
	@echo "  docker-up        - Start services with Docker"
	@echo "  docker-down      - Stop Docker services"
	@echo ""
	@echo "Utilities:"
	@echo "  clean            - Clean up artifacts and containers"
	@echo "  health-check     - Check service health"
	@echo "  verify-setup     - Verify development setup"

# Start MCP server
start-mcp:
	@echo "Starting MCP server..."
	UVICORN_PORT=8100 python -m src.mcp.google_tools_mcp

# Start agent servers
start-google-agent:
	@echo "Starting Google agent..."
	UVICORN_PORT=8001 python -m src.core.agents.google_agent

start-jira-agent:
	@echo "Starting Jira agent..."
	UVICORN_PORT=8000 python -m src.core.agents.jira_agent

# Start workflow server
start-workflow:
	@echo "Starting workflow server..."
	UVICORN_PORT=8002 python -m src.core.workflow_servers.action_items_server

# Start registry service
start-registry:
	@echo "Starting agent registry service..."
	UVICORN_PORT=8003 python -m src.services.registry_service

# Start all servers
start-all:
	@echo "Starting all servers..."
	@echo "Starting agent registry service..."
	python -m src.services.registry_service &
	@echo "Starting MCP server..."
	python -m src.mcp.google_tools_mcp &
	@echo "Starting Jira agent..."
	UVICORN_PORT=8000 python -m src.core.agents.jira_agent &
	@echo "Starting Google agent..."
	UVICORN_PORT=8001 python -m src.core.agents.google_agent &
	@echo "Starting workflow server..."
	UVICORN_PORT=8002 python -m src.core.workflow_servers.action_items_server &
	@echo "All servers started!"

# Stop all servers
stop-all:
	@echo "Stopping all servers..."
	pkill -f "python -m src.services.registry_service" || true
	pkill -f "python -m src.core.agents.jira_agent" || true
	pkill -f "python -m src.core.agents.google_agent" || true
	pkill -f "python -m src.core.workflow_servers.action_items_server" || true
	pkill -f "python -m src.mcp.google_tools_mcp" || true
	@echo "All servers stopped!"

# Installation and Setup
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "Installing pre-commit hooks..."
	pre-commit install || echo "Pre-commit not available"
	@echo "Setup complete!"

dev:
	@echo "Setting up development environment..."
	python -m venv .venv
	@echo "Activate virtual environment with: source .venv/bin/activate"
	@echo "Then run: make install"

git-setup:
	@echo "Setting up Git configuration..."
	pre-commit install
	@echo "Git hooks installed!"

# Code Quality
lint:
	@echo "Running code quality checks..."
	black --check --diff src/
	isort --check-only --diff src/
	flake8 src/ --max-line-length=88 --extend-ignore=E203,W503
	mypy src/ --ignore-missing-imports || echo "mypy check completed"
	@echo "Linting checks complete!"

format:
	@echo "Formatting code..."
	black src/
	isort src/
	@echo "Code formatted!"

security:
	@echo "Running security checks..."
	bandit -r src/ -f json -o bandit-report.json || true
	@echo "Security checks complete!"

# Testing
test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short || echo "Tests completed"

test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=src/ --cov-report=html --cov-report=term-missing || echo "Coverage tests completed"

# Docker Operations
docker-build:
	@echo "Building Docker images..."
	docker-compose build || podman-compose build

docker-up:
	@echo "Starting services with Docker..."
	docker-compose up -d || podman-compose up -d
	@echo "Services started!"

docker-down:
	@echo "Stopping Docker services..."
	docker-compose down || podman-compose down

# Utilities
health-check:
	@echo "Checking service health..."
	@curl -f http://localhost:8000/health 2>/dev/null && echo "✅ Jira Agent: Healthy" || echo "❌ Jira Agent: Down"
	@curl -f http://localhost:8001/health 2>/dev/null && echo "✅ Google Agent: Healthy" || echo "❌ Google Agent: Down"
	@curl -f http://localhost:8002/health 2>/dev/null && echo "✅ Workflows: Healthy" || echo "❌ Workflows: Down"

verify-setup:
	@echo "Verifying development setup..."
	python --version
	pip --version
	git --version
	@echo "Testing imports..."
	python -c "import src; print('✅ Source imports work')" || echo "❌ Import issues found"

# Clean up Docker containers and volumes
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage coverage.xml bandit-report.json
	@echo "Cleaning up Docker containers and volumes..."
	podman compose down -v || docker-compose down -v
	podman system prune -f || docker system prune -f

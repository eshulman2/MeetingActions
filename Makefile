.PHONY: help start-mcp start-google-agents start-jira-agents start-workflows start-registry start-all stop-all clean

# Default target
help:
	@echo "Available commands:"
	@echo "  start-mcp        - Start MCP server"
	@echo "  start-jira-agents     - Start Jira agent servers"
	@echo "  start-google-agents     - Start Google agent servers"
	@echo "  start-workflows  - Start workflow server"
	@echo "  start-registry   - Start agent registry service"
	@echo "  start-all        - Start all servers"
	@echo "  stop-all         - Stop all running servers"
	@echo "  clean            - Clean up containers and volumes"

# Start MCP server
start-mcp:
	@echo "Starting MCP server..."
	python -m src.mcp.google_tools_mcp

# Start agent servers
start-google-agents:
	@echo "Starting Google agent..."
	UVICORN_PORT=8001 python -m src.core.agents.google_agent

start-jira-agent:
	@echo "Starting Jira agent..."
	UVICORN_PORT=8000 python -m src.core.agents.jira_agent

# Start workflow server
start-workflows:
	@echo "Starting workflow server..."
	UVICORN_PORT=8002 python -m src.core.workflow_servers.action_items_server

# Start registry service
start-registry:
	@echo "Starting agent registry service..."
	python -m src.services.registry_service

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

# Clean up Docker containers and volumes
clean:
	@echo "Cleaning up Docker containers and volumes..."
	podman compose down -v
	podman system prune -f

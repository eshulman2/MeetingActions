.PHONY: help start-mcp start-google-agents start-jira-agents start-workflows start-all stop-all clean

# Default target
help:
	@echo "Available commands:"
	@echo "  start-mcp        - Start MCP server"
	@echo "  start-jira-agents     - Start Jira agent servers"
	@echo "  start-google-agents     - Start Google agent servers"
	@echo "  start-workflows  - Start workflow server"
	@echo "  start-all        - Start all servers"
	@echo "  stop-all         - Stop all running servers"
	@echo "  clean            - Clean up containers and volumes"

# Start MCP server
start-mcp:
	@echo "Starting MCP server..."
	python -m src.mcp.google_tools_mcp

# Start agent servers
start-google-agents:
	@echo "Starting agent servers..."
	@echo "Starting Google agent on port 8001..."
	uvicorn src.core.agents.google_agent:app --port 8001 --reload --loop asyncio

start-jira-agent:
	@echo "Starting agent servers..."
	@echo "Starting Jira agent on port 8000..."
	uvicorn src.core.agents.jira_agent:app --port 8000 --reload --loop asyncio

# Start workflow server
start-workflows:
	@echo "Starting workflow server on port 8002..."
	uvicorn src.core.workflow_servers.action_items_server:app --port 8002 --reload --loop asyncio

# Start all servers
start-all:
	@echo "Starting all servers..."
	@echo "Starting MCP server..."
	python -m src.mcp.google_tools_mcp &
	@echo "Starting Jira agent on port 8000..."
	uvicorn src.core.agents.jira_agent:app --port 8000 --reload --loop asyncio &
	@echo "Starting Google agent on port 8001..."
	uvicorn src.core.agents.google_agent:app --port 8001 --reload --loop asyncio &
	@echo "Starting workflow server on port 8002..."
	uvicorn src.core.workflow_servers.action_items_server:app --port 8002 --reload --loop asyncio &
	@echo "All servers started!"

# Stop all servers
stop-all:
	@echo "Stopping all servers..."
	pkill -f "uvicorn src.core.agents.jira_agent" || true
	pkill -f "uvicorn src.core.agents.google_agent" || true
	pkill -f "uvicorn src.core.workflow_servers.action_items_server" || true
	pkill -f "python -m src.mcp.google_tools_mcp" || true
	@echo "All servers stopped!"

# Clean up Docker containers and volumes
clean:
	@echo "Cleaning up Docker containers and volumes..."
	podman compose down -v
	podman system prune -f

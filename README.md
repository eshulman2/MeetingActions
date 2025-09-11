# AI Agent Microservices Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.13+-orange.svg)](https://docs.llamaindex.ai/)
[![Redis](https://img.shields.io/badge/Redis-6.4+-red.svg)](https://redis.io/)
[![Langfuse](https://img.shields.io/badge/Langfuse-3.3+-purple.svg)](https://langfuse.com/)

A distributed AI agent platform built with microservices architecture for intelligent task automation, meeting analysis, and workflow orchestration. The system integrates with Google Workspace, Jira, and other enterprise tools to provide comprehensive AI-powered assistance.

## 🏗️ Architecture Overview

The platform follows a microservices architecture with specialized agents and services:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Jira Agent    │    │  Google Agent   │    │ Action Items    │
│    (Port 8000)  │    │   (Port 8001)   │    │ Workflow Server │
│                 │    │                 │    │   (Port 8002)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └─────────────────────────────────────────────────────
                                 │
         ┌─────────────────────────────────────────────────────┐
         │              Agent Registry Service                 │
         │                 (Port 8003)                        │
         └─────────────────────────────────────────────────────
                                 │
         ┌─────────────────────────────────────────────────────┐
         │                Redis Cache                          │
         │                (Port 6380)                         │
         └─────────────────────────────────────────────────────
```

## 🚀 Core Services

### 1. **Jira Agent** (`src/core/agents/jira_agent.py`)
- **Purpose**: Automates Jira operations and task management
- **Port**: 8000
- **Features**:
  - Issue creation, updating, and querying
  - Project management automation
  - Integration with Red Hat Jira instance
  - MCP (Model Context Protocol) tool integration

### 2. **Google Agent** (`src/core/agents/google_agent.py`)
- **Purpose**: Google Workspace integration and meeting analysis
- **Port**: 8001
- **Features**:
  - Meeting notes processing
  - Google Calendar integration
  - Document analysis and generation
  - Email automation capabilities

### 3. **Action Items Workflow Server** (`src/core/workflow_servers/action_items_server.py`)
- **Purpose**: Orchestrates complex multi-step workflows
- **Port**: 8002
- **Features**:
  - Meeting notes to action items conversion
  - Multi-agent task orchestration
  - Workflow state management
  - Integration with external agent systems

### 4. **Agent Registry Service** (`src/services/registry_service.py`)
- **Purpose**: Service discovery and health monitoring
- **Port**: 8003
- **Features**:
  - Agent registration and discovery
  - Health check monitoring
  - Load balancing support
  - Service metadata management

### 5. **Google MCP Server** (`src/mcp/google_tools_mcp.py`)
- **Purpose**: Model Context Protocol server for Google tools
- **Port**: 8100
- **Features**:
  - Google API tool exposure via MCP
  - Standardized tool interface
  - Authentication management

## 🛠️ Key Features

### AI-Powered Workflow Automation
- **ReActAgent Framework**: Uses LlamaIndex's ReActAgent for intelligent reasoning and action
- **Multi-LLM Support**: Compatible with OpenAI, Google Gemini, and OpenAI-like endpoints
- **Tool Integration**: Extensible tool system for external API integration

### Enterprise Integrations
- **Jira Integration**: Full CRUD operations on issues, projects, and workflows
- **Google Workspace**: Calendar, Drive, Gmail, and Meet integration
- **Redis Caching**: High-performance caching for documents and general data
- **MCP Protocol**: Standardized tool communication protocol

### Observability & Monitoring
- **Langfuse Integration**: Comprehensive LLM observability and tracing
- **Structured Logging**: Centralized logging with configurable levels
- **Health Monitoring**: Service health checks and status reporting
- **Performance Metrics**: Request/response tracking and performance analysis

### Infrastructure
- **Containerized Deployment**: Docker/Podman containers for all services
- **Service Mesh**: Inter-service communication and discovery
- **Configuration Management**: JSON-based configuration with environment overrides
- **Development Tools**: Makefile for easy service management

## 🚀 Quick Start

### Prerequisites

```bash
# Required
- Python 3.11+
- Docker & Docker Compose
- Redis (for caching)

# API Access
- Google API credentials (credentials.json)
- Jira API token
- Gemini API key
```

### 🐳 Docker Deployment (Recommended)

```bash
# 1. Clone repository
git clone <repository-url>
cd Agents

# 2. Set environment variables
export MODEL_API_KEY="your_gemini_api_key"
export LOG_LEVEL="INFO"

# 3. Launch all services
docker-compose up --build
```

**Service Endpoints:**
- **Jira Agent**: http://localhost:8000
- **Google Agent**: http://localhost:8001
- **Workflows**: http://localhost:8002
- **Google MCP**: http://localhost:8100
- **Redis Cache**: localhost:6380

### 💻 Local Development

```bash
# Start all services
make start-all

# Or individual services (in dependency order)
make start-registry      # Port 8003 (start first - service discovery)
make start-mcp          # Port 8100 (start second - tool protocol)
make start-jira-agent    # Port 8000
make start-google-agents # Port 8001
make start-workflows     # Port 8002
```

## 🏗️ Architecture

### Core Structure

```
src/
├── common/                  # Shared utilities and patterns
│   └── singleton_meta.py   # Singleton metaclass implementation
├── core/                   # Business logic and agents
│   ├── agents/            # Individual agent implementations
│   │   ├── jira_agent.py  # Jira integration agent
│   │   └── google_agent.py # Google Workspace agent
│   ├── base/              # Base classes and utilities
│   │   ├── base_server.py # Base server implementation
│   │   └── base_agent_server.py # Base agent server class
│   ├── workflows/         # Event-driven workflow definitions
│   │   └── action_items_workflow.py # Meeting notes workflow
│   ├── workflow_servers/  # Workflow execution servers
│   │   └── action_items_server.py # Action items server
│   └── agent_utils.py     # Agent utility functions
├── infrastructure/        # Platform infrastructure
│   ├── cache/            # Redis caching with singleton pattern
│   │   ├── redis_cache.py # Redis cache implementation
│   │   └── document_cache.py # Document-specific caching
│   ├── config/           # Configuration management
│   │   ├── read_config.py # Configuration reader
│   │   └── models.py     # Configuration models
│   ├── prompts/          # System prompts
│   │   └── prompts.py    # AI system prompts and contexts
│   ├── logging/          # Structured logging
│   │   └── logging_config.py # Logging configuration
│   ├── observability/    # Langfuse integration
│   │   └── observability.py # Monitoring and tracing
│   └── registry/         # Service registry
│       ├── agent_registry.py # Agent registration
│       └── registry_client.py # Registry client
├── integrations/         # External service integrations
│   ├── google_tools/     # Google Workspace APIs
│   │   ├── google_tools.py # Google API tools
│   │   └── auth_utils.py # Authentication utilities
│   ├── jira_tools/       # Jira API integration
│   │   ├── jira_tools.py # Jira API tools
│   │   └── jira_formatter.py # Jira data formatting
│   └── general_tools/    # Utility tools
│       └── date_tools.py # Date/time utilities
├── mcp/                  # Model Context Protocol servers
│   └── google_tools_mcp.py # Google tools MCP server
└── services/             # Standalone services
    └── registry_service.py # Agent registry service
```

### Design Patterns

- **Singleton Pattern**: Efficient resource management for caching and shared services
- **Factory Pattern**: Dynamic model and configuration creation
- **Observer Pattern**: Event-driven workflow orchestration
- **Repository Pattern**: Clean data access abstraction

## 🤖 Agent Capabilities

### Google Workspace Agent

**Core Features:**
- **Meeting Intelligence**: Extract structured action items from meeting notes
- **Calendar Management**: Schedule meetings, manage events, sync calendars
- **Document Processing**: Analyze Google Docs for actionable content
- **Smart Workflows**: Automated meeting-to-action-item pipelines

**API Examples:**
```bash
# Extract action items from meeting
curl -X POST "http://localhost:8001/agent" \
  -H "Content-Type: application/json" \
  -d '{"query": "Extract action items from my team meeting notes"}'

# Process meeting workflow
curl -X POST "http://localhost:8001/meeting-notes" \
  -H "Content-Type: application/json" \
  -d '{"meeting_notes": "Meeting discussion content..."}'
```

### Jira Integration Agent

**Core Features:**
- **Ticket Lifecycle Management**: Create, update, track, and close issues
- **Project Coordination**: Manage sprints, backlogs, and project workflows
- **Automated Integration**: Convert action items to Jira tickets
- **Team Collaboration**: Comment management and notification handling

**API Examples:**
```bash
# Create Jira ticket
curl -X POST "http://localhost:8000/agent" \
  -H "Content-Type: application/json" \
  -d '{"query": "Create ticket for authentication bug fix in user login"}'

# Query project status
curl -X POST "http://localhost:8000/agent" \
  -H "Content-Type: application/json" \
  -d '{"query": "List all open tickets for the mobile app project"}'
```

## 🔄 Event-Driven Workflows

### Action Items Workflow

**Comprehensive Pipeline:**
1. **Content Ingestion**: Retrieve meeting notes from external endpoints
2. **AI Processing**: Extract structured action items using LLM analysis
3. **Quality Assurance**: Multi-stage validation and review cycles
4. **JSON Validation**: Ensure proper data structure and format
5. **Agent Routing**: Intelligent dispatch to appropriate agents
6. **Execution Tracking**: Monitor progress and aggregate results

**Advanced Features:**
- **Retry Mechanisms**: Configurable retry logic with exponential backoff
- **Error Recovery**: Automatic correction and reprocessing
- **Observability**: Full tracing with Langfuse integration
- **State Management**: Persistent workflow context and memory

**Usage Example:**
```python
from src.core.workflows.action_items_workflow import ActionItemsWorkflow

# Initialize with custom parameters
workflow = ActionItemsWorkflow(
    timeout=60,
    verbose=True,
    max_iterations=5
)

# Execute workflow
result = await workflow.run(
    meeting="Weekly Team Sync",
    date="2024-09-08"
)
```

## ⚙️ Configuration

### Core Configuration (`config.json`)

```json
{
  "llm": "OpenAILike",
  "model": "gemini-2.0-flash",
  "verify_ssl": false,
  "additional_model_parameter": {
    "api_base": "https://your-gemini-endpoint.com/v1beta/openai",
    "is_chat_model": true
  },
  "tools_config": {
    "jira_tool": {
      "server": "https://your-jira-instance.com"
    }
  },
  "agent_config": {
    "max_iterations": 20,
    "verbose": true
  },
  "mcp_config": {
    "port": 8100,
    "servers": [
      "http://127.0.0.1:8100/mcp"
    ]
  },
  "cache_config": {
    "enable": true,
    "ttl_hours": 1,
    "max_size_mb": 100,
    "host": "localhost",
    "port": 6380,
    "password": "12345"
  },
  "observability": {
    "enable": true,
    "secret_key": "sk-lf-your-secret-key",
    "public_key": "pk-lf-your-public-key",
    "host": "http://localhost:3000"
  },
  "meeting_notes_endpoint": "http://127.0.0.1:8001/meeting-notes",
  "heartbeat_interval": 60,
  "registry_endpoint": "http://localhost:8003"
}
```

### Key Configuration Options

- **`verify_ssl`**: SSL certificate verification for API calls (boolean)
- **`mcp_config`**: Model Context Protocol server configuration
  - `port`: MCP server port (default: 8100)
  - `servers`: Array of MCP server endpoints
- **`meeting_notes_endpoint`**: Endpoint for meeting notes processing
- **`heartbeat_interval`**: Service health check interval in seconds
- **`registry_endpoint`**: Agent registry service endpoint for service discovery

### Environment Variables

```bash
# Required
MODEL_API_KEY=your_gemini_api_key
JIRA_API_TOKEN=your_jira_token

# Optional
LOG_LEVEL=INFO
CONFIG_PATH=/path/to/config.json
PYTHONPATH=/app
```

## 🛡️ Enterprise Infrastructure

### High-Performance Caching

**Redis Singleton Cache:**
- **Singleton Pattern**: Single connection instance across application
- **Configurable TTL**: Flexible expiration policies
- **Error Resilience**: Graceful degradation when cache unavailable
- **Performance Monitoring**: Built-in cache statistics and health checks

```python
from src.infrastructure.cache.redis_cache import get_cache

# Get singleton cache instance
cache = get_cache()

# Cache document content
cache.set_document_content("doc_id", content, title="Document Title")

# Retrieve cached content
content = cache.get_document_content("doc_id")

# Monitor performance
stats = cache.get_cache_stats()
```

### Comprehensive Logging

**Structured Logging System:**
- **JSON Format**: Machine-readable log output
- **Contextual Information**: Request IDs, user context, timing
- **Configurable Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Performance Tracking**: Response times and resource usage

### Real-time Observability

**Langfuse Integration:**
- **LLM Monitoring**: Track token usage, costs, and performance
- **Conversation Flows**: Visualize agent interactions and decision trees
- **Error Analytics**: Detailed error tracking and debugging
- **Performance Optimization**: Identify bottlenecks and optimization opportunities

## 🚀 Deployment

### Docker Compose Architecture

```yaml
services:
  redis:           # High-performance cache
  jira-agent:      # Jira integration service
  google-agent:    # Google Workspace service
  workflows:       # Workflow orchestration
  google-mcp:      # Model Context Protocol server
```

### Production Deployment

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Deploy with scaling
docker-compose -f docker-compose.prod.yml up -d --scale jira-agent=3

# Monitor services
docker-compose logs -f
```

### Health Monitoring

```bash
# Check service health
curl http://localhost:8000/
curl http://localhost:8001/

# Monitor cache performance
curl http://localhost:8000/cache/stats

# View API documentation
open http://localhost:8000/docs
open http://localhost:8001/docs
```

## 🔌 Integrations & Extensions

### Model Context Protocol (MCP)

**Extensible Tool Framework:**
- **Google Tools MCP**: Calendar, Docs, Drive integration
- **Custom Protocols**: Build domain-specific tool integrations
- **Agent Enhancement**: Extend capabilities through external tools

### External Service APIs

- **Google Workspace**: Calendar, Docs, Drive, Gmail integration
- **Jira Cloud/Server**: Full project management capabilities
- **Redis**: High-performance distributed caching
- **Langfuse**: Comprehensive LLM observability

## 📊 Monitoring & Analytics

### Performance Metrics

- **Response Times**: Agent processing and API call latencies
- **Success Rates**: Workflow completion and error rates
- **Resource Usage**: Memory, CPU, and cache utilization
- **Cost Tracking**: LLM token usage and API costs

### Debugging & Troubleshooting

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Monitor workflow execution
curl -X POST "http://localhost:8002/action-items" \
  -H "Content-Type: application/json" \
  -d '{"meeting": "Debug Test", "date": "2024-09-08"}'

# Check cache performance
python -c "
from src.infrastructure.cache.redis_cache import get_cache
cache = get_cache()
print(cache.get_cache_stats())
"
```

## 🧪 Development & Extension

### Adding New Agents

1. **Create Agent Class**: Extend `BaseAgentServer`
2. **Define Capabilities**: Implement required methods and tools
3. **Configure Integration**: Add to Docker Compose and config
4. **Add Documentation**: Update API docs and examples

### Custom Workflow Development

1. **Define Events**: Create workflow event classes
2. **Implement Steps**: Use `@step` decorators for workflow logic
3. **Add Error Handling**: Implement retry and recovery mechanisms
4. **Integration Testing**: Validate with existing agents

### Tool Integration Patterns

1. **Tool Specification**: Implement LlamaIndex tool specs
2. **API Integration**: Handle authentication and rate limiting
3. **Error Handling**: Graceful degradation and retry logic
4. **Testing**: Comprehensive unit and integration tests

## 📚 API Documentation

### Interactive Documentation

- **Jira Agent**: http://localhost:8000/docs
- **Google Agent**: http://localhost:8001/docs
- **Workflows**: http://localhost:8002/docs

### Common Endpoints

```bash
# Health checks
GET  /                    # Service status and information
GET  /health             # Detailed health metrics

# Agent interactions
POST /agent              # Main agent query endpoint
POST /test               # Test endpoint without full context

# Workflow operations
POST /action-items       # Action items workflow
POST /meeting-notes      # Meeting notes processing

# Administrative
GET  /cache/stats        # Cache performance metrics
GET  /metrics           # Prometheus-compatible metrics
```

## 🔍 Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify Google credentials.json placement
   - Check Jira API token validity
   - Validate API endpoint accessibility

2. **Cache Connection Issues**
   - Ensure Redis is running on correct port
   - Check password configuration
   - Verify network connectivity

3. **Agent Response Delays**
   - Monitor LLM API rate limits
   - Check cache hit rates
   - Validate network latency

4. **Workflow Failures**
   - Review Langfuse traces for error details
   - Check agent endpoint availability
   - Validate JSON schema compliance

### Debug Commands

```bash
# Test Redis connection
redis-cli -h localhost -p 6380 -a 12345 ping

# Validate configuration
python -c "from src.infrastructure.config import ConfigReader; print(ConfigReader().config)"

# Check agent health
curl -f http://localhost:8000/health || echo "Jira agent down"
curl -f http://localhost:8001/health || echo "Google agent down"
```

## 📄 License & Contributing

This project demonstrates enterprise AI automation patterns and is intended for educational and development purposes. Ensure compliance with all integrated service terms of use.

### Contributing Guidelines

1. **Code Quality**: Follow PEP 8 and use type hints
2. **Documentation**: Comprehensive docstrings for all classes and methods
3. **Testing**: Unit tests for new functionality
4. **Architecture**: Maintain clean architecture principles

---

**Built with:** Python 3.11+ • FastAPI • LlamaIndex • Redis • Docker • Langfuse

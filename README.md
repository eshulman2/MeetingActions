
# MeetingActions

🚨 README was generated using claude read with caution 🚨
🚨 Please note this is not a production ready project, this is a personal side project 🚨

**AI-Powered Meeting Intelligence & Action Item Automation**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.13+-orange.svg)](https://docs.llamaindex.ai/)
[![Redis](https://img.shields.io/badge/Redis-6.4+-red.svg)](https://redis.io/)
[![Langfuse](https://img.shields.io/badge/Langfuse-3.3+-purple.svg)](https://langfuse.com/)

---

**MeetingActions** is a distributed AI agent platform that transforms meeting notes into actionable tasks through intelligent automation. Built with a clean microservices architecture, it seamlessly integrates with Google Workspace, Jira, and other enterprise tools to provide comprehensive meeting intelligence and workflow orchestration with human-in-the-loop capabilities.

## 🏗️ Architecture Overview

MeetingActions follows a microservices architecture with specialized agents and workflow services for comprehensive meeting intelligence:

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
- **Purpose**: Orchestrates action items workflow with human-in-the-loop capabilities
- **Port**: 8002
- **Architecture**: Separated workflow orchestrators for better modularity
- **Features**:
  - **Generation Endpoint** (`/generate`): Creates action items from meeting notes
  - **Dispatch Endpoint** (`/dispatch`): Routes approved action items to agents
  - Multi-agent task orchestration and routing
  - Agent discovery and dynamic dispatch via service registry
  - Human review and approval workflow support

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

### 6. **Interactive CLI Client** (`src/clients/meeting_actions_client.py`)
- **Purpose**: Human-in-the-loop workflow interface
- **Features**:
  - Rich terminal UI for action item review
  - Edit action items before dispatch
  - Approve/remove items individually
  - Add new action items manually
  - Final approval before agent dispatch
  - Detailed results display with action item tracking

## 🛠️ Key Features

### Human-in-the-Loop Workflow
- **Two-Step Process**: Generate → Review → Dispatch
- **Interactive Review**: Rich CLI for reviewing and editing action items
- **Flexible Control**: Approve, edit, remove, or add items before dispatch
- **Full Visibility**: Track which action items were processed and their results

### AI-Powered Workflow Automation
- **ReActAgent Framework**: Uses LlamaIndex's ReActAgent for intelligent reasoning and action
- **Multi-LLM Support**: Compatible with OpenAI, Google Gemini, and OpenAI-like endpoints
- **Unified Response Model**: Consistent `AgentResponse` schema across all agents
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

### Clean Architecture
- **Separated Base Classes**: Distinct `BaseAgentServer` and `BaseWorkflowServer`
- **Centralized Schemas**: All Pydantic models in `src/core/schemas/`
- **Modular Design**: Composable workflows and reusable components
- **Type Safety**: Full type hints and Pydantic validation throughout

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
- **Registry**: http://localhost:8003
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

### 🎯 Interactive CLI Client

```bash
# Run the interactive client for human-in-the-loop workflow
python -m src.clients.meeting_actions_client

# Or with custom server URL
python -m src.clients.meeting_actions_client --url http://localhost:8002
```

**Client Workflow:**
1. Enter meeting name and date
2. Review generated action items (view each individually)
3. Edit, approve, or remove items
4. Add new items if needed
5. Final approval before dispatch
6. View detailed execution results

## 🏗️ Architecture

### Core Structure

```
src/
├── clients/                # Client applications
│   └── meeting_actions_client.py # Interactive CLI client
├── common/                 # Shared utilities and patterns
│   └── singleton_meta.py  # Singleton metaclass implementation
├── core/                  # Business logic and agents
│   ├── agents/           # Individual agent implementations
│   │   ├── jira_agent.py # Jira integration agent
│   │   ├── google_agent.py # Google Workspace agent
│   │   └── utils.py      # Agent utility functions
│   ├── base/             # Base classes and utilities
│   │   ├── base_server.py # Base server for all services
│   │   ├── base_agent_server.py # Base for agent servers
│   │   └── base_workflow_server.py # Base for workflow servers
│   ├── schemas/          # Pydantic models and schemas
│   │   ├── __init__.py   # Centralized schema exports
│   │   ├── agent_response.py # Unified AgentResponse model
│   │   └── workflow_models.py # Workflow data models
│   ├── workflows/        # Event-driven workflow definitions
│   │   ├── meeting_notes_and_generation_orchestrator.py
│   │   ├── action_items_dispatch_orchestrator.py
│   │   └── sub_workflows/ # Focused sub-workflow components
│   │       ├── meeting_notes_workflow.py
│   │       ├── action_items_generation_workflow.py
│   │       └── agent_dispatch_workflow.py
│   └── workflow_servers/ # Workflow execution servers
│       └── action_items_server.py # Action items server
├── infrastructure/       # Platform infrastructure
│   ├── cache/           # Redis caching with singleton pattern
│   │   ├── redis_cache.py # Redis cache implementation
│   │   └── document_cache.py # Document-specific caching
│   ├── config/          # Configuration management
│   │   ├── read_config.py # Configuration reader
│   │   └── models.py    # Configuration models
│   ├── prompts/         # System prompts
│   │   └── prompts.py   # AI system prompts and contexts
│   ├── logging/         # Structured logging
│   │   └── logging_config.py # Logging configuration
│   ├── observability/   # Langfuse integration
│   │   └── observability.py # Monitoring and tracing
│   └── registry/        # Service registry
│       ├── agent_registry.py # Agent registration
│       └── registry_client.py # Registry client
├── integrations/        # External service integrations
│   ├── google_tools/    # Google Workspace APIs
│   │   ├── google_tools.py # Google API tools
│   │   └── auth_utils.py # Authentication utilities
│   ├── jira_tools/      # Jira API integration
│   │   ├── jira_tools.py # Jira API tools
│   │   └── jira_formatter.py # Jira data formatting
│   └── general_tools/   # Utility tools
│       └── date_tools.py # Date/time utilities
├── mcp/                 # Model Context Protocol servers
│   └── google_tools_mcp.py # Google tools MCP server
└── services/            # Standalone services
    └── registry_service.py # Agent registry service
```

### Design Patterns

- **Singleton Pattern**: Efficient resource management for caching and shared services
- **Factory Pattern**: Dynamic model and configuration creation
- **Observer Pattern**: Event-driven workflow orchestration
- **Repository Pattern**: Clean data access abstraction
- **Separation of Concerns**: Clear boundaries between agents, workflows, and infrastructure

### Key Architectural Improvements

1. **Unified AgentResponse Schema**: Single, consistent response model for all agents and workflows
2. **Separated Base Classes**: `BaseAgentServer` for agents, `BaseWorkflowServer` for workflows
3. **Centralized Schemas**: All Pydantic models organized in `src/core/schemas/`
4. **Enhanced Execution Results**: Full action item tracking in dispatch results
5. **Modular Workflows**: Composable orchestrators for better maintainability

## 🤖 Agent Capabilities

### Google Workspace Agent

**Core Features:**
- **Meeting Intelligence**: Extract structured action items from meeting notes with AI precision
- **Calendar Management**: Schedule meetings, manage events, sync calendars automatically
- **Document Processing**: Analyze Google Docs for actionable content and insights
- **MeetingActions Integration**: Seamless automated meeting-to-action-item pipelines

**API Examples:**
```bash
# Extract action items from meeting
curl -X POST "http://localhost:8001/agent" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Extract action items from my team meeting notes"
  }'

# Response format (AgentResponse)
{
  "response": "I found 3 action items...",
  "error": false,
  "additional_info_required": false
}
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
  -d '{
    "query": "Create ticket for authentication bug fix in user login"
  }'

# Response format (AgentResponse)
{
  "response": "Created ticket PROJ-123",
  "error": false,
  "additional_info_required": false
}
```

## 🔄 Human-in-the-Loop Workflow

### Architecture

The action items workflow has been separated into two distinct orchestrators to enable human review:

#### 1. **MeetingNotesAndGenerationOrchestrator**
- **Purpose**: Retrieve meeting notes and generate action items
- **Endpoint**: `POST /generate`
- **Process**:
  1. Fetch meeting notes from Google agent
  2. Generate structured action items with AI
  3. Return items for human review

#### 2. **ActionItemsDispatchOrchestrator**
- **Purpose**: Dispatch approved action items to agents
- **Endpoint**: `POST /dispatch`
- **Process**:
  1. Discover available agents
  2. Route action items to appropriate agents
  3. Execute and collect results
  4. Return detailed execution results with action item tracking

### Interactive Client Usage

The CLI client provides a rich interface for the human-in-the-loop workflow:

```bash
# Start the interactive client
python -m src.clients.meeting_actions_client

# Workflow steps:
# 1. Enter meeting information
#    → Meeting name: "Weekly Team Sync"
#    → Date: 2024-09-08

# 2. Review generated action items
#    → View each item with full details
#    → Options: Approve, Edit, Remove, Back

# 3. Edit fields if needed
#    → Title, Description, Assignee
#    → Due Date, Priority, Category

# 4. Final approval
#    → Review all items in summary table
#    → Add new items if needed
#    → Dispatch to agents

# 5. View results
#    → See which items were processed
#    → View agent responses
#    → Track success/failure status
```

### Programmatic Usage

```python
# Generate action items
import requests

generation_response = requests.post(
    "http://localhost:8002/generate",
    json={
        "meeting": "Weekly Team Sync",
        "date": "2024-09-08"
    }
)

action_items = generation_response.json()["action_items"]

# Review and modify action items (your custom logic here)
# ...

# Dispatch approved action items
dispatch_response = requests.post(
    "http://localhost:8002/dispatch",
    json={"action_items": action_items}
)

results = dispatch_response.json()["results"]

# Each result contains:
# - action_item: The original action item with title
# - agent_name: Which agent processed it
# - response: Agent's response
# - request_error: Whether request failed
# - agent_error: Whether agent reported an error
# - additional_info_required: Whether more info is needed
```

### Sub-Workflows

The system uses composable sub-workflows for maximum flexibility:

#### 1. **Meeting Notes Workflow** (`meeting_notes_workflow.py`)
- Retrieve and validate meeting notes from external sources
- Content validation and format normalization
- Error handling and retry logic

#### 2. **Action Items Generation Workflow** (`action_items_generation_workflow.py`)
- Extract structured action items using LLM analysis
- Multi-stage validation and review cycles
- Iterative refinement with feedback loops
- Pydantic model validation

#### 3. **Agent Dispatch Workflow** (`agent_dispatch_workflow.py`)
- Intelligent agent discovery via registry
- Dynamic routing decisions based on action item content
- Parallel execution and result aggregation
- Full action item tracking in results

**Advanced Features:**
- **Composable Architecture**: Each sub-workflow can be used independently
- **Shared Data Models**: Type-safe Pydantic models from `src/core/schemas/`
- **Common Events**: Standardized event system across workflows
- **Error Propagation**: Structured error handling with proper error models
- **Observability**: Full tracing with Langfuse integration
- **Enhanced Results**: Action item details included in execution results

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
  registry:        # Service discovery
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
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health

# Monitor cache performance
curl http://localhost:8000/cache/stats

# View API documentation
open http://localhost:8000/docs
open http://localhost:8001/docs
open http://localhost:8002/docs
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

# Test generation endpoint
curl -X POST "http://localhost:8002/generate" \
  -H "Content-Type: application/json" \
  -d '{"meeting": "Debug Test", "date": "2024-09-08"}'

# Test dispatch endpoint
curl -X POST "http://localhost:8002/dispatch" \
  -H "Content-Type: application/json" \
  -d '{
    "action_items": {
      "meeting_title": "Test",
      "meeting_date": "2024-09-08",
      "action_items": [...]
    }
  }'

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
   ```python
   from src.core.base.base_agent_server import BaseAgentServer
   from src.core.schemas.agent_response import AgentResponse

   class MyAgent(BaseAgentServer):
       def create_service(self):
           # No llm parameter needed - use self.llm
           return ReActAgent(
               name="my-agent",
               tools=my_tools,
               llm=self.llm,
               output_cls=AgentResponse
           )
   ```

2. **Define Capabilities**: Implement required methods and tools
3. **Configure Integration**: Add to Docker Compose and config
4. **Add Documentation**: Update API docs and examples

### Custom Workflow Development

1. **Define Workflow Class**: Extend `BaseWorkflowServer`
   ```python
   from src.core.base.base_workflow_server import BaseWorkflowServer

   class MyWorkflowServer(BaseWorkflowServer):
       def additional_routes(self):
           @self.app.post("/my-workflow")
           async def my_workflow(request: MyRequest):
               # Create orchestrator on-demand
               orchestrator = MyOrchestrator(llm=self.llm)
               result = await orchestrator.run(...)
               return result
   ```

2. **Implement Workflow Steps**: Use `@step` decorators for workflow logic
3. **Use Shared Schemas**: Import from `src.core.schemas`
4. **Add Error Handling**: Implement retry and recovery mechanisms
5. **Integration Testing**: Validate with existing agents

### Schema Development

All schemas are centralized in `src/core/schemas/`:

```python
from src.core.schemas import (
    AgentResponse,      # Unified agent response
    ActionItem,         # Single action item
    ActionItemsList,    # Complete action items list
    AgentExecutionResult,  # Execution result with action item
)
```

## 📚 API Documentation

### Interactive Documentation

- **Jira Agent**: http://localhost:8000/docs
- **Google Agent**: http://localhost:8001/docs
- **Workflows**: http://localhost:8002/docs
- **Registry**: http://localhost:8003/docs

### Common Endpoints

```bash
# Health checks
GET  /                    # Service status and information
GET  /health             # Detailed health metrics
GET  /description        # Service description

# Agent interactions
POST /agent              # Main agent query endpoint (returns AgentResponse)
POST /test               # Test endpoint without full context

# Workflow operations (NEW SEPARATED ENDPOINTS)
POST /generate           # Generate action items from meeting (step 1)
POST /dispatch           # Dispatch action items to agents (step 2)

# Administrative
GET  /info               # Agent information and capabilities
GET  /discover           # Discover other registered agents
GET  /cache/stats        # Cache performance metrics
```

### AgentResponse Format

All agents return a unified response format:

```json
{
  "response": "Agent response content or error description",
  "error": false,
  "additional_info_required": false
}
```

### Execution Result Format

Dispatch endpoint returns enhanced results with action item tracking:

```json
{
  "results": [
    {
      "action_item_index": 0,
      "action_item": {
        "title": "Update documentation",
        "description": "...",
        "assignee": "John",
        "due_date": "2024-09-15",
        "priority": "high"
      },
      "agent_name": "jira-agent",
      "request_error": false,
      "agent_error": false,
      "response": "Created ticket PROJ-123",
      "additional_info_required": false,
      "execution_time": 2.5
    }
  ]
}
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
   - Check agent endpoint availability via `/discover`
   - Validate JSON schema compliance with Pydantic models
   - Ensure action items match `ActionItemsList` schema

### Debug Commands

```bash
# Test Redis connection
redis-cli -h localhost -p 6380 -a 12345 ping

# Validate configuration
python -c "from src.infrastructure.config import ConfigReader; print(ConfigReader().config)"

# Check agent health
curl -f http://localhost:8000/health || echo "Jira agent down"
curl -f http://localhost:8001/health || echo "Google agent down"
curl -f http://localhost:8002/health || echo "Workflows down"
curl -f http://localhost:8003/health || echo "Registry down"

# Test agent discovery
curl http://localhost:8000/discover

# Run tests
pytest tests/unit/ -v
pytest tests/integration/ -v
```

## 📄 License & Contributing

**MeetingActions** demonstrates enterprise AI automation patterns for meeting intelligence and is intended for educational and development purposes. Ensure compliance with all integrated service terms of use.

### Contributing Guidelines

1. **Code Quality**: Follow PEP 8 and use type hints
2. **Documentation**: Comprehensive docstrings for all classes and methods
3. **Testing**: Unit tests for new functionality
4. **Architecture**: Maintain clean architecture principles
5. **Schema Validation**: Use Pydantic models from `src/core/schemas/`
6. **Consistent Responses**: Use `AgentResponse` for all agent endpoints

### Recent Architectural Improvements

- **Unified AgentResponse**: Single response model across all agents
- **Separated Base Classes**: `BaseAgentServer` vs `BaseWorkflowServer`
- **Centralized Schemas**: All models in `src/core/schemas/`
- **Human-in-the-Loop**: Separated generation and dispatch workflows
- **Enhanced Results**: Full action item tracking in execution results
- **Interactive CLI**: Rich terminal interface for workflow management

---

<div align="center">

**MeetingActions** - *Transforming Meetings into Actions with AI*

**Built with:** Python 3.11+ • FastAPI • LlamaIndex • Redis • Docker • Langfuse

</div>

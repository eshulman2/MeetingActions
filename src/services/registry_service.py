"""Agent Registry Service

This service provides centralized agent registration and discovery endpoints.
It can be run as a standalone service or integrated into existing services.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.registry.agent_registry import AgentInfo, AgentRegistry

logger = get_logger("registry_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    # Startup
    logger.info("Starting Agent Registry Service")

    # Initialize registry during startup (not at module import)
    logger.info("Initializing agent registry...")
    app.state.registry = AgentRegistry()
    logger.info("Agent registry initialized")

    cleanup_task = asyncio.create_task(cleanup_stale_agents(app))
    logger.info("Registry service started successfully")

    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down Agent Registry Service")
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("Registry service shutdown complete")


app = FastAPI(
    title="Agent Registry Service",
    description="Centralized service discovery for AI agents",
    version="1.0.0",
    lifespan=lifespan,
)


class RegistrationResponse(BaseModel):
    """Response model for agent registration"""

    status: str
    agent_id: str
    message: str


class DiscoveryResponse(BaseModel):
    """Response model for agent discovery"""

    agents: List[Dict[str, Any]]
    total: int


class HeartbeatResponse(BaseModel):
    """Response model for heartbeat"""

    status: str
    agent_id: str
    timestamp: str


@app.post("/register", response_model=RegistrationResponse)
async def register_agent(agent_info: AgentInfo):
    """Register a new agent with the registry"""
    registry = app.state.registry
    try:
        success = registry.register_agent(agent_info)
        if success:
            logger.info(f"Agent registered: {agent_info.agent_id}")
            return RegistrationResponse(
                status="registered",
                agent_id=agent_info.agent_id,
                message=f"Agent {agent_info.name} successfully registered",
            )

        raise HTTPException(status_code=500, detail="Failed to register agent")
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Registration failed: {str(e)}"
        ) from e


@app.get("/discover", response_model=DiscoveryResponse)
async def discover_agents():
    """Discover all active agents"""
    registry = app.state.registry
    try:
        agents = registry.discover_agents()

        agent_list = [
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "description": agent.description,
                "endpoint": agent.endpoint,
                "health_endpoint": agent.health_endpoint,
                "version": agent.version,
                "status": agent.status,
                "last_heartbeat": agent.last_heartbeat.isoformat(),
                "metadata": agent.metadata,
            }
            for agent in agents
        ]

        logger.debug(f"Discovery request found {len(agents)} agents")
        return DiscoveryResponse(agents=agent_list, total=len(agents))

    except Exception as e:
        logger.error(f"Discovery error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Discovery failed: {str(e)}"
        ) from e


@app.post("/heartbeat/{agent_id}", response_model=HeartbeatResponse)
async def agent_heartbeat(agent_id: str):
    """Receive heartbeat from an agent"""
    registry = app.state.registry
    try:
        success = registry.heartbeat(agent_id)
        if success:
            agent = registry.get_agent(agent_id)
            return HeartbeatResponse(
                status="received",
                agent_id=agent_id,
                timestamp=agent.last_heartbeat.isoformat() if agent else "",
            )

        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        logger.error(f"Heartbeat error for {agent_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Heartbeat failed: {str(e)}"
        ) from e


@app.get("/agents/{agent_id}")
async def get_agent_info(agent_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific agent"""
    registry = app.state.registry
    try:
        agent = registry.get_agent(agent_id)
        if agent:
            return {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "description": agent.description,
                "endpoint": agent.endpoint,
                "health_endpoint": agent.health_endpoint,
                "version": agent.version,
                "status": agent.status,
                "last_heartbeat": agent.last_heartbeat.isoformat(),
                "metadata": agent.metadata,
            }

        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        logger.error(f"Error getting agent {agent_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get agent info: {str(e)}"
        ) from e


@app.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str) -> Dict[str, str]:
    """Unregister an agent from the registry"""
    registry = app.state.registry
    try:
        success = registry.unregister_agent(agent_id)
        if success:
            logger.info(f"Agent unregistered: {agent_id}")
            return {"status": "unregistered", "agent_id": agent_id}

        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        logger.error(f"Unregistration error for {agent_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Unregistration failed: {str(e)}"
        ) from e


@app.get("/stats")
async def get_registry_stats() -> Dict[str, Any]:
    """Get registry statistics and health information"""
    registry = app.state.registry
    try:
        stats = registry.get_registry_stats()
        return {
            "registry_stats": stats,
            "service_info": {
                "title": app.title,
                "version": app.version,
                "description": app.description,
            },
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get stats: {str(e)}"
        ) from e


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    registry = app.state.registry
    return {
        "status": "healthy",
        "service": app.title,
        "version": app.version,
        "registry_enabled": registry.cache.enabled if registry.cache else False,
    }


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with service information"""
    return {
        "message": f"{app.title} is running",
        "version": app.version,
        "endpoints": {
            "register": "POST /register",
            "discover": "GET /discover",
            "heartbeat": "POST /heartbeat/<agent_id>",
            "agent_info": "GET /agents/<agent_id>",
            "unregister": "DELETE /agents/<agent_id>",
            "stats": "GET /stats",
            "health": "GET /health",
            "docs": "GET /docs",
        },
    }


# Background task for cleanup
async def cleanup_stale_agents(app: FastAPI) -> None:
    """Background task to clean up stale agents"""
    while True:
        try:
            # Cleanup agents older than 15 minutes (1.5x the TTL for safety margin)
            stale_count = app.state.registry.cleanup_stale_agents(max_age_minutes=15)
            if stale_count > 0:
                logger.info(f"Cleaned up {stale_count} stale agents")
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")

        # Run cleanup every 5 minutes
        await asyncio.sleep(300)


if __name__ == "__main__":
    config = get_config()
    logger.info("Starting Agent Registry Service")
    uvicorn.run(
        "src.services.registry_service:app",
        host=config.config.host,
        port=config.config.port,
        reload=True,
        log_level="info",
    )

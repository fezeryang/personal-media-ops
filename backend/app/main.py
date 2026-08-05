from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.crawler import router as crawler_router
from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.api.library import router as library_router
from app.api.monitoring import notifications_router
from app.api.monitoring import router as monitoring_router
from app.api.organization import router as organization_router
from app.api.research import router as research_router
from app.api.subscriptions import router as subscriptions_router
from app.api.v1 import router as v1_router
from app.api.watchlist import router as watchlist_router
from app.core.config import Settings, settings
from app.crawler.registry import platform_registry
from app.repositories.ai import AIRepository
from app.repositories.auth import AuthRepository
from app.repositories.automation import AutomationRepository
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.discovery import DiscoveryRepository
from app.repositories.intelligence import IntelligenceRepository
from app.repositories.library import LibraryRepository
from app.repositories.monitoring import MonitoringRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.research import ResearchTaskRepository
from app.security.provider_secrets import ProviderSecretCipher
from app.services.agent_tools import AgentToolService
from app.services.ai.discovery import DiscoveryEngine
from app.services.ai.model_gateway import ModelGateway
from app.services.ai.research_runtime import ResearchRuntime
from app.services.ai.research_tools import ResearchToolService
from app.services.auth import AuthService
from app.services.automation import AutomationCoordinator
from app.services.intelligence.briefs import DeterministicBriefGenerator
from app.services.intelligence.trends import TrendService
from app.services.monitoring.service import MonitoringService


def create_app(config: Settings | None = None) -> FastAPI:
    active_settings = config or settings
    platform_registry.list_capabilities(active_settings.enabled_platforms)
    repository = CrawlerTaskRepository(active_settings.database_path)
    library_repository = LibraryRepository(active_settings.database_path)
    intelligence_repository = IntelligenceRepository(active_settings.database_path)
    organization_repository = OrganizationRepository(active_settings.database_path)
    automation_repository = AutomationRepository(active_settings)
    auth_repository = AuthRepository(active_settings.database_path)
    auth_service = AuthService(auth_repository, active_settings)
    ai_repository = AIRepository(active_settings.database_path)
    research_repository = ResearchTaskRepository(active_settings.database_path)
    monitoring_repository = MonitoringRepository(active_settings.database_path)
    monitoring_service = MonitoringService(monitoring_repository, research_repository)
    discovery_repository = DiscoveryRepository(active_settings.database_path)
    production_verified_search_platforms = platform_registry.production_verified_platforms_for_mode(
        "search",
        active_settings.enabled_platforms,
    )
    provider_secret_cipher = ProviderSecretCipher(
        active_settings.model_gateway_master_key_path
    )
    ai_http_client = httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=active_settings.model_gateway_max_connections,
            max_keepalive_connections=(
                active_settings.model_gateway_max_keepalive_connections
            ),
        ),
        timeout=httpx.Timeout(60, connect=10, pool=10),
        follow_redirects=False,
        trust_env=False,
    )
    model_gateway = ModelGateway(
        repository=ai_repository,
        secret_cipher=provider_secret_cipher,
        client=ai_http_client,
    )
    automation_coordinator = AutomationCoordinator(
        automation_repository,
        active_settings,
        library_repository=library_repository,
    )
    trend_service = TrendService(intelligence_repository)
    brief_generator = DeterministicBriefGenerator(intelligence_repository)
    agent_tools = AgentToolService(
        library=library_repository,
        intelligence=intelligence_repository,
        automation=automation_repository,
    )
    research_tools = ResearchToolService(
        settings=active_settings,
        library_tools=agent_tools,
        crawler=repository,
        research=research_repository,
    )
    discovery_engine = DiscoveryEngine(
        discovery=discovery_repository,
        research=research_repository,
        production_verified_platforms=production_verified_search_platforms,
    )
    research_runtime = ResearchRuntime(
        research=research_repository,
        ai_repository=ai_repository,
        gateway=model_gateway,
        tools=research_tools,
        discovery=discovery_engine,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        repository.initialize()
        ai_repository.ensure_governance_defaults()
        await research_runtime.start()
        try:
            yield
        finally:
            await research_runtime.stop()
            await ai_http_client.aclose()

    application = FastAPI(
        title="personal-media-ops-api",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = active_settings
    application.state.crawler_repository = repository
    application.state.library_repository = library_repository
    application.state.organization_repository = organization_repository
    application.state.intelligence_repository = intelligence_repository
    application.state.trend_service = trend_service
    application.state.brief_generator = brief_generator
    application.state.agent_tools = agent_tools
    application.state.auth_repository = auth_repository
    application.state.auth_service = auth_service
    application.state.ai_repository = ai_repository
    application.state.research_repository = research_repository
    application.state.discovery_repository = discovery_repository
    application.state.discovery_engine = discovery_engine
    application.state.research_tools = research_tools
    application.state.research_runtime = research_runtime
    application.state.provider_secret_cipher = provider_secret_cipher
    application.state.ai_http_client = ai_http_client
    application.state.model_gateway = model_gateway
    application.state.automation_repository = automation_repository
    application.state.automation_coordinator = automation_coordinator
    application.state.monitoring_repository = monitoring_repository
    application.state.monitoring_service = monitoring_service
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_settings.frontend_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @application.exception_handler(HTTPException)
    async def api_http_exception(
        request: Request,
        error: HTTPException,
    ) -> JSONResponse:
        if request.url.path.startswith("/api/v1/"):
            code = {
                401: "authentication_required",
                403: "insufficient_scope",
                404: "not_found",
                409: "conflict",
                429: "rate_limited",
            }.get(error.status_code, "request_failed")
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error": {
                        "code": code,
                        "message": str(error.detail),
                    }
                },
                headers=error.headers,
            )
        return await http_exception_handler(request, error)

    @application.exception_handler(RequestValidationError)
    async def api_validation_exception(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        if request.url.path.startswith("/api/v1/"):
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "invalid_request",
                        "message": "Request validation failed",
                    }
                },
            )
        return await request_validation_exception_handler(request, error)
    application.include_router(health_router, prefix="/api")
    application.include_router(auth_router, prefix="/api")
    application.include_router(ai_router, prefix="/api")
    application.include_router(crawler_router, prefix="/api")
    application.include_router(library_router, prefix="/api")
    application.include_router(monitoring_router, prefix="/api")
    application.include_router(notifications_router, prefix="/api")
    application.include_router(organization_router, prefix="/api")
    application.include_router(research_router, prefix="/api")
    application.include_router(intelligence_router, prefix="/api")
    application.include_router(subscriptions_router, prefix="/api")
    application.include_router(watchlist_router, prefix="/api")
    application.include_router(v1_router, prefix="/api")
    return application


app = create_app()

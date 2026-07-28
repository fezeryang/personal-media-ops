from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.crawler import router as crawler_router
from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.api.library import router as library_router
from app.api.organization import router as organization_router
from app.api.subscriptions import router as subscriptions_router
from app.api.v1 import router as v1_router
from app.api.watchlist import router as watchlist_router
from app.core.config import Settings, settings
from app.crawler.registry import platform_registry
from app.repositories.auth import AuthRepository
from app.repositories.automation import AutomationRepository
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.intelligence import IntelligenceRepository
from app.repositories.library import LibraryRepository
from app.repositories.organization import OrganizationRepository
from app.services.agent_tools import AgentToolService
from app.services.auth import AuthService
from app.services.automation import AutomationCoordinator
from app.services.intelligence.briefs import DeterministicBriefGenerator
from app.services.intelligence.trends import TrendService


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

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        repository.initialize()
        yield

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
    application.state.automation_repository = automation_repository
    application.state.automation_coordinator = automation_coordinator
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
    application.include_router(crawler_router, prefix="/api")
    application.include_router(library_router, prefix="/api")
    application.include_router(organization_router, prefix="/api")
    application.include_router(intelligence_router, prefix="/api")
    application.include_router(subscriptions_router, prefix="/api")
    application.include_router(watchlist_router, prefix="/api")
    application.include_router(v1_router, prefix="/api")
    return application


app = create_app()

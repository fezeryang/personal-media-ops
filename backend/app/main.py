from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.crawler import router as crawler_router
from app.api.health import router as health_router
from app.api.library import router as library_router
from app.core.config import Settings, settings
from app.crawler.registry import platform_registry
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.library import LibraryRepository


def create_app(config: Settings | None = None) -> FastAPI:
    active_settings = config or settings
    platform_registry.list_capabilities(active_settings.enabled_platforms)
    repository = CrawlerTaskRepository(active_settings.database_path)
    library_repository = LibraryRepository(active_settings.database_path)

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
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(active_settings.frontend_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    application.include_router(health_router, prefix="/api")
    application.include_router(crawler_router, prefix="/api")
    application.include_router(library_router, prefix="/api")
    return application


app = create_app()

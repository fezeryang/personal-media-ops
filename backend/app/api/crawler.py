from collections import deque
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.core.config import Settings
from app.crawler.registry import (
    ModeDisabledError,
    PlatformDisabledError,
    UnsupportedPlatformError,
    platform_registry,
)
from app.crawler.results import (
    CrawlerResultDataError,
    read_normalized_result_page,
)
from app.models.crawler_platform import CrawlerCapabilitiesResponse
from app.models.crawler_task import (
    CrawlerResultsResponse,
    CrawlerTaskResponse,
    CreateCrawlerTaskRequest,
)
from app.repositories.crawler_tasks import (
    CrawlerTaskRepository,
    TaskNotCancellableError,
)

router = APIRouter(prefix="/crawler", tags=["crawler"])
MAX_LOG_BYTES = 256 * 1024
MAX_LOG_TAIL_LINES = 1000
MAX_RESULTS_LIMIT = 100


def get_repository(request: Request) -> CrawlerTaskRepository:
    return request.app.state.crawler_repository


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


RepositoryDependency = Annotated[CrawlerTaskRepository, Depends(get_repository)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def _get_task_or_404(
    repository: CrawlerTaskRepository,
    task_id: str,
) -> dict[str, Any]:
    task = repository.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Crawler task not found")
    return task


def _validated_task_path(
    *,
    stored_path: str,
    expected_path: Path,
    allowed_root: Path,
) -> Path:
    root = allowed_root.resolve()
    expected = expected_path.resolve()
    stored = Path(stored_path).resolve()
    if not expected.is_relative_to(root) or stored != expected:
        raise HTTPException(status_code=409, detail="Task storage path is invalid")
    return expected


@router.get("/capabilities", response_model=CrawlerCapabilitiesResponse)
def get_crawler_capabilities(
    settings: SettingsDependency,
) -> CrawlerCapabilitiesResponse:
    try:
        capabilities = platform_registry.list_capabilities(settings.enabled_platforms)
    except UnsupportedPlatformError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return CrawlerCapabilitiesResponse(
        max_concurrent_tasks=1,
        platforms=capabilities,
    )


@router.post("/tasks", response_model=CrawlerTaskResponse, status_code=201)
def create_crawler_task(
    payload: CreateCrawlerTaskRequest,
    repository: RepositoryDependency,
    settings: SettingsDependency,
) -> dict[str, Any]:
    try:
        adapter = platform_registry.require_mode_enabled(
            payload.platform,
            payload.mode,
            settings.enabled_platforms,
        )
    except UnsupportedPlatformError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except PlatformDisabledError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ModeDisabledError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    try:
        adapter.validate_task_request(payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    task_id = repository.new_id()
    return repository.create(
        task_id=task_id,
        platform=payload.platform,
        crawler_type=payload.mode,
        keywords=payload.keywords,
        target_ids=payload.target_ids,
        target_urls=payload.target_urls,
        creator_ids=payload.creator_ids,
        creator_urls=payload.creator_urls,
        parent_content_id=payload.parent_content_id,
        parent_comment_id=payload.parent_comment_id,
        login_type=payload.login_type,
        requested_count=payload.requested_count,
        requested_comment_count=payload.requested_comment_count,
        requested_sub_comment_count=payload.requested_sub_comment_count,
        output_dir=str(settings.output_root / "tasks" / task_id),
        log_path=str(settings.log_root / "crawler" / f"{task_id}.log"),
        qrcode_path=str(settings.qrcode_root / f"{task_id}.png"),
    )


@router.get("/tasks", response_model=list[CrawlerTaskResponse])
def list_crawler_tasks(repository: RepositoryDependency) -> list[dict[str, Any]]:
    return repository.list()


@router.get("/tasks/{task_id}", response_model=CrawlerTaskResponse)
def get_crawler_task(
    task_id: str,
    repository: RepositoryDependency,
) -> dict[str, Any]:
    return _get_task_or_404(repository, task_id)


@router.get("/tasks/{task_id}/logs", response_class=PlainTextResponse)
def get_crawler_task_logs(
    task_id: str,
    repository: RepositoryDependency,
    settings: SettingsDependency,
    offset: Annotated[int | None, Query(ge=0)] = None,
    tail: Annotated[int | None, Query(ge=1, le=MAX_LOG_TAIL_LINES)] = None,
) -> PlainTextResponse:
    if offset is not None and tail is not None:
        raise HTTPException(status_code=422, detail="Use either offset or tail")
    task = _get_task_or_404(repository, task_id)
    log_path = _validated_task_path(
        stored_path=str(task["log_path"]),
        expected_path=settings.log_root / "crawler" / f"{task_id}.log",
        allowed_root=settings.log_root / "crawler",
    )
    if not log_path.is_file():
        raise HTTPException(status_code=404, detail="Task log is not available yet")

    if tail is not None:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            content = "".join(deque(handle, maxlen=tail))
        return PlainTextResponse(content)

    start = offset or 0
    with log_path.open("rb") as handle:
        handle.seek(start)
        content = handle.read(MAX_LOG_BYTES)
        next_offset = handle.tell()
    return PlainTextResponse(
        content.decode("utf-8", errors="replace"),
        headers={"X-Next-Offset": str(next_offset)},
    )


@router.get("/tasks/{task_id}/qrcode", response_model=None)
def get_crawler_task_qrcode(
    task_id: str,
    repository: RepositoryDependency,
    settings: SettingsDependency,
) -> FileResponse | JSONResponse:
    task = _get_task_or_404(repository, task_id)
    qrcode_path = _validated_task_path(
        stored_path=str(task["qrcode_path"]),
        expected_path=settings.qrcode_root / f"{task_id}.png",
        allowed_root=settings.qrcode_root,
    )
    if not qrcode_path.is_file():
        return JSONResponse(
            status_code=404,
            content={
                "status": task["status"],
                "detail": "QR code is not available yet",
            },
        )
    return FileResponse(qrcode_path, media_type="image/png", filename="qrcode.png")


@router.get("/tasks/{task_id}/results", response_model=CrawlerResultsResponse)
def get_crawler_task_results(
    task_id: str,
    repository: RepositoryDependency,
    settings: SettingsDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_RESULTS_LIMIT)] = 20,
) -> dict[str, object]:
    task = _get_task_or_404(repository, task_id)
    task_dir = _validated_task_path(
        stored_path=str(task["output_dir"]),
        expected_path=settings.output_root / "tasks" / task_id,
        allowed_root=settings.output_root / "tasks",
    )
    try:
        adapter = platform_registry.get(str(task["platform"]))
        items, has_more = read_normalized_result_page(
            adapter=adapter,
            task_dir=task_dir,
            offset=offset,
            limit=limit,
            maximum=int(task["requested_count"]),
        )
    except UnsupportedPlatformError as error:
        raise HTTPException(
            status_code=409,
            detail="Task platform is invalid",
        ) from error
    except CrawlerResultDataError as error:
        status_code = 409 if "escapes" in str(error) else 500
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    return {
        "items": items,
        "offset": offset,
        "limit": limit,
        "next_offset": offset + len(items),
        "has_more": has_more,
    }


@router.post("/tasks/{task_id}/cancel", response_model=CrawlerTaskResponse)
def cancel_crawler_task(
    task_id: str,
    repository: RepositoryDependency,
) -> dict[str, Any]:
    try:
        task = repository.request_cancel(task_id)
    except TaskNotCancellableError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if task is None:
        raise HTTPException(status_code=404, detail="Crawler task not found")
    return task

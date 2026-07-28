from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models.library import (
    LibraryCommentPage,
    LibraryContentDetail,
    LibraryContentPage,
    LibraryCreatorDetail,
    LibraryCreatorPage,
    LibraryStats,
)
from app.repositories.library import ContentSort, LibraryRepository

router = APIRouter(prefix="/library", tags=["library"])
MAX_LIBRARY_LIMIT = 100


def get_library_repository(request: Request) -> LibraryRepository:
    return request.app.state.library_repository


LibraryDependency = Annotated[
    LibraryRepository,
    Depends(get_library_repository),
]
PlatformQuery = Annotated[
    str | None,
    Query(min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]+$"),
]


def _utc_query_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


@router.get("/stats", response_model=LibraryStats)
def get_library_stats(repository: LibraryDependency) -> dict[str, int]:
    return repository.counts()


@router.get("/contents", response_model=LibraryContentPage)
def list_library_contents(
    repository: LibraryDependency,
    platform: PlatformQuery = None,
    content_type: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    keyword: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    creator: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    has_comments: bool | None = None,
    sort: ContentSort = "last_collected_desc",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIBRARY_LIMIT)] = 20,
) -> dict[str, object]:
    return repository.list_contents(
        platform=platform,
        content_type=content_type,
        keyword=keyword,
        creator=creator,
        date_from=_utc_query_timestamp(date_from),
        date_to=_utc_query_timestamp(date_to),
        has_comments=has_comments,
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get("/contents/{content_id}", response_model=LibraryContentDetail)
def get_library_content(
    content_id: str,
    repository: LibraryDependency,
    include_raw: bool = False,
) -> dict[str, object]:
    content = repository.get_content(content_id, include_raw=include_raw)
    if content is None:
        raise HTTPException(status_code=404, detail="Library content not found")
    return content


@router.get("/creators", response_model=LibraryCreatorPage)
def list_library_creators(
    repository: LibraryDependency,
    platform: PlatformQuery = None,
    query: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIBRARY_LIMIT)] = 20,
) -> dict[str, object]:
    return repository.list_creators(
        platform=platform,
        query=query,
        offset=offset,
        limit=limit,
    )


@router.get("/creators/{creator_id}", response_model=LibraryCreatorDetail)
def get_library_creator(
    creator_id: str,
    repository: LibraryDependency,
    include_raw: bool = False,
) -> dict[str, object]:
    creator = repository.get_creator(creator_id, include_raw=include_raw)
    if creator is None:
        raise HTTPException(status_code=404, detail="Library creator not found")
    return creator


@router.get("/comments", response_model=LibraryCommentPage)
def list_library_comments(
    repository: LibraryDependency,
    platform: PlatformQuery = None,
    source_content_id: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    parent_comment_id: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIBRARY_LIMIT)] = 20,
) -> dict[str, object]:
    return repository.list_comments(
        platform=platform,
        source_content_id=source_content_id,
        parent_comment_id=parent_comment_id,
        offset=offset,
        limit=limit,
    )

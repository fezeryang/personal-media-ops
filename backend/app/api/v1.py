from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models.agent_api import (
    AgentComment,
    AgentContent,
    AgentContentDetail,
    AgentCreatorDetail,
    AgentProvenance,
    ApiData,
    ApiPage,
)
from app.models.automation import Subscription
from app.models.intelligence import Brief, TrendSignal
from app.security.dependencies import AuthContext, require_scopes

router = APIRouter(prefix="/v1", tags=["agent-api-v1"])
LibraryRead = Annotated[
    AuthContext,
    Depends(require_scopes("library:read")),
]
IntelligenceRead = Annotated[
    AuthContext,
    Depends(require_scopes("intelligence:read")),
]
SubscriptionsRead = Annotated[
    AuthContext,
    Depends(require_scopes("subscriptions:read")),
]


@router.get(
    "/library/search",
    response_model=ApiPage[AgentContent],
    summary="Search normalized library content",
)
def search_contents(
    request: Request,
    auth: LibraryRead,
    q: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
    platform: Annotated[str | None, Query(min_length=2, max_length=32)] = None,
    tag_id: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    is_favorite: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    return request.app.state.agent_tools.search_contents(
        query=q,
        platform=platform,
        tag_id=tag_id,
        is_favorite=is_favorite,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/library/contents/{content_id}",
    response_model=ApiData[AgentContentDetail],
    summary="Get normalized content and provenance",
)
def get_content(
    content_id: str,
    request: Request,
    auth: LibraryRead,
) -> dict[str, object]:
    item = request.app.state.agent_tools.get_content(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"data": item}


@router.get(
    "/library/contents/{content_id}/provenance",
    response_model=ApiData[list[AgentProvenance]],
)
def get_content_provenance(
    content_id: str,
    request: Request,
    auth: LibraryRead,
) -> dict[str, object]:
    items = request.app.state.agent_tools.get_source_provenance(content_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"data": items}


@router.get(
    "/library/creators/{creator_id}",
    response_model=ApiData[AgentCreatorDetail],
)
def get_creator(
    creator_id: str,
    request: Request,
    auth: LibraryRead,
) -> dict[str, object]:
    item = request.app.state.agent_tools.get_creator(creator_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    return {"data": item}


@router.get(
    "/library/creators/{creator_id}/activity",
    response_model=ApiPage[AgentContent],
)
def list_creator_activity(
    creator_id: str,
    request: Request,
    auth: LibraryRead,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    result = request.app.state.agent_tools.list_creator_activity(
        creator_id=creator_id,
        offset=offset,
        limit=limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    return result


@router.get("/library/comments", response_model=ApiPage[AgentComment])
def list_comments(
    request: Request,
    auth: LibraryRead,
    platform: Annotated[str | None, Query(min_length=2, max_length=32)] = None,
    source_content_id: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    parent_comment_id: Annotated[
        str | None,
        Query(min_length=1, max_length=500),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    return request.app.state.agent_tools.list_comments(
        platform=platform,
        source_content_id=source_content_id,
        parent_comment_id=parent_comment_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/intelligence/trends",
    response_model=ApiPage[TrendSignal],
)
def list_trends(
    request: Request,
    auth: IntelligenceRead,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, object]:
    return request.app.state.agent_tools.list_trends(
        offset=offset,
        limit=limit,
    )


@router.get(
    "/intelligence/briefs/latest",
    response_model=ApiData[Brief],
)
def get_latest_brief(
    request: Request,
    auth: IntelligenceRead,
) -> dict[str, object]:
    result = request.app.state.agent_tools.get_latest_brief(
        user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    return result


@router.get(
    "/subscriptions",
    response_model=ApiData[list[Subscription]],
)
def list_subscriptions(
    request: Request,
    auth: SubscriptionsRead,
) -> dict[str, object]:
    return request.app.state.agent_tools.list_subscriptions(user_id=auth.user_id)


@router.get(
    "/subscriptions/{subscription_id}",
    response_model=ApiData[Subscription],
)
def get_subscription(
    subscription_id: str,
    request: Request,
    auth: SubscriptionsRead,
) -> dict[str, object]:
    result = request.app.state.agent_tools.get_subscription_status(
        user_id=auth.user_id,
        subscription_id=subscription_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return result

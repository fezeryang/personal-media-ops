import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.organization import (
    Collection,
    CollectionDetail,
    CollectionItem,
    CollectionItemWrite,
    CollectionWrite,
    FavoriteWrite,
    NameWrite,
    Tag,
)
from app.security.dependencies import (
    AuthContext,
    require_owner_session,
    require_scopes,
)

router = APIRouter(prefix="/library", tags=["library-organization"])
LibraryRead = Annotated[
    AuthContext,
    Depends(require_scopes("library:read")),
]
OwnerWrite = Annotated[
    AuthContext,
    Depends(require_owner_session),
]


@router.get("/tags", response_model=list[Tag])
def list_tags(request: Request, auth: LibraryRead) -> list[dict[str, object]]:
    return request.app.state.organization_repository.list_tags(auth.user_id)


@router.post("/tags", response_model=Tag, status_code=201)
def create_tag(
    payload: NameWrite,
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    try:
        return request.app.state.organization_repository.create_tag(
            user_id=auth.user_id,
            name=payload.name,
        )
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="tag name already exists") from error


@router.patch("/tags/{tag_id}", response_model=Tag)
def rename_tag(
    tag_id: str,
    payload: NameWrite,
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    try:
        tag = request.app.state.organization_repository.rename_tag(
            tag_id=tag_id,
            user_id=auth.user_id,
            name=payload.name,
        )
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="tag name already exists") from error
    if tag is None:
        raise HTTPException(status_code=404, detail="tag not found")
    return tag


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: str, request: Request, auth: OwnerWrite) -> None:
    try:
        deleted = request.app.state.organization_repository.delete_tag(
            tag_id=tag_id,
            user_id=auth.user_id,
        )
    except sqlite3.IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail="tag is still assigned to content",
        ) from error
    if not deleted:
        raise HTTPException(status_code=404, detail="tag not found")


@router.post("/contents/{content_id}/tags/{tag_id}", status_code=204)
def add_content_tag(
    content_id: str,
    tag_id: str,
    request: Request,
    auth: OwnerWrite,
) -> None:
    if not request.app.state.organization_repository.add_tag(
        content_id=content_id,
        tag_id=tag_id,
        user_id=auth.user_id,
    ):
        raise HTTPException(status_code=404, detail="content or tag not found")


@router.delete("/contents/{content_id}/tags/{tag_id}", status_code=204)
def remove_content_tag(
    content_id: str,
    tag_id: str,
    request: Request,
    auth: OwnerWrite,
) -> None:
    if not request.app.state.organization_repository.remove_tag(
        content_id=content_id,
        tag_id=tag_id,
        user_id=auth.user_id,
    ):
        raise HTTPException(status_code=404, detail="content tag not found")


@router.patch("/contents/{content_id}/favorite")
def set_content_favorite(
    content_id: str,
    payload: FavoriteWrite,
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    result = request.app.state.organization_repository.set_favorite(
        content_id,
        payload.is_favorite,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="content not found")
    return result


@router.get("/collections", response_model=list[Collection])
def list_collections(
    request: Request,
    auth: LibraryRead,
) -> list[dict[str, object]]:
    return request.app.state.organization_repository.list_collections(auth.user_id)


@router.post("/collections", response_model=CollectionDetail, status_code=201)
def create_collection(
    payload: CollectionWrite,
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    try:
        return request.app.state.organization_repository.create_collection(
            user_id=auth.user_id,
            name=payload.name,
            description=payload.description,
        )
    except sqlite3.IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail="collection name already exists",
        ) from error


@router.get("/collections/{collection_id}", response_model=CollectionDetail)
def get_collection(
    collection_id: str,
    request: Request,
    auth: LibraryRead,
) -> dict[str, object]:
    result = request.app.state.organization_repository.get_collection(
        collection_id,
        user_id=auth.user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="collection not found")
    return result


@router.put("/collections/{collection_id}", response_model=CollectionDetail)
def update_collection(
    collection_id: str,
    payload: CollectionWrite,
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    try:
        result = request.app.state.organization_repository.update_collection(
            collection_id=collection_id,
            user_id=auth.user_id,
            name=payload.name,
            description=payload.description,
        )
    except sqlite3.IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail="collection name already exists",
        ) from error
    if result is None:
        raise HTTPException(status_code=404, detail="collection not found")
    return result


@router.post(
    "/collections/{collection_id}/items",
    response_model=CollectionItem,
    status_code=201,
)
def add_collection_item(
    collection_id: str,
    payload: CollectionItemWrite,
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    result = request.app.state.organization_repository.add_collection_item(
        collection_id=collection_id,
        user_id=auth.user_id,
        content_id=payload.content_id,
        position=payload.position,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="collection or content not found",
        )
    return result


@router.delete(
    "/collections/{collection_id}/items/{content_id}",
    status_code=204,
)
def remove_collection_item(
    collection_id: str,
    content_id: str,
    request: Request,
    auth: OwnerWrite,
) -> None:
    if not request.app.state.organization_repository.remove_collection_item(
        collection_id=collection_id,
        user_id=auth.user_id,
        content_id=content_id,
    ):
        raise HTTPException(status_code=404, detail="collection item not found")

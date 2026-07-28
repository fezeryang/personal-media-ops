from typing import Any

from app.repositories.automation import AutomationRepository
from app.repositories.intelligence import IntelligenceRepository
from app.repositories.library import LibraryRepository


def _page(result: dict[str, object], items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "data": items,
        "meta": {
            "offset": result["offset"],
            "limit": result["limit"],
            "next_offset": result["next_offset"],
            "has_more": result["has_more"],
        },
    }


def _content(item: dict[str, Any]) -> dict[str, object]:
    return {
        "id": str(item["id"]),
        "content_type": str(item["content_type"]),
        "title": item["title"],
        "description": item["description"],
        "author_id": item["author_source_id"],
        "author_name": item["author_name"],
        "published_at": item["published_at"],
        "first_collected_at": str(item["first_collected_at"]),
        "last_collected_at": str(item["last_collected_at"]),
        "source_keyword": item["source_keyword"],
        "is_favorite": bool(item.get("is_favorite", False)),
        "tags": item.get("tags", []),
        "source": {
            "platform": str(item["platform"]),
            "source_id": str(item["source_content_id"]),
            "url": item["source_url"],
        },
        "metrics": {
            "view_count": item["view_count"],
            "like_count": item["like_count"],
            "favorite_count": item["favorite_count"],
            "comment_count": item["comment_count"],
            "share_count": item["share_count"],
        },
    }


def _creator(item: dict[str, Any]) -> dict[str, object]:
    return {
        "id": str(item["id"]),
        "display_name": item["display_name"],
        "description": item["description"],
        "first_collected_at": str(item["first_collected_at"]),
        "last_collected_at": str(item["last_collected_at"]),
        "source": {
            "platform": str(item["platform"]),
            "source_id": str(item["source_creator_id"]),
            "url": item["profile_url"],
        },
        "metrics": {
            "follower_count": item["follower_count"],
            "following_count": item["following_count"],
            "content_count": item["content_count"],
        },
    }


def _comment(item: dict[str, Any]) -> dict[str, object]:
    return {
        "id": str(item["id"]),
        "source_id": str(item["source_comment_id"]),
        "source_content_id": str(item["source_content_id"]),
        "parent_comment_id": item["parent_comment_id"],
        "author_id": item["author_source_id"],
        "author_name": item["author_name"],
        "body": str(item["body"]),
        "like_count": item["like_count"],
        "reply_count": item["reply_count"],
        "published_at": item["published_at"],
        "collected_at": str(item["collected_at"]),
        "platform": str(item["platform"]),
    }


class AgentToolService:
    """Stable DTO service shared by REST v1 and future Agent transports."""

    def __init__(
        self,
        *,
        library: LibraryRepository,
        intelligence: IntelligenceRepository,
        automation: AutomationRepository,
    ) -> None:
        self.library = library
        self.intelligence = intelligence
        self.automation = automation

    def search_contents(
        self,
        *,
        query: str | None,
        platform: str | None,
        tag_id: str | None,
        is_favorite: bool | None,
        offset: int,
        limit: int,
    ) -> dict[str, object]:
        result = self.library.list_contents(
            platform=platform,
            content_type=None,
            keyword=query,
            creator=None,
            date_from=None,
            date_to=None,
            has_comments=None,
            tag_id=tag_id,
            is_favorite=is_favorite,
            sort="last_collected_desc",
            offset=offset,
            limit=limit,
        )
        return _page(
            result,
            [_content(item) for item in result["items"]],
        )

    def get_content(self, content_id: str) -> dict[str, object] | None:
        item = self.library.get_content(content_id, include_raw=False)
        if item is None:
            return None
        result = _content(item)
        creator = item.get("creator")
        result["creator"] = _creator(creator) if creator else None
        result["comments"] = [_comment(comment) for comment in item["comments"]]
        result["provenance"] = [
            {
                "task_id": str(link["task_id"]),
                "collected_at": str(link["collected_at"]),
            }
            for link in item["tasks"]
        ]
        return result

    def get_creator(self, creator_id: str) -> dict[str, object] | None:
        item = self.library.get_creator(creator_id, include_raw=False)
        if item is None:
            return None
        result = _creator(item)
        result["recent_contents"] = [
            _content(content) for content in item["contents"]
        ]
        result["provenance"] = [
            {
                "task_id": str(link["task_id"]),
                "collected_at": str(link["collected_at"]),
            }
            for link in item["tasks"]
        ]
        return result

    def list_creator_activity(
        self,
        *,
        creator_id: str,
        offset: int,
        limit: int,
    ) -> dict[str, object] | None:
        result = self.library.list_creator_contents(
            creator_id=creator_id,
            offset=offset,
            limit=limit,
        )
        if result is None:
            return None
        return _page(
            result,
            [_content(content) for content in result["items"]],
        )

    def list_comments(
        self,
        *,
        platform: str | None,
        source_content_id: str | None,
        parent_comment_id: str | None,
        offset: int,
        limit: int,
    ) -> dict[str, object]:
        result = self.library.list_comments(
            platform=platform,
            source_content_id=source_content_id,
            parent_comment_id=parent_comment_id,
            offset=offset,
            limit=limit,
        )
        return _page(result, [_comment(item) for item in result["items"]])

    def list_trends(self, *, offset: int, limit: int) -> dict[str, object]:
        result = self.intelligence.list_trends(offset=offset, limit=limit)
        return _page(result, list(result["items"]))

    def get_latest_brief(self, *, user_id: str) -> dict[str, object] | None:
        brief = self.intelligence.get_latest_brief(user_id=user_id)
        return {"data": brief} if brief is not None else None

    def get_source_provenance(
        self,
        content_id: str,
    ) -> list[dict[str, object]] | None:
        item = self.get_content(content_id)
        return None if item is None else list(item["provenance"])

    def list_subscriptions(self, *, user_id: str) -> dict[str, object]:
        return {"data": self.automation.list_subscriptions(user_id)}

    def get_subscription_status(
        self,
        *,
        user_id: str,
        subscription_id: str,
    ) -> dict[str, object] | None:
        item = self.automation.get_subscription(
            subscription_id=subscription_id,
            user_id=user_id,
            include_runs=True,
        )
        return {"data": item} if item is not None else None

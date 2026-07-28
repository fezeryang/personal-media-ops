import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.crawler.results import TaskEntityBatch
from app.db import connect_database
from app.models.library import (
    NormalizedComment,
    NormalizedContent,
    NormalizedCreator,
)
from app.repositories.crawler_tasks import utc_now

ContentSort = Literal[
    "last_collected_desc",
    "published_desc",
    "published_asc",
    "first_collected_desc",
]


def _json_payload(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _read_payload(value: object) -> dict[str, object]:
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _iso_timestamp(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=UTC).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return str(uuid4())


def _page(
    rows: list[sqlite3.Row],
    *,
    offset: int,
    limit: int,
) -> dict[str, object]:
    has_more = len(rows) > limit
    items = [dict(row) for row in rows[:limit]]
    return {
        "items": items,
        "offset": offset,
        "limit": limit,
        "next_offset": offset + len(items),
        "has_more": has_more,
    }


class LibraryRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @staticmethod
    def _existing_id(
        connection: sqlite3.Connection,
        table: str,
        platform: str,
        source_column: str,
        source_id: str,
    ) -> str:
        row = connection.execute(
            f"SELECT id FROM {table} WHERE platform = ? AND {source_column} = ?",
            (platform, source_id),
        ).fetchone()
        return str(row["id"]) if row is not None else _new_id()

    def _upsert_content(
        self,
        connection: sqlite3.Connection,
        item: NormalizedContent,
        collected_at: str,
    ) -> str:
        identifier = self._existing_id(
            connection,
            "library_contents",
            item.platform,
            "source_content_id",
            item.source_content_id,
        )
        connection.execute(
            """
            INSERT INTO library_contents (
                id, platform, source_content_id, content_type, title,
                description, source_url, cover_url, author_source_id,
                author_name, published_at, first_collected_at,
                last_collected_at, source_keyword, view_count, like_count,
                favorite_count, comment_count, share_count, raw_payload,
                created_at, updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?
            )
            ON CONFLICT(platform, source_content_id) DO UPDATE SET
                content_type = excluded.content_type,
                title = COALESCE(excluded.title, library_contents.title),
                description = COALESCE(
                    excluded.description,
                    library_contents.description
                ),
                source_url = COALESCE(
                    excluded.source_url,
                    library_contents.source_url
                ),
                cover_url = COALESCE(
                    excluded.cover_url,
                    library_contents.cover_url
                ),
                author_source_id = COALESCE(
                    excluded.author_source_id,
                    library_contents.author_source_id
                ),
                author_name = COALESCE(
                    excluded.author_name,
                    library_contents.author_name
                ),
                published_at = COALESCE(
                    excluded.published_at,
                    library_contents.published_at
                ),
                last_collected_at = excluded.last_collected_at,
                source_keyword = COALESCE(
                    excluded.source_keyword,
                    library_contents.source_keyword
                ),
                view_count = COALESCE(
                    excluded.view_count,
                    library_contents.view_count
                ),
                like_count = COALESCE(
                    excluded.like_count,
                    library_contents.like_count
                ),
                favorite_count = COALESCE(
                    excluded.favorite_count,
                    library_contents.favorite_count
                ),
                comment_count = COALESCE(
                    excluded.comment_count,
                    library_contents.comment_count
                ),
                share_count = COALESCE(
                    excluded.share_count,
                    library_contents.share_count
                ),
                raw_payload = excluded.raw_payload,
                updated_at = excluded.updated_at
            """,
            (
                identifier,
                item.platform,
                item.source_content_id,
                item.content_type,
                item.title,
                item.description,
                item.source_url,
                item.cover_url,
                item.author_source_id,
                item.author_name,
                _iso_timestamp(item.published_at),
                collected_at,
                collected_at,
                item.source_keyword,
                item.view_count,
                item.like_count,
                item.favorite_count,
                item.comment_count,
                item.share_count,
                _json_payload(item.raw_payload),
                collected_at,
                collected_at,
            ),
        )
        row = connection.execute(
            """
            SELECT id FROM library_contents
            WHERE platform = ? AND source_content_id = ?
            """,
            (item.platform, item.source_content_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("upserted content could not be read")
        return str(row["id"])

    def _upsert_creator(
        self,
        connection: sqlite3.Connection,
        item: NormalizedCreator,
        collected_at: str,
    ) -> str:
        identifier = self._existing_id(
            connection,
            "library_creators",
            item.platform,
            "source_creator_id",
            item.source_creator_id,
        )
        connection.execute(
            """
            INSERT INTO library_creators (
                id, platform, source_creator_id, display_name, profile_url,
                avatar_url, description, follower_count, following_count,
                content_count, first_collected_at, last_collected_at,
                raw_payload, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, source_creator_id) DO UPDATE SET
                display_name = COALESCE(
                    excluded.display_name,
                    library_creators.display_name
                ),
                profile_url = COALESCE(
                    excluded.profile_url,
                    library_creators.profile_url
                ),
                avatar_url = COALESCE(
                    excluded.avatar_url,
                    library_creators.avatar_url
                ),
                description = COALESCE(
                    excluded.description,
                    library_creators.description
                ),
                follower_count = COALESCE(
                    excluded.follower_count,
                    library_creators.follower_count
                ),
                following_count = COALESCE(
                    excluded.following_count,
                    library_creators.following_count
                ),
                content_count = COALESCE(
                    excluded.content_count,
                    library_creators.content_count
                ),
                last_collected_at = excluded.last_collected_at,
                raw_payload = CASE
                    WHEN excluded.raw_payload = '{}' THEN library_creators.raw_payload
                    ELSE excluded.raw_payload
                END,
                updated_at = excluded.updated_at
            """,
            (
                identifier,
                item.platform,
                item.source_creator_id,
                item.display_name,
                item.profile_url,
                item.avatar_url,
                item.description,
                item.follower_count,
                item.following_count,
                item.content_count,
                collected_at,
                collected_at,
                _json_payload(item.raw_payload),
                collected_at,
                collected_at,
            ),
        )
        row = connection.execute(
            """
            SELECT id FROM library_creators
            WHERE platform = ? AND source_creator_id = ?
            """,
            (item.platform, item.source_creator_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("upserted creator could not be read")
        return str(row["id"])

    def _upsert_comment(
        self,
        connection: sqlite3.Connection,
        item: NormalizedComment,
        collected_at: str,
    ) -> str:
        identifier = self._existing_id(
            connection,
            "library_comments",
            item.platform,
            "source_comment_id",
            item.source_comment_id,
        )
        connection.execute(
            """
            INSERT INTO library_comments (
                id, platform, source_comment_id, source_content_id,
                parent_comment_id, author_source_id, author_name, body,
                like_count, reply_count, published_at, collected_at,
                raw_payload, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, source_comment_id) DO UPDATE SET
                source_content_id = excluded.source_content_id,
                parent_comment_id = COALESCE(
                    excluded.parent_comment_id,
                    library_comments.parent_comment_id
                ),
                author_source_id = COALESCE(
                    excluded.author_source_id,
                    library_comments.author_source_id
                ),
                author_name = COALESCE(
                    excluded.author_name,
                    library_comments.author_name
                ),
                body = excluded.body,
                like_count = COALESCE(
                    excluded.like_count,
                    library_comments.like_count
                ),
                reply_count = COALESCE(
                    excluded.reply_count,
                    library_comments.reply_count
                ),
                published_at = COALESCE(
                    excluded.published_at,
                    library_comments.published_at
                ),
                collected_at = excluded.collected_at,
                raw_payload = excluded.raw_payload,
                updated_at = excluded.updated_at
            """,
            (
                identifier,
                item.platform,
                item.source_comment_id,
                item.source_content_id,
                item.parent_comment_id,
                item.author_source_id,
                item.author_name,
                item.body,
                item.like_count,
                item.reply_count,
                _iso_timestamp(item.published_at),
                collected_at,
                _json_payload(item.raw_payload),
                collected_at,
                collected_at,
            ),
        )
        row = connection.execute(
            """
            SELECT id FROM library_comments
            WHERE platform = ? AND source_comment_id = ?
            """,
            (item.platform, item.source_comment_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("upserted comment could not be read")
        return str(row["id"])

    def ingest_task(
        self,
        *,
        task_id: str,
        batch: TaskEntityBatch,
    ) -> dict[str, int]:
        collected_at = utc_now()
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT status FROM crawler_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if task is None:
                raise RuntimeError("crawler task disappeared during ingestion")
            if task["status"] not in {"running", "waiting_login"}:
                raise RuntimeError("crawler task is not active during ingestion")

            creator_ids: dict[tuple[str, str], str] = {}
            content_ids: list[str] = []
            comment_ids: list[str] = []
            task_creator_ids: set[str] = set()

            for creator in batch.creators:
                identifier = self._upsert_creator(
                    connection,
                    creator,
                    collected_at,
                )
                creator_ids[(creator.platform, creator.source_creator_id)] = identifier
                task_creator_ids.add(identifier)

            for content in batch.contents:
                identifier = self._upsert_content(connection, content, collected_at)
                content_ids.append(identifier)
                if content.author_source_id is not None:
                    creator_key = (content.platform, content.author_source_id)
                    creator_id = creator_ids.get(creator_key)
                    if creator_id is None:
                        placeholder = NormalizedCreator(
                            platform=content.platform,
                            source_creator_id=content.author_source_id,
                            display_name=content.author_name,
                            profile_url=None,
                            avatar_url=None,
                            description=None,
                            follower_count=None,
                            following_count=None,
                            content_count=None,
                            raw_payload={},
                        )
                        creator_id = self._upsert_creator(
                            connection,
                            placeholder,
                            collected_at,
                        )
                        creator_ids[creator_key] = creator_id
                    task_creator_ids.add(creator_id)
                    connection.execute(
                        """
                        INSERT INTO content_creator_links (
                            content_id, creator_id, first_collected_at,
                            last_collected_at
                        )
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(content_id, creator_id) DO UPDATE SET
                            last_collected_at = excluded.last_collected_at
                        """,
                        (identifier, creator_id, collected_at, collected_at),
                    )

            for comment in batch.comments:
                comment_ids.append(
                    self._upsert_comment(connection, comment, collected_at)
                )

            for entity_type, identifiers in (
                ("content", content_ids),
                ("creator", sorted(task_creator_ids)),
                ("comment", comment_ids),
            ):
                for identifier in identifiers:
                    connection.execute(
                        """
                        INSERT INTO crawl_task_entities (
                            task_id, entity_type, entity_id, collected_at
                        )
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(task_id, entity_type, entity_id)
                        DO UPDATE SET collected_at = excluded.collected_at
                        """,
                        (task_id, entity_type, identifier, collected_at),
                    )

            updated = connection.execute(
                """
                UPDATE crawler_tasks
                SET status = 'succeeded', actual_count = ?, finished_at = ?,
                    error_message = NULL
                WHERE id = ? AND status IN ('running', 'waiting_login')
                """,
                (batch.actual_count, collected_at, task_id),
            )
            if updated.rowcount != 1:
                raise RuntimeError("crawler task completion state changed")
            connection.commit()
            return {
                "contents": len(content_ids),
                "creators": len(task_creator_ids),
                "comments": len(comment_ids),
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_contents(
        self,
        *,
        platform: str | None = None,
        content_type: str | None = None,
        keyword: str | None = None,
        creator: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        has_comments: bool | None = None,
        sort: ContentSort = "last_collected_desc",
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, object]:
        clauses: list[str] = []
        values: list[object] = []
        if platform:
            clauses.append("c.platform = ?")
            values.append(platform)
        if content_type:
            clauses.append("c.content_type = ?")
            values.append(content_type)
        if keyword:
            clauses.append(
                "(c.source_keyword LIKE ? OR c.title LIKE ? OR c.description LIKE ?)"
            )
            pattern = f"%{keyword}%"
            values.extend((pattern, pattern, pattern))
        if creator:
            clauses.append("(c.author_source_id = ? OR c.author_name LIKE ?)")
            values.extend((creator, f"%{creator}%"))
        if date_from:
            clauses.append("c.published_at >= ?")
            values.append(date_from)
        if date_to:
            clauses.append("c.published_at <= ?")
            values.append(date_to)
        comment_exists = (
            "EXISTS (SELECT 1 FROM library_comments cm "
            "WHERE cm.platform = c.platform "
            "AND cm.source_content_id = c.source_content_id)"
        )
        if has_comments is not None:
            clauses.append(comment_exists if has_comments else f"NOT {comment_exists}")
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        order_by = {
            "last_collected_desc": "c.last_collected_at DESC, c.id DESC",
            "published_desc": "c.published_at DESC, c.id DESC",
            "published_asc": "c.published_at ASC, c.id ASC",
            "first_collected_desc": "c.first_collected_at DESC, c.id DESC",
        }[sort]
        values.extend((limit + 1, offset))
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT c.id, c.platform, c.source_content_id, c.content_type,
                       c.title, c.description, c.source_url, c.cover_url,
                       c.author_source_id, c.author_name, c.published_at,
                       c.first_collected_at, c.last_collected_at,
                       c.source_keyword, c.view_count, c.like_count,
                       c.favorite_count, c.comment_count, c.share_count,
                       {comment_exists} AS has_comments
                FROM library_contents c
                {where}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
                """,
                values,
            ).fetchall()
        page = _page(rows, offset=offset, limit=limit)
        for item in page["items"]:
            item["has_comments"] = bool(item["has_comments"])
        return page

    def get_content(
        self,
        content_id: str,
        *,
        include_raw: bool = False,
    ) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT c.*,
                       EXISTS (
                           SELECT 1 FROM library_comments cm
                           WHERE cm.platform = c.platform
                             AND cm.source_content_id = c.source_content_id
                       ) AS has_comments
                FROM library_contents c
                WHERE c.id = ?
                """,
                (content_id,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["has_comments"] = bool(result["has_comments"])
            raw_payload = result.pop("raw_payload")
            result["raw_payload"] = _read_payload(raw_payload) if include_raw else None
            creator = connection.execute(
                """
                SELECT cr.id, cr.platform, cr.source_creator_id,
                       cr.display_name, cr.profile_url, cr.avatar_url,
                       cr.description, cr.follower_count, cr.following_count,
                       cr.content_count, cr.first_collected_at,
                       cr.last_collected_at
                FROM library_creators cr
                JOIN content_creator_links link ON link.creator_id = cr.id
                WHERE link.content_id = ?
                ORDER BY link.last_collected_at DESC
                LIMIT 1
                """,
                (content_id,),
            ).fetchone()
            comments = connection.execute(
                """
                SELECT id, platform, source_comment_id, source_content_id,
                       parent_comment_id, author_source_id, author_name, body,
                       like_count, reply_count, published_at, collected_at
                FROM library_comments
                WHERE platform = ? AND source_content_id = ?
                ORDER BY published_at ASC, id ASC
                LIMIT 100
                """,
                (result["platform"], result["source_content_id"]),
            ).fetchall()
            tasks = connection.execute(
                """
                SELECT task_id, collected_at
                FROM crawl_task_entities
                WHERE entity_type = 'content' AND entity_id = ?
                ORDER BY collected_at DESC
                """,
                (content_id,),
            ).fetchall()
        result["creator"] = dict(creator) if creator is not None else None
        result["comments"] = [dict(item) for item in comments]
        result["tasks"] = [dict(item) for item in tasks]
        return result

    def list_creators(
        self,
        *,
        platform: str | None = None,
        query: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, object]:
        clauses: list[str] = []
        values: list[object] = []
        if platform:
            clauses.append("platform = ?")
            values.append(platform)
        if query:
            clauses.append("(source_creator_id = ? OR display_name LIKE ?)")
            values.extend((query, f"%{query}%"))
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        values.extend((limit + 1, offset))
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT id, platform, source_creator_id, display_name,
                       profile_url, avatar_url, description, follower_count,
                       following_count, content_count, first_collected_at,
                       last_collected_at
                FROM library_creators
                {where}
                ORDER BY last_collected_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                values,
            ).fetchall()
        return _page(rows, offset=offset, limit=limit)

    def get_creator(
        self,
        creator_id: str,
        *,
        include_raw: bool = False,
    ) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM library_creators WHERE id = ?",
                (creator_id,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            raw_payload = result.pop("raw_payload")
            result["raw_payload"] = _read_payload(raw_payload) if include_raw else None
            contents = connection.execute(
                """
                SELECT c.id, c.platform, c.source_content_id, c.content_type,
                       c.title, c.description, c.source_url, c.cover_url,
                       c.author_source_id, c.author_name, c.published_at,
                       c.first_collected_at, c.last_collected_at,
                       c.source_keyword, c.view_count, c.like_count,
                       c.favorite_count, c.comment_count, c.share_count,
                       EXISTS (
                           SELECT 1 FROM library_comments cm
                           WHERE cm.platform = c.platform
                             AND cm.source_content_id = c.source_content_id
                       ) AS has_comments
                FROM library_contents c
                JOIN content_creator_links link ON link.content_id = c.id
                WHERE link.creator_id = ?
                ORDER BY c.last_collected_at DESC
                LIMIT 100
                """,
                (creator_id,),
            ).fetchall()
            tasks = connection.execute(
                """
                SELECT task_id, collected_at
                FROM crawl_task_entities
                WHERE entity_type = 'creator' AND entity_id = ?
                ORDER BY collected_at DESC
                """,
                (creator_id,),
            ).fetchall()
        result["contents"] = [dict(item) for item in contents]
        for content in result["contents"]:
            content["has_comments"] = bool(content["has_comments"])
        result["tasks"] = [dict(item) for item in tasks]
        return result

    def list_comments(
        self,
        *,
        platform: str | None = None,
        source_content_id: str | None = None,
        parent_comment_id: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, object]:
        clauses: list[str] = []
        values: list[object] = []
        if platform:
            clauses.append("platform = ?")
            values.append(platform)
        if source_content_id:
            clauses.append("source_content_id = ?")
            values.append(source_content_id)
        if parent_comment_id:
            clauses.append("parent_comment_id = ?")
            values.append(parent_comment_id)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        values.extend((limit + 1, offset))
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT id, platform, source_comment_id, source_content_id,
                       parent_comment_id, author_source_id, author_name, body,
                       like_count, reply_count, published_at, collected_at
                FROM library_comments
                {where}
                ORDER BY collected_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                values,
            ).fetchall()
        return _page(rows, offset=offset, limit=limit)

    def counts(self) -> dict[str, int]:
        with connect_database(self.database_path) as connection:
            return {
                "contents": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM library_contents"
                    ).fetchone()[0]
                ),
                "creators": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM library_creators"
                    ).fetchone()[0]
                ),
                "comments": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM library_comments"
                    ).fetchone()[0]
                ),
            }

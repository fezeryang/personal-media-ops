import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db import connect_database
from app.repositories.crawler_tasks import utc_now


class OrganizationRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def list_tags(self, user_id: str) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT tag.id, tag.name, tag.created_at, tag.updated_at,
                           COUNT(link.content_id) AS content_count
                    FROM library_tags tag
                    LEFT JOIN library_content_tags link ON link.tag_id = tag.id
                    WHERE tag.user_id = ?
                    GROUP BY tag.id
                    ORDER BY tag.name COLLATE NOCASE
                    """,
                    (user_id,),
                ).fetchall()
            ]

    def create_tag(self, *, user_id: str, name: str) -> dict[str, Any]:
        identifier = str(uuid4())
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO library_tags (
                    id, user_id, name, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (identifier, user_id, name, now, now),
            )
        return self.get_tag(identifier, user_id=user_id) or {}

    def get_tag(self, tag_id: str, *, user_id: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT tag.id, tag.name, tag.created_at, tag.updated_at,
                       COUNT(link.content_id) AS content_count
                FROM library_tags tag
                LEFT JOIN library_content_tags link ON link.tag_id = tag.id
                WHERE tag.id = ? AND tag.user_id = ?
                GROUP BY tag.id
                """,
                (tag_id, user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def rename_tag(
        self,
        *,
        tag_id: str,
        user_id: str,
        name: str,
    ) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            updated = connection.execute(
                """
                UPDATE library_tags SET name = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (name, utc_now(), tag_id, user_id),
            )
        return (
            self.get_tag(tag_id, user_id=user_id)
            if updated.rowcount == 1
            else None
        )

    def delete_tag(self, *, tag_id: str, user_id: str) -> bool:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            used = connection.execute(
                """
                SELECT 1
                FROM library_content_tags link
                JOIN library_tags tag ON tag.id = link.tag_id
                WHERE tag.id = ? AND tag.user_id = ?
                LIMIT 1
                """,
                (tag_id, user_id),
            ).fetchone()
            if used is not None:
                raise sqlite3.IntegrityError("tag is still assigned to content")
            deleted = connection.execute(
                "DELETE FROM library_tags WHERE id = ? AND user_id = ?",
                (tag_id, user_id),
            )
            connection.commit()
            return deleted.rowcount == 1
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def add_tag(
        self,
        *,
        content_id: str,
        tag_id: str,
        user_id: str,
    ) -> bool:
        with connect_database(self.database_path) as connection:
            tag = connection.execute(
                "SELECT 1 FROM library_tags WHERE id = ? AND user_id = ?",
                (tag_id, user_id),
            ).fetchone()
            content = connection.execute(
                "SELECT 1 FROM library_contents WHERE id = ?",
                (content_id,),
            ).fetchone()
            if tag is None or content is None:
                return False
            connection.execute(
                """
                INSERT INTO library_content_tags (content_id, tag_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(content_id, tag_id) DO NOTHING
                """,
                (content_id, tag_id, utc_now()),
            )
            return True

    def remove_tag(
        self,
        *,
        content_id: str,
        tag_id: str,
        user_id: str,
    ) -> bool:
        with connect_database(self.database_path) as connection:
            deleted = connection.execute(
                """
                DELETE FROM library_content_tags
                WHERE content_id = ? AND tag_id IN (
                    SELECT id FROM library_tags
                    WHERE id = ? AND user_id = ?
                )
                """,
                (content_id, tag_id, user_id),
            )
        return deleted.rowcount == 1

    def set_favorite(self, content_id: str, value: bool) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            updated = connection.execute(
                """
                UPDATE library_contents
                SET is_favorite = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(value), utc_now(), content_id),
            )
            row = connection.execute(
                """
                SELECT id, is_favorite
                FROM library_contents WHERE id = ?
                """,
                (content_id,),
            ).fetchone()
        if updated.rowcount != 1 or row is None:
            return None
        return {"id": str(row["id"]), "is_favorite": bool(row["is_favorite"])}

    def list_collections(self, user_id: str) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT collection.id, collection.name,
                           collection.description, collection.created_at,
                           collection.updated_at,
                           COUNT(item.content_id) AS content_count
                    FROM library_collections collection
                    LEFT JOIN library_collection_items item
                      ON item.collection_id = collection.id
                    WHERE collection.user_id = ?
                    GROUP BY collection.id
                    ORDER BY collection.updated_at DESC, collection.id DESC
                    """,
                    (user_id,),
                ).fetchall()
            ]

    def create_collection(
        self,
        *,
        user_id: str,
        name: str,
        description: str | None,
    ) -> dict[str, Any]:
        identifier = str(uuid4())
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO library_collections (
                    id, user_id, name, description, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (identifier, user_id, name, description, now, now),
            )
        return self.get_collection(identifier, user_id=user_id) or {}

    def update_collection(
        self,
        *,
        collection_id: str,
        user_id: str,
        name: str,
        description: str | None,
    ) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            updated = connection.execute(
                """
                UPDATE library_collections
                SET name = ?, description = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (name, description, utc_now(), collection_id, user_id),
            )
        return (
            self.get_collection(collection_id, user_id=user_id)
            if updated.rowcount == 1
            else None
        )

    def get_collection(
        self,
        collection_id: str,
        *,
        user_id: str,
    ) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT collection.id, collection.name, collection.description,
                       collection.created_at, collection.updated_at,
                       COUNT(item.content_id) AS content_count
                FROM library_collections collection
                LEFT JOIN library_collection_items item
                  ON item.collection_id = collection.id
                WHERE collection.id = ? AND collection.user_id = ?
                GROUP BY collection.id
                """,
                (collection_id, user_id),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            items = connection.execute(
                """
                SELECT item.position, item.created_at,
                       content.id, content.platform,
                       content.source_content_id, content.content_type,
                       content.title, content.description, content.source_url,
                       content.cover_url, content.author_source_id,
                       content.author_name, content.published_at,
                       content.first_collected_at, content.last_collected_at,
                       content.source_keyword, content.view_count,
                       content.like_count, content.favorite_count,
                       content.comment_count, content.share_count,
                       content.is_favorite,
                       EXISTS (
                           SELECT 1 FROM library_comments comment
                           WHERE comment.platform = content.platform
                             AND comment.source_content_id =
                                 content.source_content_id
                       ) AS has_comments
                FROM library_collection_items item
                JOIN library_contents content ON content.id = item.content_id
                WHERE item.collection_id = ?
                ORDER BY item.position
                """,
                (collection_id,),
            ).fetchall()
            result["items"] = []
            for item in items:
                content = dict(item)
                position = int(content.pop("position"))
                created_at = str(content.pop("created_at"))
                content["has_comments"] = bool(content["has_comments"])
                content["is_favorite"] = bool(content["is_favorite"])
                content["tags"] = []
                result["items"].append(
                    {
                        "content": content,
                        "position": position,
                        "created_at": created_at,
                    }
                )
            return result

    def add_collection_item(
        self,
        *,
        collection_id: str,
        user_id: str,
        content_id: str,
        position: int,
    ) -> dict[str, Any] | None:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                """
                SELECT 1 FROM library_collections
                WHERE id = ? AND user_id = ?
                """,
                (collection_id, user_id),
            ).fetchone()
            content = connection.execute(
                "SELECT 1 FROM library_contents WHERE id = ?",
                (content_id,),
            ).fetchone()
            if owner is None or content is None:
                connection.rollback()
                return None
            existing = [
                str(row["content_id"])
                for row in connection.execute(
                    """
                    SELECT content_id FROM library_collection_items
                    WHERE collection_id = ?
                    ORDER BY position
                    """,
                    (collection_id,),
                ).fetchall()
                if str(row["content_id"]) != content_id
            ]
            insert_at = min(position, len(existing))
            existing.insert(insert_at, content_id)
            connection.execute(
                """
                INSERT INTO library_collection_items (
                    collection_id, content_id, position, created_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(collection_id, content_id)
                DO UPDATE SET position = excluded.position
                """,
                (collection_id, content_id, len(existing) + 1000, utc_now()),
            )
            self._reindex_collection(connection, collection_id, existing)
            connection.execute(
                "UPDATE library_collections SET updated_at = ? WHERE id = ?",
                (utc_now(), collection_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        detail = self.get_collection(collection_id, user_id=user_id)
        if detail is None:
            return None
        return next(
            (
                item
                for item in detail["items"]
                if item["content"]["id"] == content_id
            ),
            None,
        )

    @staticmethod
    def _reindex_collection(
        connection: sqlite3.Connection,
        collection_id: str,
        content_ids: list[str],
    ) -> None:
        for index, content_id in enumerate(content_ids):
            connection.execute(
                """
                UPDATE library_collection_items
                SET position = ?
                WHERE collection_id = ? AND content_id = ?
                """,
                (100_000 + index, collection_id, content_id),
            )
        for index, content_id in enumerate(content_ids):
            connection.execute(
                """
                UPDATE library_collection_items
                SET position = ?
                WHERE collection_id = ? AND content_id = ?
                """,
                (index, collection_id, content_id),
            )

    def remove_collection_item(
        self,
        *,
        collection_id: str,
        user_id: str,
        content_id: str,
    ) -> bool:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                """
                SELECT 1 FROM library_collections
                WHERE id = ? AND user_id = ?
                """,
                (collection_id, user_id),
            ).fetchone()
            if owner is None:
                connection.rollback()
                return False
            deleted = connection.execute(
                """
                DELETE FROM library_collection_items
                WHERE collection_id = ? AND content_id = ?
                """,
                (collection_id, content_id),
            )
            remaining = [
                str(row["content_id"])
                for row in connection.execute(
                    """
                    SELECT content_id FROM library_collection_items
                    WHERE collection_id = ? ORDER BY position
                    """,
                    (collection_id,),
                ).fetchall()
            ]
            self._reindex_collection(connection, collection_id, remaining)
            connection.execute(
                "UPDATE library_collections SET updated_at = ? WHERE id = ?",
                (utc_now(), collection_id),
            )
            connection.commit()
            return deleted.rowcount == 1
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.crawler.registry import (
    ModeDisabledError,
    PlatformDisabledError,
    UnsupportedPlatformError,
    platform_registry,
)
from app.repositories.automation import AutomationRepository
from app.repositories.library import LibraryRepository


class AutomationCapabilityError(RuntimeError):
    pass


class AutomationNotFoundError(RuntimeError):
    pass


class AutomationConflictError(RuntimeError):
    pass


class AutomationCoordinator:
    def __init__(
        self,
        repository: AutomationRepository,
        settings: Settings,
        *,
        library_repository: LibraryRepository | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.library_repository = library_repository or LibraryRepository(
            settings.database_path
        )

    def _require_production_mode(self, platform: str, mode: str) -> None:
        try:
            adapter = platform_registry.require_mode_enabled(
                platform,
                mode,
                self.settings.enabled_platforms,
            )
        except (
            UnsupportedPlatformError,
            PlatformDisabledError,
            ModeDisabledError,
        ) as error:
            raise AutomationCapabilityError(str(error)) from error
        if adapter.mode_statuses.get(mode) != "production_verified":
            raise AutomationCapabilityError(
                f"{platform}/{mode} is not production verified"
            )

    def validate_subscription_platforms(
        self,
        platforms: Sequence[Mapping[str, object]],
    ) -> None:
        for item in platforms:
            self._require_production_mode(str(item["platform"]), "search")

    def create_subscription(
        self,
        *,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.validate_subscription_platforms(payload["platforms"])
        try:
            return self.repository.create_subscription(
                user_id=user_id,
                **payload,
            )
        except sqlite3.IntegrityError as error:
            raise AutomationConflictError("subscription name already exists") from error

    def update_subscription(
        self,
        *,
        subscription_id: str,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.validate_subscription_platforms(payload["platforms"])
        try:
            result = self.repository.update_subscription(
                subscription_id=subscription_id,
                user_id=user_id,
                **payload,
            )
        except sqlite3.IntegrityError as error:
            raise AutomationConflictError("subscription name already exists") from error
        if result is None:
            raise AutomationNotFoundError("subscription not found")
        return result

    def set_subscription_enabled(
        self,
        *,
        subscription_id: str,
        user_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        if enabled:
            subscription = self.repository.get_subscription(
                subscription_id=subscription_id,
                user_id=user_id,
                include_runs=False,
            )
            if subscription is None:
                raise AutomationNotFoundError("subscription not found")
            self.validate_subscription_platforms(subscription["platforms"])
        result = self.repository.set_subscription_enabled(
            subscription_id=subscription_id,
            user_id=user_id,
            enabled=enabled,
        )
        if result is None:
            raise AutomationNotFoundError("subscription not found")
        return result

    def manual_subscription_run(
        self,
        *,
        subscription_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        subscription = self.repository.get_subscription(
            subscription_id=subscription_id,
            user_id=user_id,
            include_runs=False,
        )
        if subscription is None:
            raise AutomationNotFoundError("subscription not found")
        self.validate_subscription_platforms(subscription["platforms"])
        try:
            result = self.repository.create_manual_subscription_run(
                subscription_id=subscription_id,
                user_id=user_id,
            )
        except sqlite3.IntegrityError as error:
            raise AutomationConflictError(str(error)) from error
        if result is None:
            raise AutomationNotFoundError("subscription not found")
        return result

    def schedule_due(self, now: datetime) -> int:
        self._disable_invalid_due_subscriptions(now)
        self._disable_invalid_due_watches(now)
        subscriptions = self.repository.schedule_due_subscriptions(now)
        watches = self.repository.schedule_due_watches(now)
        return subscriptions + watches

    def _disable_invalid_due_subscriptions(self, now: datetime) -> None:
        now_text = now.isoformat().replace("+00:00", "Z")
        connection = sqlite3.connect(self.settings.database_path)
        connection.row_factory = sqlite3.Row
        try:
            due = connection.execute(
                """
                SELECT subscription.id, platform.platform
                FROM subscriptions subscription
                JOIN subscription_platforms platform
                  ON platform.subscription_id = subscription.id
                WHERE subscription.enabled = 1
                  AND subscription.next_run_at IS NOT NULL
                  AND subscription.next_run_at <= ?
                """,
                (now_text,),
            ).fetchall()
            invalid: dict[str, str] = {}
            for item in due:
                try:
                    self._require_production_mode(str(item["platform"]), "search")
                except AutomationCapabilityError as error:
                    invalid[str(item["id"])] = str(error)
            for subscription_id, error in invalid.items():
                connection.execute(
                    """
                    UPDATE subscriptions
                    SET enabled = 0, next_run_at = NULL, last_error = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (error[:2000], now_text, subscription_id),
                )
            connection.commit()
        finally:
            connection.close()

    def _disable_invalid_due_watches(self, now: datetime) -> None:
        now_text = now.isoformat().replace("+00:00", "Z")
        connection = sqlite3.connect(self.settings.database_path)
        connection.row_factory = sqlite3.Row
        try:
            due = connection.execute(
                """
                SELECT id, platform FROM creator_watchlist
                WHERE enabled = 1 AND next_check_at IS NOT NULL
                  AND next_check_at <= ?
                """,
                (now_text,),
            ).fetchall()
            for item in due:
                try:
                    self._require_production_mode(
                        str(item["platform"]),
                        "creator",
                    )
                except AutomationCapabilityError as error:
                    connection.execute(
                        """
                        UPDATE creator_watchlist
                        SET enabled = 0, next_check_at = NULL,
                            last_error = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (str(error)[:2000], now_text, item["id"]),
                    )
            connection.commit()
        finally:
            connection.close()

    def reconcile_runs(self) -> None:
        self.repository.reconcile_subscription_runs()
        self.repository.reconcile_watch_runs()

    def create_watch(
        self,
        *,
        user_id: str,
        creator_id: str,
        enabled: bool,
        check_frequency: str,
        requested_count: int,
        timezone: str,
    ) -> dict[str, Any]:
        creator = self.library_repository.get_creator(creator_id)
        if creator is None:
            raise AutomationNotFoundError("creator not found")
        self._require_production_mode(str(creator["platform"]), "creator")
        try:
            return self.repository.create_watch(
                user_id=user_id,
                creator_id=creator_id,
                enabled=enabled,
                check_frequency=check_frequency,
                requested_count=requested_count,
                timezone=timezone,
            )
        except sqlite3.IntegrityError as error:
            raise AutomationConflictError("creator is already watched") from error

    def manual_watch_run(
        self,
        *,
        watch_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        watch = self.repository.get_watch(watch_id, user_id=user_id)
        if watch is None:
            raise AutomationNotFoundError("watch not found")
        self._require_production_mode(str(watch["platform"]), "creator")
        try:
            result = self.repository.create_manual_watch_run(
                watch_id=watch_id,
                user_id=user_id,
            )
        except sqlite3.IntegrityError as error:
            raise AutomationConflictError(str(error)) from error
        if result is None:
            raise AutomationNotFoundError("watch not found")
        return result

    def set_watch_enabled(
        self,
        *,
        watch_id: str,
        user_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        if enabled:
            watch = self.repository.get_watch(watch_id, user_id=user_id)
            if watch is None:
                raise AutomationNotFoundError("watch not found")
            self._require_production_mode(str(watch["platform"]), "creator")
        result = self.repository.set_watch_enabled(
            watch_id=watch_id,
            user_id=user_id,
            enabled=enabled,
        )
        if result is None:
            raise AutomationNotFoundError("watch not found")
        return result

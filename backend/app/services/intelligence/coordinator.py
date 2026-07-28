from datetime import UTC, datetime, timedelta

from app.repositories.intelligence import (
    BriefConflictError,
    IntelligenceRepository,
)
from app.services.intelligence.briefs import BriefGenerator
from app.services.intelligence.trends import TrendService


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class IntelligenceCoordinator:
    """Runs low-resource deterministic intelligence jobs inside the Worker."""

    def __init__(
        self,
        repository: IntelligenceRepository,
        trend_service: TrendService,
        brief_generator: BriefGenerator,
    ) -> None:
        self.repository = repository
        self.trend_service = trend_service
        self.brief_generator = brief_generator

    def schedule_due(self, now: datetime) -> int:
        schedules = self.repository.claim_due_brief_schedules(now=now)
        completed = 0
        for schedule in schedules:
            try:
                window_end = datetime.fromisoformat(
                    str(schedule["scheduled_for"])
                ).astimezone(UTC)
                window_start = window_end - timedelta(hours=24)
                self.trend_service.generate(
                    window_end=window_end,
                    window_hours=24,
                )
                self.brief_generator.generate(
                    user_id=str(schedule["user_id"]),
                    window_start=_utc(window_start),
                    window_end=_utc(window_end),
                    timezone=str(schedule["timezone"]),
                    regenerate=False,
                )
            except BriefConflictError:
                pass
            except Exception as error:  # noqa: BLE001 - isolate worker job boundary
                self.repository.record_brief_schedule_outcome(
                    schedule_id=str(schedule["id"]),
                    error=f"brief generation failed: {error}",
                )
                continue
            self.repository.record_brief_schedule_outcome(
                schedule_id=str(schedule["id"]),
                error=None,
            )
            completed += 1
        return completed

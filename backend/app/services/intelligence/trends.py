from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.repositories.intelligence import IntelligenceRepository

FORMULA_VERSION = "rules-v1"


@dataclass(frozen=True)
class TrendScores:
    score: float
    volume_score: float
    velocity_score: float
    cross_platform_score: float
    engagement_score: float


def _bounded(value: float) -> float:
    return round(min(max(value, 0), 100), 2)


def calculate_trend_scores(
    *,
    current_volume: int,
    previous_volume: int,
    platform_count: int,
    engagement_change: float,
) -> TrendScores:
    volume = _bounded(current_volume * 10)
    velocity = _bounded(
        max(current_volume - previous_volume, 0)
        / max(previous_volume, 3)
        * 50
    )
    cross_platform = _bounded(platform_count / 3 * 100)
    engagement = _bounded(max(engagement_change, 0) * 50)
    score = round(
        0.35 * volume
        + 0.30 * velocity
        + 0.20 * cross_platform
        + 0.15 * engagement,
        2,
    )
    return TrendScores(
        score=score,
        volume_score=volume,
        velocity_score=velocity,
        cross_platform_score=cross_platform,
        engagement_score=engagement,
    )


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class TrendService:
    def __init__(self, repository: IntelligenceRepository) -> None:
        self.repository = repository

    def generate(
        self,
        *,
        window_end: datetime,
        window_hours: int,
    ) -> list[dict[str, object]]:
        current_end = window_end.astimezone(UTC)
        current_start = current_end - timedelta(hours=window_hours)
        previous_start = current_start - timedelta(hours=window_hours)
        results: list[dict[str, object]] = []
        for topic in self.repository.source_topics():
            current = self.repository.topic_contents(
                topic=topic,
                window_start=_utc(current_start),
                window_end=_utc(current_end),
            )
            previous = self.repository.topic_contents(
                topic=topic,
                window_start=_utc(previous_start),
                window_end=_utc(current_start),
            )
            platforms = sorted({str(item["platform"]) for item in current})
            engagement_change = self.repository.topic_engagement_change(
                topic=topic,
                window_start=_utc(current_start),
                window_end=_utc(current_end),
            )
            scores = calculate_trend_scores(
                current_volume=len(current),
                previous_volume=len(previous),
                platform_count=len(platforms),
                engagement_change=engagement_change,
            )
            sufficient = len(current) >= 3 and len(current) + len(previous) >= 5
            status = "detected" if sufficient else "insufficient_data"
            evidence: dict[str, object] = {
                "current_volume": len(current),
                "previous_volume": len(previous),
                "platform_count": len(platforms),
                "minimum_current_volume": 3,
                "minimum_total_volume": 5,
                "engagement_change": round(engagement_change, 4),
            }
            explanation = (
                f"{topic} 在当前窗口出现 {len(current)} 次，上一窗口 "
                f"{len(previous)} 次，覆盖 {len(platforms)} 个平台。"
            )
            if not sufficient:
                explanation += " 样本未达到趋势判定门槛。"
            results.append(
                self.repository.upsert_trend(
                    topic=topic,
                    window_start=_utc(current_start),
                    window_end=_utc(current_end),
                    score=scores.score,
                    volume_score=scores.volume_score,
                    velocity_score=scores.velocity_score,
                    cross_platform_score=scores.cross_platform_score,
                    engagement_score=scores.engagement_score,
                    platforms=platforms,
                    content_ids=[str(item["id"]) for item in current],
                    explanation=explanation,
                    evidence=evidence,
                    status=status,
                    formula_version=FORMULA_VERSION,
                )
            )
        return sorted(
            results,
            key=lambda item: (-float(item["score"]), str(item["topic"]).casefold()),
        )

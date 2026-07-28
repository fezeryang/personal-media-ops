from typing import Protocol

from app.repositories.intelligence import IntelligenceRepository


class BriefGenerator(Protocol):
    def generate(
        self,
        *,
        user_id: str,
        window_start: str,
        window_end: str,
        timezone: str,
        regenerate: bool,
    ) -> dict[str, object]: ...


class DeterministicBriefGenerator:
    def __init__(self, repository: IntelligenceRepository) -> None:
        self.repository = repository

    def generate(
        self,
        *,
        user_id: str,
        window_start: str,
        window_end: str,
        timezone: str,
        regenerate: bool,
    ) -> dict[str, object]:
        contents = self.repository.brief_source_contents(
            window_start=window_start,
            window_end=window_end,
        )
        content_count = self.repository.brief_source_content_count(
            window_start=window_start,
            window_end=window_end,
        )
        trends = self.repository.list_trends(
            window_end_before=window_end,
            limit=20,
        )["items"]
        failures = self.repository.brief_source_failures(
            window_start=window_start,
            window_end=window_end,
        )
        creator_activity = self.repository.brief_source_creator_activity(
            window_start=window_start,
            window_end=window_end,
        )
        items: list[dict[str, object]] = []
        content_ids = [str(content["id"]) for content in contents]
        items.append(
            {
                "section": "new_content",
                "conclusion_type": "fact",
                "title": f"窗口内新增 {content_count} 条内容",
                "body": (
                    "该数量来自资料库 first_collected_at，重复采集不会重复计数。"
                ),
                "content_ids": content_ids[:20],
                "trend_ids": [],
                "evidence": {
                    "new_content_count": content_count,
                    "linked_content_count": len(contents),
                    "source_urls": [
                        content["source_url"]
                        for content in contents[:20]
                        if content["source_url"]
                    ],
                },
            }
        )
        if trends:
            trend_ids = [str(trend["id"]) for trend in trends]
            trend_content_ids = list(
                dict.fromkeys(
                    content_id
                    for trend in trends
                    for content_id in trend["content_ids"]
                )
            )
            detected = sum(
                1 for trend in trends if trend["status"] == "detected"
            )
            items.append(
                {
                    "section": "trends",
                    "conclusion_type": (
                        "calculation" if detected else "insufficient_data"
                    ),
                    "title": f"{detected} 个主题达到趋势门槛",
                    "body": (
                        "结果由 rules-v1 公式计算；未达样本门槛的主题保持"
                        " insufficient_data。"
                    ),
                    "content_ids": trend_content_ids[:30],
                    "trend_ids": trend_ids,
                    "evidence": {
                        "detected_count": detected,
                        "signal_count": len(trends),
                    },
                }
            )
        ranked = sorted(
            contents,
            key=lambda content: sum(
                int(content[field] or 0)
                for field in (
                    "view_count",
                    "like_count",
                    "favorite_count",
                    "comment_count",
                    "share_count",
                )
            ),
            reverse=True,
        )
        if ranked:
            items.append(
                {
                    "section": "engagement",
                    "conclusion_type": "rule",
                    "title": "窗口内高互动内容",
                    "body": (
                        "按当前可用互动计数之和排序；缺失指标按未知值处理，"
                        "不推断为零增长。"
                    ),
                    "content_ids": [
                        str(content["id"]) for content in ranked[:5]
                    ],
                    "trend_ids": [],
                    "evidence": {"ranking": "sum_of_available_current_metrics"},
                }
            )
            items[-1]["evidence"]["source_urls"] = [
                content["source_url"]
                for content in ranked[:5]
                if content["source_url"]
            ]
        if creator_activity:
            items.append(
                {
                    "section": "creator_activity",
                    "conclusion_type": "fact",
                    "title": (
                        f"{len(creator_activity)} 次创作者监控运行成功"
                    ),
                    "body": (
                        "动态来自已完成的创作者监控任务；新增与已存在内容"
                        "按资料库幂等结果区分。"
                    ),
                    "content_ids": [],
                    "trend_ids": [],
                    "evidence": {
                        "runs": creator_activity,
                    },
                }
            )
        favorites = [
            str(content["id"])
            for content in contents
            if bool(content["is_favorite"])
        ]
        if favorites:
            items.append(
                {
                    "section": "favorites",
                    "conclusion_type": "fact",
                    "title": f"窗口内有 {len(favorites)} 条收藏内容",
                    "body": "收藏状态来自资料库唯一 is_favorite 字段。",
                    "content_ids": favorites,
                    "trend_ids": [],
                    "evidence": {"favorite_count": len(favorites)},
                }
            )
        if failures:
            items.append(
                {
                    "section": "data_gaps",
                    "conclusion_type": "fact",
                    "title": f"记录到 {len(failures)} 次采集失败或部分失败",
                    "body": "失败属于已记录的数据缺口，不代表平台没有相关内容。",
                    "content_ids": [],
                    "trend_ids": [],
                    "evidence": {
                        "run_ids": [str(failure["id"]) for failure in failures]
                    },
                }
            )
        else:
            items.append(
                {
                    "section": "data_gaps",
                    "conclusion_type": "unknown",
                    "title": "未记录新的采集失败",
                    "body": (
                        "这仅说明当前窗口没有失败运行；延期平台仍未被自动采集。"
                    ),
                    "content_ids": [],
                    "trend_ids": [],
                    "evidence": {"failed_run_count": 0},
                }
            )
        return self.repository.create_brief(
            user_id=user_id,
            window_start=window_start,
            window_end=window_end,
            timezone=timezone,
            regenerate=regenerate,
            items=items,
        )


class AIEnhancedBriefGenerator:
    def generate(self, **_: object) -> dict[str, object]:
        raise RuntimeError("MEDIAOPS_AI_PROVIDER is disabled")

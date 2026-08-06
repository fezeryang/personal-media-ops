from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from app.repositories.monitoring import MonitoringConflict, MonitoringRepository
from app.repositories.research import ResearchTaskRepository
from app.services.ai.intent_interpreter import build_default_intent
from app.services.monitoring.attention import attention_for_change
from app.services.monitoring.change_detection import (
    compare_baseline,
    memory_update_for_change,
)


class MonitoringService:
    def __init__(
        self,
        repository: MonitoringRepository,
        research: ResearchTaskRepository | None = None,
    ) -> None:
        self.repository = repository
        self.research = research

    @staticmethod
    def understand_goal(
        goal: str,
        *,
        mission_type: str,
        targets: Sequence[Mapping[str, object]],
        platforms: Sequence[str],
        schedule_type: str,
        budget: Mapping[str, object],
    ) -> dict[str, object]:
        normalized = goal.strip()
        lower = normalized.casefold()
        inferred_type = mission_type
        if mission_type == "research_question":
            if any(token in lower for token in ("创作者", "作者", "creator")):
                inferred_type = "creator"
            elif any(token in lower for token in ("产品", "工具", "功能", "feature")):
                inferred_type = "entity"
            elif any(token in lower for token in ("事件", "发布", "融资")):
                inferred_type = "event"
            elif any(token in lower for token in ("抱怨", "不好用", "痛点", "反馈")):
                inferred_type = "topic"
        ignore = ["基础介绍", "营销转载", "重复内容", "没有变化的背景材料"]
        focus = ["新实体", "重要功能变化", "真实用户反馈变化", "重要事件", "反向证据"]
        return {
            "interpreted_goal": f"持续判断与‘{normalized[:120]}’相比有哪些有证据的变化",
            "mission_type": inferred_type,
            "why_monitor": "该目标需要比较长期基线，而不是重复收集内容。",
            "known_baseline": "首次运行只建立基线，不把历史内容伪装成新变化。",
            "watch_for": focus,
            "ignore": ignore,
            "targets": [dict(item) for item in targets],
            "suggested_platforms": list(dict.fromkeys(platforms))[: int(budget.get("max_platforms", 3))],
            "schedule": {"type": schedule_type, "frequency_guard": "最低每日一次"},
            "evidence_requirements": ["evidence_id/content_id", "独立来源数量", "发布时间", "反向证据"],
            "importance_rule": "高相关、新颖且有独立证据的变化进入发现收件箱。",
            "budget_summary": dict(budget),
        }

    def create_mission(self, *, owner_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        targets = payload.get("targets")
        target_items = [dict(item) for item in targets if isinstance(item, Mapping)] if isinstance(targets, list) else []
        budget = payload.get("budget")
        budget_data = dict(budget) if isinstance(budget, Mapping) else {}
        platforms = payload.get("platforms")
        platform_values = [str(item) for item in platforms] if isinstance(platforms, list) else []
        understanding = self.understand_goal(
            str(payload["goal"]),
            mission_type=str(payload.get("mission_type") or "research_question"),
            targets=target_items,
            platforms=platform_values,
            schedule_type=str(payload.get("schedule_type") or "manual"),
            budget=budget_data,
        )
        return self.repository.create_mission(
            owner_id=owner_id,
            goal=str(payload["goal"]),
            title=str(payload.get("title") or understanding["interpreted_goal"]),
            mission_type=str(understanding["mission_type"]),
            targets=target_items,
            platforms=platform_values,
            schedule_type=str(payload.get("schedule_type") or "manual"),
            schedule_config=payload.get("schedule_config") if isinstance(payload.get("schedule_config"), Mapping) else {},
            importance_rule=str(payload["importance_rule"]) if payload.get("importance_rule") else None,
            ignored_content_rule=str(payload["ignored_content_rule"]) if payload.get("ignored_content_rule") else None,
            budget=budget_data,
            understanding=understanding,
            confirmed=bool(payload.get("confirmed")),
        )

    def run_once(
        self,
        *,
        owner_id: str,
        mission_id: str,
        trigger: str = "manual",
        existing_run_id: str | None = None,
    ) -> dict[str, object]:
        mission = self.repository.get_mission(owner_id, mission_id, detail=True)
        if mission is None:
            raise KeyError(mission_id)
        run = (
            self.repository.claim_run(owner_id=owner_id, mission_id=mission_id, trigger=trigger)
            if existing_run_id is None
            else self.repository.get_run(owner_id, existing_run_id)
        )
        if run is None:
            raise MonitoringConflict("monitoring run is unavailable")
        run_id = str(run["id"])
        if run.get("research_task_id"):
            return {
                **run,
                "baseline": self.repository.latest_baseline(owner_id, mission_id),
                "changes": [],
                "outcome": "research_task_queued",
            }
        baseline_record = self.repository.latest_baseline(owner_id, mission_id)
        baseline = baseline_record.get("snapshot") if baseline_record is not None else None
        targets = mission.get("targets") if isinstance(mission.get("targets"), list) else []
        platforms = mission.get("platforms") if isinstance(mission.get("platforms"), list) else []
        budget = mission.get("budget") if isinstance(mission.get("budget"), Mapping) else {}
        try:
            if platforms and self.research is not None:
                return self._queue_research_run(
                    owner_id=owner_id,
                    mission=mission,
                    run=run,
                    baseline_record=baseline_record,
                    targets=targets,
                    platforms=platforms,
                    budget=budget,
                )
            contents = self.repository.list_matching_contents(
                goal=str(mission["goal"]),
                targets=[item for item in targets if isinstance(item, Mapping)],
                platforms=[str(item) for item in platforms],
                limit=int(budget.get("max_collection_count", 3)) * 20,
            )
            query_platforms = [str(item) for item in platforms] or ["library"]
            for platform in query_platforms[: int(budget.get("max_platforms", 3))]:
                self.repository.add_run_query(
                    run_id=run_id,
                    platform=platform,
                    query=str(mission["goal"]),
                    query_role="monitoring_baseline_compare",
                    status="library_reuse",
                    result_count=len(contents),
                    new_content_count=0,
                    reason="复用已有证据；平台采集由现有单 Worker 队列负责",
                )
            comparison = compare_baseline(goal=str(mission["goal"]), baseline=baseline, current_contents=contents)
            saved_baseline = self.repository.save_baseline(
                mission_id=mission_id,
                run_id=run_id,
                snapshot=comparison["baseline"] if isinstance(comparison.get("baseline"), Mapping) else {"content_ids": []},
            )
            notifications = 0
            saved_changes: list[dict[str, object]] = []
            for raw_change in comparison.get("changes", []):
                if not isinstance(raw_change, Mapping):
                    continue
                attention = attention_for_change(dict(raw_change))
                change = dict(raw_change)
                change["attention_level"] = attention["level"]
                change["attention_score"] = attention["score"]
                change["explanation"] = {
                    **(dict(raw_change.get("explanation", {})) if isinstance(raw_change.get("explanation"), Mapping) else {}),
                    "attention": attention,
                    "monitoring_goal": mission["goal"],
                }
                memory = memory_update_for_change(change, old_value={"known": True}, new_value={"title": change.get("title"), "summary": change.get("summary")})
                stored = self.repository.save_change(mission_id=mission_id, run_id=run_id, change=change, attention=attention, memory_update=memory)
                saved_changes.append(stored)
                if self.repository.create_notification(owner_id=owner_id, mission_id=mission_id, change=stored) is not None:
                    notifications += 1
            outcome = str(comparison.get("outcome") or "no_meaningful_change")
            status = "completed" if outcome in {"baseline_created", "meaningful_change"} else "no_meaningful_change"
            resource = {
                "model_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "collection_count": len(contents),
                "source": "existing_library_baseline",
                "platform_results": {platform: "library_reuse" for platform in query_platforms},
            }
            result = self.repository.complete_run(
                owner_id=owner_id,
                run_id=run_id,
                status=status,
                change_count=len(saved_changes),
                notification_count=notifications,
                baseline_created=baseline_record is None,
                resource=resource,
            )
            if result is None:
                raise RuntimeError("monitoring run disappeared")
            result["baseline"] = saved_baseline
            result["changes"] = saved_changes
            result["outcome"] = outcome
            return result
        except Exception as error:
            self.repository.complete_run(
                owner_id=owner_id,
                run_id=run_id,
                status="degraded",
                change_count=0,
                notification_count=0,
                baseline_created=False,
                resource={"model_calls": 0, "source": "existing_library_baseline"},
                failure_reason=str(error)[:500],
            )
            raise

    def _queue_research_run(
        self,
        *,
        owner_id: str,
        mission: Mapping[str, object],
        run: Mapping[str, object],
        baseline_record: Mapping[str, object] | None,
        targets: Sequence[Mapping[str, object]],
        platforms: Sequence[object],
        budget: Mapping[str, object],
    ) -> dict[str, object]:
        """Queue one bounded ResearchTask instead of creating a second runtime.

        The monitoring record remains open while the existing Research Runtime
        performs intent planning, library-first search, and (when needed) one
        single-concurrency crawler task. The Worker later reconciles the linked
        ResearchTask into a baseline comparison and notification result.
        """
        assert self.research is not None
        run_id = str(run["id"])
        mission_id = str(mission["id"])
        selected_platforms = [str(item) for item in platforms][: int(budget.get("max_platforms", 3))]
        existing_contents = self.repository.list_matching_contents(
            goal=str(mission["goal"]),
            targets=[item for item in targets if isinstance(item, Mapping)],
            platforms=selected_platforms,
            limit=int(budget.get("max_collection_count", 3)) * 20,
        )
        baseline_created = baseline_record is None
        if baseline_created:
            comparison = compare_baseline(
                goal=str(mission["goal"]),
                baseline=None,
                current_contents=existing_contents,
            )
            baseline_record = self.repository.save_baseline(
                mission_id=mission_id,
                run_id=run_id,
                snapshot=comparison["baseline"] if isinstance(comparison.get("baseline"), Mapping) else {"content_ids": []},
            )
        max_collections = max(1, int(budget.get("max_collection_count", 3)))
        max_tokens = max(1_000, int(budget.get("max_total_tokens", 8_000)))
        research_task = self.research.create(
            user_id=owner_id,
            objective=str(mission["goal"]),
            platforms=selected_platforms,
            crawl_limit=max(1, min(4, max_collections)),
            content_limit=max(20, min(200, max_collections * 20)),
            duration_seconds=max(30, min(3_600, int(budget.get("max_runtime_seconds", 300)))),
            token_limit=max_tokens,
            cost_limit=None,
            cost_currency=None,
            coverage={
                "target_platform_count": len(selected_platforms),
                "target_independent_evidence_count": max(1, min(10, max_collections)),
                "target_new_content_count": max(1, min(20, max_collections * 5)),
            },
            max_total_tokens=max_tokens,
            max_crawl_tasks=max(1, min(4, max_collections)),
            max_new_contents=max(20, min(200, max_collections * 20)),
            max_runtime_seconds=max(30, min(3_600, int(budget.get("max_runtime_seconds", 300)))),
            max_model_calls=max(0, min(20, int(budget.get("max_model_calls", 4)))),
            route_policy="balanced",
        )
        # ResearchTaskRepository.create intentionally stays a low-level
        # storage primitive; normal API creation writes the understanding-card
        # intent immediately afterwards. Monitoring must do the same before
        # waking the Runtime, otherwise the task is treated as a legacy task
        # and a valid broad monitoring goal can fail the legacy three-term
        # planner gate before deterministic intent directions are available.
        initial_intent = build_default_intent(str(mission["goal"]), selected_platforms)
        self.research.save_intent(
            str(research_task["id"]),
            initial_intent.model_dump(mode="json"),
            change_reason="monitoring_mission_understanding",
        )
        resource = {
            "source": "research_runtime",
            "research_task_id": str(research_task["id"]),
            "platform_results": {platform: "queued" for platform in selected_platforms},
            "baseline_created": baseline_created,
        }
        linked = self.repository.attach_research_task(
            owner_id=owner_id,
            run_id=run_id,
            research_task_id=str(research_task["id"]),
            resource=resource,
        )
        if linked is None:
            raise RuntimeError("monitoring run disappeared while queuing research")
        return {
            **linked,
            "baseline": baseline_record,
            "changes": [],
            "outcome": "research_task_queued",
        }

    def reconcile_linked_runs(self, *, limit: int = 3) -> int:
        """Reconcile completed Research Runtime tasks into monitoring changes."""
        if self.research is None:
            return 0
        reconciled = 0
        for run in self.repository.linked_active_runs(limit=limit):
            research_task_id = str(run["research_task_id"])
            task = self.research.get_for_runtime(research_task_id, detail=False)
            if task is None:
                continue
            status = str(task.get("status"))
            owner_id = str(run["owner_id"])
            run_id = str(run["id"])
            if status == "WaitingLogin":
                self.repository.update_waiting_state(
                    owner_id=owner_id,
                    run_id=run_id,
                    run_status="waiting_login",
                    mission_status="waiting_login",
                )
                continue
            if status == "WaitingCrawl":
                self.repository.update_waiting_state(
                    owner_id=owner_id,
                    run_id=run_id,
                    run_status="waiting_platform",
                    mission_status="waiting_platform",
                )
                continue
            if status in {"Draft", "Planning", "Researching", "Summarizing"}:
                self.repository.update_waiting_state(
                    owner_id=owner_id,
                    run_id=run_id,
                    run_status="running",
                    mission_status="running",
                )
                continue
            if status in {"Failed", "Cancelled", "BudgetExceeded"}:
                self.repository.complete_run(
                    owner_id=owner_id,
                    run_id=run_id,
                    status="degraded",
                    change_count=0,
                    notification_count=0,
                    baseline_created=False,
                    resource={
                        **dict(run.get("resource", {})),
                        "research_status": status,
                        "research_task_id": research_task_id,
                    },
                    failure_reason=str(task.get("failure_reason") or f"Research Runtime {status}"),
                )
                reconciled += 1
                continue
            if status != "Done":
                continue
            mission = self.repository.get_mission(owner_id, str(run["mission_id"]), detail=True)
            baseline = self.repository.latest_baseline(owner_id, str(run["mission_id"]))
            if mission is None or baseline is None:
                continue
            targets = mission.get("targets") if isinstance(mission.get("targets"), list) else []
            platforms = mission.get("platforms") if isinstance(mission.get("platforms"), list) else []
            contents = self.repository.list_matching_contents(
                goal=str(mission["goal"]),
                targets=[item for item in targets if isinstance(item, Mapping)],
                platforms=[str(item) for item in platforms],
                limit=int(dict(mission.get("budget", {})).get("max_collection_count", 3)) * 20,
            )
            comparison = compare_baseline(
                goal=str(mission["goal"]),
                baseline=baseline.get("snapshot") if isinstance(baseline.get("snapshot"), Mapping) else {},
                current_contents=contents,
            )
            saved_changes, notifications = self._persist_comparison(
                owner_id=owner_id,
                mission_id=str(run["mission_id"]),
                run_id=run_id,
                goal=str(mission["goal"]),
                comparison=comparison,
            )
            self.repository.save_baseline(
                mission_id=str(run["mission_id"]),
                run_id=run_id,
                snapshot=comparison["baseline"] if isinstance(comparison.get("baseline"), Mapping) else {},
            )
            resource = {
                **dict(run.get("resource", {})),
                "research_status": status,
                "research_task_id": research_task_id,
                "model_calls": int(task.get("consumed_model_call_count") or 0),
                "input_tokens": int(task.get("input_tokens") or 0),
                "output_tokens": int(task.get("output_tokens") or 0),
                "collection_count": int(task.get("consumed_content_count") or 0),
            }
            outcome = str(comparison.get("outcome") or "no_meaningful_change")
            completed = self.repository.complete_run(
                owner_id=owner_id,
                run_id=run_id,
                status="completed" if outcome == "meaningful_change" else "no_meaningful_change",
                change_count=len(saved_changes),
                notification_count=notifications,
                baseline_created=bool(run.get("resource", {}).get("baseline_created")),
                resource=resource,
            )
            if completed is not None:
                reconciled += 1
        return reconciled

    def _persist_comparison(
        self,
        *,
        owner_id: str,
        mission_id: str,
        run_id: str,
        goal: str,
        comparison: Mapping[str, object],
    ) -> tuple[list[dict[str, object]], int]:
        notifications = 0
        saved_changes: list[dict[str, object]] = []
        for raw_change in comparison.get("changes", []):
            if not isinstance(raw_change, Mapping):
                continue
            attention = attention_for_change(dict(raw_change))
            change = dict(raw_change)
            change["attention_level"] = attention["level"]
            change["attention_score"] = attention["score"]
            change["explanation"] = {
                **(dict(raw_change.get("explanation", {})) if isinstance(raw_change.get("explanation"), Mapping) else {}),
                "attention": attention,
                "monitoring_goal": goal,
            }
            memory = memory_update_for_change(
                change,
                old_value={"known": True},
                new_value={"title": change.get("title"), "summary": change.get("summary")},
            )
            stored = self.repository.save_change(
                mission_id=mission_id,
                run_id=run_id,
                change=change,
                attention=attention,
                memory_update=memory,
            )
            saved_changes.append(stored)
            if self.repository.create_notification(owner_id=owner_id, mission_id=mission_id, change=stored) is not None:
                notifications += 1
        return saved_changes, notifications

    def run_due(self, *, limit: int = 1) -> int:
        claimed = self.repository.claim_due_runs(now=datetime.now(UTC), limit=limit)
        completed = 0
        for item in claimed:
            mission_id = str(item["mission_id"])
            mission = self.repository.get_mission_for_run(str(item["id"]))
            if mission is None:
                continue
            try:
                self.run_once(
                    owner_id=str(mission["owner_id"]),
                    mission_id=mission_id,
                    trigger="scheduled",
                    existing_run_id=str(item["id"]),
                )
            except (KeyError, MonitoringConflict, RuntimeError, ValueError):
                continue
            completed += 1
        return completed

import asyncio
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.crawler.results import TaskEntityBatch
from app.models.ai import (
    GatewayResponse,
    ModelResponse,
    ModelToolCall,
    ModelUsage,
)
from app.models.library import NormalizedContent
from app.repositories.auth import AuthRepository
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.library import LibraryRepository
from app.repositories.research import ResearchTaskConflict, ResearchTaskRepository
from app.security.passwords import hash_password
from app.services.ai.providers import ProviderError
from app.services.ai.research_runtime import (
    ResearchRuntime,
    _elapsed_from,
    _json,
    _safe_arguments,
)
from app.services.ai.research_tools import ResearchToolService
from tests.alembic_utils import run_alembic_command


def setup_database(tmp_path: Path) -> tuple[Path, str]:
    database = tmp_path / "mediaops.db"
    run_alembic_command(database, "upgrade", "head")
    owner = AuthRepository(database).create_owner(
        username="research-owner",
        password_hash=hash_password("password"),
    )
    return database, str(owner["id"])


def create_task(database: Path, owner_id: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "user_id": owner_id,
        "objective": "Find AI workbench products",
        "platforms": ["bili"],
        "crawl_limit": 2,
        "content_limit": 100,
        "duration_seconds": 3_600,
        "token_limit": 50_000,
        "cost_limit": None,
        "cost_currency": None,
    }
    values.update(overrides)
    return ResearchTaskRepository(database).create(**values)  # type: ignore[arg-type]


def test_research_task_state_and_evidence_are_durable(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task_id = str(task["id"])
    repository.transition(task_id, status="Planning", reason="test", step="planning")
    repository.save_plan(
        task_id,
        plan={"derived_keywords": ["local-first", "knowledge workspace", "agent memory"]},
        route_snapshot={"primary": {"model_record_id": "m1"}},
        round_number=1,
    )
    repository.transition(
        task_id,
        status="Researching",
        reason="test",
        step="research_round",
        round_number=1,
    )

    crawler = CrawlerTaskRepository(database)
    crawler_task = crawler.create(
        platform="bili",
        crawler_type="search",
        keywords="AI workbench",
        login_type="qrcode",
        requested_count=2,
        research_task_id=task_id,
        output_dir=str(tmp_path / "output"),
        log_path=str(tmp_path / "logs" / "task.log"),
        qrcode_path=str(tmp_path / "qrcode.png"),
    )
    repository.add_crawl_submission(task_id, str(crawler_task["id"]))
    assert crawler.claim_next() is not None
    repository.mark_waiting_login(str(crawler_task["id"]))
    assert repository.get_for_runtime(task_id)["status"] == "WaitingLogin"  # type: ignore[index]
    repository.mark_crawl_resumed(str(crawler_task["id"]))
    library = LibraryRepository(database)
    ingestion = library.ingest_task(
        task_id=str(crawler_task["id"]),
        batch=TaskEntityBatch(
            contents=[
                NormalizedContent(
                    platform="bili",
                    source_content_id="av-1",
                    content_type="video",
                    title="Local AI workspace",
                    description="A real evidence record",
                    source_url="https://example.test/av-1",
                    cover_url=None,
                    author_source_id="creator-1",
                    author_name="Author",
                    published_at=None,
                    source_keyword="AI workbench",
                    view_count=10,
                    like_count=1,
                    favorite_count=0,
                    comment_count=0,
                    share_count=0,
                    raw_payload={},
                )
            ],
            creators=[],
            comments=[],
            actual_count=1,
        ),
    )
    assert ingestion.new_content_count == 1
    # The ingestion count is not the content id; read the deterministic row.
    with repository_connection(database) as connection:
        content_id = str(connection.execute("SELECT id FROM library_contents LIMIT 1").fetchone()[0])
    repository.record_crawl_completion(str(crawler_task["id"]), succeeded=True, new_content_count=1)
    finding = repository.save_finding(
        task_id=task_id,
        round_number=1,
        kind="fact",
        statement="The source describes a local AI workspace.",
        derivation=None,
        content_ids=[content_id],
    )
    assert finding["content_ids"] == [content_id]
    detail = repository.get(user_id=owner_id, task_id=task_id, detail=True)
    assert detail is not None
    assert detail["findings"][0]["evidence"][0]["crawl_task_id"] == crawler_task["id"]
    assert len(detail["execution_trace"]) >= 6

    with pytest.raises(ResearchTaskConflict, match="require content evidence"):
        repository.save_finding(
            task_id=task_id,
            round_number=1,
            kind="fact",
            statement="Unsupported",
            derivation=None,
            content_ids=[],
        )


def repository_connection(database: Path):
    from app.db import connect_database

    return connect_database(database)


def test_tool_allow_list_and_inference_policy(tmp_path: Path, test_settings) -> None:
    database, owner_id = setup_database(tmp_path)
    task = create_task(database, owner_id)
    library_tools = Mock()
    tools = ResearchToolService(
        settings=test_settings,
        library_tools=library_tools,
        crawler=CrawlerTaskRepository(database),
        research=ResearchTaskRepository(database),
    )
    with pytest.raises(ResearchTaskConflict, match="allow-list"):
        asyncio.run(
            tools.execute(
                task=task,
                tool_name="delete_everything",
                arguments={},
            )
        )
    with pytest.raises(ResearchTaskConflict, match="derivation"):
        asyncio.run(
            tools.execute(
                task=task,
                tool_name="save_finding",
                arguments={
                    "kind": "inference",
                    "statement": "A hypothesis",
                    "content_ids": ["missing"],
                },
            )
        )


def test_research_tools_cover_read_dedupe_find_and_action_paths(
    tmp_path: Path,
    test_settings,
) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    content_id = _seed_content(database, tmp_path)
    library_tools = Mock()
    content = {
        "id": content_id,
        "title": "Local-first AI workspace",
        "description": "agent memory evidence graph",
        "author_name": "Author",
        "published_at": None,
        "source": {"platform": "bili", "url": "https://example.test/seed-1"},
        "provenance": [{"task_id": "crawl-1", "collected_at": "2026-08-01T00:00:00Z"}],
    }
    library_tools.search_contents.return_value = {"data": [], "meta": {}}
    library_tools.get_content.return_value = content
    library_tools.get_creator.return_value = {"id": "creator-1", "recent_contents": []}
    tools = ResearchToolService(
        settings=test_settings,
        library_tools=library_tools,
        crawler=CrawlerTaskRepository(database),
        research=repository,
    )
    assert len(tools.definitions()) == 8
    search = asyncio.run(
        tools.execute(
            task=task,
            tool_name="search_library",
            arguments={"query": "AI", "platform": "bili"},
        )
    )
    assert search["data"] == []
    assert asyncio.run(
        tools.execute(task=task, tool_name="get_content", arguments={"content_id": content_id})
    )["id"] == content_id
    provenance = asyncio.run(
        tools.execute(task=task, tool_name="get_provenance", arguments={"content_id": content_id})
    )
    assert provenance["platform"] == "bili"
    assert asyncio.run(
        tools.execute(task=task, tool_name="get_creator_history", arguments={"creator_id": "creator-1"})
    )["id"] == "creator-1"
    event = asyncio.run(
        tools.execute(
            task=task,
            tool_name="dedupe_check",
            arguments={"content_ids": [content_id], "title": "Event", "summary": "Summary"},
        )
    )
    assert event["fingerprint"]
    fact = asyncio.run(
        tools.execute(
            task=task,
            tool_name="save_finding",
            arguments={"kind": "fact", "statement": "Fact", "content_ids": [content_id]},
        )
    )
    assert fact["kind"] == "fact"
    inference = asyncio.run(
        tools.execute(
            task=task,
            tool_name="save_finding",
            arguments={
                "kind": "inference",
                "statement": "Inference",
                "derivation": "Derived from Fact",
                "content_ids": [content_id],
            },
        )
    )
    assert inference["kind"] == "inference"
    action = asyncio.run(
        tools.execute(
            task=task,
            tool_name="propose_action",
            arguments={"action": "review", "reason": "owner", "payload": {"x": "y"}},
        )
    )
    assert action["status"] == "pending"


def test_search_library_falls_back_to_bounded_terms_for_objectives(
    tmp_path: Path,
    test_settings,
) -> None:
    database, owner_id = setup_database(tmp_path)
    task = create_task(database, owner_id)
    library_tools = Mock()

    def search_contents(**kwargs: object) -> dict[str, object]:
        query = str(kwargs["query"])
        if query == "工作台产品，分析其解决的需求、产品形态与可能机会。":
            return {"data": [], "meta": {}}
        if query in {"工作台产品", "产品"}:
            return {
                "data": [
                    {
                        "id": "content-1",
                        "title": "AI 工作台产品",
                        "description": "agent workspace",
                    }
                ],
                "meta": {},
            }
        return {"data": [], "meta": {}}

    library_tools.search_contents.side_effect = search_contents
    tools = ResearchToolService(
        settings=test_settings,
        library_tools=library_tools,
        crawler=CrawlerTaskRepository(database),
        research=ResearchTaskRepository(database),
    )
    result = asyncio.run(
        tools.execute(
            task=task,
            tool_name="search_library",
            arguments={
                "query": "工作台产品，分析其解决的需求、产品形态与可能机会。"
            },
        )
    )
    assert result["data"][0]["id"] == "content-1"
    assert library_tools.search_contents.call_count >= 2


def test_submit_crawl_is_persisted_as_waiting_state_after_library_search(
    tmp_path: Path,
    test_settings,
) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    repository.transition(
        str(task["id"]),
        status="Researching",
        reason="test",
        step="research_round",
        round_number=1,
    )
    repository.update_context(
        str(task["id"]),
        {"last_search_query": "AI workbench"},
        step="search_library",
        round_number=1,
    )
    tools = ResearchToolService(
        settings=test_settings,
        library_tools=Mock(),
        crawler=CrawlerTaskRepository(database),
        research=repository,
    )
    result = asyncio.run(
        tools.execute(
            task=repository.get_for_runtime(str(task["id"])) or task,
            tool_name="submit_crawl",
            arguments={"platform": "bili", "keywords": "agent memory"},
        )
    )
    assert result["status"] == "waiting_crawl"
    current = repository.get_for_runtime(str(task["id"]))
    assert current is not None
    assert current["status"] == "WaitingCrawl"
    assert current["waiting_crawl_task_id"] == result["crawler_task_id"]


def test_orphan_crawl_is_reconciled_after_runtime_restart(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task_id = str(task["id"])
    repository.transition(task_id, status="Researching", reason="test")
    crawler = CrawlerTaskRepository(database)
    orphan = crawler.create(
        platform="bili",
        crawler_type="search",
        keywords="orphan",
        login_type="qrcode",
        requested_count=1,
        research_task_id=task_id,
        output_dir=str(tmp_path / "output"),
        log_path=str(tmp_path / "logs" / "orphan.log"),
        qrcode_path=str(tmp_path / "orphan.png"),
    )
    assert repository.reconcile_orphan_crawls() == [str(orphan["id"])]
    current = repository.get_for_runtime(task_id)
    assert current is not None
    assert current["status"] == "WaitingCrawl"
    assert current["consumed_crawl_count"] == 1
    assert crawler.claim_next() is not None
    crawler.complete_success(str(orphan["id"]), actual_count=0)
    repository.record_crawl_completion(str(orphan["id"]), succeeded=True)
    assert repository.reconcile_orphan_crawls() == []
    current = repository.get_for_runtime(task_id)
    assert current is not None
    assert current["consumed_crawl_count"] == 1
    assert current["context"]["crawl_requested"] is False


def test_repository_controls_usage_events_and_terminal_guards(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task_id = str(task["id"])

    assert repository.claim_next() is not None
    repository.append_trace(
        task_id,
        event="test_event",
        status="Draft",
        tool_name="search_library",
        tool_arguments={"query": "AI"},
        provider="MiniMax",
        model="MiniMax-M3",
        route_role="tool_calling",
        request_correlation_id="corr-1",
        input_tokens=10,
        output_tokens=5,
        elapsed_ms=12,
    )
    repository.record_usage(
        task_id,
        input_tokens=10,
        output_tokens=5,
        cached_tokens=2,
        estimated_cost=Decimal("0.123"),
        provider="MiniMax",
        model="MiniMax-M3",
        route_role="tool_calling",
        request_correlation_id="corr-1",
        elapsed_ms=12,
    )
    repository.record_duration(task_id)
    repository.set_cost_enabled(task_id, True)
    repository.dedupe_event(
        task_id=task_id,
        round_number=1,
        fingerprint="fingerprint-1",
        title="Event",
        summary="Summary",
        content_ids=[],
    )
    action = repository.add_action(
        task_id=task_id,
        action="create_collection",
        reason="owner review",
        payload={"name": "AI"},
    )
    decided = repository.decide_action(task_id, str(action["id"]), "approved")
    assert decided["status"] == "approved"
    with pytest.raises(ValueError, match="unsupported research task control"):
        repository.control(task_id, "unknown")

    repository.control(task_id, "pause", "owner pause")
    assert repository.get_for_runtime(task_id)["paused"] is True  # type: ignore[index]
    repository.control(task_id, "resume")
    repository.transition(
        task_id,
        status="AwaitingReview",
        reason="test review",
        step="awaiting_review",
    )
    repository.control(task_id, "rerun", "one more round")
    assert repository.get_for_runtime(task_id)["status"] == "Researching"  # type: ignore[index]
    repository.transition(task_id, status="AwaitingReview", reason="done")
    repository.complete_review(task_id)
    assert repository.get_for_runtime(task_id)["status"] == "Done"  # type: ignore[index]
    with pytest.raises(ResearchTaskConflict, match="terminal"):
        repository.control(task_id, "pause")
    repository.set_failure(task_id, "ignored after terminal")
    detail = repository.get(user_id=owner_id, task_id=task_id, detail=True)
    assert detail is not None
    assert detail["estimated_cost"] == "0.123"
    assert detail["budget_cost_enabled"] is True
    assert detail["events"][0]["fingerprint"] == "fingerprint-1"


class FakeResearchGateway:
    def __init__(self, responses: list[ModelResponse | Exception]) -> None:
        self.responses = responses
        self.requests: list[object] = []

    async def generate(self, request, **_kwargs) -> GatewayResponse:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return GatewayResponse(
            response=response,
            route_role="tool_calling",
            fallback_used=False,
            request_correlation_id=f"corr-{len(self.requests)}",
            initial_provider_id="provider-1",
            initial_model_id="model-1",
            final_provider_id="provider-1",
            final_model_id="model-1",
        )


class FakeResearchTools:
    def __init__(self, repository: ResearchTaskRepository, content_id: str) -> None:
        self.repository = repository
        self.content_id = content_id

    @staticmethod
    def definitions():
        return []

    async def execute(self, *, task, tool_name: str, arguments: dict[str, object]):
        if tool_name == "save_finding":
            return self.repository.save_finding(
                task_id=str(task["id"]),
                round_number=int(task["current_round"]),
                kind=str(arguments.get("kind") or "fact"),
                statement=str(arguments.get("statement") or "A real evidence-bound finding."),
                derivation=(
                    str(arguments["derivation"])
                    if arguments.get("derivation") is not None
                    else None
                ),
                content_ids=[str(item) for item in arguments.get("content_ids", [self.content_id])],
            )
        if tool_name == "search_library":
            return {
                "data": [
                    {
                        "id": self.content_id,
                        "title": "Local-first AI workspace",
                        "description": "agent memory evidence graph",
                    }
                ]
            }
        if tool_name == "propose_action":
            return self.repository.add_action(
                task_id=str(task["id"]),
                action=str(arguments.get("action") or "review"),
                reason=str(arguments.get("reason") or "owner review"),
                payload=(arguments.get("payload") if isinstance(arguments.get("payload"), dict) else {}),
            )
        return {"status": "ok"}


class ScopeRejectingResearchTools(FakeResearchTools):
    async def execute(self, *, task, tool_name: str, arguments: dict[str, object]):
        if tool_name == "submit_crawl":
            raise ResearchTaskConflict("crawl platform is outside this research task scope")
        return await super().execute(task=task, tool_name=tool_name, arguments=arguments)


def _seed_content(database: Path, tmp_path: Path) -> str:
    crawler = CrawlerTaskRepository(database)
    task = crawler.create(
        platform="bili",
        crawler_type="search",
        keywords="AI workbench",
        login_type="qrcode",
        requested_count=1,
        output_dir=str(tmp_path / "output"),
        log_path=str(tmp_path / "logs" / "seed.log"),
        qrcode_path=str(tmp_path / "qrcode.png"),
    )
    assert crawler.claim_next() is not None
    LibraryRepository(database).ingest_task(
        task_id=str(task["id"]),
        batch=TaskEntityBatch(
            contents=[
                NormalizedContent(
                    platform="bili",
                    source_content_id="seed-1",
                    content_type="video",
                    title="Local-first AI workspace",
                    description="agent memory evidence graph",
                    source_url="https://example.test/seed-1",
                    cover_url=None,
                    author_source_id="creator-1",
                    author_name="Author",
                    published_at=None,
                    source_keyword="AI workbench",
                    view_count=1,
                    like_count=1,
                    favorite_count=0,
                    comment_count=0,
                    share_count=0,
                    raw_payload={},
                )
            ],
            creators=[],
            comments=[],
            actual_count=1,
        ),
    )
    with repository_connection(database) as connection:
        return str(connection.execute("SELECT id FROM library_contents LIMIT 1").fetchone()[0])


def test_runtime_plans_researches_with_tools_and_summarizes(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task_id = str(task["id"])
    content_id = _seed_content(database, tmp_path)
    with repository_connection(database) as connection:
        connection.execute(
            "UPDATE research_tasks SET consumed_crawl_count = 2 WHERE id = ?",
            (task_id,),
        )
    ai_repository = Mock()
    ai_repository.list_routes.return_value = [
        {
            "role": "tool_calling",
            "model_record_id": "model-1",
            "provider_name": "MiniMax",
            "model_id": "MiniMax-M3",
            "model_enabled": True,
            "provider_enabled": True,
        }
    ]
    ai_repository.get_model.return_value = {
        "id": "model-1",
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_million": None,
        "output_price_per_million": None,
        "price_currency": None,
        "price_effective_at": None,
    }
    ai_repository.invocation_cost.return_value = None
    gateway = FakeResearchGateway(
        [
            ModelResponse(
                content='{"search_terms":["local-first workspace","agent memory","evidence graph"]}',
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=10, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="call-1",
                        name="save_finding",
                        arguments={"kind": "fact", "statement": "x", "content_ids": [content_id]},
                    )
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="tool work completed",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="artifact-inference",
                        name="save_finding",
                        arguments={
                            "kind": "inference",
                            "statement": "An evidence-backed inference.",
                            "derivation": "Derived from the saved fact.",
                            "content_ids": [content_id],
                        },
                    ),
                    ModelToolCall(
                        id="artifact-action",
                        name="propose_action",
                        arguments={"action": "review", "reason": "Owner review", "payload": {}},
                    ),
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="required artifacts saved",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="Final report with evidence IDs.",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=10),
            ),
        ]
    )
    runtime = ResearchRuntime(
        research=repository,
        ai_repository=ai_repository,
        gateway=gateway,
        tools=FakeResearchTools(repository, content_id),
    )

    async def run() -> None:
        assert await runtime.run_once() is True
        assert (repository.get_for_runtime(task_id) or {})["status"] == "Planning"
        assert await runtime.run_once() is True
        assert (repository.get_for_runtime(task_id) or {})["status"] == "Researching"
        assert await runtime.run_once() is True
        assert (repository.get_for_runtime(task_id) or {})["status"] == "Summarizing"
        assert await runtime.run_once() is True
        assert (repository.get_for_runtime(task_id) or {})["status"] == "AwaitingReview"

    asyncio.run(run())
    detail = repository.get(user_id=owner_id, task_id=task_id, detail=True)
    assert detail is not None
    assert detail["result"]["summary"] == "Final report with evidence IDs."
    assert detail["findings"][0]["evidence"][0]["content_id"] == content_id


def test_runtime_repairs_missing_inference_and_action_artifacts(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task_id = str(task["id"])
    content_id = _seed_content(database, tmp_path)
    with repository_connection(database) as connection:
        connection.execute(
            "UPDATE research_tasks SET consumed_crawl_count = 2 WHERE id = ?",
            (task_id,),
        )
    ai_repository = Mock()
    ai_repository.list_routes.return_value = [
        {
            "role": "tool_calling",
            "model_record_id": "model-1",
            "provider_name": "MiniMax",
            "model_id": "MiniMax-M3",
            "model_enabled": True,
            "provider_enabled": True,
        }
    ]
    ai_repository.get_model.return_value = {
        "id": "model-1",
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_million": None,
        "output_price_per_million": None,
        "price_currency": None,
        "price_effective_at": None,
    }
    ai_repository.invocation_cost.return_value = None
    gateway = FakeResearchGateway(
        [
            ModelResponse(
                content='{"search_terms":["local-first workspace","agent memory","evidence graph"]}',
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=10, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="fact-call",
                        name="save_finding",
                        arguments={
                            "kind": "fact",
                            "statement": "A durable fact.",
                            "content_ids": [content_id],
                        },
                    )
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="The evidence pass is complete.",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="inference-call",
                        name="save_finding",
                        arguments={
                            "kind": "inference",
                            "statement": "The evidence suggests a workflow opportunity.",
                            "derivation": "Derived from the durable fact.",
                            "content_ids": [content_id],
                        },
                    ),
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="The inference artifact is saved.",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="action-call",
                        name="propose_action",
                        arguments={
                            "action": "collect_more_evidence",
                            "reason": "Validate the opportunity with a second source.",
                            "payload": {"content_id": content_id},
                        },
                    )
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="The action artifact is saved.",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="Final report with facts, inference and action.",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=10),
            ),
        ]
    )
    runtime = ResearchRuntime(
        research=repository,
        ai_repository=ai_repository,
        gateway=gateway,
        tools=FakeResearchTools(repository, content_id),
    )

    async def run() -> None:
        assert await runtime.run_once() is True
        assert await runtime.run_once() is True
        assert await runtime.run_once() is True
        assert (repository.get_for_runtime(task_id) or {})["status"] == "Summarizing"
        assert await runtime.run_once() is True

    asyncio.run(run())
    detail = repository.get(user_id=owner_id, task_id=task_id, detail=True)
    assert detail is not None
    assert detail["status"] == "AwaitingReview"
    assert {finding["kind"] for finding in detail["findings"]} == {"fact", "inference"}
    assert detail["proposed_actions"][0]["action"] == "collect_more_evidence"
    assert any(
        entry["event"] == "artifact_gate"
        and entry["reason"] == "missing_inference_and_action"
        for entry in detail["execution_trace"]
    )


def test_runtime_returns_scope_tool_error_to_model_and_keeps_researching(
    tmp_path: Path,
) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task_id = str(task["id"])
    content_id = _seed_content(database, tmp_path)
    with repository_connection(database) as connection:
        connection.execute(
            "UPDATE research_tasks SET consumed_crawl_count = 2 WHERE id = ?",
            (task_id,),
        )
    ai_repository = Mock()
    ai_repository.list_routes.return_value = [
        {
            "role": "tool_calling",
            "model_record_id": "model-1",
            "provider_name": "MiniMax",
            "model_id": "MiniMax-M3",
            "model_enabled": True,
            "provider_enabled": True,
        }
    ]
    ai_repository.get_model.return_value = {
        "id": "model-1",
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_million": None,
        "output_price_per_million": None,
        "price_currency": None,
        "price_effective_at": None,
    }
    ai_repository.invocation_cost.return_value = None
    gateway = FakeResearchGateway(
        [
            ModelResponse(
                content='{"search_terms":["local-first workspace","agent memory","evidence graph"]}',
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=10, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="scope-call",
                        name="submit_crawl",
                        arguments={"platform": "zhihu", "keywords": "out of scope"},
                    )
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="finding-call",
                        name="save_finding",
                        arguments={
                            "kind": "fact",
                            "statement": "A real evidence-bound finding.",
                            "content_ids": [content_id],
                        },
                    )
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="Research complete",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="artifact-inference",
                        name="save_finding",
                        arguments={
                            "kind": "inference",
                            "statement": "An evidence-backed inference.",
                            "derivation": "Derived from the saved fact.",
                            "content_ids": [content_id],
                        },
                    ),
                    ModelToolCall(
                        id="artifact-action",
                        name="propose_action",
                        arguments={"action": "review", "reason": "Owner review", "payload": {}},
                    ),
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="required artifacts saved",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ModelResponse(
                content="Final report with evidence IDs.",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=10),
            ),
        ]
    )
    runtime = ResearchRuntime(
        research=repository,
        ai_repository=ai_repository,
        gateway=gateway,
        tools=ScopeRejectingResearchTools(repository, content_id),
    )

    async def run() -> None:
        assert await runtime.run_once() is True
        assert await runtime.run_once() is True
        assert await runtime.run_once() is True
        assert (repository.get_for_runtime(task_id) or {})["status"] == "Summarizing"
        assert await runtime.run_once() is True

    asyncio.run(run())
    detail = repository.get(user_id=owner_id, task_id=task_id, detail=True)
    assert detail is not None
    assert detail["status"] == "AwaitingReview"
    assert detail["findings"][0]["evidence"][0]["content_id"] == content_id
    assert any(
        entry["event"] == "tool_error"
        and entry["reason"] == "crawl platform is outside this research task scope"
        for entry in detail["execution_trace"]
    )


def test_runtime_converges_after_protocol_error_when_findings_exist(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task_id = str(task["id"])
    content_id = _seed_content(database, tmp_path)
    with repository_connection(database) as connection:
        connection.execute(
            "UPDATE research_tasks SET consumed_crawl_count = 2 WHERE id = ?",
            (task_id,),
        )
    ai_repository = Mock()
    ai_repository.list_routes.return_value = [
        {
            "role": "tool_calling",
            "model_record_id": "model-1",
            "provider_name": "MiniMax",
            "model_id": "MiniMax-M3",
            "model_enabled": True,
            "provider_enabled": True,
        }
    ]
    ai_repository.get_model.return_value = {
        "id": "model-1",
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_million": None,
        "output_price_per_million": None,
        "price_currency": None,
        "price_effective_at": None,
    }
    ai_repository.invocation_cost.return_value = None
    gateway = FakeResearchGateway(
        [
            ModelResponse(
                content='{"search_terms":["local-first workspace","agent memory","evidence graph"]}',
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=10, output_tokens=5),
            ),
            ModelResponse(
                content=None,
                provider="MiniMax",
                model="MiniMax-M3",
                tool_calls=[
                    ModelToolCall(
                        id="finding-call",
                        name="save_finding",
                        arguments={
                            "kind": "fact",
                            "statement": "A durable evidence-bound finding.",
                            "content_ids": [content_id],
                        },
                    )
                ],
                usage=ModelUsage(input_tokens=20, output_tokens=5),
            ),
            ProviderError(
                code="protocol_error",
                safe_summary="Provider returned an invalid message",
                retryable=False,
            ),
            ModelResponse(
                content="Final report with the durable finding.",
                provider="MiniMax",
                model="MiniMax-M3",
                usage=ModelUsage(input_tokens=20, output_tokens=10),
            ),
        ]
    )
    runtime = ResearchRuntime(
        research=repository,
        ai_repository=ai_repository,
        gateway=gateway,
        tools=FakeResearchTools(repository, content_id),
    )

    async def run() -> None:
        assert await runtime.run_once() is True
        assert await runtime.run_once() is True
        assert await runtime.run_once() is True
        assert (repository.get_for_runtime(task_id) or {})["status"] == "Summarizing"
        assert await runtime.run_once() is True

    asyncio.run(run())
    detail = repository.get(user_id=owner_id, task_id=task_id, detail=True)
    assert detail is not None
    assert detail["status"] == "AwaitingReview"
    assert detail["result"]["summary"] == "Final report with the durable finding."
    assert any(
        entry["event"] == "model_error"
        and entry["reason"] == "Provider returned an invalid message"
        for entry in detail["execution_trace"]
    )


def test_runtime_budget_reasons_and_lifecycle_guards(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id, cost_limit="1.00", cost_currency="USD")
    ai_repository = Mock()
    ai_repository.list_routes.return_value = []
    runtime = ResearchRuntime(
        research=repository,
        ai_repository=ai_repository,
        gateway=Mock(),
        tools=Mock(),
    )
    current = repository.get_for_runtime(str(task["id"]))
    assert current is not None
    current["context"] = {"crawl_requested": True}
    current["consumed_crawl_count"] = 2
    assert runtime._budget_reason(current) == "crawl task budget reached"
    current["context"] = {}
    current["consumed_crawl_count"] = 0
    current["consumed_content_count"] = 100
    assert runtime._budget_reason(current) == "new content budget reached"
    current["consumed_content_count"] = 0
    current["input_tokens"] = 50_000
    assert runtime._budget_reason(current) == "token budget reached"
    current["input_tokens"] = 0
    current["budget_cost_enabled"] = True
    current["estimated_cost"] = "1.00"
    assert runtime._budget_reason(current) == "configured cost budget reached"
    current["status"] = "Researching"
    current["waiting_crawl_task_id"] = None
    current["context"] = {"crawl_requested": True}
    current["consumed_crawl_count"] = 2
    normalized = runtime._clear_stale_completed_crawl_marker(current)
    assert normalized["context"]["crawl_requested"] is False
    assert runtime._safe_failure(ProviderError(code="unreachable", safe_summary="safe", retryable=False)) == "safe"
    assert runtime._safe_failure(ResearchTaskConflict("conflict")) == "conflict"
    assert runtime._safe_failure(ValueError("secret-looking detail")) == "Research runtime failed while executing a bounded step"

    async def lifecycle() -> None:
        await runtime.start()
        await runtime.stop()

    asyncio.run(lifecycle())


def test_runtime_safety_helpers_bound_context() -> None:
    assert _json('{"ok": true}', {}) == {"ok": True}
    assert _json("not-json", {}) == {}
    safe = _safe_arguments({"long": "x" * 800, "list": ["y" * 300]})
    assert len(str(safe["long"])) == 500
    assert len(str(safe["list"][0])) == 200
    assert _elapsed_from("not-a-timestamp") == 0


def test_runtime_plan_keywords_are_bounded_and_non_verbatim() -> None:
    keywords = ResearchRuntime._plan_keywords(
        "1. local-first workspace, 2. agent memory, 3. evidence graph, 4. local-first workspace",
        "Find AI workbench products",
    )
    assert keywords == [
        "local-first workspace",
        "agent memory",
        "evidence graph",
    ]
    assert ResearchRuntime._plan_keywords(
        "```json\n{\"search_terms\": [\"local-first workspace\", \"agent memory\", \"evidence graph\"]}\n```",
        "Find AI workbench products",
    ) == [
        "local-first workspace",
        "agent memory",
        "evidence graph",
    ]


def test_research_api_requires_owner_session_csrf_and_returns_task(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/research/tasks",
        json={"objective": "Find AI workbench products", "platforms": ["bili"]},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] in {"Draft", "Planning", "Researching", "Failed"}
    assert "encrypted_api_key" not in response.text

    missing_csrf = TestClient(client.app)
    missing_csrf.cookies.update(client.cookies)
    denied = missing_csrf.post(
        "/api/research/tasks",
        json={"objective": "Another bounded research objective"},
        headers={"Origin": "http://testserver"},
    )
    assert denied.status_code == 403


def test_research_api_detail_controls_actions_and_sse(
    client: TestClient,
    owner_id: str,
) -> None:
    repository = client.app.state.research_repository
    task = repository.create(
        user_id=owner_id,
        objective="Review AI workspace evidence",
        platforms=["bili"],
        crawl_limit=2,
        content_limit=100,
        duration_seconds=3600,
        token_limit=50_000,
        cost_limit=None,
        cost_currency=None,
    )
    task_id = str(task["id"])
    repository.control(task_id, "pause", "hold for API test")
    assert client.get(f"/api/research/tasks/{task_id}").status_code == 200
    assert client.get("/api/research/tasks").status_code == 200
    assert client.post(f"/api/research/tasks/{task_id}/pause", json={}).status_code == 200
    assert client.post(f"/api/research/tasks/{task_id}/resume", json={}).status_code == 200

    review = repository.create(
        user_id=owner_id,
        objective="Review a completed research result",
        platforms=["bili"],
        crawl_limit=2,
        content_limit=100,
        duration_seconds=3600,
        token_limit=50_000,
        cost_limit=None,
        cost_currency=None,
    )
    review_id = str(review["id"])
    repository.control(review_id, "pause")
    repository.transition(review_id, status="AwaitingReview", reason="test")
    action = repository.add_action(
        task_id=review_id,
        action="review",
        reason="owner",
        payload={},
    )
    approved = client.post(
        f"/api/research/tasks/{review_id}/actions/{action['id']}/approve"
    )
    assert approved.status_code == 200
    rerun = client.post(f"/api/research/tasks/{review_id}/rerun", json={})
    assert rerun.status_code == 200
    repository.transition(review_id, status="AwaitingReview", reason="again")
    completed = client.post(f"/api/research/tasks/{review_id}/complete")
    assert completed.status_code == 200
    stream = client.get(f"/api/research/tasks/{review_id}/events")
    assert stream.status_code == 200
    assert "event: complete" in stream.text

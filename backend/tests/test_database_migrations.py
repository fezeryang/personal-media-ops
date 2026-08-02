import sqlite3
from pathlib import Path

import pytest

from app.database_migrations import (
    DatabaseMigrationRequired,
    get_current_revision,
    get_head_revision,
    require_database_current,
)
from tests.alembic_utils import run_alembic_command

LEGACY_REVISION = "0001_legacy_tasks"
MULTIPLATFORM_REVISION = "0002_multiplatform_tasks"
REMAINING_PLATFORMS_REVISION = "0003_remaining_platforms"
LIBRARY_REVISION = "0005_library_entities"
STAGE_SEVEN_REVISION = "0009_metrics_and_intelligence"
REGISTERED_PLATFORMS = ("bili", "xhs", "dy", "zhihu", "wb", "tieba", "ks")
LEGACY_TASK_COLUMNS = (
    "id",
    "platform",
    "crawler_type",
    "keywords",
    "login_type",
    "status",
    "requested_count",
    "actual_count",
    "output_dir",
    "log_path",
    "qrcode_path",
    "pid",
    "error_message",
    "created_at",
    "started_at",
    "finished_at",
    "cancel_requested",
)
LEGACY_TASK_VALUES = (
    "28a58041-9be7-4b39-9dea-2493fe10c249",
    "bili",
    "search",
    "AI Agent",
    "qrcode",
    "succeeded",
    20,
    7,
    "/var/lib/mediaops/crawler-output/tasks/28a58041",
    "/var/log/mediaops/crawler/28a58041.log",
    "/var/lib/mediaops/qrcodes/28a58041.png",
    1234,
    None,
    "2026-07-25T12:00:00Z",
    "2026-07-25T12:00:01Z",
    "2026-07-25T12:01:00Z",
    0,
)


def create_legacy_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE crawler_tasks (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL CHECK (platform = 'bili'),
                crawler_type TEXT NOT NULL CHECK (crawler_type = 'search'),
                keywords TEXT NOT NULL CHECK (length(trim(keywords)) > 0),
                login_type TEXT NOT NULL CHECK (login_type = 'qrcode'),
                status TEXT NOT NULL CHECK (
                    status IN (
                        'pending', 'running', 'waiting_login',
                        'succeeded', 'failed', 'cancelled'
                    )
                ),
                requested_count INTEGER NOT NULL
                    CHECK (requested_count BETWEEN 1 AND 20),
                actual_count INTEGER NOT NULL DEFAULT 0
                    CHECK (actual_count >= 0),
                output_dir TEXT NOT NULL,
                log_path TEXT NOT NULL,
                qrcode_path TEXT NOT NULL,
                pid INTEGER,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0
                    CHECK (cancel_requested IN (0, 1))
            );
            CREATE INDEX idx_crawler_tasks_status_created
            ON crawler_tasks (status, created_at);
            """
        )
        connection.execute(
            """
            INSERT INTO crawler_tasks VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            LEGACY_TASK_VALUES,
        )


def read_task_values(database_path: Path) -> tuple[object, ...]:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            f"""
            SELECT {", ".join(LEGACY_TASK_COLUMNS)}
            FROM crawler_tasks WHERE id = ?
            """,
            (LEGACY_TASK_VALUES[0],),
        ).fetchone()
    assert row is not None
    return row


def test_upgrade_blank_database_to_head(tmp_path: Path) -> None:
    database_path = tmp_path / "blank" / "mediaops.db"

    run_alembic_command(database_path, "upgrade", "head")

    assert get_current_revision(database_path) == get_head_revision()
    with sqlite3.connect(database_path) as connection:
        for platform in REGISTERED_PLATFORMS:
            connection.execute(
                """
                INSERT INTO crawler_tasks (
                    id, platform, crawler_type, keywords, login_type, status,
                    requested_count, actual_count, output_dir, log_path,
                    qrcode_path, created_at, cancel_requested
                )
                VALUES (?, ?, 'search', 'test', 'qrcode', 'pending',
                        1, 0, '/output', '/log', '/qrcode',
                        '2026-07-26T00:00:00Z', 0)
                """,
                (f"{platform}-task", platform),
            )
        assert {
            "library_contents",
            "library_creators",
            "library_comments",
            "users",
            "sessions",
            "api_keys",
            "subscriptions",
            "subscription_platforms",
            "subscription_runs",
            "subscription_run_tasks",
            "library_tags",
            "library_content_tags",
            "library_collections",
            "library_collection_items",
            "creator_watchlist",
            "creator_watch_runs",
            "content_metric_snapshots",
            "creator_metric_snapshots",
            "trend_signals",
            "trend_signal_contents",
            "briefs",
            "brief_items",
            "brief_item_contents",
            "brief_item_trends",
            "brief_schedules",
            "ai_providers",
            "ai_provider_secrets",
            "ai_models",
            "ai_model_routes",
            "ai_provider_health_checks",
            "ai_model_invocations",
            "research_tasks",
            "findings",
            "finding_contents",
            "events",
            "event_contents",
            "research_queries",
            "evidence_occurrences",
        }.issubset({
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                """
            )
        })
        indexes = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'index'
                """
            )
        }
        assert {
            "idx_library_contents_published_at",
            "idx_library_contents_last_collected_at",
            "idx_library_contents_source_keyword",
            "idx_library_comments_content",
            "idx_library_comments_parent",
            "idx_sessions_user_active",
            "idx_api_keys_user_active",
            "idx_subscriptions_due",
            "idx_subscription_runs_subscription_created",
            "idx_library_contents_favorite",
            "idx_content_metric_snapshots_entity_time",
            "idx_creator_metric_snapshots_entity_time",
            "idx_trend_signals_window_score",
            "idx_briefs_user_created",
            "idx_ai_providers_enabled",
            "idx_ai_models_provider_enabled",
            "idx_ai_model_routes_model",
            "idx_ai_provider_health_provider_checked",
            "idx_ai_invocations_started",
            "idx_ai_invocations_provider_model",
            "idx_ai_invocations_route_started",
            "idx_ai_invocations_correlation",
            "idx_research_queries_task_created",
            "idx_research_queries_normalized",
            "idx_research_queries_parent",
            "idx_evidence_occurrences_task_content",
            "idx_evidence_occurrences_finding",
            "idx_evidence_occurrences_query",
        }.issubset(indexes)


def test_upgrade_from_0011_preserves_research_findings_and_adds_quality_columns(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "research-legacy.db"
    run_alembic_command(database_path, "upgrade", "0011_ai_runtime_research")
    now = "2026-08-01T00:00:00Z"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO users (
                id, username, password_hash, is_active, failed_login_count,
                created_at, updated_at
            ) VALUES ('research-owner', 'research-owner', 'hash', 1, 0, ?, ?)
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO library_contents (
                id, platform, source_content_id, content_type, title,
                first_collected_at, last_collected_at, raw_payload,
                created_at, updated_at
            ) VALUES ('research-content', 'bili', 'BV-research', 'video',
                      'Preserved research evidence', ?, ?, '{}', ?, ?)
            """,
            (now, now, now, now),
        )
        connection.execute(
            """
            INSERT INTO research_tasks (
                id, user_id, task_type, objective, platforms, status,
                plan, context, execution_trace, proposed_actions,
                route_snapshot, budget_crawl_limit, budget_content_limit,
                budget_duration_seconds, budget_token_limit,
                budget_cost_enabled, created_at, updated_at
            ) VALUES (
                'research-task', 'research-owner', 'research', 'Preserve this task',
                '["bili"]', 'AwaitingReview', '{}', '{}', '[]', '[]', '{}',
                2, 100, 3600, 50000, 0, ?, ?
            )
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO findings (
                id, research_task_id, round_number, kind, statement,
                derivation, status, created_at, updated_at
            ) VALUES (
                'finding-legacy', 'research-task', 1, 'inference',
                'A preserved inference', 'Legacy derivation', 'active', ?, ?
            )
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO finding_contents (finding_id, content_id, evidence_role)
            VALUES ('finding-legacy', 'research-content', 'derived_from')
            """
        )

    run_alembic_command(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        task_count = connection.execute(
            "SELECT COUNT(*) FROM research_tasks WHERE id = 'research-task'"
        ).fetchone()[0]
        finding_count = connection.execute(
            "SELECT COUNT(*) FROM findings WHERE id = 'finding-legacy'"
        ).fetchone()[0]
        evidence = connection.execute(
            """
            SELECT support_type, support_strength, counterevidence_status
            FROM finding_contents fc
            JOIN findings f ON f.id = fc.finding_id
            WHERE fc.finding_id = 'finding-legacy'
            """
        ).fetchone()
        quality_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert task_count == 1
    assert finding_count == 1
    assert evidence == ("background", "weak", "unknown")
    assert {"research_queries", "evidence_occurrences"}.issubset(quality_tables)
    assert integrity == "ok"
    assert get_current_revision(database_path) == get_head_revision()


def test_upgrade_from_0012_preserves_query_lifecycle_history(tmp_path: Path) -> None:
    database_path = tmp_path / "research-query-history.db"
    run_alembic_command(database_path, "upgrade", "0012_research_quality_foundation")
    now = "2026-08-02T00:00:00Z"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO users (
                id, username, password_hash, is_active, failed_login_count,
                created_at, updated_at
            ) VALUES ('query-owner', 'query-owner', 'hash', 1, 0, ?, ?)
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO research_tasks (
                id, user_id, task_type, objective, platforms, status,
                plan, context, execution_trace, proposed_actions,
                route_snapshot, budget_crawl_limit, budget_content_limit,
                budget_duration_seconds, budget_token_limit,
                budget_cost_enabled, created_at, updated_at
            ) VALUES (
                'query-task', 'query-owner', 'research', 'Preserve query history',
                '["bili"]', 'Done', '{}', '{}', '[]', '[]', '{}',
                2, 100, 3600, 50000, 0, ?, ?
            )
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO research_queries (
                id, research_task_id, query, normalized_query, query_type,
                platform, source_type, generation_reason, specificity_score,
                novelty_score, noise_risk_score, expected_value_score, status,
                executed_at, result_count, new_content_count,
                existing_content_count, updated_content_count,
                duplicate_evidence_count, created_at, updated_at
            ) VALUES (
                'query-history', 'query-task', 'WorkBuddy 使用体验',
                'workbuddy 使用体验', 'product', 'bili', 'goal',
                'historical query', 0.9, 0.8, 0.1, 0.7, 'completed',
                ?, 4, 2, 1, 1, 0, ?, ?
            )
            """,
            (now, now, now),
        )

    run_alembic_command(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        lifecycle = connection.execute(
            "SELECT status, lifecycle_status FROM research_queries WHERE id = 'query-history'"
        ).fetchone()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert lifecycle == ("completed", "completed")
    assert integrity == "ok"


def test_upgrade_from_0013_backfills_legacy_intent_without_reexecuting(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "research-8c-compatibility.db"
    run_alembic_command(database_path, "upgrade", "0013_cross_platform_research_completion")
    now = "2026-08-02T00:00:00Z"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO users (
                id, username, password_hash, is_active, failed_login_count,
                created_at, updated_at
            ) VALUES ('legacy-intent-owner', 'legacy-intent-owner', 'hash', 1, 0, ?, ?)
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO research_tasks (
                id, user_id, task_type, objective, platforms, status,
                plan, context, execution_trace, proposed_actions,
                route_snapshot, budget_crawl_limit, budget_content_limit,
                budget_duration_seconds, budget_token_limit,
                budget_cost_enabled, created_at, updated_at
            ) VALUES (
                'legacy-intent-task', 'legacy-intent-owner', 'research',
                'Preserve this 8C research goal', '["bili"]', 'Done',
                '{}', '{}', '[]', '[]', '{}', 2, 100, 3600, 50000,
                0, ?, ?
            )
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO research_queries (
                id, research_task_id, query, normalized_query, query_type,
                platform, source_type, generation_reason, specificity_score,
                novelty_score, noise_risk_score, expected_value_score, status,
                result_count, new_content_count, existing_content_count,
                updated_content_count, duplicate_evidence_count, created_at, updated_at
            ) VALUES (
                'legacy-user-goal', 'legacy-intent-task',
                'Preserve this 8C research goal', 'preserve this 8c research goal',
                'generic_topic', 'bili', 'goal', 'legacy goal', 0.4, 1, 0.4,
                NULL, 'generated', 0, 0, 0, 0, 0, ?, ?
            )
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO research_queries (
                id, research_task_id, query, normalized_query, query_type,
                platform, source_type, generation_reason, specificity_score,
                novelty_score, noise_risk_score, expected_value_score, status,
                result_count, new_content_count, existing_content_count,
                updated_content_count, duplicate_evidence_count, created_at, updated_at
            ) VALUES (
                'legacy-execution', 'legacy-intent-task', '具体产品体验',
                '具体产品体验', 'product', 'bili', 'content_entity',
                'legacy execution', 0.8, 1, 0.1, 0.7, 'completed',
                2, 1, 1, 0, 0, ?, ?
            )
            """,
            (now, now),
        )

    run_alembic_command(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        intent = connection.execute(
            "SELECT intent_source, confidence FROM research_intents WHERE research_task_id = ?",
            ("legacy-intent-task",),
        ).fetchone()
        queries = connection.execute(
            """
            SELECT record_type, gate_status, intent_id
            FROM research_queries WHERE research_task_id = ? ORDER BY id
            """,
            ("legacy-intent-task",),
        ).fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert intent == ("legacy_migrated", 0.0)
    assert queries[0][0:2] == ("execution_query", "completed")
    assert queries[1][0:2] == ("user_goal", "not_applicable")
    assert queries[0][2] == queries[1][2]
    assert integrity == "ok"


def test_upgrade_from_0009_preserves_existing_product_data(tmp_path: Path) -> None:
    database_path = tmp_path / "stage-seven.db"
    run_alembic_command(database_path, "upgrade", STAGE_SEVEN_REVISION)
    now = "2026-08-01T00:00:00Z"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, finished_at, cancel_requested
            ) VALUES (
                'existing-task', 'bili', 'search', 'AI', 'qrcode',
                'succeeded', 1, 1, '/output', '/log', '/qrcode', ?, ?, 0
            )
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO library_contents (
                id, platform, source_content_id, content_type, title,
                first_collected_at, last_collected_at, view_count,
                raw_payload, created_at, updated_at, is_favorite
            ) VALUES (
                'existing-content', 'bili', 'BV-existing', 'video',
                'Existing content', ?, ?, 10, '{}', ?, ?, 0
            )
            """,
            (now, now, now, now),
        )
        connection.execute(
            """
            INSERT INTO users (
                id, username, password_hash, is_active, failed_login_count,
                created_at, updated_at
            ) VALUES ('owner-1', 'owner', 'hash', 1, 0, ?, ?)
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO subscriptions (
                id, user_id, name, query, enabled, schedule_type,
                schedule_config, timezone, consecutive_failures,
                created_at, updated_at
            ) VALUES (
                'subscription-1', 'owner-1', 'Existing subscription', 'AI',
                1, 'daily', '{"time_of_day":"08:00"}', 'Asia/Shanghai',
                0, ?, ?
            )
            """,
            (now, now),
        )
        connection.execute(
            """
            INSERT INTO trend_signals (
                id, topic, window_start, window_end, score, volume_score,
                velocity_score, cross_platform_score, engagement_score,
                platforms, explanation, evidence, status, formula_version,
                created_at
            ) VALUES (
                'trend-1', 'AI', ?, ?, 50, 50, 50, 50, 50,
                '["bili"]', 'Existing signal', '[]', 'detected', 'rules-v1', ?
            )
            """,
            (now, now, now),
        )
        before = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "crawler_tasks",
                "library_contents",
                "users",
                "subscriptions",
                "trend_signals",
            )
        }

    run_alembic_command(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        after = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before
        }
        roles = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT role, model_id FROM ai_model_routes"
            )
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert after == before
    assert roles == {
        "default": None,
        "fast": None,
        "deep": None,
        "tool_calling": None,
        "final_report": None,
        "fallback": None,
    }
    assert integrity == "ok"
    assert get_current_revision(database_path) == get_head_revision()


def test_ai_gateway_downgrade_refuses_configured_provider(tmp_path: Path) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", "head")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO ai_providers (
                id, name, provider_type, protocol, base_url, enabled,
                timeout_seconds, max_retries, concurrency_limit,
                created_at, updated_at
            ) VALUES (
                'provider-1', 'Existing provider', 'custom_openai',
                'openai_compatible', 'https://example.test/v1', 0,
                30, 0, 1, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z'
            )
            """
        )

    result = run_alembic_command(
        database_path,
        "downgrade",
        STAGE_SEVEN_REVISION,
        check=False,
    )

    assert result.returncode != 0
    assert "refusing to discard configured AI providers" in result.stderr
    assert get_current_revision(database_path) == get_head_revision()


def test_upgrade_from_0003_adds_modes_without_changing_old_task(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(
        database_path,
        "upgrade",
        REMAINING_PLATFORMS_REVISION,
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, cancel_requested
            )
            VALUES (
                'old-task', 'xhs', 'search', 'AI', 'qrcode', 'succeeded',
                5, 5, '/output', '/log', '/qrcode',
                '2026-07-26T00:00:00Z', 0
            )
            """
        )

    run_alembic_command(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        old = connection.execute(
            """
            SELECT platform, crawler_type, keywords, status, actual_count
            FROM crawler_tasks WHERE id = 'old-task'
            """
        ).fetchone()
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, cancel_requested, target_ids
            )
            VALUES (
                'detail-task', 'bili', 'detail', NULL, 'qrcode', 'pending',
                1, 0, '/output', '/log', '/qrcode',
                '2026-07-28T00:00:00Z', 0, '["BV1"]'
            )
            """
        )
    assert old == ("xhs", "search", "AI", "succeeded", 5)


def test_upgrade_from_0005_preserves_tasks_and_library_entities(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "stage-six.db"
    run_alembic_command(database_path, "upgrade", LIBRARY_REVISION)
    now = "2026-07-28T00:00:00Z"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, finished_at, cancel_requested
            )
            VALUES (
                'stage-six-task', 'bili', 'search', 'AI Agent', 'qrcode',
                'succeeded', 2, 1, '/output', '/log', '/qrcode', ?, ?, 0
            )
            """,
            (now, now),
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
                'stage-six-content', 'bili', 'BV-stage-six', 'video',
                'Preserved content', NULL,
                'https://www.bilibili.com/video/BV-stage-six', NULL,
                NULL, NULL, NULL, ?, ?, 'AI Agent', 10, 2, NULL, 1,
                NULL, '{}', ?, ?
            )
            """,
            (now, now, now, now),
        )
        connection.execute(
            """
            INSERT INTO crawl_task_entities (
                task_id, entity_type, entity_id, collected_at
            )
            VALUES (
                'stage-six-task', 'content', 'stage-six-content', ?
            )
            """,
            (now,),
        )

    run_alembic_command(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        task = connection.execute(
            """
            SELECT status, actual_count FROM crawler_tasks
            WHERE id = 'stage-six-task'
            """
        ).fetchone()
        content = connection.execute(
            """
            SELECT title, view_count, is_favorite FROM library_contents
            WHERE id = 'stage-six-content'
            """
        ).fetchone()
        provenance = connection.execute(
            """
            SELECT COUNT(*) FROM crawl_task_entities
            WHERE task_id = 'stage-six-task'
            """
        ).fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert task == ("succeeded", 1)
    assert content == ("Preserved content", 10, 0)
    assert provenance == 1
    assert integrity == "ok"
    assert get_current_revision(database_path) == get_head_revision()


def test_runtime_head_matches_alembic_script_head(tmp_path: Path) -> None:
    result = run_alembic_command(tmp_path / "unused.db", "heads")

    assert result.stdout.split()[0] == get_head_revision()


def test_head_rejects_unregistered_platform(tmp_path: Path) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", "head")

    with (
        sqlite3.connect(database_path) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, cancel_requested
            )
            VALUES (
                'youtube-task', 'youtube', 'search', 'test', 'qrcode',
                'pending', 1, 0, '/output', '/log', '/qrcode',
                '2026-07-26T00:00:00Z', 0
            )
            """
        )


def test_upgrade_legacy_database_preserves_bilibili_row(tmp_path: Path) -> None:
    database_path = tmp_path / "mediaops.db"
    create_legacy_database(database_path)
    before = read_task_values(database_path)

    run_alembic_command(database_path, "upgrade", "head")

    assert read_task_values(database_path) == before
    assert get_current_revision(database_path) == get_head_revision()


def test_upgrade_from_0002_preserves_all_existing_platform_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", MULTIPLATFORM_REVISION)
    existing = (
        ("bili-task", "bili", "succeeded", 2),
        ("xhs-task", "xhs", "succeeded", 5),
        ("dy-task", "dy", "failed", 0),
    )
    with sqlite3.connect(database_path) as connection:
        for task_id, platform, status, actual_count in existing:
            connection.execute(
                """
                INSERT INTO crawler_tasks (
                    id, platform, crawler_type, keywords, login_type, status,
                    requested_count, actual_count, output_dir, log_path,
                    qrcode_path, error_message, created_at, finished_at,
                    cancel_requested
                )
                VALUES (?, ?, 'search', 'AI', 'qrcode', ?, 5, ?,
                        ?, ?, ?, ?, '2026-07-26T00:00:00Z',
                        '2026-07-26T00:01:00Z', 0)
                """,
                (
                    task_id,
                    platform,
                    status,
                    actual_count,
                    f"/output/{task_id}",
                    f"/log/{task_id}",
                    f"/qrcode/{task_id}",
                    None if status == "succeeded" else "resource constrained",
                ),
            )
        before = connection.execute(
            f"""
            SELECT {", ".join(LEGACY_TASK_COLUMNS)}
            FROM crawler_tasks ORDER BY id
            """
        ).fetchall()

    run_alembic_command(database_path, "upgrade", "head")

    with sqlite3.connect(database_path) as connection:
        after = connection.execute(
            f"""
            SELECT {", ".join(LEGACY_TASK_COLUMNS)}
            FROM crawler_tasks ORDER BY id
            """
        ).fetchall()
    assert after == before
    assert get_current_revision(database_path) == get_head_revision()


def test_runtime_rejects_missing_or_outdated_database(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"

    with pytest.raises(DatabaseMigrationRequired, match="upgrade head"):
        require_database_current(missing)

    create_legacy_database(missing)
    with pytest.raises(DatabaseMigrationRequired, match="upgrade head"):
        require_database_current(missing)


def test_downgrade_refuses_when_multiplatform_rows_exist(tmp_path: Path) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", "head")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, cancel_requested
            )
            VALUES (
                'xhs-task', 'xhs', 'search', 'test', 'qrcode', 'pending',
                1, 0, '/output', '/log', '/qrcode', '2026-07-26T00:00:00Z', 0
            )
            """
        )

    result = run_alembic_command(
        database_path,
        "downgrade",
        LEGACY_REVISION,
        check=False,
    )

    assert result.returncode != 0
    assert "non-Bilibili" in result.stderr
    assert get_current_revision(database_path) == get_head_revision()


def test_downgrade_to_0002_refuses_when_remaining_platform_rows_exist(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "mediaops.db"
    run_alembic_command(database_path, "upgrade", "head")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO crawler_tasks (
                id, platform, crawler_type, keywords, login_type, status,
                requested_count, actual_count, output_dir, log_path,
                qrcode_path, created_at, cancel_requested
            )
            VALUES (
                'zhihu-task', 'zhihu', 'search', 'test', 'qrcode', 'pending',
                1, 0, '/output', '/log', '/qrcode',
                '2026-07-28T00:00:00Z', 0
            )
            """
        )

    result = run_alembic_command(
        database_path,
        "downgrade",
        MULTIPLATFORM_REVISION,
        check=False,
    )

    assert result.returncode != 0
    assert "remaining-platform" in result.stderr
    assert get_current_revision(database_path) == get_head_revision()

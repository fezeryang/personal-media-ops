"""Persist research intent contracts and information value artifacts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_research_intent_and_information_utility"
down_revision: str | Sequence[str] | None = "0013_cross_platform_research_completion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INTENTS = (
    "discovery",
    "verification",
    "comparison",
    "trend_tracking",
    "pain_point_research",
    "competitor_scan",
    "creator_scan",
    "content_opportunity",
    "market_mapping",
    "product_opportunity",
    "monitoring",
)
UTILITY_TYPES = (
    "core_evidence",
    "discovery_seed",
    "background_context",
    "event_signal",
    "counterevidence",
    "memory_update",
    "action_trigger",
    "noise",
    "duplicate",
)


def _in_check(column: str, values: Sequence[str]) -> str:
    encoded = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({encoded})"


def upgrade() -> None:
    op.create_table(
        "research_intents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("original_request", sa.Text(), nullable=False),
        sa.Column("original_intent", sa.Text(), nullable=False),
        sa.Column("interpreted_goal", sa.Text(), nullable=False),
        sa.Column("primary_intent", sa.Text(), nullable=False),
        sa.Column("secondary_intents_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("subject_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("known_entities_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("known_constraints_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("unknowns_to_discover_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("time_scope_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("platform_preferences_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("target_audience", sa.Text()),
        sa.Column("evidence_requirements_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("negative_evidence_requirements_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("exclusions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("desired_output_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("success_criteria_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ambiguities_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("assumptions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("current_research_hypothesis", sa.Text(), nullable=False),
        sa.Column("intent_revisions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("intent_source", sa.Text(), nullable=False, server_default="fallback_default"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_intents_task",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("research_task_id", name="uq_research_intents_task"),
        sa.CheckConstraint(_in_check("primary_intent", INTENTS), name="ck_research_intents_primary"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_research_intents_confidence"),
        sa.CheckConstraint("version >= 1", name="ck_research_intents_version"),
        sa.CheckConstraint(
            "intent_source IN ('model', 'fallback_default', 'legacy_migrated', 'owner_revised')",
            name="ck_research_intents_source",
        ),
    )
    op.create_index(
        "idx_research_intents_task_updated",
        "research_intents",
        ["research_task_id", "updated_at"],
    )

    op.create_table(
        "research_intent_versions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("contract_json", sa.Text(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_intent_versions_task",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("research_task_id", "version", name="uq_research_intent_versions_task_version"),
        sa.CheckConstraint("version >= 1", name="ck_research_intent_versions_version"),
    )
    op.create_index(
        "idx_research_intent_versions_task_created",
        "research_intent_versions",
        ["research_task_id", "created_at"],
    )

    op.create_table(
        "research_intent_assumptions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("intent_version", sa.Integer(), nullable=False),
        sa.Column("assumption", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.Text()),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_intent_assumptions_task",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("status IN ('active', 'confirmed', 'rejected', 'superseded')", name="ck_research_intent_assumptions_status"),
    )
    op.create_index(
        "idx_research_intent_assumptions_task_status",
        "research_intent_assumptions",
        ["research_task_id", "status"],
    )

    op.create_table(
        "research_unknowns",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("unknown", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolution", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_unknowns_task",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("research_task_id", "unknown", name="uq_research_unknowns_task_unknown"),
        sa.CheckConstraint("priority >= 0", name="ck_research_unknowns_priority"),
        sa.CheckConstraint("evidence_count >= 0", name="ck_research_unknowns_evidence"),
        sa.CheckConstraint("status IN ('open', 'discovered', 'verified', 'unresolved')", name="ck_research_unknowns_status"),
    )
    op.create_index(
        "idx_research_unknowns_task_status_priority",
        "research_unknowns",
        ["research_task_id", "status", "priority"],
    )

    op.create_table(
        "research_alignment_reviews",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("alignment_score", sa.Float(), nullable=False),
        sa.Column("covered_requirements_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("missing_requirements_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("scope_drift_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("recommended_next_step", sa.Text()),
        sa.Column("review_status", sa.Text(), nullable=False, server_default="partial_completion"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_task_id"],
            ["research_tasks.id"],
            name="fk_research_alignment_reviews_task",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("alignment_score BETWEEN 0 AND 1", name="ck_research_alignment_score"),
        sa.CheckConstraint("review_status IN ('passed', 'needs_more_research', 'partial_completion')", name="ck_research_alignment_status"),
    )
    op.create_index(
        "idx_research_alignment_reviews_task_created",
        "research_alignment_reviews",
        ["research_task_id", "created_at"],
    )

    op.create_table(
        "content_research_utilities",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=False),
        sa.Column("utility_type", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("research_query_id", sa.Text()),
        sa.Column("source_finding_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["research_task_id"], ["research_tasks.id"], name="fk_content_research_utilities_task", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["library_contents.id"], name="fk_content_research_utilities_content", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["research_query_id"], ["research_queries.id"], name="fk_content_research_utilities_query", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_finding_id"], ["findings.id"], name="fk_content_research_utilities_finding", ondelete="SET NULL"),
        sa.UniqueConstraint("research_task_id", "content_id", "utility_type", name="uq_content_research_utilities_item"),
        sa.CheckConstraint(_in_check("utility_type", UTILITY_TYPES), name="ck_content_research_utilities_type"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_content_research_utilities_confidence"),
    )
    op.create_index(
        "idx_content_research_utilities_task_type",
        "content_research_utilities",
        ["research_task_id", "utility_type", "created_at"],
    )

    op.create_table(
        "research_entity_candidates",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("source_content_id", sa.Text()),
        sa.Column("relevance_to_intent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("novelty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("suggested_next_action", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="candidate_discovery"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["research_task_id"], ["research_tasks.id"], name="fk_research_entity_candidates_task", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_content_id"], ["library_contents.id"], name="fk_research_entity_candidates_content", ondelete="SET NULL"),
        sa.UniqueConstraint("research_task_id", "normalized_name", "entity_type", name="uq_research_entity_candidates_name"),
        sa.CheckConstraint("relevance_to_intent BETWEEN 0 AND 1", name="ck_research_entity_candidates_relevance"),
        sa.CheckConstraint("novelty BETWEEN 0 AND 1", name="ck_research_entity_candidates_novelty"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_research_entity_candidates_confidence"),
        sa.CheckConstraint("status IN ('candidate_discovery', 'accepted', 'dismissed')", name="ck_research_entity_candidates_status"),
    )
    op.create_index(
        "idx_research_entity_candidates_task_status",
        "research_entity_candidates",
        ["research_task_id", "status", "confidence"],
    )

    op.create_table(
        "research_event_candidates",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_content_id", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="candidate"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["research_task_id"], ["research_tasks.id"], name="fk_research_event_candidates_task", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_content_id"], ["library_contents.id"], name="fk_research_event_candidates_content", ondelete="SET NULL"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_research_event_candidates_confidence"),
        sa.CheckConstraint("status IN ('candidate', 'accepted', 'dismissed')", name="ck_research_event_candidates_status"),
    )
    op.create_index(
        "idx_research_event_candidates_task_created",
        "research_event_candidates",
        ["research_task_id", "created_at"],
    )

    op.create_table(
        "research_memory_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("research_task_id", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.Text(), nullable=False),
        sa.Column("memory_key", sa.Text(), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("source_content_id", sa.Text()),
        sa.Column("source_query_id", sa.Text()),
        sa.Column("source_finding_id", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_current", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["research_task_id"], ["research_tasks.id"], name="fk_research_memory_items_task", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_content_id"], ["library_contents.id"], name="fk_research_memory_items_content", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_query_id"], ["research_queries.id"], name="fk_research_memory_items_query", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_finding_id"], ["findings.id"], name="fk_research_memory_items_finding", ondelete="SET NULL"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_research_memory_items_confidence"),
        sa.CheckConstraint("is_current IN (0, 1)", name="ck_research_memory_items_current"),
    )
    op.create_index(
        "idx_research_memory_items_task_type_current",
        "research_memory_items",
        ["research_task_id", "memory_type", "is_current", "updated_at"],
    )

    with op.batch_alter_table("research_queries", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("record_type", sa.Text(), nullable=False, server_default="execution_query"))
        batch_op.add_column(sa.Column("gate_status", sa.Text(), nullable=False, server_default="pending"))
        batch_op.add_column(sa.Column("query_role", sa.Text(), nullable=False, server_default="seed_discovery"))
        batch_op.add_column(sa.Column("decision", sa.Text(), nullable=False, server_default="allow"))
        batch_op.add_column(sa.Column("intent_id", sa.Text()))
        batch_op.create_foreign_key(
            "fk_research_queries_intent",
            "research_intents",
            ["intent_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_research_queries_record_type",
            "record_type IN ('user_goal', 'execution_query')",
        )
        batch_op.create_check_constraint(
            "ck_research_queries_gate_status",
            "gate_status IN ('not_applicable', 'pending', 'allow', 'transform', 'hold', 'reject', 'completed')",
        )
        batch_op.create_check_constraint(
            "ck_research_queries_role",
            "query_role IN ('seed_discovery', 'entity_expansion', 'cross_platform_validation', 'counterevidence', 'competitor_scan', 'trend_probe', 'creator_scan', 'pain_point_probe')",
        )
        batch_op.create_check_constraint(
            "ck_research_queries_decision",
            "decision IN ('allow', 'transform', 'hold', 'reject')",
        )
    op.create_index(
        "idx_research_queries_task_record_type",
        "research_queries",
        ["research_task_id", "record_type", "created_at"],
    )
    op.create_index("idx_research_queries_intent", "research_queries", ["intent_id", "query_role"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE research_queries SET record_type = 'user_goal', "
            "gate_status = 'not_applicable', query_role = 'seed_discovery' "
            "WHERE lower(source_type) IN ('user_goal', 'goal')"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE research_queries SET gate_status = CASE "
            "WHEN status IN ('completed', 'failed') THEN 'completed' "
            "WHEN status IN ('rejected', 'rejected_generic', 'rejected_duplicate', 'rejected_low_relevance', 'rejected_low_value') THEN 'reject' "
            "WHEN status IN ('approved', 'approved_pending', 'running', 'executing') THEN 'allow' "
            "ELSE 'pending' END "
            "WHERE record_type = 'execution_query'"
        )
    )

    # Historical tasks retain their original objective and findings but gain a
    # read-only intent projection.  No old task is resumed or re-planned.
    rows = connection.execute(
        sa.text("SELECT id, objective, platforms FROM research_tasks")
    ).fetchall()
    import json
    import uuid
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for row in rows:
        row_data = row._mapping
        intent_id = str(uuid.uuid4())
        objective = str(row_data["objective"])
        platforms = row_data["platforms"] if isinstance(row_data["platforms"], str) else "[]"
        contract = {
            "original_request": objective,
            "original_intent": objective,
            "interpreted_goal": objective,
            "primary_intent": "discovery",
            "secondary_intents": [],
            "subject": {"description": objective},
            "known_entities": [],
            "known_constraints": [],
            "unknowns_to_discover": [],
            "time_scope": {},
            "platform_preferences": json.loads(platforms) if platforms.startswith("[") else [],
            "target_audience": None,
            "evidence_requirements": [],
            "negative_evidence_requirements": [],
            "exclusions": [],
            "desired_output": [],
            "success_criteria": [],
            "confidence": 0.0,
            "ambiguities": ["历史任务未保存结构化研究意图"],
            "assumptions": [],
            "current_research_hypothesis": objective,
            "intent_revisions": [],
            "intent_source": "legacy_migrated",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        encoded = {key: json.dumps(value, ensure_ascii=False, separators=(",", ":")) for key, value in {
            "secondary_intents_json": contract["secondary_intents"],
            "subject_json": contract["subject"],
            "known_entities_json": contract["known_entities"],
            "known_constraints_json": contract["known_constraints"],
            "unknowns_to_discover_json": contract["unknowns_to_discover"],
            "time_scope_json": contract["time_scope"],
            "platform_preferences_json": contract["platform_preferences"],
            "evidence_requirements_json": contract["evidence_requirements"],
            "negative_evidence_requirements_json": contract["negative_evidence_requirements"],
            "exclusions_json": contract["exclusions"],
            "desired_output_json": contract["desired_output"],
            "success_criteria_json": contract["success_criteria"],
            "ambiguities_json": contract["ambiguities"],
            "assumptions_json": contract["assumptions"],
            "intent_revisions_json": contract["intent_revisions"],
        }.items()}
        connection.execute(
            sa.text(
                "INSERT INTO research_intents ("
                "id, research_task_id, original_request, original_intent, interpreted_goal, primary_intent, "
                "secondary_intents_json, subject_json, known_entities_json, known_constraints_json, "
                "unknowns_to_discover_json, time_scope_json, platform_preferences_json, target_audience, "
                "evidence_requirements_json, negative_evidence_requirements_json, exclusions_json, "
                "desired_output_json, success_criteria_json, confidence, ambiguities_json, assumptions_json, "
                "current_research_hypothesis, intent_revisions_json, intent_source, version, created_at, updated_at"
                ") VALUES (:id, :task_id, :original_request, :original_intent, :interpreted_goal, 'discovery', "
                ":secondary, :subject, :known, :constraints, :unknowns, :time_scope, :platforms, NULL, "
                ":evidence, :negative, :exclusions, :output, :criteria, 0, :ambiguities, :assumptions, "
                ":hypothesis, :revisions, 'legacy_migrated', 1, :created_at, :updated_at)"
            ),
            {
                "id": intent_id,
                "task_id": str(row_data["id"]),
                "original_request": objective,
                "original_intent": objective,
                "interpreted_goal": objective,
                "secondary": encoded["secondary_intents_json"],
                "subject": encoded["subject_json"],
                "known": encoded["known_entities_json"],
                "constraints": encoded["known_constraints_json"],
                "unknowns": encoded["unknowns_to_discover_json"],
                "time_scope": encoded["time_scope_json"],
                "platforms": encoded["platform_preferences_json"],
                "evidence": encoded["evidence_requirements_json"],
                "negative": encoded["negative_evidence_requirements_json"],
                "exclusions": encoded["exclusions_json"],
                "output": encoded["desired_output_json"],
                "criteria": encoded["success_criteria_json"],
                "ambiguities": encoded["ambiguities_json"],
                "assumptions": encoded["assumptions_json"],
                "hypothesis": objective,
                "revisions": encoded["intent_revisions_json"],
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO research_intent_versions (id, research_task_id, version, contract_json, change_reason, created_at) "
                "VALUES (:id, :task_id, 1, :contract, 'legacy_migrated_read_only_projection', :created_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "task_id": str(row_data["id"]),
                "contract": json.dumps(contract, ensure_ascii=False, separators=(",", ":")),
                "created_at": now,
            },
        )
        connection.execute(
            sa.text("UPDATE research_queries SET intent_id = :intent_id WHERE research_task_id = :task_id"),
            {"intent_id": intent_id, "task_id": str(row_data["id"])},
        )


def downgrade() -> None:
    connection = op.get_bind()
    populated = connection.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM research_intents) "
            "OR EXISTS(SELECT 1 FROM research_intent_versions) "
            "OR EXISTS(SELECT 1 FROM research_intent_assumptions) "
            "OR EXISTS(SELECT 1 FROM research_unknowns) "
            "OR EXISTS(SELECT 1 FROM research_alignment_reviews) "
            "OR EXISTS(SELECT 1 FROM content_research_utilities) "
            "OR EXISTS(SELECT 1 FROM research_entity_candidates) "
            "OR EXISTS(SELECT 1 FROM research_event_candidates) "
            "OR EXISTS(SELECT 1 FROM research_memory_items)"
        )
    ).scalar()
    if populated:
        raise RuntimeError("refusing to discard 8D-0 intent or information-value history")

    op.drop_index("idx_research_queries_intent", table_name="research_queries")
    op.drop_index("idx_research_queries_task_record_type", table_name="research_queries")
    with op.batch_alter_table("research_queries", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_research_queries_decision", type_="check")
        batch_op.drop_constraint("ck_research_queries_role", type_="check")
        batch_op.drop_constraint("ck_research_queries_gate_status", type_="check")
        batch_op.drop_constraint("ck_research_queries_record_type", type_="check")
        batch_op.drop_constraint("fk_research_queries_intent", type_="foreignkey")
        batch_op.drop_column("intent_id")
        batch_op.drop_column("decision")
        batch_op.drop_column("query_role")
        batch_op.drop_column("gate_status")
        batch_op.drop_column("record_type")

    for index_name, table_name in (
        ("idx_research_memory_items_task_type_current", "research_memory_items"),
        ("idx_research_event_candidates_task_created", "research_event_candidates"),
        ("idx_research_entity_candidates_task_status", "research_entity_candidates"),
        ("idx_content_research_utilities_task_type", "content_research_utilities"),
        ("idx_research_alignment_reviews_task_created", "research_alignment_reviews"),
        ("idx_research_unknowns_task_status_priority", "research_unknowns"),
        ("idx_research_intent_assumptions_task_status", "research_intent_assumptions"),
        ("idx_research_intent_versions_task_created", "research_intent_versions"),
        ("idx_research_intents_task_updated", "research_intents"),
    ):
        op.drop_index(index_name, table_name=table_name)
    for table_name in (
        "research_memory_items",
        "research_event_candidates",
        "research_entity_candidates",
        "content_research_utilities",
        "research_alignment_reviews",
        "research_unknowns",
        "research_intent_assumptions",
        "research_intent_versions",
        "research_intents",
    ):
        op.drop_table(table_name)

"""Prompt roles, defaults, and call-level version metadata."""

from __future__ import annotations

from collections.abc import Mapping

PROMPT_ROLES = (
    "intent_interpreter",
    "research_planner",
    "query_strategist",
    "evidence_judge",
    "information_utility_classifier",
    "discovery_analyst",
    "change_analyst",
    "alignment_reviewer",
    "report_composer",
)


def default_prompt_specs() -> list[dict[str, object]]:
    return [
        {
            "prompt_key": role,
            "role": role,
            "version": "v1",
            "status": "active",
            "model_family": "gateway-default",
            "system_prompt": (
                f"You are the {role.replace('_', ' ').title()} role. "
                "Follow the Product Constitution, return only the requested schema, "
                "and never invent evidence."
            ),
            "task_template": "Use the bounded task context and preserve evidence IDs.",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "temperature": 0.1,
            "max_tokens": 800,
            "change_reason": "initial 8E role registry",
        }
        for role in PROMPT_ROLES
    ]


def prompt_metadata(
    prompt_key: str,
    prompt_version: str,
    context_version: str,
    tool_contract_version: str,
) -> dict[str, str]:
    values = {
        "prompt_key": prompt_key,
        "prompt_version": prompt_version,
        "context_version": context_version,
        "tool_contract_version": tool_contract_version,
    }
    if any(not value.strip() for value in values.values()):
        raise ValueError("prompt call metadata must be non-blank")
    return values


def metadata_from_request(metadata: Mapping[str, str]) -> dict[str, str]:
    """Return the four governance fields without copying request bodies."""

    return prompt_metadata(
        metadata.get("prompt_key", "direct_model_call"),
        metadata.get("prompt_version", "v1"),
        metadata.get("context_version", "ctx-v1"),
        metadata.get("tool_contract_version", "v1"),
    )

from __future__ import annotations

from datetime import datetime, timezone
import json
import re

from fastapi.testclient import TestClient
import pytest

from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.author.jobs import _AuthorJobRecord
from rpg_backend.author.jobs import AuthorJobService
from rpg_backend.author.copilot import build_copilot_workspace_view
from rpg_backend.author.planning import build_tone_plan
from rpg_backend.author.preview import build_author_preview_from_seed
from rpg_backend.author.preview import build_author_story_summary
from rpg_backend.author.storage import SQLiteAuthorJobStorage
from rpg_backend.author.contracts import (
    AuthorCacheMetrics,
    AuthorLoadingCastPoolEntry,
    AuthorPreviewCastSlotSummary,
    AuthorCopilotProposalResponse,
    AuthorCopilotRewriteBrief,
    AuthorEditorStateResponse,
    AuthorCopilotWorkspaceSnapshot,
    AuthorJobProgress,
    AuthorJobProgressSnapshot,
    AuthorJobResultResponse,
    AuthorJobStatusResponse,
    AuthorLoadingCard,
    PortraitVariants,
    AuthorPreviewFlashcard,
    AuthorPreviewResponse,
    AuthorStorySparkResponse,
)
from rpg_backend.play.compiler import compile_play_plan
from rpg_backend.config import get_settings
from rpg_backend.main import app
from rpg_backend.product_copy import BANNED_ZH_REGISTER_PATTERNS, BANNED_ZH_SURFACE_TERMS
from tests.author_fixtures import FakeGateway
from tests.author_fixtures import author_fixture_bundle
from tests.auth_helpers import ensure_authenticated_client


class _FakeAuthorJobService:
    def create_preview(self, payload, *, actor_user_id=None):  # noqa: ANN001
        del actor_user_id
        return _preview_response(payload.prompt_seed)

    def create_story_spark(self, payload, *, actor_user_id=None):  # noqa: ANN001
        del actor_user_id
        return AuthorStorySparkResponse(
            prompt_seed=(
                "A civic archivist must restore one binding public record before a forged emergency mandate hardens into public law."
                if getattr(payload, "language", "en") != "zh"
                else "一名市政档案官必须在伪造的紧急授权凝固成公共法律前，先救回一份具约束力的公开记录。"
            ),
            language=getattr(payload, "language", "en"),
        )

    def create_job(self, payload, *, actor_user_id=None):  # noqa: ANN001
        del actor_user_id
        return AuthorJobStatusResponse(
            job_id="job-123",
            status="queued",
            prompt_seed=payload.prompt_seed,
            preview=_preview_response(payload.prompt_seed),
            progress=AuthorJobProgress(stage="queued", stage_index=1, stage_total=10),
            progress_snapshot=_progress_snapshot(stage="queued", stage_index=1, total_tokens=150),
            cache_metrics=AuthorCacheMetrics(
                session_cache_enabled=True,
                cache_path_used=True,
                total_call_count=2,
                previous_response_call_count=1,
                total_input_characters=400,
                estimated_input_tokens_from_chars=100,
                provider_usage={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
                input_tokens=120,
                output_tokens=30,
                total_tokens=150,
                reasoning_tokens=18,
                cached_input_tokens=80,
                cache_creation_input_tokens=20,
                cache_type="ephemeral",
                billing_type="response_api",
                cache_metrics_source="provider_usage_no_cache_breakdown",
            ),
        )

    def get_job(self, job_id: str, *, actor_user_id=None) -> AuthorJobStatusResponse:
        del actor_user_id
        return AuthorJobStatusResponse(
            job_id=job_id,
            status="running",
            prompt_seed="seed",
            preview=_preview_response("seed"),
            progress=AuthorJobProgress(stage="story_frame_ready", stage_index=3, stage_total=10),
            progress_snapshot=_progress_snapshot(stage="story_frame_ready", stage_index=3, total_tokens=225),
            cache_metrics=AuthorCacheMetrics(
                session_cache_enabled=True,
                cache_path_used=True,
                total_call_count=3,
                previous_response_call_count=2,
                total_input_characters=640,
                estimated_input_tokens_from_chars=160,
                provider_usage={"input_tokens": 180, "output_tokens": 45, "total_tokens": 225},
                input_tokens=180,
                output_tokens=45,
                total_tokens=225,
                reasoning_tokens=22,
                cached_input_tokens=120,
                cache_creation_input_tokens=30,
                cache_type="ephemeral",
                billing_type="response_api",
                cache_metrics_source="provider_usage_no_cache_breakdown",
            ),
        )

    def get_job_result(self, job_id: str, *, actor_user_id=None) -> AuthorJobResultResponse:
        del actor_user_id
        return AuthorJobResultResponse(
            job_id=job_id,
            status="completed",
            summary={
                "title": "The Harbor Compact",
                "one_liner": "A harbor inspector keeps a city from splintering during quarantine.",
                "premise": "A harbor inspector keeps a city from splintering during quarantine.",
                "tone": "Tense civic fantasy",
                "theme": "Logistics quarantine crisis",
                "npc_count": 4,
                "beat_count": 3,
            },
            publishable=True,
            progress_snapshot=_progress_snapshot(stage="completed", stage_index=10, total_tokens=570),
            cache_metrics=AuthorCacheMetrics(
                session_cache_enabled=True,
                cache_path_used=True,
                total_call_count=7,
                previous_response_call_count=6,
                total_input_characters=1800,
                estimated_input_tokens_from_chars=450,
                provider_usage={"input_tokens": 480, "output_tokens": 90, "total_tokens": 570},
                input_tokens=480,
                output_tokens=90,
                total_tokens=570,
                reasoning_tokens=55,
                cached_input_tokens=360,
                cache_creation_input_tokens=40,
                cache_type="ephemeral",
                billing_type="response_api",
                cache_metrics_source="provider_usage_no_cache_breakdown",
            ),
        )

    def get_job_editor_state(self, job_id: str, *, actor_user_id=None) -> AuthorEditorStateResponse:
        del actor_user_id
        return AuthorEditorStateResponse.model_validate(
            {
                "job_id": job_id,
                "status": "completed",
                "language": "en",
                "revision": "2026-03-23T00:00:00+00:00",
                "publishable": True,
                "focused_brief": _preview_response("seed").focused_brief.model_dump(mode="json"),
                "summary": self.get_job_result(job_id).summary.model_dump(mode="json"),
                "story_frame_view": {
                    "title": "The Harbor Compact",
                    "premise": "In a harbor city under quarantine, an inspector must keep supply lines open before panic hardens into factional seizure.",
                    "tone": "Tense civic fantasy",
                    "stakes": "If the harbor fails, the city fractures around scarcity and emergency power.",
                    "style_guard": "Keep the story tense and civic.",
                    "world_rules": ["Trade and legitimacy are linked.", "The plot advances in fixed beats."],
                    "truths": [],
                    "state_axes": [],
                    "flags": [],
                },
                "cast_view": [
                    {
                        "npc_id": "corin_hale",
                        "name": "Corin Hale",
                        "role": "Harbor inspector",
                        "agenda": "Keep the harbor open.",
                        "red_line": "Will not surrender public accountability.",
                        "pressure_signature": "Turns vague claims into hard checkpoints.",
                        "template_version": "tpl-harbor-1",
                    }
                ],
                "beat_view": [
                    {
                        "beat_id": "b1",
                        "title": "The Quarantine Line",
                        "goal": "Stabilize the harbor perimeter.",
                        "milestone_kind": "reveal",
                        "pressure_axis_id": "external_pressure",
                        "route_pivot_tag": "contain_chaos",
                        "progress_required": 2,
                        "focus_npcs": [],
                        "conflict_npcs": [],
                        "affordance_tags": ["contain_chaos"],
                        "blocked_affordances": [],
                    }
                ],
                "rule_pack_view": {
                    "route_unlock_rules": [],
                    "ending_rules": [],
                    "affordance_effect_profiles": [],
                },
                "play_profile_view": {
                    "protagonist": {
                        "npc_id": "corin_hale",
                        "name": "Corin Hale",
                        "role": "Harbor inspector",
                        "agenda": "Keep the harbor open.",
                        "red_line": "Will not surrender public accountability.",
                        "pressure_signature": "Turns vague claims into hard checkpoints.",
                    },
                    "runtime_profile": "harbor_quarantine_play",
                    "runtime_profile_label": "Harbor Quarantine Play",
                    "closeout_profile": "logistics_cost_closeout",
                    "closeout_profile_label": "Logistics Cost Closeout",
                    "max_turns": 4,
                },
                "copilot_view": {
                    "mode": "primary",
                    "headline": "Steer 'The Harbor Compact' with Author Copilot before you publish.",
                    "supporting_text": "The draft is ready. Use Copilot to reshape protagonist pressure, ending tilt, and political texture while preserving the current runtime profile (Harbor Quarantine Play).",
                    "publish_readiness_text": "Publish only after the draft feels final for play. The current closeout tilt is Logistics Cost Closeout.",
                    "suggested_instructions": [
                        {
                            "suggestion_id": "protagonist_assertive",
                            "label": "Sharpen the protagonist",
                            "instruction": "Make the protagonist more assertive.",
                            "rationale": "Use this when the current lead feels too observational and you want public pressure to feel more playable.",
                        },
                        {
                            "suggestion_id": "ending_pyrrhic",
                            "label": "Push toward pyrrhic",
                            "instruction": "Make the third act feel more pyrrhic.",
                            "rationale": "Use this when stabilization should still come with visible trust, legitimacy, or coalition damage.",
                        },
                    ],
                },
            }
        )

    def stream_job_events(self, job_id: str, *, actor_user_id=None, last_event_id: int | None = None, heartbeat_seconds: float = 15.0):  # noqa: ANN001
        del actor_user_id, heartbeat_seconds
        start_id = (last_event_id or 0) + 1
        payloads = [
            {
                "id": start_id,
                "event": "job_started",
                "data": {
                    "job_id": job_id,
                    "status": "running",
                    "progress": {"stage": "running", "stage_index": 1, "stage_total": 10},
                    "progress_snapshot": _progress_snapshot(stage="running", stage_index=1, total_tokens=160).model_dump(mode="json"),
                    "token_usage": {"total_tokens": 160},
                    "token_cost_estimate": {"estimated_total_cost_rmb": 0.000141},
                },
                "emitted_at": "2026-03-21T00:00:00+00:00",
            },
            {
                "id": start_id + 1,
                "event": "stage_changed",
                "data": {
                    "job_id": job_id,
                    "status": "running",
                    "progress": {"stage": "story_frame_ready", "stage_index": 3, "stage_total": 10},
                    "progress_snapshot": _progress_snapshot(stage="story_frame_ready", stage_index=3, total_tokens=225).model_dump(mode="json"),
                    "token_usage": {"total_tokens": 225},
                    "token_cost_estimate": {"estimated_total_cost_rmb": 0.00012},
                },
                "emitted_at": "2026-03-21T00:00:00.500000+00:00",
            },
            {
                "id": start_id + 2,
                "event": "job_completed",
                "data": {
                    "job_id": job_id,
                    "status": "completed",
                    "result": self.get_job_result(job_id).model_dump(mode="json"),
                    "token_usage": {"total_tokens": 570},
                    "token_cost_estimate": {"estimated_total_cost_rmb": 0.000141},
                },
                "emitted_at": "2026-03-21T00:00:01+00:00",
            },
        ]
        for event in payloads:
            yield (
                f"id: {event['id']}\n"
                f"event: {event['event']}\n"
                f"data: {json.dumps(event['data'], ensure_ascii=False, separators=(',', ':'))}\n\n"
            )


class _EnglishCopilotProvider:
    max_output_tokens_overview = 700
    max_output_tokens_rulepack = 900
    transport_style = "responses"
    model = "test-copilot-model"
    use_session_cache = False

    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self._payloads = list(payloads)
        self.prompts: list[str] = []

    def text_policy(self, capability: str):
        budget = self.max_output_tokens_overview if capability == "copilot.reply" else self.max_output_tokens_rulepack
        return type(
            "Policy",
            (),
            {
                "capability": capability,
                "max_output_tokens": budget,
                "transport_style": self.transport_style,
                "use_session_cache": self.use_session_cache,
                "enable_thinking": False,
                "model": self.model,
            },
        )()

    def invoke_text_capability(
        self,
        capability: str,
        request,
    ):
        del capability
        self.prompts.append(request.system_prompt)
        return type(
            "CapabilityResponse",
            (),
            {
                "payload": self._payloads.pop(0),
                "response_id": "copilot-response",
                "usage": {},
                "input_characters": 0,
                "capability": request.operation_name or "copilot",
                "provider": "test",
                "model": self.model,
                "transport_style": self.transport_style,
                "fallback_source": None,
            },
        )()


def _copilot_workspace_snapshot(primary_theme: str = "logistics_quarantine_crisis") -> AuthorCopilotWorkspaceSnapshot:
    fixture = author_fixture_bundle()
    plan = compile_play_plan(story_id="copilot-fixture", bundle=fixture.design_bundle)
    return AuthorCopilotWorkspaceSnapshot(
        focused_brief=fixture.focused_brief,
        story_frame_draft=fixture.story_frame,
        cast_overview_draft=fixture.cast_overview,
        cast_member_drafts=list(fixture.cast_draft.cast),
        cast_draft=fixture.cast_draft,
        beat_plan_draft=fixture.beat_plan,
        route_opportunity_plan_draft=fixture.route_opportunity_plan,
        route_affordance_pack_draft=None,
        ending_intent_draft=None,
        ending_rules_draft=None,
        primary_theme=primary_theme,
        theme_modifiers=[],
        cast_topology="four_slot",
        runtime_profile=plan.runtime_policy_profile,
        closeout_profile=plan.closeout_profile,
        max_turns=plan.max_turns,
    )

    def get_job(self, job_id: str, *, actor_user_id=None) -> AuthorJobStatusResponse:
        del actor_user_id
        return AuthorJobStatusResponse(
            job_id=job_id,
            status="running",
            prompt_seed="seed",
            preview=_preview_response("seed"),
            progress=AuthorJobProgress(stage="story_frame_ready", stage_index=3, stage_total=10),
            progress_snapshot=_progress_snapshot(stage="story_frame_ready", stage_index=3, total_tokens=225),
            cache_metrics=AuthorCacheMetrics(
                session_cache_enabled=True,
                cache_path_used=True,
                total_call_count=3,
                previous_response_call_count=2,
                total_input_characters=640,
                estimated_input_tokens_from_chars=160,
                provider_usage={"input_tokens": 180, "output_tokens": 45, "total_tokens": 225},
                input_tokens=180,
                output_tokens=45,
                total_tokens=225,
                reasoning_tokens=22,
                cached_input_tokens=120,
                cache_creation_input_tokens=30,
                cache_type="ephemeral",
                billing_type="response_api",
                cache_metrics_source="provider_usage_no_cache_breakdown",
            ),
        )

    def get_job_result(self, job_id: str, *, actor_user_id=None) -> AuthorJobResultResponse:
        del actor_user_id
        return AuthorJobResultResponse(
            job_id=job_id,
            status="completed",
            summary={
                "title": "The Harbor Compact",
                "one_liner": "A harbor inspector keeps a city from splintering during quarantine.",
                "premise": "A harbor inspector keeps a city from splintering during quarantine.",
                "tone": "Tense civic fantasy",
                "theme": "Logistics quarantine crisis",
                "npc_count": 4,
                "beat_count": 3,
            },
            publishable=True,
            progress_snapshot=_progress_snapshot(stage="completed", stage_index=10, total_tokens=570),
            cache_metrics=AuthorCacheMetrics(
                session_cache_enabled=True,
                cache_path_used=True,
                total_call_count=7,
                previous_response_call_count=6,
                total_input_characters=1800,
                estimated_input_tokens_from_chars=450,
                provider_usage={"input_tokens": 480, "output_tokens": 90, "total_tokens": 570},
                input_tokens=480,
                output_tokens=90,
                total_tokens=570,
                reasoning_tokens=55,
                cached_input_tokens=360,
                cache_creation_input_tokens=40,
                cache_type="ephemeral",
                billing_type="response_api",
                cache_metrics_source="provider_usage_no_cache_breakdown",
            ),
        )

    def get_job_editor_state(self, job_id: str, *, actor_user_id=None) -> AuthorEditorStateResponse:
        del actor_user_id
        return AuthorEditorStateResponse.model_validate(
            {
                "job_id": job_id,
                "status": "completed",
                "language": "en",
                "revision": "2026-03-23T00:00:00+00:00",
                "publishable": True,
                "focused_brief": _preview_response("seed").focused_brief.model_dump(mode="json"),
                "summary": self.get_job_result(job_id).summary.model_dump(mode="json"),
                "story_frame_view": {
                    "title": "The Harbor Compact",
                    "premise": "In a harbor city under quarantine, an inspector must keep supply lines open before panic hardens into factional seizure.",
                    "tone": "Tense civic fantasy",
                    "stakes": "If the harbor fails, the city fractures around scarcity and emergency power.",
                    "style_guard": "Keep the story tense and civic.",
                    "world_rules": ["Trade and legitimacy are linked.", "The plot advances in fixed beats."],
                    "truths": [],
                    "state_axes": [],
                    "flags": [],
                },
                "cast_view": [
                    {
                        "npc_id": "corin_hale",
                        "name": "Corin Hale",
                        "role": "Harbor inspector",
                        "agenda": "Keep the harbor open.",
                        "red_line": "Will not surrender public accountability.",
                        "pressure_signature": "Turns vague claims into hard checkpoints.",
                        "template_version": "tpl-harbor-1",
                    }
                ],
                "beat_view": [
                    {
                        "beat_id": "b1",
                        "title": "The Quarantine Line",
                        "goal": "Stabilize the harbor perimeter.",
                        "milestone_kind": "reveal",
                        "pressure_axis_id": "external_pressure",
                        "route_pivot_tag": "contain_chaos",
                        "progress_required": 2,
                        "focus_npcs": [],
                        "conflict_npcs": [],
                        "affordance_tags": ["contain_chaos"],
                        "blocked_affordances": [],
                    }
                ],
                "rule_pack_view": {
                    "route_unlock_rules": [],
                    "ending_rules": [],
                    "affordance_effect_profiles": [],
                },
                "play_profile_view": {
                    "protagonist": {
                        "npc_id": "corin_hale",
                        "name": "Corin Hale",
                        "role": "Harbor inspector",
                        "agenda": "Keep the harbor open.",
                        "red_line": "Will not surrender public accountability.",
                        "pressure_signature": "Turns vague claims into hard checkpoints.",
                    },
                    "runtime_profile": "harbor_quarantine_play",
                    "runtime_profile_label": "Harbor Quarantine Play",
                    "closeout_profile": "logistics_cost_closeout",
                    "closeout_profile_label": "Logistics Cost Closeout",
                    "max_turns": 4,
                },
                "copilot_view": {
                    "mode": "primary",
                    "headline": "Steer 'The Harbor Compact' with Author Copilot before you publish.",
                    "supporting_text": "The draft is ready. Use Copilot to reshape protagonist pressure, ending tilt, and political texture while preserving the current runtime profile (Harbor Quarantine Play).",
                    "publish_readiness_text": "Publish only after the draft feels final for play. The current closeout tilt is Logistics Cost Closeout.",
                    "suggested_instructions": [
                        {
                            "suggestion_id": "protagonist_assertive",
                            "label": "Sharpen the protagonist",
                            "instruction": "Make the protagonist more assertive.",
                            "rationale": "Use this when the current lead feels too observational and you want public pressure to feel more playable.",
                        },
                        {
                            "suggestion_id": "ending_pyrrhic",
                            "label": "Push toward pyrrhic",
                            "instruction": "Make the third act feel more pyrrhic.",
                            "rationale": "Use this when stabilization should still come with visible trust, legitimacy, or coalition damage.",
                        },
                    ],
                },
            }
        )

    def stream_job_events(self, job_id: str, *, actor_user_id=None, last_event_id: int | None = None, heartbeat_seconds: float = 15.0):  # noqa: ANN001
        del job_id, actor_user_id, last_event_id, heartbeat_seconds
        yield (
            "id: 1\n"
            "event: job_started\n"
            "data: {\"status\":\"running\",\"progress_snapshot\":{\"primary_theme\":\"logistics_quarantine_crisis\",\"cast_topology\":\"four_slot\",\"completion_ratio\":0.1,\"stage_label\":\"Starting generation\",\"loading_cards\":[{\"card_id\":\"theme\",\"label\":\"Theme\",\"value\":\"Logistics quarantine crisis\",\"emphasis\":\"stable\"},{\"card_id\":\"generation_status\",\"label\":\"Generation Status\",\"value\":\"Starting generation.\",\"emphasis\":\"live\"}]},\"token_usage\":{\"total_tokens\":150},\"token_cost_estimate\":{\"estimated_total_cost_rmb\":0.00009}}\n\n"
        )
        yield (
            "id: 2\n"
            "event: stage_changed\n"
            "data: {\"progress\":{\"stage\":\"story_frame_ready\"},\"progress_snapshot\":{\"primary_theme\":\"logistics_quarantine_crisis\",\"cast_topology\":\"four_slot\",\"completion_ratio\":0.3,\"stage_label\":\"Story frame drafted\",\"loading_cards\":[{\"card_id\":\"generation_status\",\"label\":\"Generation Status\",\"value\":\"Story frame drafted. Title, premise, and stakes are set.\",\"emphasis\":\"live\"},{\"card_id\":\"beat_count\",\"label\":\"Beat Count\",\"value\":\"3 planned beats\",\"emphasis\":\"stable\"}]},\"token_usage\":{\"total_tokens\":225},\"token_cost_estimate\":{\"estimated_total_cost_rmb\":0.00012}}\n\n"
        )

    def get_publishable_job_source(self, job_id: str, *, actor_user_id=None):  # noqa: ANN001
        del actor_user_id
        from tests.test_story_library_api import _publish_source

        return _publish_source(job_id)


def _preview_response(prompt_seed: str) -> AuthorPreviewResponse:
    return AuthorPreviewResponse.model_validate(
        {
            "preview_id": "preview-123",
            "prompt_seed": prompt_seed,
            "focused_brief": {
                "story_kernel": "a harbor inspector preventing collapse",
                "setting_signal": "port city under quarantine and supply panic",
                "core_conflict": "keep the harbor operating while quarantine politics escalate",
                "tone_signal": "tense civic fantasy",
                "hard_constraints": [],
                "forbidden_tones": ["graphic cruelty", "sadistic evil"],
            },
            "theme": {
                "primary_theme": "logistics_quarantine_crisis",
                "modifiers": ["harbor", "quarantine", "public_panic"],
                "router_reason": "matched_brief_logistics_quarantine_keywords",
            },
            "strategies": {
                "story_frame_strategy": "harbor_quarantine_story",
                "cast_strategy": "harbor_quarantine_cast",
                "beat_plan_strategy": "harbor_quarantine_compile",
            },
            "structure": {
                "cast_topology": "four_slot",
                "expected_npc_count": 4,
                "expected_beat_count": 3,
            },
            "story": {
                "title": "The Harbor Compact",
                "premise": "In a harbor city under quarantine, an inspector must keep supply lines open before panic hardens into factional seizure.",
                "tone": "tense civic fantasy",
                "stakes": "If the harbor fails, the city fractures around scarcity and emergency power.",
            },
            "cast_slots": [
                {"slot_label": "Mediator Anchor", "public_role": "Harbor inspector"},
                {"slot_label": "Institutional Guardian", "public_role": "Port authority"},
                {"slot_label": "Leverage Broker", "public_role": "Trade bloc rival"},
                {"slot_label": "Civic Witness", "public_role": "Dock delegate"},
            ],
            "beats": [
                {"title": "The Quarantine Line", "goal": "Stabilize the harbor perimeter.", "milestone_kind": "reveal"},
                {"title": "The Dockside Audit", "goal": "Expose who profits from scarcity.", "milestone_kind": "fracture"},
                {"title": "The Harbor Compact", "goal": "Lock in a recovery bargain.", "milestone_kind": "commitment"},
            ],
            "flashcards": [
                AuthorPreviewFlashcard(card_id="theme", kind="stable", label="Theme", value="Logistics quarantine crisis").model_dump(mode="json"),
                AuthorPreviewFlashcard(card_id="tone", kind="stable", label="Tone", value="tense civic fantasy").model_dump(mode="json"),
                AuthorPreviewFlashcard(card_id="npc_count", kind="stable", label="NPC Count", value="4").model_dump(mode="json"),
                AuthorPreviewFlashcard(card_id="beat_count", kind="stable", label="Beat Count", value="3").model_dump(mode="json"),
                AuthorPreviewFlashcard(card_id="cast_topology", kind="stable", label="Cast Structure", value="4-slot civic web").model_dump(mode="json"),
                AuthorPreviewFlashcard(card_id="title", kind="draft", label="Working Title", value="The Harbor Compact").model_dump(mode="json"),
                AuthorPreviewFlashcard(
                    card_id="conflict",
                    kind="draft",
                    label="Core Conflict",
                    value="trade pressure and quarantine politics keep turning relief into factional leverage",
                ).model_dump(mode="json"),
            ],
            "stage": "brief_parsed",
        }
    )


def test_auth_session_and_me_route_reflect_logged_in_user() -> None:
    client = TestClient(app)
    ensure_authenticated_client(client, email="author-me@example.com", display_name="Alice")

    session_response = client.get("/auth/session")
    response = client.get("/me")

    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is True
    assert session_response.json()["user"]["display_name"] == "Alice"
    assert response.status_code == 200
    assert response.json()["display_name"] == "Alice"
    assert response.json()["email"] == "author-me@example.com"
    assert response.json()["is_default"] is False


def _contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def _progress_snapshot(stage: str, stage_index: int, total_tokens: int, *, stage_total: int = 10) -> AuthorJobProgressSnapshot:
    estimated_total_rmb = {
        150: 0.00009,
        225: 0.00012,
        300: 0.000141,
        360: 0.000141,
        570: 0.000141,
    }.get(total_tokens, 0.000141)
    estimated_total_usd = estimated_total_rmb * get_settings().responses_usd_per_rmb
    loading_cards = [
        AuthorLoadingCard(card_id="structure", emphasis="stable", label="Story Shape", value="4-slot civic web"),
        AuthorLoadingCard(card_id="theme", emphasis="stable", label="Theme", value="Logistics quarantine crisis"),
    ]
    if stage in {"story_frame_ready", "cast_ready", "beat_plan_ready", "completed"}:
        loading_cards.extend(
            [
                AuthorLoadingCard(card_id="working_title", emphasis="draft", label="Working Title", value="The Harbor Compact"),
                AuthorLoadingCard(card_id="tone", emphasis="stable", label="Tone", value="Tense civic fantasy"),
                AuthorLoadingCard(
                    card_id="story_premise",
                    emphasis="draft",
                    label="Story Premise",
                    value="In a harbor city under quarantine, an inspector must keep supply lines open before panic hardens into factional seizure.",
                ),
                AuthorLoadingCard(
                    card_id="story_stakes",
                    emphasis="draft",
                    label="Story Stakes",
                    value="If the harbor fails, the city fractures around scarcity and emergency power.",
                ),
            ]
        )
    if stage in {"cast_ready", "beat_plan_ready", "completed"}:
        loading_cards.extend(
            [
                AuthorLoadingCard(
                    card_id="cast_count",
                    emphasis="stable",
                    label="NPC Count",
                    value="4 NPCs drafted",
                ),
                AuthorLoadingCard(
                    card_id="cast_anchor",
                    emphasis="draft",
                    label="Cast Anchor",
                    value="Mediator Anchor · Harbor inspector",
                ),
            ]
        )
    if stage in {"beat_plan_ready", "completed"}:
        loading_cards.extend(
            [
                AuthorLoadingCard(
                    card_id="beat_count",
                    emphasis="stable",
                    label="Beat Count",
                    value="3 beats drafted",
                ),
                AuthorLoadingCard(
                    card_id="opening_beat",
                    emphasis="draft",
                    label="Opening Beat",
                    value="The Quarantine Line: Stabilize the harbor perimeter.",
                ),
                AuthorLoadingCard(
                    card_id="final_beat",
                    emphasis="draft",
                    label="Final Beat",
                    value="The Harbor Compact: Lock in a recovery bargain.",
                ),
            ]
        )
    loading_cards.extend(
        [
            AuthorLoadingCard(
                card_id="generation_status",
                emphasis="live",
                label="Generation Status",
                value=(
                    "Story frame drafted. Title, premise, and stakes are set."
                    if stage == "story_frame_ready"
                    else "Beat plan drafted. Main progression is mapped."
                    if stage == "beat_plan_ready"
                    else "Cast roster drafted. NPC tensions are in place."
                    if stage == "cast_ready"
                    else "Bundle complete. Story package is ready."
                    if stage == "completed"
                    else "Queued. Preparing generation graph."
                ),
            ),
            AuthorLoadingCard(
                card_id="token_budget",
                emphasis="live",
                label="Token Budget",
                value=f"{total_tokens} total tokens · USD {estimated_total_usd:.6f} est.",
            ),
        ]
    )
    cast_pool = (
        [
            AuthorLoadingCastPoolEntry(
                npc_id="envoy_iri",
                name="Envoy Iri",
                role="Mediator",
                portrait_url="http://127.0.0.1:8000/portraits/author/envoy_iri.png",
            )
        ]
        if stage in {"cast_ready", "beat_plan_ready", "completed"}
        else []
    )
    return AuthorJobProgressSnapshot(
        stage=stage,
        stage_label=(
            "Story frame drafted"
            if stage == "story_frame_ready"
            else "Beat plan drafted"
            if stage == "beat_plan_ready"
            else "Cast roster drafted"
            if stage == "cast_ready"
            else "Bundle complete"
            if stage == "completed"
            else "Queued for generation"
        ),
        stage_index=stage_index,
        stage_total=stage_total,
        completion_ratio=round(stage_index / stage_total, 3),
        primary_theme="logistics_quarantine_crisis",
        cast_topology="four_slot",
        expected_npc_count=4,
        expected_beat_count=3,
        preview_title="The Harbor Compact",
        preview_premise="In a harbor city under quarantine, an inspector must keep supply lines open before panic hardens into factional seizure.",
        flashcards=[
            AuthorPreviewFlashcard(card_id="theme", kind="stable", label="Theme", value="Logistics quarantine crisis"),
        ],
        loading_cards=loading_cards,
        cast_pool=cast_pool,
    )


def test_story_preview_api_returns_preview_payload() -> None:
    import rpg_backend.main as main_module

    original = main_module.author_job_service
    main_module.author_job_service = _FakeAuthorJobService()
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="author-preview@example.com", display_name="Author Preview")
        response = client.post(
            "/author/story-previews",
            json={"prompt_seed": "A harbor quarantine officer tries to stop a port city from collapsing into panic."},
        )
    finally:
        main_module.author_job_service = original

    assert response.status_code == 200
    body = response.json()
    assert body["preview_id"]
    assert body["theme"]["primary_theme"]
    assert body["structure"]["expected_npc_count"] >= 3
    assert body["flashcards"]
    assert [card["label"] for card in body["flashcards"]] == [
        "Theme",
        "Tone",
        "NPC Count",
        "Beat Count",
        "Cast Structure",
        "Working Title",
        "Core Conflict",
    ]
    assert body["flashcards"][0]["value"] == "Logistics quarantine crisis"
    for card in body["flashcards"]:
        assert not _contains_cjk(card["label"])
        assert not _contains_cjk(card["value"])


def test_story_spark_api_returns_seed_payload() -> None:
    import rpg_backend.main as main_module

    original = main_module.author_job_service
    main_module.author_job_service = _FakeAuthorJobService()
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="author-spark@example.com", display_name="Author Spark")
        response = client.post("/author/story-seeds/spark", json={"language": "zh"})
    finally:
        main_module.author_job_service = original

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_seed"]
    assert body["language"] == "zh"
    assert "记录" in body["prompt_seed"] or "授权" in body["prompt_seed"]


def test_story_spark_api_returns_prompt_seed_payload() -> None:
    import rpg_backend.main as main_module

    original = main_module.author_job_service
    main_module.author_job_service = _FakeAuthorJobService()
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="author-spark@example.com", display_name="Author Spark")
        response = client.post(
            "/author/story-seeds/spark",
            json={"language": "en"},
        )
    finally:
        main_module.author_job_service = original

    assert response.status_code == 200
    body = response.json()
    assert body["prompt_seed"]
    assert body["language"] == "en"
    assert "mandate" in body["prompt_seed"].casefold() or "record" in body["prompt_seed"].casefold()


def test_author_job_service_reuses_registered_preview(monkeypatch) -> None:
    service = AuthorJobService(gateway_factory=lambda _settings=None: FakeGateway())
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    preview = service.create_preview(
        type(
            "PreviewRequest",
            (),
            {
                "prompt_seed": "seed",
                "random_seed": None,
                "target_duration_minutes": 25,
                "tone_direction": "Measured institutional melancholy with visible public cost.",
                "tone_focus": "public_ethics",
                "prose_style": "restrained",
            },
        )(),
        actor_user_id="usr_preview",
    )
    response = service.create_job(
        type(
            "JobRequest",
            (),
            {
                "prompt_seed": "different-seed",
                "random_seed": None,
                "preview_id": preview.preview_id,
                "target_duration_minutes": None,
                "tone_direction": None,
                "tone_focus": None,
                "prose_style": None,
                "model_fields_set": {"prompt_seed", "random_seed", "preview_id"},
            },
        )(),
        actor_user_id="usr_preview",
    )

    assert response.preview.preview_id == preview.preview_id
    assert response.preview.prompt_seed == preview.prompt_seed
    assert response.preview.generation_controls == preview.generation_controls
    assert response.progress.stage == "generate_cast_members"
    assert response.progress.stage_index == 0
    assert response.progress.stage_total == 9
    assert response.progress_snapshot is not None
    assert response.progress_snapshot.completion_ratio == 0.0
    assert response.status == "running"


def test_author_job_service_rejects_preview_generation_control_drift(monkeypatch) -> None:
    service = AuthorJobService(gateway_factory=lambda _settings=None: FakeGateway())
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    preview = service.create_preview(
        type(
            "PreviewRequest",
            (),
            {
                "prompt_seed": "seed",
                "random_seed": None,
                "target_duration_minutes": 25,
                "tone_direction": None,
                "tone_focus": None,
                "prose_style": None,
            },
        )(),
        actor_user_id="usr_preview",
    )

    with pytest.raises(AuthorGatewayError) as exc_info:
        service.create_job(
            type(
                "JobRequest",
                (),
                {
                    "prompt_seed": "seed",
                    "random_seed": None,
                    "preview_id": preview.preview_id,
                    "target_duration_minutes": 10,
                    "tone_direction": None,
                    "tone_focus": None,
                    "prose_style": None,
                    "model_fields_set": {"prompt_seed", "random_seed", "preview_id", "target_duration_minutes"},
                },
            )(),
            actor_user_id="usr_preview",
        )

    assert exc_info.value.code == "author_preview_generation_controls_mismatch"


def test_author_job_service_create_preview_preserves_requested_language(monkeypatch) -> None:
    service = AuthorJobService(gateway_factory=lambda _settings=None: FakeGateway())
    preview = service.create_preview(
        type(
            "PreviewRequest",
            (),
            {
                "prompt_seed": "A harbor inspector must keep quarantine from turning into private rule.",
                "random_seed": None,
                "language": "zh",
            },
        )(),
        actor_user_id="usr_preview_zh",
    )

    assert preview.language == "zh"


def test_author_job_service_enriches_preview_timeout_with_stage_and_capability(monkeypatch) -> None:
    import rpg_backend.author.jobs as jobs_module

    class _PreviewTimeoutGateway:
        def __init__(self) -> None:
            self.call_trace = [
                {
                    "capability": "author.story_frame_scaffold",
                    "operation_name": "story_frame_semantics",
                    "operation": "story_frame_semantics",
                    "transport_style": "chat_completions",
                    "model": "qwen3.5-flash",
                    "timeout_seconds": 45.0,
                    "elapsed_ms": 62487,
                    "input_characters": 512,
                    "system_prompt_characters": 1335,
                    "sdk_retries_disabled": True,
                    "error_code": "gateway_text_provider_failed",
                    "error_message": "Request timed out.",
                }
            ]

    class _FailingPreviewGraph:
        def stream(self, *_args, **_kwargs):
            yield {"focus_brief": {}}
            yield {"plan_brief_theme": {}}
            yield {"plan_generation_intent": {}}
            raise AuthorGatewayError(
                code="llm_provider_failed",
                message="Request timed out.",
                status_code=502,
            )

        def get_state(self, _config):
            raise AssertionError("get_state should not be reached after preview timeout")

    monkeypatch.setattr(jobs_module, "build_author_graph", lambda **_kwargs: _FailingPreviewGraph())
    service = AuthorJobService(gateway_factory=lambda _settings=None: _PreviewTimeoutGateway())

    with pytest.raises(AuthorGatewayError) as exc_info:
        service.create_preview(
            type(
                "PreviewRequest",
                (),
                {
                    "prompt_seed": "A civic archivist must keep a blackout vote from collapsing into private rule.",
                    "random_seed": None,
                    "language": "en",
                    "target_duration_minutes": 25,
                    "tone_direction": None,
                    "tone_focus": None,
                    "prose_style": None,
                },
            )(),
            actor_user_id="usr_preview_probe",
        )

    message = exc_info.value.message
    assert exc_info.value.code == "llm_provider_failed"
    assert "preview failed during generate_story_frame" in message
    assert "stage=story_frame_ready" in message
    assert "capability=author.story_frame_scaffold" in message
    assert "operation=story_frame_semantics" in message
    assert "transport=chat_completions" in message
    assert "model=qwen3.5-flash" in message
    assert "input_characters=512" in message
    assert "system_prompt_characters=1335" in message
    assert "timeout_seconds=45.0" in message
    assert "elapsed_ms=62487" in message
    assert "sdk_retries_disabled=True" in message


def test_author_job_routes_are_scoped_to_actor(monkeypatch) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    service = AuthorJobService(gateway_factory=lambda _settings=None: FakeGateway())
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    main_module.author_job_service = service
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    try:
        ensure_authenticated_client(alice_client, email="alice-author@example.com", display_name="Alice")
        ensure_authenticated_client(bob_client, email="bob-author@example.com", display_name="Bob")
        preview = alice_client.post("/author/story-previews", json={"prompt_seed": "seed"})
        created = alice_client.post(
            "/author/jobs",
            json={"prompt_seed": "seed", "preview_id": preview.json()["preview_id"]},
        )
        hidden = bob_client.get(f"/author/jobs/{created.json()['job_id']}")
        visible = alice_client.get(f"/author/jobs/{created.json()['job_id']}")
    finally:
        main_module.author_job_service = original_author_service

    assert preview.status_code == 200
    assert created.status_code == 200
    assert hidden.status_code == 404
    assert visible.status_code == 200


def test_author_job_service_event_payload_includes_token_snapshot() -> None:
    import rpg_backend.author.jobs as jobs_module

    service = AuthorJobService()
    service._jobs["job-123"] = jobs_module._AuthorJobRecord(
        job_id="job-123",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=_preview_response("seed"),
        status="running",
        progress=AuthorJobProgress(stage="cast_ready", stage_index=6, stage_total=10),
        cache_metrics=AuthorCacheMetrics(
            session_cache_enabled=True,
            cache_path_used=True,
            total_call_count=4,
            previous_response_call_count=3,
            total_input_characters=920,
            estimated_input_tokens_from_chars=230,
            provider_usage={"input_tokens": 240, "output_tokens": 60, "total_tokens": 300},
            input_tokens=240,
            output_tokens=60,
            total_tokens=300,
            reasoning_tokens=28,
            cached_input_tokens=160,
            cache_creation_input_tokens=30,
            cache_type="ephemeral",
            billing_type="response_api",
            cache_metrics_source="provider_usage_no_cache_breakdown",
        ),
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )

    payload = service._build_status_event_payload("job-123")

    assert payload["status"] == "running"
    assert payload["progress"]["stage"] == "cast_ready"
    assert payload["progress_snapshot"]["stage_label"] == "Cast roster drafted"
    assert payload["progress_snapshot"]["primary_theme"] == "logistics_quarantine_crisis"
    assert payload["progress_snapshot"]["cast_topology"] == "four_slot"
    cards = {card["card_id"]: card for card in payload["progress_snapshot"]["loading_cards"]}
    assert set(cards) == {
        "theme",
        "structure",
        "working_title",
        "tone",
        "story_premise",
        "story_stakes",
        "cast_count",
        "cast_anchor",
        "generation_status",
        "token_budget",
    }
    assert cards["cast_count"]["value"] == "4 NPCs drafted"
    assert cards["cast_anchor"]["value"] == "Mediator Anchor · Harbor inspector"
    assert cards["generation_status"]["value"] == "Cast roster drafted. NPC tensions are in place."
    assert payload["token_usage"]["total_tokens"] == 300
    assert payload["token_cost_estimate"]["estimated_total_cost_rmb"] > 0


def test_author_job_service_loading_cards_are_stage_adaptive() -> None:
    import rpg_backend.author.jobs as jobs_module

    service = AuthorJobService()
    fixture = author_fixture_bundle()

    def build_record(stage: str, stage_index: int, total_tokens: int | None) -> jobs_module._AuthorJobRecord:
        metrics = None
        if total_tokens is not None:
            metrics = AuthorCacheMetrics(
                session_cache_enabled=True,
                cache_path_used=True,
                total_call_count=4,
                previous_response_call_count=3,
                total_input_characters=920,
                estimated_input_tokens_from_chars=230,
                provider_usage={"input_tokens": 240, "output_tokens": 60, "total_tokens": total_tokens},
                input_tokens=240,
                output_tokens=60,
                total_tokens=total_tokens,
                reasoning_tokens=28,
                cached_input_tokens=160,
                cache_creation_input_tokens=30,
                cache_type="ephemeral",
                billing_type="response_api",
                cache_metrics_source="provider_usage_no_cache_breakdown",
            )
        preview = _preview_response("seed")
        if stage in {"cast_ready", "beat_plan_ready", "completed"}:
            preview = preview.model_copy(
                update={
                    "cast_slots": [
                        AuthorPreviewCastSlotSummary(
                            slot_label=member.name,
                            public_role=member.role,
                            npc_id=member.npc_id,
                            name=member.name,
                            roster_character_id=member.roster_character_id,
                            roster_public_summary=member.roster_public_summary,
                            portrait_url=member.portrait_url,
                            portrait_variants=member.portrait_variants,
                            template_version=member.template_version,
                        )
                        for member in fixture.design_bundle.story_bible.cast
                    ]
                }
            )
        return jobs_module._AuthorJobRecord(
            job_id=f"job-{stage}",
            owner_user_id="local-dev",
            prompt_seed="seed",
            preview=preview,
            status="running" if stage != "completed" else "completed",
            progress=AuthorJobProgress(stage=stage, stage_index=stage_index, stage_total=10),
            cache_metrics=metrics,
        )

    scenarios = [
        ("queued", 1, None, {"theme", "structure", "generation_status", "token_budget"}, "Queued. Preparing generation graph.", "Waiting for first model call"),
        (
            "story_frame_ready",
            3,
            225,
            {"theme", "structure", "working_title", "tone", "story_premise", "story_stakes", "generation_status", "token_budget"},
            "Story frame drafted. Title, premise, and stakes are set.",
            "225 total tokens · USD 0.000020 est.",
        ),
        (
            "cast_ready",
            6,
            300,
            {"theme", "structure", "working_title", "tone", "story_premise", "story_stakes", "cast_count", "cast_anchor", "generation_status", "token_budget"},
            "Cast roster drafted. NPC tensions are in place.",
            "300 total tokens · USD 0.000020 est.",
        ),
        (
            "beat_plan_ready",
            7,
            360,
            {"theme", "structure", "working_title", "tone", "story_premise", "story_stakes", "cast_count", "cast_anchor", "beat_count", "opening_beat", "final_beat", "generation_status", "token_budget"},
            "Beat plan drafted. Main progression is mapped.",
            "360 total tokens · USD 0.000020 est.",
        ),
        (
            "completed",
            10,
            570,
            {"theme", "structure", "working_title", "tone", "story_premise", "story_stakes", "cast_count", "cast_anchor", "beat_count", "opening_beat", "final_beat", "generation_status", "token_budget"},
            "Bundle complete. Story package is ready.",
            "570 total tokens · USD 0.000020 est.",
        ),
    ]

    for stage, stage_index, total_tokens, expected_card_ids, status_value, token_value in scenarios:
        snapshot = service._progress_snapshot(build_record(stage, stage_index, total_tokens))
        cards = {card.card_id: card for card in snapshot.loading_cards}
        assert set(cards) == expected_card_ids
        assert cards["generation_status"].value == status_value
        assert cards["token_budget"].value == token_value
        if stage in {"queued", "story_frame_ready"}:
            assert snapshot.cast_pool == []
            if stage in {"cast_ready", "beat_plan_ready", "completed"}:
                assert cards["cast_count"].value == "4 NPCs drafted"
                assert cards["cast_anchor"].value == "Envoy Iri · Mediator"
                assert len(snapshot.cast_pool) == len(fixture.design_bundle.story_bible.cast)
                assert snapshot.cast_pool[0].npc_id
                assert snapshot.cast_pool[0].name
                assert snapshot.cast_pool[0].role
        if stage in {"beat_plan_ready", "completed"}:
            assert cards["beat_count"].value == "3 beats drafted"
            assert cards["opening_beat"].value == "The Quarantine Line: Stabilize the harbor perimeter."
            assert cards["final_beat"].value == "The Harbor Compact: Lock in a recovery bargain."


def test_author_job_service_post_preview_progress_snapshot_starts_low_and_tracks_cast_slots() -> None:
    import rpg_backend.author.jobs as jobs_module

    service = AuthorJobService()
    fixture = author_fixture_bundle()
    preview = _preview_response("seed").model_copy(
        update={
            "cast_slots": [
                AuthorPreviewCastSlotSummary(
                    slot_label=member.name,
                    public_role=member.role,
                    npc_id=member.npc_id,
                    name=member.name,
                    roster_character_id=member.roster_character_id,
                    roster_public_summary=member.roster_public_summary,
                    portrait_url=member.portrait_url,
                    portrait_variants=member.portrait_variants,
                    template_version=member.template_version,
                )
                for member in fixture.design_bundle.story_bible.cast
            ]
        }
    )
    record = jobs_module._AuthorJobRecord(
        job_id="job-post-preview-cast",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=preview,
        status="running",
        progress=AuthorJobProgress(stage="generate_cast_members", stage_index=0, stage_total=9),
        cache_metrics=AuthorCacheMetrics(
            session_cache_enabled=True,
            cache_path_used=True,
            total_call_count=4,
            previous_response_call_count=3,
            total_input_characters=920,
            estimated_input_tokens_from_chars=230,
            provider_usage={"input_tokens": 240, "output_tokens": 60, "total_tokens": 300},
            input_tokens=240,
            output_tokens=60,
            total_tokens=300,
            reasoning_tokens=28,
            cached_input_tokens=160,
            cache_creation_input_tokens=30,
            cache_type="ephemeral",
            billing_type="response_api",
            cache_metrics_source="provider_usage_no_cache_breakdown",
        ),
        running_node="generate_cast_members",
        running_substage="slot_generate",
        running_slot_index=2,
        running_slot_total=4,
        running_slot_label="Institutional Guardian",
        running_capability="author.cast_member_generate",
    )

    snapshot = service._progress_snapshot(record)
    cards = {card.card_id: card for card in snapshot.loading_cards}

    assert snapshot.stage == "generate_cast_members"
    assert snapshot.stage_label == "Sketching the cast web · character 2/4"
    assert snapshot.completion_ratio == 0.056
    assert "working_title" in cards
    assert "cast_count" not in cards
    assert snapshot.cast_pool == []


def test_author_job_service_post_preview_progress_snapshot_uses_running_node_and_card_thresholds() -> None:
    import rpg_backend.author.jobs as jobs_module

    service = AuthorJobService()
    fixture = author_fixture_bundle()
    preview = _preview_response("seed").model_copy(
        update={
            "cast_slots": [
                AuthorPreviewCastSlotSummary(
                    slot_label=member.name,
                    public_role=member.role,
                    npc_id=member.npc_id,
                    name=member.name,
                    roster_character_id=member.roster_character_id,
                    roster_public_summary=member.roster_public_summary,
                    portrait_url=member.portrait_url,
                    portrait_variants=member.portrait_variants,
                    template_version=member.template_version,
                )
                for member in fixture.design_bundle.story_bible.cast
            ]
        }
    )

    def build_record(stage: str, stage_index: int, *, running_node: str | None = None) -> jobs_module._AuthorJobRecord:
        return jobs_module._AuthorJobRecord(
            job_id=f"job-{stage}-{stage_index}",
            owner_user_id="local-dev",
            prompt_seed="seed",
            preview=preview,
            status="running",
            progress=AuthorJobProgress(stage=stage, stage_index=stage_index, stage_total=9),
            cache_metrics=AuthorCacheMetrics(
                session_cache_enabled=True,
                cache_path_used=True,
                total_call_count=4,
                previous_response_call_count=3,
                total_input_characters=920,
                estimated_input_tokens_from_chars=230,
                provider_usage={"input_tokens": 240, "output_tokens": 60, "total_tokens": 360},
                input_tokens=240,
                output_tokens=60,
                total_tokens=360,
                reasoning_tokens=28,
                cached_input_tokens=160,
                cache_creation_input_tokens=30,
                cache_type="ephemeral",
                billing_type="response_api",
                cache_metrics_source="provider_usage_no_cache_breakdown",
            ),
            running_node=running_node,
            running_substage="running" if running_node is not None else None,
        )

    cast_snapshot = service._progress_snapshot(build_record("assemble_cast", 1))
    cast_cards = {card.card_id: card for card in cast_snapshot.loading_cards}
    assert "cast_count" in cast_cards
    assert "cast_anchor" in cast_cards
    assert "beat_count" not in cast_cards
    assert cast_snapshot.cast_pool == []

    running_snapshot = service._progress_snapshot(build_record("assemble_cast", 1, running_node="generate_beat_plan"))
    assert running_snapshot.stage == "generate_beat_plan"
    assert running_snapshot.stage_label == "Mapping the major beats"

    beat_snapshot = service._progress_snapshot(build_record("generate_route_opportunity_plan", 3))
    beat_cards = {card.card_id: card for card in beat_snapshot.loading_cards}
    assert "beat_count" in beat_cards
    assert "opening_beat" in beat_cards
    assert "final_beat" in beat_cards
    assert len(beat_snapshot.cast_pool) == len(fixture.design_bundle.story_bible.cast)


def test_author_job_service_loading_cards_localize_for_zh_preview_language() -> None:
    import rpg_backend.author.jobs as jobs_module

    service = AuthorJobService()
    base_preview = _preview_response("seed")
    preview = base_preview.model_copy(
        update={
            "language": "zh",
            "story": base_preview.story.model_copy(
                update={
                    "title": "港务协定",
                    "premise": "一名港口检查官必须在港区分裂前揭开被操纵的检疫扣押。",
                    "tone": "紧张的政治惊悚",
                    "stakes": "若公共合法性先崩，整座城市会在公开场域中失控。",
                }
            ),
            "cast_slots": [],
            "beats": [],
            "flashcards": [
                AuthorPreviewFlashcard(card_id="theme", kind="stable", label="题材", value="封线断供"),
                AuthorPreviewFlashcard(card_id="tone", kind="stable", label="气质", value="港城政治惊悚"),
                AuthorPreviewFlashcard(card_id="npc_count", kind="stable", label="角色数", value="4"),
                AuthorPreviewFlashcard(card_id="beat_count", kind="stable", label="节拍数", value="3"),
                AuthorPreviewFlashcard(card_id="cast_topology", kind="stable", label="人物布局", value="四方角力"),
                AuthorPreviewFlashcard(card_id="title", kind="draft", label="暂定标题", value="港务协定"),
                AuthorPreviewFlashcard(card_id="conflict", kind="draft", label="核心冲突", value="港口与检疫压力正在把救济扭成筹码"),
            ],
        }
    )
    record = jobs_module._AuthorJobRecord(
        job_id="job-zh-loading",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=preview,
        status="running",
        progress=AuthorJobProgress(stage="beat_plan_ready", stage_index=7, stage_total=10),
        cache_metrics=AuthorCacheMetrics(
            session_cache_enabled=True,
            cache_path_used=True,
            total_call_count=4,
            previous_response_call_count=3,
            total_input_characters=920,
            estimated_input_tokens_from_chars=230,
            provider_usage={"input_tokens": 240, "output_tokens": 60, "total_tokens": 360},
            input_tokens=240,
            output_tokens=60,
            total_tokens=360,
            reasoning_tokens=28,
            cached_input_tokens=160,
            cache_creation_input_tokens=30,
            cache_type="ephemeral",
            billing_type="response_api",
            cache_metrics_source="provider_usage_no_cache_breakdown",
        ),
    )

    snapshot = service._progress_snapshot(record)
    cards = {card.card_id: card for card in snapshot.loading_cards}

    assert snapshot.stage_label == "节拍排布完成"
    assert cards["generation_status"].value == "主线推进已经排好，接下来把路线和收束接上。"
    assert cards["token_budget"].value == "累计用量 360 · 预估 USD 0.000020"
    assert cards["cast_anchor"].value == "人物信息稍后补齐"
    assert cards["opening_beat"].value == "节拍信息稍后补齐"
    assert cards["final_beat"].value == "节拍信息稍后补齐"
    assert cards["cast_count"].value == "4 名角色已落位"
    assert cards["beat_count"].value == "3 段主节拍已成型"


def test_zh_preview_and_progress_snapshot_avoid_banned_surface_terms() -> None:
    service = AuthorJobService()
    preview = build_author_preview_from_seed(
        "一名港口档案员必须在投票前救回被动过手脚的紧急舱单，别让一场偏袒性的分配先被写成既成事实。",
        language="zh",
    )
    record = _AuthorJobRecord(
        job_id="job-zh-copy",
        owner_user_id="local-dev",
        prompt_seed=preview.prompt_seed,
        preview=preview,
        status="running",
        progress=AuthorJobProgress(stage="beat_plan_ready", stage_index=7, stage_total=10),
        cache_metrics=AuthorCacheMetrics(
            session_cache_enabled=True,
            cache_path_used=True,
            total_call_count=3,
            previous_response_call_count=2,
            total_input_characters=640,
            estimated_input_tokens_from_chars=160,
            provider_usage={"input_tokens": 190, "output_tokens": 50, "total_tokens": 240},
            input_tokens=190,
            output_tokens=50,
            total_tokens=240,
            reasoning_tokens=18,
            cached_input_tokens=100,
            cache_creation_input_tokens=20,
            cache_type="ephemeral",
            billing_type="response_api",
            cache_metrics_source="provider_usage_no_cache_breakdown",
        ),
    )
    snapshot = service._progress_snapshot(record)
    visible_strings = [
        preview.story.title,
        preview.story.premise,
        preview.story.tone,
        preview.story.stakes,
        *(card.label for card in preview.flashcards),
        *(card.value for card in preview.flashcards),
        snapshot.stage_label,
        *(card.label for card in snapshot.loading_cards),
        *(card.value for card in snapshot.loading_cards),
    ]
    payload = json.dumps(visible_strings, ensure_ascii=False).casefold()

    for term in BANNED_ZH_SURFACE_TERMS:
        assert term not in payload
    for pattern in BANNED_ZH_REGISTER_PATTERNS:
        assert pattern not in payload


def test_zh_copilot_workspace_copy_avoids_banned_surface_terms() -> None:
    view = build_copilot_workspace_view(
        language="zh",
        title="港务协定",
        protagonist_name="岑港",
        runtime_profile_label="港口封线",
        closeout_profile_label="代价落账",
        premise="港城在检疫封线与断供恐慌里已经被压到临界点。",
        theme="封线断供",
    )
    payload = json.dumps(view.model_dump(mode="json"), ensure_ascii=False).casefold()

    for term in BANNED_ZH_SURFACE_TERMS:
        assert term not in payload
    for pattern in BANNED_ZH_REGISTER_PATTERNS:
        assert pattern not in payload


def test_zh_tone_plan_guidance_avoids_banned_register_patterns() -> None:
    tone_plan = build_tone_plan(
        focused_brief=author_fixture_bundle().focused_brief.model_copy(
            update={"language": "zh", "tone_signal": "封线政治惊悚"}
        ),
        controls=None,
    )
    payload = json.dumps(tone_plan.model_dump(mode="json"), ensure_ascii=False).casefold()

    for pattern in BANNED_ZH_REGISTER_PATTERNS:
        assert pattern not in payload


def test_author_job_routes_use_job_service(monkeypatch) -> None:
    import rpg_backend.main as main_module

    original = main_module.author_job_service
    main_module.author_job_service = _FakeAuthorJobService()
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="author-job-routes@example.com", display_name="Author Routes")
        create_response = client.post(
            "/author/jobs",
            json={"prompt_seed": "港口检疫官阻止城市崩溃"},
        )
        status_response = client.get("/author/jobs/job-123")
        result_response = client.get("/author/jobs/job-123/result")
        editor_state_response = client.get("/author/jobs/job-123/editor-state")
    finally:
        main_module.author_job_service = original

    assert create_response.status_code == 200
    assert create_response.json()["job_id"] == "job-123"
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "running"
    assert status_response.json()["cache_metrics"]["session_cache_enabled"] is True
    stage_cards = {card["card_id"]: card for card in status_response.json()["progress_snapshot"]["loading_cards"]}
    assert {"theme", "structure", "working_title", "tone", "story_premise", "story_stakes", "generation_status", "token_budget"} <= set(stage_cards)
    assert stage_cards["generation_status"]["value"] == "Story frame drafted. Title, premise, and stakes are set."
    assert result_response.status_code == 200
    assert result_response.json()["summary"]["title"] == "The Harbor Compact"
    assert result_response.json()["publishable"] is True
    assert result_response.json()["progress_snapshot"]["stage_label"] == "Bundle complete"
    assert result_response.json()["progress_snapshot"]["cast_pool"][0]["name"] == "Envoy Iri"
    assert result_response.json()["summary"]["theme"] == "Logistics quarantine crisis"
    assert result_response.json()["cache_metrics"]["total_call_count"] == 7
    assert editor_state_response.status_code == 200
    assert editor_state_response.json()["story_frame_view"]["title"] == "The Harbor Compact"
    assert editor_state_response.json()["play_profile_view"]["runtime_profile"] == "harbor_quarantine_play"
    assert editor_state_response.json()["copilot_view"]["mode"] == "primary"
    assert len(editor_state_response.json()["copilot_view"]["suggested_instructions"]) >= 2


def test_author_job_events_route_streams_sse(monkeypatch) -> None:
    import rpg_backend.main as main_module

    original = main_module.author_job_service
    main_module.author_job_service = _FakeAuthorJobService()
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="author-events@example.com", display_name="Author Events")
        response = client.get("/author/jobs/job-123/events")
    finally:
        main_module.author_job_service = original

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: job_started" in response.text
    assert "event: stage_changed" in response.text
    assert "\"progress_snapshot\"" in response.text
    assert "\"loading_cards\"" in response.text
    assert "\"cast_topology\":\"four_slot\"" in response.text
    assert "\"token_usage\"" in response.text
    assert "\"estimated_total_cost_rmb\"" in response.text
    assert "Story frame drafted. Title, premise, and stakes are set." in response.text


def test_product_api_loading_copy_is_english_only(monkeypatch) -> None:
    import rpg_backend.main as main_module

    original = main_module.author_job_service
    main_module.author_job_service = _FakeAuthorJobService()
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="author-copy@example.com", display_name="Author Copy")
        preview_response = client.post(
            "/author/story-previews",
            json={"prompt_seed": "A harbor quarantine officer tries to stop a port city from collapsing into panic."},
        )
        status_response = client.get("/author/jobs/job-123")
        result_response = client.get("/author/jobs/job-123/result")
    finally:
        main_module.author_job_service = original

    assert preview_response.status_code == 200
    assert status_response.status_code == 200
    assert result_response.status_code == 200

    display_strings = []
    display_strings.extend(card["label"] for card in preview_response.json()["flashcards"])
    display_strings.extend(card["value"] for card in preview_response.json()["flashcards"])
    display_strings.extend(card["label"] for card in status_response.json()["progress_snapshot"]["loading_cards"])
    display_strings.extend(card["value"] for card in status_response.json()["progress_snapshot"]["loading_cards"])
    display_strings.append(result_response.json()["summary"]["theme"])

    for value in display_strings:
        assert not _contains_cjk(value)


def test_author_copilot_routes_create_preview_and_apply(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-job",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(
            fixture.design_bundle.model_copy(
                update={
                    "focused_brief": fixture.focused_brief.model_copy(
                        update={
                            "story_kernel": "A harbor inspector must keep quarantine from turning into private rule.",
                            "setting_signal": "port city under quarantine and supply panic",
                            "core_conflict": "keep the harbor operating while quarantine politics escalate",
                            "tone_signal": "Tense civic fantasy",
                        }
                    )
                }
            ),
            primary_theme="logistics_quarantine_crisis",
        ),
        bundle=fixture.design_bundle.model_copy(
            update={
                "focused_brief": fixture.focused_brief.model_copy(
                    update={
                        "story_kernel": "A harbor inspector must keep quarantine from turning into private rule.",
                        "setting_signal": "port city under quarantine and supply panic",
                        "core_conflict": "keep the harbor operating while quarantine politics escalate",
                        "tone_signal": "Tense civic fantasy",
                    }
                )
            }
        ),
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot@example.com", display_name="Copilot", password="TestPass123!")
        # Align owner with authenticated user for scoping.
        service._jobs["copilot-job"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-job"])
        proposal = client.post(
            "/author/jobs/copilot-job/copilot/proposals",
            json={"instruction": "Make the protagonist more assertive and make the third act feel more pyrrhic."},
        )
        proposal_id = proposal.json()["proposal_id"]
        preview = client.post(f"/author/jobs/copilot-job/copilot/proposals/{proposal_id}/preview")
        applied = client.post(f"/author/jobs/copilot-job/copilot/proposals/{proposal_id}/apply")
        editor_state = client.get("/author/jobs/copilot-job/editor-state")
    finally:
        main_module.author_job_service = original_author_service

    assert proposal.status_code == 200
    assert proposal.json()["proposal_group_id"]
    assert proposal.json()["variant_index"] == 1
    assert proposal.json()["variant_label"]
    assert proposal.json()["patch_targets"] == ["cast", "rule_pack"]
    assert preview.status_code == 200
    assert "assertive" in preview.json()["proposal"]["instruction"].lower()
    assert preview.json()["editor_state"]["beat_view"]
    assert applied.status_code == 200
    assert applied.json()["proposal"]["status"] == "applied"
    assert editor_state.status_code == 200
    assert editor_state.json()["cast_view"][0]["pressure_signature"]


def test_author_copilot_undo_route_restores_previous_state_and_exposes_undo_metadata(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-undo",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(
            fixture.design_bundle.model_copy(
                update={
                    "focused_brief": fixture.focused_brief.model_copy(
                        update={
                            "story_kernel": "A harbor inspector must keep quarantine from turning into private rule.",
                            "setting_signal": "port city under quarantine and supply panic",
                            "core_conflict": "keep the harbor operating while quarantine politics escalate",
                            "tone_signal": "Tense civic fantasy",
                        }
                    )
                }
            ),
            primary_theme="logistics_quarantine_crisis",
        ),
        bundle=fixture.design_bundle.model_copy(
            update={
                "focused_brief": fixture.focused_brief.model_copy(
                    update={
                        "story_kernel": "A harbor inspector must keep quarantine from turning into private rule.",
                        "setting_signal": "port city under quarantine and supply panic",
                        "core_conflict": "keep the harbor operating while quarantine politics escalate",
                        "tone_signal": "Tense civic fantasy",
                    }
                )
            }
        ),
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-undo@example.com", display_name="Copilot Undo", password="TestPass123!")
        service._jobs["copilot-undo"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-undo"])
        before_state = client.get("/author/jobs/copilot-undo/editor-state")
        created = client.post("/author/jobs/copilot-undo/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        client.post(
            f"/author/jobs/copilot-undo/copilot/sessions/{session_id}/messages",
            json={"content": "Make the protagonist more assertive."},
        )
        proposed = client.post(f"/author/jobs/copilot-undo/copilot/sessions/{session_id}/proposal")
        proposal_id = proposed.json()["proposal_id"]
        applied = client.post(f"/author/jobs/copilot-undo/copilot/proposals/{proposal_id}/apply")
        editor_state_after_apply = client.get("/author/jobs/copilot-undo/editor-state")
        undone = client.post(f"/author/jobs/copilot-undo/copilot/proposals/{proposal_id}/undo")
        editor_state_after_undo = client.get("/author/jobs/copilot-undo/editor-state")
    finally:
        main_module.author_job_service = original_author_service

    assert before_state.status_code == 200
    assert created.status_code == 200
    assert proposed.status_code == 200
    assert applied.status_code == 200
    assert editor_state_after_apply.status_code == 200
    assert editor_state_after_apply.json()["copilot_view"]["undo_available"] is True
    assert editor_state_after_apply.json()["copilot_view"]["undo_proposal_id"] == proposal_id
    assert editor_state_after_apply.json()["copilot_view"]["undo_request_summary"]
    assert undone.status_code == 200
    assert undone.json()["proposal"]["status"] == "superseded"
    assert editor_state_after_undo.status_code == 200
    assert editor_state_after_undo.json()["copilot_view"]["undo_available"] is False
    assert editor_state_after_undo.json()["story_frame_view"] == before_state.json()["story_frame_view"]
    assert editor_state_after_undo.json()["cast_view"] == before_state.json()["cast_view"]
    assert editor_state_after_undo.json()["beat_view"] == before_state.json()["beat_view"]
    assert editor_state_after_undo.json()["rule_pack_view"] == before_state.json()["rule_pack_view"]


def test_author_copilot_undo_route_rejects_unapplied_proposal(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-undo-unapplied",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-undo-unapplied@example.com", display_name="Copilot Undo Unapplied", password="TestPass123!")
        service._jobs["copilot-undo-unapplied"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-undo-unapplied"])
        created = client.post("/author/jobs/copilot-undo-unapplied/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        client.post(
            f"/author/jobs/copilot-undo-unapplied/copilot/sessions/{session_id}/messages",
            json={"content": "Make the protagonist more assertive."},
        )
        proposed = client.post(f"/author/jobs/copilot-undo-unapplied/copilot/sessions/{session_id}/proposal")
        proposal_id = proposed.json()["proposal_id"]
        undone = client.post(f"/author/jobs/copilot-undo-unapplied/copilot/proposals/{proposal_id}/undo")
    finally:
        main_module.author_job_service = original_author_service

    assert undone.status_code == 409
    assert undone.json()["error"]["code"] == "author_copilot_proposal_not_undoable"


def test_author_copilot_undo_route_rejects_stale_revision(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-undo-stale",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-undo-stale@example.com", display_name="Copilot Undo Stale", password="TestPass123!")
        service._jobs["copilot-undo-stale"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-undo-stale"])
        created = client.post("/author/jobs/copilot-undo-stale/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        client.post(
            f"/author/jobs/copilot-undo-stale/copilot/sessions/{session_id}/messages",
            json={"content": "Make the protagonist more assertive."},
        )
        proposed = client.post(f"/author/jobs/copilot-undo-stale/copilot/sessions/{session_id}/proposal")
        proposal_id = proposed.json()["proposal_id"]
        applied = client.post(f"/author/jobs/copilot-undo-stale/copilot/proposals/{proposal_id}/apply")
        assert applied.status_code == 200
        service._jobs["copilot-undo-stale"].updated_at = service._now()
        service._save_record(service._jobs["copilot-undo-stale"])
        undone = client.post(f"/author/jobs/copilot-undo-stale/copilot/proposals/{proposal_id}/undo")
    finally:
        main_module.author_job_service = original_author_service

    assert undone.status_code == 409
    assert undone.json()["error"]["code"] == "author_copilot_undo_stale"


def test_author_copilot_retry_produces_new_variant_and_supersedes_previous(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-retry",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-retry@example.com", display_name="Copilot Retry", password="TestPass123!")
        service._jobs["copilot-retry"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-retry"])
        first = client.post(
            "/author/jobs/copilot-retry/copilot/proposals",
            json={"instruction": "Make the protagonist more assertive."},
        )
        first_id = first.json()["proposal_id"]
        second = client.post(
            "/author/jobs/copilot-retry/copilot/proposals",
            json={
                "instruction": "Make the protagonist more assertive.",
                "retry_from_proposal_id": first_id,
            },
        )
        first_reloaded = client.get(f"/author/jobs/copilot-retry/copilot/proposals/{first_id}")
    finally:
        main_module.author_job_service = original_author_service

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["proposal_group_id"] == second.json()["proposal_group_id"]
    assert first.json()["variant_index"] == 1
    assert second.json()["variant_index"] == 2
    assert first.json()["variant_label"] != second.json()["variant_label"]
    assert first.json()["operations"] != second.json()["operations"]
    assert second.json()["supersedes_proposal_id"] == first_id
    assert first_reloaded.status_code == 200
    assert first_reloaded.json()["status"] == "superseded"


def test_author_copilot_retry_exhausts_variants(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-exhaust",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-exhaust@example.com", display_name="Copilot Exhaust", password="TestPass123!")
        service._jobs["copilot-exhaust"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-exhaust"])
        proposal = client.post(
            "/author/jobs/copilot-exhaust/copilot/proposals",
            json={"instruction": "Make the protagonist more assertive."},
        )
        proposal_id = proposal.json()["proposal_id"]
        for _ in range(2):
            proposal = client.post(
                "/author/jobs/copilot-exhaust/copilot/proposals",
                json={
                    "instruction": "Make the protagonist more assertive.",
                    "retry_from_proposal_id": proposal_id,
                },
            )
            proposal_id = proposal.json()["proposal_id"]
        exhausted = client.post(
            "/author/jobs/copilot-exhaust/copilot/proposals",
            json={
                "instruction": "Make the protagonist more assertive.",
                "retry_from_proposal_id": proposal_id,
            },
        )
    finally:
        main_module.author_job_service = original_author_service

    assert exhausted.status_code == 409
    assert exhausted.json()["error"]["code"] == "author_copilot_no_more_variants"


def test_author_copilot_superseded_proposal_cannot_preview_or_apply(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-superseded",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-superseded@example.com", display_name="Copilot Superseded", password="TestPass123!")
        service._jobs["copilot-superseded"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-superseded"])
        first = client.post(
            "/author/jobs/copilot-superseded/copilot/proposals",
            json={"instruction": "Make the protagonist more assertive."},
        )
        first_id = first.json()["proposal_id"]
        second = client.post(
            "/author/jobs/copilot-superseded/copilot/proposals",
            json={
                "instruction": "Make the protagonist more assertive.",
                "retry_from_proposal_id": first_id,
            },
        )
        preview_old = client.post(f"/author/jobs/copilot-superseded/copilot/proposals/{first_id}/preview")
        apply_old = client.post(f"/author/jobs/copilot-superseded/copilot/proposals/{first_id}/apply")
    finally:
        main_module.author_job_service = original_author_service

    assert second.status_code == 200
    assert preview_old.status_code == 409
    assert preview_old.json()["error"]["code"] == "author_copilot_proposal_superseded"
    assert apply_old.status_code == 409
    assert apply_old.json()["error"]["code"] == "author_copilot_proposal_superseded"
def test_author_copilot_rejects_unsupported_instruction(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-unsupported",
        owner_user_id="usr_copilot",
        prompt_seed="A civic archivist must restore one public record.",
        preview=_preview_response("A civic archivist must restore one public record."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="legitimacy_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(primary_theme="legitimacy_crisis"),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-unsupported@example.com", display_name="Copilot Unsupported", password="TestPass123!")
        service._jobs["copilot-unsupported"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-unsupported"])
        response = client.post(
            "/author/jobs/copilot-unsupported/copilot/proposals",
            json={"instruction": "Tell me a joke about the moon."},
        )
    finally:
        main_module.author_job_service = original_author_service

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "author_copilot_instruction_unsupported"


def test_author_copilot_rejects_published_job(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module
    from tests.test_story_library_api import _publish_source
    from rpg_backend.library.service import StoryLibraryService
    from rpg_backend.library.storage import SQLiteStoryLibraryStorage

    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    fixture = author_fixture_bundle()
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    service = AuthorJobService(
        storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")),
        story_library_service=library_service,
    )
    completed_record = _AuthorJobRecord(
        job_id="copilot-published",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="legitimacy_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(primary_theme="legitimacy_crisis"),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    source = _publish_source("copilot-published")
    library_service.publish_story(
        owner_user_id="usr_copilot",
        source_job_id=source.source_job_id,
        prompt_seed=source.prompt_seed,
        summary=source.summary,
        preview=source.preview,
        bundle=source.bundle,
        visibility="private",
    )
    main_module.author_job_service = service
    main_module.story_library_service = library_service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-published@example.com", display_name="Copilot Published", password="TestPass123!")
        user_id = client.get("/me").json()["user_id"]
        service._jobs["copilot-published"].owner_user_id = user_id
        service._save_record(service._jobs["copilot-published"])
        result_response = client.get("/author/jobs/copilot-published/result")
        editor_state_response = client.get("/author/jobs/copilot-published/editor-state")
        response = client.post(
            "/author/jobs/copilot-published/copilot/proposals",
            json={"instruction": "Make the protagonist more assertive."},
        )
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service

    assert result_response.status_code == 200
    assert result_response.json()["publishable"] is False
    assert editor_state_response.status_code == 200
    assert editor_state_response.json()["publishable"] is False
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "author_copilot_job_already_published"


def test_author_copilot_session_routes_create_message_and_proposal(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-session",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-session@example.com", display_name="Copilot Session", password="TestPass123!")
        service._jobs["copilot-session"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-session"])
        created = client.post("/author/jobs/copilot-session/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        messaged = client.post(
            f"/author/jobs/copilot-session/copilot/sessions/{session_id}/messages",
            json={"content": "Make the protagonist more assertive and make the third act feel more pyrrhic."},
        )
        proposed = client.post(f"/author/jobs/copilot-session/copilot/sessions/{session_id}/proposal")
        reloaded = client.get(f"/author/jobs/copilot-session/copilot/sessions/{session_id}")
    finally:
        main_module.author_job_service = original_author_service

    assert created.status_code == 200
    assert messaged.status_code == 200
    assert messaged.json()["messages"][-2]["role"] == "user"
    assert messaged.json()["messages"][-1]["role"] == "assistant"
    assert proposed.status_code == 200
    assert proposed.json()["mode"] == "bundle_rewrite"
    assert proposed.json()["session_id"] == session_id
    assert "story_frame" in proposed.json()["affected_sections"] or "cast" in proposed.json()["affected_sections"]
    assert reloaded.status_code == 200
    assert reloaded.json()["status"] == "proposal_ready"
    assert reloaded.json()["last_proposal_id"] == proposed.json()["proposal_id"]


def test_author_copilot_session_supports_broad_en_brief_without_exact_heuristic_keywords(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(
        storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")),
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(RuntimeError("disabled_for_test")),
    )
    completed_record = _AuthorJobRecord(
        job_id="copilot-broad-en",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-broad-en@example.com", display_name="Copilot Broad En", password="TestPass123!")
        service._jobs["copilot-broad-en"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-broad-en"])
        created = client.post("/author/jobs/copilot-broad-en/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        client.post(
            f"/author/jobs/copilot-broad-en/copilot/sessions/{session_id}/messages",
            json={"content": "Broaden the story rules and political texture, push the draft toward public record exposure, and keep the same runtime lane."},
        )
        proposed = client.post(f"/author/jobs/copilot-broad-en/copilot/sessions/{session_id}/proposal")
    finally:
        main_module.author_job_service = original_author_service

    assert created.status_code == 200
    assert proposed.status_code == 200
    assert "story_frame" in proposed.json()["affected_sections"]
    assert proposed.json()["request_summary"]


def test_author_copilot_session_supports_broad_zh_brief_without_exact_heuristic_keywords(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(
        storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")),
        gateway_factory=lambda _settings=None: (_ for _ in ()).throw(RuntimeError("disabled_for_test")),
    )
    zh_bundle = fixture.design_bundle.model_copy(
        update={"focused_brief": fixture.focused_brief.model_copy(update={"language": "zh"})}
    )
    completed_record = _AuthorJobRecord(
        job_id="copilot-broad-zh",
        owner_user_id="usr_copilot",
        prompt_seed="一名市政档案官发现，停电后的配给名册被人动过手脚。",
        preview=_preview_response("seed").model_copy(update={"language": "zh"}),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(zh_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=zh_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(primary_theme="logistics_quarantine_crisis").model_copy(
            update={"focused_brief": fixture.focused_brief.model_copy(update={"language": "zh"})}
        ),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-broad-zh@example.com", display_name="Copilot Broad Zh", password="TestPass123!")
        service._jobs["copilot-broad-zh"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-broad-zh"])
        created = client.post("/author/jobs/copilot-broad-zh/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        client.post(
            f"/author/jobs/copilot-broad-zh/copilot/sessions/{session_id}/messages",
            json={"content": "在不改变当前玩法轮廓的前提下，强化公开记录曝光与政治拉扯，让世界规则、角色关系和节拍反馈更鲜明。"},
        )
        proposed = client.post(f"/author/jobs/copilot-broad-zh/copilot/sessions/{session_id}/proposal")
    finally:
        main_module.author_job_service = original_author_service

    assert created.status_code == 200
    assert proposed.status_code == 200
    assert "story_frame" in proposed.json()["affected_sections"]
    assert "公开" in proposed.json()["request_summary"] or "记录" in proposed.json()["request_summary"]


def test_author_copilot_session_preview_and_apply_richer_rewrite_payload(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module
    import rpg_backend.author.jobs as jobs_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))

    def _fake_session_reply(*, session, message, **kwargs):  # noqa: ANN001
        del kwargs
        return (
            "I can turn that into a bundle-level rewrite plan.",
            AuthorCopilotRewriteBrief(
                summary="Push the story toward record exposure and sharper harbor leverage.",
                latest_instruction=message,
                user_goals=["sharper harbor leverage", "clearer record exposure"],
                preserved_invariants=[],
                open_questions=[],
            ),
            "llm",
        )

    def _fake_proposal(**kwargs):  # noqa: ANN003
        proposal = AuthorCopilotProposalResponse.model_validate(
            {
                "proposal_id": "copilot-rich-proposal",
                "proposal_group_id": kwargs["proposal_group_id"],
                "session_id": kwargs["session"].session_id,
                "job_id": kwargs["job_id"],
                "status": "draft",
                "source": "llm",
                "mode": "bundle_rewrite",
                "instruction": kwargs["instruction"],
                "base_revision": kwargs["base_revision"],
                "variant_index": kwargs["variant_index"],
                "variant_label": "Record pressure",
                "supersedes_proposal_id": kwargs.get("supersedes_proposal_id"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "request_summary": "Broaden the harbor story into a sharper record-exposure struggle.",
                "rewrite_scope": "global_story_rewrite",
                "rewrite_brief": kwargs["session"].rewrite_brief.summary,
                "affected_sections": ["story_frame", "cast", "beats", "rule_pack"],
                "stability_guards": [],
                "rewrite_plan": {
                    "story_frame": {
                        "world_rules": [
                            "Emergency shipping law only works if every exception is visible.",
                            "Every sealed record becomes a new political weapon at the docks.",
                        ],
                        "truths": [
                            {
                                "text": "The quarantine ledger was falsified before the first inspection.",
                                "importance": "core",
                            },
                            {
                                "text": "Every faction needs the harbor open but wants the blame pinned elsewhere.",
                                "importance": "core",
                            },
                        ],
                        "flags": [
                            {
                                "label": "Ledger leak",
                                "starting_value": True,
                            }
                        ],
                        "state_axis_choices": [
                            {
                                "template_id": "external_pressure",
                                "story_label": "Harbor Heat",
                                "starting_value": 2,
                            }
                        ],
                    },
                    "cast": [
                        {
                            "npc_id": fixture.design_bundle.story_bible.cast[1].npc_id,
                            "name": "Certifier Jun",
                            "roster_character_id": "roster_archive_certifier",
                        }
                    ],
                    "beats": [
                        {
                            "beat_id": "b1",
                            "focus_names": ["Envoy Iri", "Broker Tal"],
                            "conflict_pair": ["Envoy Iri", "Broker Tal"],
                            "required_truth_texts": ["The quarantine ledger was falsified before the first inspection."],
                            "return_hooks": ["A missing seal becomes the one detail everyone has to answer for in public."],
                            "affordance_tags": ["reveal_truth", "shift_public_narrative"],
                            "blocked_affordances": ["build_trust"],
                        },
                        {
                            "beat_id": "b2",
                            "focus_names": ["Certifier Jun", "Broker Tal"],
                            "conflict_pair": ["Certifier Jun", "Broker Tal"],
                            "required_truth_texts": ["Every faction needs the harbor open but wants the blame pinned elsewhere."],
                        },
                    ],
                    "rule_pack": {
                        "route_unlock_rules": [
                            {
                                "rule_id": "b1_public_archive_route",
                                "beat_id": "b1",
                                "conditions": {"required_truths": ["truth_1"]},
                                "unlock_route_id": "b1_public_archive_route",
                                "unlock_affordance_tag": "reveal_truth",
                            }
                        ],
                        "affordance_effect_profiles": [
                            {
                                "affordance_tag": "reveal_truth",
                                "default_story_function": "reveal",
                                "axis_deltas": {"external_pressure": 1},
                                "stance_deltas": {},
                                "can_add_truth": True,
                                "can_add_event": False,
                            },
                            {
                                "affordance_tag": "shift_public_narrative",
                                "default_story_function": "advance",
                                "axis_deltas": {"political_leverage": 1},
                                "stance_deltas": {},
                                "can_add_truth": False,
                                "can_add_event": True,
                            },
                        ],
                        "ending_rules": [
                            {
                                "ending_id": "collapse",
                                "priority": 1,
                                "conditions": {"min_axes": {"external_pressure": 5}},
                            },
                            {
                                "ending_id": "pyrrhic",
                                "priority": 2,
                                "conditions": {
                                    "min_axes": {"political_leverage": 5, "external_pressure": 3},
                                    "required_truths": ["truth_1"],
                                },
                            },
                            {
                                "ending_id": "mixed",
                                "priority": 10,
                                "conditions": {},
                            },
                        ],
                    },
                },
                "patch_targets": ["story_frame", "cast", "beats", "rule_pack"],
                "operations": [],
                "impact_summary": ["State and route feedback should feel more explicit and political."],
                "warnings": [],
            }
        )
        return proposal, "rich-fingerprint"

    monkeypatch.setattr(jobs_module, "build_copilot_session_reply", _fake_session_reply)
    monkeypatch.setattr(jobs_module, "build_copilot_proposal", _fake_proposal)
    completed_record = _AuthorJobRecord(
        job_id="copilot-rich",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-rich@example.com", display_name="Copilot Rich", password="TestPass123!")
        service._jobs["copilot-rich"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-rich"])
        created = client.post("/author/jobs/copilot-rich/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        client.post(
            f"/author/jobs/copilot-rich/copilot/sessions/{session_id}/messages",
            json={"content": "Broaden story rules and political texture."},
        )
        proposed = client.post(f"/author/jobs/copilot-rich/copilot/sessions/{session_id}/proposal")
        proposal_id = proposed.json()["proposal_id"]
        preview = client.post(f"/author/jobs/copilot-rich/copilot/proposals/{proposal_id}/preview")
        applied = client.post(f"/author/jobs/copilot-rich/copilot/proposals/{proposal_id}/apply")
    finally:
        main_module.author_job_service = original_author_service

    assert created.status_code == 200
    assert proposed.status_code == 200
    assert preview.status_code == 200
    assert applied.status_code == 200
    assert preview.json()["editor_state"]["story_frame_view"]["world_rules"][0] == "Emergency shipping law only works if every exception is visible."
    assert preview.json()["editor_state"]["story_frame_view"]["flags"][0]["label"] == "Ledger leak"
    assert preview.json()["editor_state"]["cast_view"][1]["roster_character_id"] == "roster_archive_certifier"
    assert {"reveal_truth", "shift_public_narrative"}.issubset(set(preview.json()["editor_state"]["beat_view"][0]["affordance_tags"]))
    assert len(preview.json()["editor_state"]["rule_pack_view"]["route_unlock_rules"]) >= 1
    assert {item["ending_id"] for item in applied.json()["editor_state"]["rule_pack_view"]["ending_rules"]} == {"collapse", "pyrrhic", "mixed"}


def test_author_copilot_apply_can_publish_and_play_without_drift(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module
    import rpg_backend.author.jobs as jobs_module
    from rpg_backend.library.service import StoryLibraryService
    from rpg_backend.library.storage import SQLiteStoryLibraryStorage
    from rpg_backend.play.service import PlaySessionService
    from tests.test_play_runtime import _FakePlayTransport

    original_author_service = main_module.author_job_service
    original_library_service = main_module.story_library_service
    original_play_service = main_module.play_session_service
    fixture = author_fixture_bundle()
    library_service = StoryLibraryService(SQLiteStoryLibraryStorage(str(tmp_path / "stories.sqlite3")))
    play_gateway = _FakePlayTransport(
        {
            "play_interpret_turn": [
                {
                    "affordance_tag": "reveal_truth",
                    "target_npc_ids": ["broker_tal"],
                    "risk_level": "medium",
                    "tactic_summary": "Force the forged ledger into the open.",
                }
            ],
            "play_render_turn": [
                {
                    "narration": "You slam the forged ledger into public view and force Broker Tal to answer while the harbor coalition realizes the record can no longer be buried.",
                    "suggested_actions": [
                        {"label": "Press the certifier", "prompt": "You make Certifier Jun lock the ledger into the public record."},
                        {"label": "Turn on Tal", "prompt": "You force Broker Tal to explain who profited from the sealed record."},
                        {"label": "Address the harbor floor", "prompt": "You turn the exposed ledger into a public test of legitimacy."},
                    ],
                }
            ],
        }
    )
    play_service = PlaySessionService(
        story_library_service=library_service,
        gateway_factory=lambda _settings=None: play_gateway,
    )
    service = AuthorJobService(
        storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")),
        story_library_service=library_service,
    )

    def _fake_session_reply(*, message, **kwargs):  # noqa: ANN003
        del kwargs
        return (
            "I can turn that into a bundle-level rewrite plan.",
            AuthorCopilotRewriteBrief(
                summary="Push the story toward record exposure and sharper harbor leverage.",
                latest_instruction=message,
                user_goals=["sharper harbor leverage", "clearer record exposure"],
                preserved_invariants=[],
                open_questions=[],
            ),
            "llm",
        )

    def _fake_proposal(**kwargs):  # noqa: ANN003
        proposal = AuthorCopilotProposalResponse.model_validate(
            {
                "proposal_id": "copilot-publish-play",
                "proposal_group_id": kwargs["proposal_group_id"],
                "session_id": kwargs["session"].session_id,
                "job_id": kwargs["job_id"],
                "status": "draft",
                "source": "llm",
                "mode": "bundle_rewrite",
                "instruction": kwargs["instruction"],
                "base_revision": kwargs["base_revision"],
                "variant_index": kwargs["variant_index"],
                "variant_label": "Record pressure",
                "supersedes_proposal_id": kwargs.get("supersedes_proposal_id"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "request_summary": "Broaden the harbor story into a sharper record-exposure struggle.",
                "rewrite_scope": "global_story_rewrite",
                "rewrite_brief": kwargs["session"].rewrite_brief.summary,
                "affected_sections": ["story_frame", "cast", "beats", "rule_pack"],
                "stability_guards": [],
                "rewrite_plan": {
                    "story_frame": {
                        "world_rules": [
                            "Emergency shipping law only works if every exception is visible.",
                            "Every sealed record becomes a new political weapon at the docks.",
                        ],
                        "truths": [
                            {
                                "text": "The quarantine ledger was falsified before the first inspection.",
                                "importance": "core",
                            },
                            {
                                "text": "Every faction needs the harbor open but wants the blame pinned elsewhere.",
                                "importance": "core",
                            },
                        ],
                    },
                    "cast": [
                        {
                            "npc_id": fixture.design_bundle.story_bible.cast[1].npc_id,
                            "name": "Certifier Jun",
                            "roster_character_id": "roster_archive_certifier",
                        }
                    ],
                    "beats": [
                        {
                            "beat_id": "b1",
                            "focus_names": ["Envoy Iri", "Broker Tal"],
                            "conflict_pair": ["Envoy Iri", "Broker Tal"],
                            "required_truth_texts": ["The quarantine ledger was falsified before the first inspection."],
                            "affordance_tags": ["reveal_truth", "shift_public_narrative"],
                        },
                        {
                            "beat_id": "b2",
                            "focus_names": ["Certifier Jun", "Broker Tal"],
                            "conflict_pair": ["Certifier Jun", "Broker Tal"],
                            "required_truth_texts": ["Every faction needs the harbor open but wants the blame pinned elsewhere."],
                        },
                    ],
                    "rule_pack": {
                        "route_unlock_rules": [
                            {
                                "rule_id": "b1_public_archive_route",
                                "beat_id": "b1",
                                "conditions": {"required_truths": ["truth_1"]},
                                "unlock_route_id": "b1_public_archive_route",
                                "unlock_affordance_tag": "reveal_truth",
                            }
                        ],
                        "affordance_effect_profiles": [
                            {
                                "affordance_tag": "reveal_truth",
                                "default_story_function": "reveal",
                                "axis_deltas": {"external_pressure": 1},
                                "stance_deltas": {},
                                "can_add_truth": True,
                                "can_add_event": False,
                            },
                            {
                                "affordance_tag": "shift_public_narrative",
                                "default_story_function": "advance",
                                "axis_deltas": {"political_leverage": 1},
                                "stance_deltas": {},
                                "can_add_truth": False,
                                "can_add_event": True,
                            },
                        ],
                        "ending_rules": [
                            {
                                "ending_id": "collapse",
                                "priority": 1,
                                "conditions": {"min_axes": {"external_pressure": 5}},
                            },
                            {
                                "ending_id": "pyrrhic",
                                "priority": 2,
                                "conditions": {
                                    "min_axes": {"political_leverage": 5, "external_pressure": 3},
                                    "required_truths": ["truth_1"],
                                },
                            },
                            {
                                "ending_id": "mixed",
                                "priority": 10,
                                "conditions": {},
                            },
                        ],
                    },
                },
                "patch_targets": ["story_frame", "cast", "beats", "rule_pack"],
                "operations": [],
                "impact_summary": ["State and route feedback should feel more explicit and political."],
                "warnings": [],
            }
        )
        return proposal, "publish-play-fingerprint"

    monkeypatch.setattr(jobs_module, "build_copilot_session_reply", _fake_session_reply)
    monkeypatch.setattr(jobs_module, "build_copilot_proposal", _fake_proposal)
    completed_record = _AuthorJobRecord(
        job_id="copilot-publish-play-job",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    main_module.story_library_service = library_service
    main_module.play_session_service = play_service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-publish-play@example.com", display_name="Copilot Publish Play", password="TestPass123!")
        service._jobs["copilot-publish-play-job"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-publish-play-job"])
        created = client.post("/author/jobs/copilot-publish-play-job/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        client.post(
            f"/author/jobs/copilot-publish-play-job/copilot/sessions/{session_id}/messages",
            json={"content": "Broaden story rules and political texture."},
        )
        proposed = client.post(f"/author/jobs/copilot-publish-play-job/copilot/sessions/{session_id}/proposal")
        proposal_id = proposed.json()["proposal_id"]
        applied = client.post(f"/author/jobs/copilot-publish-play-job/copilot/proposals/{proposal_id}/apply")
        published = client.post("/author/jobs/copilot-publish-play-job/publish")
        story_id = published.json()["story_id"]
        created_session = client.post("/play/sessions", json={"story_id": story_id})
        session_snapshot = client.post(
            f"/play/sessions/{created_session.json()['session_id']}/turns",
            json={"input_text": "I force the forged ledger into the open and make Broker Tal answer for it."},
        )
    finally:
        main_module.author_job_service = original_author_service
        main_module.story_library_service = original_library_service
        main_module.play_session_service = original_play_service

    assert applied.status_code == 200
    assert published.status_code == 200
    assert published.json()["title"]
    assert published.json()["story_id"]
    assert created_session.status_code == 200
    assert created_session.json()["story_id"] == story_id
    assert created_session.json()["protagonist"]["title"]
    assert session_snapshot.status_code == 200
    assert session_snapshot.json()["status"] == "active"
    assert "forged ledger" in session_snapshot.json()["narration"]
    assert len(session_snapshot.json()["suggested_actions"]) == 3


def test_author_editor_state_exposes_active_copilot_session_id_for_visible_session(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-active-session",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-active-session@example.com", display_name="Copilot Active Session", password="TestPass123!")
        service._jobs["copilot-active-session"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-active-session"])
        created = client.post("/author/jobs/copilot-active-session/copilot/sessions", json={"hidden": False})
        editor_state = client.get("/author/jobs/copilot-active-session/editor-state")
    finally:
        main_module.author_job_service = original_author_service

    assert created.status_code == 200
    assert editor_state.status_code == 200
    assert editor_state.json()["copilot_view"]["active_session_id"] == created.json()["session_id"]


def test_author_editor_state_hides_hidden_copilot_session_id(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-hidden-session",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-hidden-session@example.com", display_name="Copilot Hidden Session", password="TestPass123!")
        service._jobs["copilot-hidden-session"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-hidden-session"])
        created = client.post("/author/jobs/copilot-hidden-session/copilot/sessions", json={"hidden": True})
        editor_state = client.get("/author/jobs/copilot-hidden-session/editor-state")
    finally:
        main_module.author_job_service = original_author_service

    assert created.status_code == 200
    assert editor_state.status_code == 200
    assert editor_state.json()["copilot_view"]["active_session_id"] is None


def test_zh_copilot_session_message_falls_back_to_chinese_when_gateway_replies_in_english(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    gateway = _EnglishCopilotProvider(
        [
            {
                "assistant_reply": "I can rewrite this to feel sharper.",
                "rewrite_brief": {
                    "summary": "Rewrite focus: make the protagonist stronger.",
                    "latest_instruction": "Make the protagonist more assertive.",
                    "user_goals": ["more assertive protagonist"],
                    "preserved_invariants": [],
                    "open_questions": [],
                },
            }
        ]
    )
    service = AuthorJobService(
        storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")),
        gateway_factory=lambda _settings=None: gateway,  # type: ignore[arg-type]
    )
    zh_bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": fixture.focused_brief.model_copy(update={"language": "zh"}),
        }
    )
    completed_record = _AuthorJobRecord(
        job_id="copilot-zh-session",
        owner_user_id="usr_copilot",
        prompt_seed="一名港口检查官必须阻止检疫权力滑向私人控制。",
        preview=_preview_response("seed").model_copy(update={"language": "zh"}),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(zh_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=zh_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(primary_theme="logistics_quarantine_crisis").model_copy(
            update={"focused_brief": fixture.focused_brief.model_copy(update={"language": "zh"})}
        ),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-zh-session@example.com", display_name="Copilot Zh Session", password="TestPass123!")
        service._jobs["copilot-zh-session"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-zh-session"])
        created = client.post("/author/jobs/copilot-zh-session/copilot/sessions", json={"hidden": False})
        messaged = client.post(
            f"/author/jobs/copilot-zh-session/copilot/sessions/{created.json()['session_id']}/messages",
            json={"content": "把主角改得更强硬。"},
        )
    finally:
        main_module.author_job_service = original_author_service

    assert created.status_code == 200
    assert messaged.status_code == 200
    assert "我可以按这个方向继续" in messaged.json()["messages"][-1]["content"]
    assert "本轮重写重点" in messaged.json()["rewrite_brief"]["summary"]


def test_zh_copilot_proposal_falls_back_to_chinese_when_gateway_returns_english_plan(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    gateway = _EnglishCopilotProvider(
        [
            {
                "assistant_reply": "I can rewrite this to feel sharper.",
                "rewrite_brief": {
                    "summary": "Rewrite focus: make the protagonist stronger.",
                    "latest_instruction": "Make the protagonist more assertive.",
                    "user_goals": ["more assertive protagonist"],
                    "preserved_invariants": [],
                    "open_questions": [],
                },
            },
            {
                "request_summary": "Reframe the protagonist as more forceful under pressure.",
                "variant_label": "Public pressure",
                "affected_sections": ["cast"],
                "impact_summary": ["Public pressure should feel more natural."],
                "warnings": [],
                "story_frame": None,
                "cast": [
                    {
                        "npc_id": "corin-hale",
                        "agenda": "Force a visible answer before delay hardens into private control.",
                    }
                ],
                "beats": [],
                "rule_pack": None,
            },
        ]
    )
    service = AuthorJobService(
        storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")),
        gateway_factory=lambda _settings=None: gateway,  # type: ignore[arg-type]
    )
    zh_bundle = fixture.design_bundle.model_copy(
        update={
            "focused_brief": fixture.focused_brief.model_copy(update={"language": "zh"}),
        }
    )
    completed_record = _AuthorJobRecord(
        job_id="copilot-zh-proposal",
        owner_user_id="usr_copilot",
        prompt_seed="一名港口检查官必须阻止检疫权力滑向私人控制。",
        preview=_preview_response("seed").model_copy(update={"language": "zh"}),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(zh_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=zh_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(primary_theme="logistics_quarantine_crisis").model_copy(
            update={"focused_brief": fixture.focused_brief.model_copy(update={"language": "zh"})}
        ),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-zh-proposal@example.com", display_name="Copilot Zh Proposal", password="TestPass123!")
        service._jobs["copilot-zh-proposal"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-zh-proposal"])
        created = client.post("/author/jobs/copilot-zh-proposal/copilot/sessions", json={"hidden": False})
        client.post(
            f"/author/jobs/copilot-zh-proposal/copilot/sessions/{created.json()['session_id']}/messages",
            json={"content": "把主角改得更强硬。"},
        )
        proposed = client.post(
            f"/author/jobs/copilot-zh-proposal/copilot/sessions/{created.json()['session_id']}/proposal"
        )
    finally:
        main_module.author_job_service = original_author_service

    assert proposed.status_code == 200
    assert "公开施压" in proposed.json()["variant_label"]
    assert "把主角改成在压力下更强硬" in proposed.json()["request_summary"]


def test_author_copilot_session_create_rejects_workspace_unavailable(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-nosnapshot",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=None,
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    monkeypatch.setattr(service, "_recover_workspace_snapshot_from_checkpoint", lambda **_: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-nosnapshot@example.com", display_name="Copilot No Snapshot", password="TestPass123!")
        service._jobs["copilot-nosnapshot"].owner_user_id = client.get("/me").json()["user_id"]
        service._save_record(service._jobs["copilot-nosnapshot"])
        response = client.post("/author/jobs/copilot-nosnapshot/copilot/sessions", json={"hidden": False})
    finally:
        main_module.author_job_service = original_author_service

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "author_copilot_workspace_unavailable"


def test_author_copilot_session_message_rejects_stale_revision(monkeypatch, tmp_path) -> None:
    import rpg_backend.main as main_module

    original_author_service = main_module.author_job_service
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    completed_record = _AuthorJobRecord(
        job_id="copilot-stale",
        owner_user_id="usr_copilot",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
        copilot_workspace_snapshot=_copilot_workspace_snapshot(),
    )
    monkeypatch.setattr(service, "_start_background_job", lambda job_id, resume_from_checkpoint: None)
    service._save_record(completed_record)
    main_module.author_job_service = service
    client = TestClient(app)
    try:
        ensure_authenticated_client(client, email="copilot-stale@example.com", display_name="Copilot Stale", password="TestPass123!")
        user_id = client.get("/me").json()["user_id"]
        service._jobs["copilot-stale"].owner_user_id = user_id
        service._save_record(service._jobs["copilot-stale"])
        created = client.post("/author/jobs/copilot-stale/copilot/sessions", json={"hidden": False})
        session_id = created.json()["session_id"]
        service._jobs["copilot-stale"].updated_at = service._now()
        service._save_record(service._jobs["copilot-stale"])
        response = client.post(
            f"/author/jobs/copilot-stale/copilot/sessions/{session_id}/messages",
            json={"content": "Make it more assertive."},
        )
    finally:
        main_module.author_job_service = original_author_service

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "author_copilot_session_stale"


def test_author_service_can_disable_default_actor_fallback(tmp_path) -> None:
    fixture = author_fixture_bundle()
    service = AuthorJobService(
        storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")),
        allow_default_actor_fallback=False,
    )
    record = _AuthorJobRecord(
        job_id="no-fallback-job",
        owner_user_id="usr_owner",
        prompt_seed="A harbor inspector must keep quarantine from turning into private rule.",
        preview=_preview_response("A harbor inspector must keep quarantine from turning into private rule."),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(fixture.design_bundle, primary_theme="logistics_quarantine_crisis"),
        bundle=fixture.design_bundle,
    )
    service._save_record(record)

    with pytest.raises(AuthorGatewayError) as exc_info:
        service.get_job("no-fallback-job")

    assert exc_info.value.code == "auth_session_required"


def test_author_editor_state_exposes_roster_metadata(tmp_path) -> None:
    fixture = author_fixture_bundle()
    roster_cast = list(fixture.design_bundle.story_bible.cast)
    roster_cast[1] = roster_cast[1].model_copy(
        update={
            "roster_character_id": "roster_archive_certifier",
            "roster_public_summary": "A records certifier trusted by no faction precisely because they have blocked all of them before.",
            "portrait_url": None,
            "template_version": "tpl-archive-certifier-v1",
        }
    )
    bundle = fixture.design_bundle.model_copy(update={"story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": roster_cast})})
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    record = _AuthorJobRecord(
        job_id="job-roster-editor",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=_preview_response("seed"),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(bundle, primary_theme="truth_record_crisis"),
        bundle=bundle,
    )
    service._save_record(record)

    editor_state = service.get_job_editor_state("job-roster-editor")

    assert editor_state.cast_view[1].roster_character_id == "roster_archive_certifier"
    assert editor_state.cast_view[1].roster_public_summary
    assert editor_state.cast_view[1].template_version


def test_author_editor_state_can_expose_three_portrait_urls(tmp_path) -> None:
    fixture = author_fixture_bundle()
    roster_cast = [
        member.model_copy(
            update={
                "roster_character_id": roster_id,
                "roster_public_summary": f"Summary for {roster_id}.",
                "portrait_url": f"http://127.0.0.1:8000/portraits/roster/{roster_id}.png",
                "portrait_variants": PortraitVariants(
                    positive=f"http://127.0.0.1:8000/portraits/roster/{roster_id}__positive.png",
                    neutral=f"http://127.0.0.1:8000/portraits/roster/{roster_id}.png",
                    negative=f"http://127.0.0.1:8000/portraits/roster/{roster_id}__negative.png",
                ),
            }
        )
        for member, roster_id in zip(
            fixture.design_bundle.story_bible.cast,
            [
                "roster_archive_certifier",
                "roster_courtyard_witness",
                "roster_blackout_grid_broker",
            ],
            strict=False,
        )
    ]
    bundle = fixture.design_bundle.model_copy(
        update={"story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": roster_cast})}
    )
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    record = _AuthorJobRecord(
        job_id="job-roster-editor-three",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=_preview_response("seed"),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(bundle, primary_theme="truth_record_crisis"),
        bundle=bundle,
    )
    service._save_record(record)

    editor_state = service.get_job_editor_state("job-roster-editor-three")

    assert len([item for item in editor_state.cast_view if item.portrait_url]) == 3


def test_author_editor_state_can_expose_portrait_variants_when_present(tmp_path) -> None:
    fixture = author_fixture_bundle()
    roster_cast = [
        fixture.design_bundle.story_bible.cast[0].model_copy(
            update={
                "roster_character_id": "roster_archive_certifier",
                "roster_public_summary": "Summary for roster_archive_certifier.",
                "portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                "portrait_variants": PortraitVariants(
                    negative="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/negative/current.png",
                    neutral="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                    positive="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/positive/current.png",
                ),
            }
        ),
        *fixture.design_bundle.story_bible.cast[1:],
    ]
    bundle = fixture.design_bundle.model_copy(
        update={"story_bible": fixture.design_bundle.story_bible.model_copy(update={"cast": roster_cast})}
    )
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(str(tmp_path / "author.sqlite3")))
    record = _AuthorJobRecord(
        job_id="job-roster-editor-variants",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=_preview_response("seed"),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(bundle, primary_theme="truth_record_crisis"),
        bundle=bundle,
    )
    service._save_record(record)

    editor_state = service.get_job_editor_state("job-roster-editor-variants")

    assert editor_state.cast_view[0].portrait_variants is not None
    assert editor_state.cast_view[0].portrait_variants.neutral == "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png"
    assert editor_state.cast_view[1].portrait_variants == bundle.story_bible.cast[1].portrait_variants

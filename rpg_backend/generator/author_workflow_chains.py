from __future__ import annotations

import inspect
from typing import Any

from pydantic import ValidationError

from rpg_backend.domain.conflict_tags import NPC_CONFLICT_TAG_CATALOG
from rpg_backend.generator.author_workflow_errors import PromptCompileError
from rpg_backend.generator.author_workflow_models import (
    AuthorMemory,
    BeatScenePlan,
    BeatScenePlanItem,
    BeatOverviewContext,
    BeatPrefixSummary,
    GeneratedBeatScene,
    StoryOverview,
)
from rpg_backend.generator.author_workflow_policy import AuthorWorkflowPolicy, get_author_workflow_policy
from rpg_backend.llm.agents import AuthorAgent
from rpg_backend.llm.factory import get_author_agent


def _compact_last_accepted_beat(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    compact: dict[str, Any] = {}
    for key in ("beat_id", "title", "objective", "present_npcs", "events_produced", "closing_hook"):
        value = payload.get(key)
        if value is not None:
            compact[key] = value

    scenes = payload.get("scenes")
    if "closing_hook" not in compact and isinstance(scenes, list) and scenes:
        last_scene = scenes[-1]
        if isinstance(last_scene, dict) and isinstance(last_scene.get("scene_seed"), str):
            compact["closing_hook"] = last_scene["scene_seed"]

    return compact or None


def _compact_overview_context_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}

    for key in ("premise", "stakes", "tone", "ending_shape", "ending_shape_note", "move_bias_note"):
        value = payload.get(key)
        if value is not None:
            compact[key] = value

    move_bias = payload.get("move_bias")
    if isinstance(move_bias, list):
        compact["move_bias"] = list(move_bias)[:3]

    scene_constraints = payload.get("scene_constraints")
    if isinstance(scene_constraints, list):
        compact["scene_constraints"] = list(scene_constraints)[:2]

    npc_roster = payload.get("npc_roster")
    if isinstance(npc_roster, list):
        compact["npc_roster"] = [
            {
                key: npc.get(key)
                for key in ("name", "role", "red_line", "conflict_tags", "pressure_signature")
                if key in npc
            }
            for npc in npc_roster
            if isinstance(npc, dict)
        ]

    return compact


def _compact_author_memory_payload(author_memory: AuthorMemory | None) -> dict[str, Any] | None:
    if author_memory is None:
        return None
    payload = author_memory.model_dump(mode="json")
    recent_beats = payload.get("recent_beats")
    compact_recent_beats: list[dict[str, Any]] = []
    if isinstance(recent_beats, list):
        for beat in recent_beats[:2]:
            if not isinstance(beat, dict):
                continue
            compact_recent_beats.append(
                {
                    "beat_id": beat.get("beat_id"),
                    "title": beat.get("title"),
                    "objective": beat.get("objective"),
                    "present_npcs": list(beat.get("present_npcs") or [])[:3],
                    "events_produced": list(beat.get("events_produced") or [])[:2],
                    "closing_hook": beat.get("closing_hook"),
                }
            )
    return {
        "beat_count": int(payload.get("beat_count") or 0),
        "active_npcs": list(payload.get("active_npcs") or [])[:4],
        "unresolved_threads": list(payload.get("unresolved_threads") or [])[:6],
        "recent_beats": compact_recent_beats,
    }


def _compact_blueprint_for_scene_generation(blueprint: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("beat_id", "title", "objective", "conflict", "required_event", "scene_intent"):
        value = blueprint.get(key)
        if value is not None:
            compact[key] = value
    return compact


class _JsonSchemaChain:
    non_thinking_timeout_seconds = 40.0
    thinking_timeout_seconds = 60.0
    task_spec_attr_name: str | None = None

    def __init__(
        self,
        *,
        policy: AuthorWorkflowPolicy | None = None,
        author_agent: AuthorAgent | None = None,
    ) -> None:
        self.policy = policy or get_author_workflow_policy()
        self._author_agent = author_agent
        self.model = getattr(author_agent, "model", "unknown")
        self.timeout_seconds = None if self.policy.timeout_seconds is None else float(self.policy.timeout_seconds)
        self.max_retries = int(self.policy.llm_call_max_retries)

    @property
    def author_agent(self) -> AuthorAgent:
        if self._author_agent is None:
            self._author_agent = get_author_agent()
            self.model = getattr(self._author_agent, "model", self.model)
        return self._author_agent

    @staticmethod
    def _build_validation_feedback(exc: Exception) -> list[str]:
        if isinstance(exc, ValidationError):
            feedback: list[str] = []
            seen_paths: set[str] = set()
            for issue in exc.errors():
                path = ".".join(str(part) for part in issue.get("loc", ())) or "<root>"
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                feedback.append(f"{path}: {issue.get('msg', 'invalid value')}")
            return feedback or [str(exc)]
        return [str(exc)]

    @staticmethod
    def _accepts_kwarg(func: Any, name: str) -> bool:
        signature = inspect.signature(func)
        if name in signature.parameters:
            return True
        return any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
        )

    @property
    def enable_thinking(self) -> bool:
        task_spec_attr_name = getattr(self, "task_spec_attr_name", None)
        if not task_spec_attr_name:
            return False
        task_spec = getattr(self.author_agent, task_spec_attr_name, None)
        return bool(getattr(task_spec, "enable_thinking", False))

    @property
    def workflow_timeout_seconds(self) -> float:
        if self.timeout_seconds is not None:
            return float(self.timeout_seconds)
        return self.thinking_timeout_seconds if self.enable_thinking else self.non_thinking_timeout_seconds


class StoryOverviewChain(_JsonSchemaChain):
    task_spec_attr_name = "overview_task_spec"

    async def _invoke_chain(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        timeout_seconds: float | None = None,
        run_id: str | None = None,
    ):
        return await self.author_agent.generate_overview(
            run_id=run_id or "author_overview_stateless",
            raw_brief=system_prompt,
            output_schema=dict(user_payload.get("output_schema") or StoryOverview.model_json_schema()),
            timeout_seconds=timeout_seconds,
        )

    async def compile(
        self,
        *,
        raw_brief: str,
        timeout_seconds: float | None = None,
        run_id: str | None = None,
    ) -> StoryOverview:
        effective_timeout_seconds = float(self.workflow_timeout_seconds if timeout_seconds is None else timeout_seconds)
        catalog_markdown = "\n".join(
            f"- `{key}`: {value}" for key, value in dict(NPC_CONFLICT_TAG_CATALOG).items()
        )
        if not self.model:
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=["responses config missing model"],
                notes=["check APP_RESPONSES_MODEL"],
            )

        system_prompt = (
            "# Role & Intent\n"
            "You transform a raw author brief into one strict StoryOverview JSON object.\n"
            "Do NOT output any text outside JSON.\n\n"
            "# Hard Constraints\n"
            "- target_minutes must be between 8 and 12 inclusive.\n"
            "- npc_count must be between 3 and 5 inclusive.\n"
            "- npc_roster length must equal npc_count.\n"
            "- Keep text compact: premise <= 240 characters, tone <= 70 characters, stakes <= 180 characters.\n"
            "- Use one short sentence for premise and one short sentence for stakes. Avoid semicolon chains and list formatting.\n"
            "- ending_shape must be one of triumph, pyrrhic, uncertain, sacrifice.\n"
            "- ending_shape_note must briefly explain the emotional flavor and tradeoff implied by ending_shape.\n"
            "- move_bias values must come from the move_bias enum only.\n"
            "- move_bias_note must explain how the selected move_bias should feel in play without replacing the enum values.\n"
            "- npc_roster[*].conflict_tags must use only the npc conflict tag enum values below.\n"
            "- npc_roster[*].pressure_signature must be a short free-text tension cue that complements conflict_tags instead of replacing them.\n"
            "- npc conflict tags are NOT move_bias values. Never use social, technical, stealth, investigate, support, resource, conflict, or mobility in npc_roster[*].conflict_tags.\n\n"
            "# Soft Goals\n"
            "- Design a cast that can recur across multiple beats; prefer durable pressure relationships over disposable one-scene characters.\n"
            "- Give every NPC a sharp enough role and red line that later beat generation can keep them distinct without extra exposition.\n"
            "- Use ending_shape_note, move_bias_note, and pressure_signature to carry story-specific nuance while keeping ending_shape, move_bias, and conflict_tags machine-stable.\n"
            "- Write scene_constraints as playable pressure lenses, not decorative lore fragments.\n\n"
            "# NPC Conflict Tags\n"
            f"{catalog_markdown}\n\n"
            "# Raw Brief\n"
            f"{raw_brief}"
        )
        invoke_kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "user_payload": {
                "output_schema": StoryOverview.model_json_schema(),
            },
            "timeout_seconds": effective_timeout_seconds,
        }
        if self._accepts_kwarg(self._invoke_chain, "run_id"):
            invoke_kwargs["run_id"] = run_id
        try:
            result = await self._invoke_chain(**invoke_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=[str(exc)],
                notes=["story overview responses execution failed"],
            ) from exc

        try:
            return StoryOverview.model_validate(result.payload)
        except ValidationError as exc:
            raise PromptCompileError(
                error_code="overview_invalid",
                errors=self._build_validation_feedback(exc),
                notes=["story overview schema validation failed"],
            ) from exc


class BeatGenerationChain(_JsonSchemaChain):
    task_spec_attr_name = "scene_task_spec"

    @staticmethod
    def _enable_thinking_for_task(agent: AuthorAgent, attr_name: str) -> bool:
        task_spec = getattr(agent, attr_name, None)
        return bool(getattr(task_spec, "enable_thinking", False))

    @classmethod
    def _default_timeout_for_thinking(cls, *, enabled: bool) -> float:
        return cls.thinking_timeout_seconds if enabled else cls.non_thinking_timeout_seconds

    @property
    def scene_plan_timeout_seconds(self) -> float:
        if self.timeout_seconds is not None:
            return float(self.timeout_seconds)
        enabled = self._enable_thinking_for_task(self.author_agent, "beat_plan_task_spec")
        return self._default_timeout_for_thinking(enabled=enabled)

    @property
    def scene_generation_timeout_seconds(self) -> float:
        if self.timeout_seconds is not None:
            return float(self.timeout_seconds)
        enabled = self._enable_thinking_for_task(self.author_agent, "scene_task_spec")
        return self._default_timeout_for_thinking(enabled=enabled)

    @property
    def workflow_timeout_seconds(self) -> float:
        return self.scene_generation_timeout_seconds

    async def compile_beat_scene_plan(
        self,
        *,
        story_id: str,
        overview_context: BeatOverviewContext,
        blueprint: dict[str, Any],
        last_accepted_beat: dict[str, Any] | None,
        prefix_summary: BeatPrefixSummary,
        author_memory: AuthorMemory | None = None,
        lint_feedback: list[str] | None = None,
        timeout_seconds: float | None = None,
        run_id: str | None = None,
    ) -> BeatScenePlan:
        effective_timeout_seconds = float(
            self.scene_plan_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        beat_id = str(blueprint.get("beat_id") or "beat")
        system_prompt = (
            "# Role & Intent\n"
            "Generate one strict BeatScenePlan JSON object for the current beat blueprint.\n"
            "Do NOT output any text outside JSON.\n\n"
            "# Hard Constraints\n"
            "- beat_id must exactly equal the current blueprint beat_id.\n"
            "- include 1-3 scenes only.\n"
            "- each scene plan item must include concise purpose, pressure, handoff_intent, present_npcs, transition_style, and is_terminal.\n"
            "- scene_id is optional in each scene item; backend will assign deterministic scene ids by order.\n"
            "- present_npcs must come from overview_context npc_roster names.\n"
            "- only the final planned scene may set is_terminal=true.\n\n"
            "# Soft Goals\n"
            "- Keep each scene purpose/actionable for one generation call.\n"
            "- Preserve continuity from prefix_summary, author_memory, and last_accepted_beat.\n"
            "- Prefer continuity pressure over lore expansion."
        )
        payload = {
            "story_id": story_id,
            "overview_context": _compact_overview_context_payload(overview_context.model_dump(mode="json")),
            "blueprint": blueprint,
            "last_accepted_beat": _compact_last_accepted_beat(last_accepted_beat),
            "prefix_summary": prefix_summary.model_dump(mode="json"),
            "author_memory": _compact_author_memory_payload(author_memory),
            "lint_feedback": list(lint_feedback or []),
            "output_schema": BeatScenePlan.model_json_schema(),
        }
        invoke_kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "user_payload": payload,
            "timeout_seconds": effective_timeout_seconds,
        }
        if self._accepts_kwarg(self._invoke_scene_plan, "run_id"):
            invoke_kwargs["run_id"] = run_id
        try:
            result = await self._invoke_scene_plan(**invoke_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=[str(exc)],
                notes=["beat scene plan responses execution failed"],
            ) from exc

        try:
            plan = BeatScenePlan.model_validate(result.payload)
        except ValidationError as exc:
            raise PromptCompileError(
                error_code="beat_scene_plan_invalid",
                errors=self._build_validation_feedback(exc),
                notes=["beat scene plan schema validation failed"],
            ) from exc
        if plan.beat_id != beat_id:
            raise PromptCompileError(
                error_code="beat_scene_plan_invalid",
                errors=["beat scene plan beat_id does not match current blueprint"],
                notes=["beat scene plan schema validation failed"],
            )
        return plan

    async def compile_scene(
        self,
        *,
        story_id: str,
        overview_context: BeatOverviewContext,
        blueprint: dict[str, Any],
        scene_plan_item: dict[str, Any],
        scene_count: int,
        scene_index: int,
        prior_generated_scenes: list[dict[str, Any]],
        prefix_summary: BeatPrefixSummary,
        author_memory: AuthorMemory | None = None,
        lint_feedback: list[str] | None = None,
        timeout_seconds: float | None = None,
        run_id: str | None = None,
    ) -> GeneratedBeatScene:
        if scene_index < 0 or scene_index >= int(scene_count):
            raise PromptCompileError(
                error_code="scene_invalid",
                errors=["scene_index is outside current beat scene plan"],
                notes=["generate_scene called with invalid scene index"],
            )
        effective_timeout_seconds = float(
            self.scene_generation_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        planned_scene = BeatScenePlanItem.model_validate(scene_plan_item)
        beat_id = str(blueprint.get("beat_id") or "beat")
        scene_seq = scene_index + 1
        scene_id = str(planned_scene.scene_id or f"{beat_id}.sc{scene_seq}")
        system_prompt = (
            "# Role & Intent\n"
            "Generate one strict GeneratedBeatScene JSON object for the current planned scene.\n"
            "Do NOT output any text outside JSON.\n\n"
            "# Hard Constraints\n"
            f"- this output is for beat '{beat_id}', scene order {scene_seq}, deterministic scene id '{scene_id}'.\n"
            "- include scene_seed and present_npcs.\n"
            "- include exactly three local_moves.\n"
            "- each local move must include label, strategy_style, intents, optional synonyms, and outcomes.\n"
            "- each local move outcomes list must include success, partial, and fail_forward exactly once.\n"
            "- each outcome must include narration_slots only (npc_reaction, world_shift, clue_delta, cost_delta, next_hook).\n"
            "- do not emit ids, enabled_moves, always_available_moves, exit_conditions, or next_scene_id wiring fields.\n"
            "- present_npcs should follow the planned scene present_npcs unless continuity requires a strict subset.\n\n"
            "# Soft Goals\n"
            "- Keep the scene concise and pressure-forward.\n"
            "- Preserve continuity with prior_scene_memory and author_memory."
        )
        payload = {
            "story_id": story_id,
            "overview_context": _compact_overview_context_payload(overview_context.model_dump(mode="json")),
            "blueprint": _compact_blueprint_for_scene_generation(blueprint),
            "scene_plan_item": planned_scene.model_dump(mode="json"),
            "scene_order": scene_seq,
            "total_scenes": int(scene_count),
            "prior_scene_memory": list(prior_generated_scenes),
            "prefix_summary": prefix_summary.model_dump(mode="json"),
            "author_memory": _compact_author_memory_payload(author_memory),
            "lint_feedback": list(lint_feedback or []),
            "output_schema": GeneratedBeatScene.model_json_schema(),
        }
        invoke_kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "user_payload": payload,
            "timeout_seconds": effective_timeout_seconds,
        }
        if self._accepts_kwarg(self._invoke_scene, "run_id"):
            invoke_kwargs["run_id"] = run_id
        try:
            result = await self._invoke_scene(**invoke_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=[str(exc)],
                notes=["generated beat scene responses execution failed"],
            ) from exc

        try:
            generated = GeneratedBeatScene.model_validate(result.payload)
        except ValidationError as exc:
            raise PromptCompileError(
                error_code="scene_invalid",
                errors=self._build_validation_feedback(exc),
                notes=["generated beat scene schema validation failed"],
            ) from exc
        return generated

    async def _invoke_scene_plan(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        timeout_seconds: float | None = None,
        run_id: str | None = None,
    ):
        payload = dict(user_payload)
        payload["instructions"] = system_prompt
        story_id = str(payload.get("story_id") or "story")
        return await self.author_agent.plan_beat_scenes(
            run_id=run_id or f"author_beat_plan_stateless:{story_id}",
            payload=payload,
            timeout_seconds=timeout_seconds,
        )

    async def _invoke_scene(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        timeout_seconds: float | None = None,
        run_id: str | None = None,
    ):
        payload = dict(user_payload)
        payload["instructions"] = system_prompt
        story_id = str(payload.get("story_id") or "story")
        beat_id = str(payload.get("blueprint", {}).get("beat_id") or "beat")
        return await self.author_agent.generate_scene(
            run_id=run_id or f"author_scene_stateless:{story_id}",
            beat_id=beat_id,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )

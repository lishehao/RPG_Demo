from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from rpg_backend.application.author_runs.beat_context_builder import (
    BeatGenerationContext,
    build_beat_generation_context,
    build_scene_generation_context,
)
from rpg_backend.application.author_runs.workflow_retry import AuthorWorkflowNodeHandler
from rpg_backend.application.author_runs.workflow_state import (
    AuthorWorkflowState,
    build_accepted_beat_update,
    build_beat_assembly_update,
    build_beat_phase_seed_update,
    build_beat_plan_update,
    build_beat_scene_plan_update,
    build_overview_generation_update,
    build_scene_generation_update,
    get_beat_phase,
    get_overview_phase,
)
from rpg_backend.application.author_runs.workflow_vocabulary import AuthorWorkflowNode, AuthorWorkflowStatus
from rpg_backend.domain.linter import lint_story_pack
from rpg_backend.domain.story_pack_normalizer import try_normalize_story_pack_payload
from rpg_backend.generator.author_workflow_assembler import assemble_beat, assemble_story_pack
from rpg_backend.generator.author_workflow_chains import BeatGenerationChain, StoryOverviewChain
from rpg_backend.generator.author_workflow_planner import (
    check_beat_blueprints,
    plan_beat_blueprints_from_overview,
)
from rpg_backend.generator.author_workflow_policy import AuthorWorkflowPolicy
from rpg_backend.generator.author_workflow_validators import (
    check_story_overview,
    lint_beat_draft,
)

DEFAULT_AUTHOR_NODE_TIMEOUT_SECONDS = 40.0


def _build_chain(factory: Callable[..., Any], *, policy: AuthorWorkflowPolicy) -> Any:
    signature = inspect.signature(factory)
    if "policy" in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
    ):
        return factory(policy=policy)
    return factory()


def _accepts_kwarg(func: Callable[..., Any], name: str) -> bool:
    signature = inspect.signature(func)
    if name in signature.parameters:
        return True
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
    )


def build_workflow_node_timeout_seconds(
    *,
    overview_chain_factory: Callable[..., StoryOverviewChain],
    beat_chain_factory: Callable[..., BeatGenerationChain],
    policy: AuthorWorkflowPolicy,
) -> dict[str, float]:
    if policy.timeout_seconds is not None:
        fixed_timeout_seconds = float(policy.timeout_seconds)
        return {node_name: fixed_timeout_seconds for node_name in AuthorWorkflowNode}

    overview_chain = _build_chain(overview_chain_factory, policy=policy)
    beat_chain = _build_chain(beat_chain_factory, policy=policy)
    timeout_seconds = {node_name: DEFAULT_AUTHOR_NODE_TIMEOUT_SECONDS for node_name in AuthorWorkflowNode}
    timeout_seconds[AuthorWorkflowNode.GENERATE_STORY_OVERVIEW] = float(
        getattr(overview_chain, "workflow_timeout_seconds", DEFAULT_AUTHOR_NODE_TIMEOUT_SECONDS)
    )
    timeout_seconds[AuthorWorkflowNode.PLAN_BEAT_SCENES] = float(
        getattr(beat_chain, "scene_plan_timeout_seconds", DEFAULT_AUTHOR_NODE_TIMEOUT_SECONDS)
    )
    timeout_seconds[AuthorWorkflowNode.GENERATE_SCENE] = float(
        getattr(beat_chain, "scene_generation_timeout_seconds", DEFAULT_AUTHOR_NODE_TIMEOUT_SECONDS)
    )
    return timeout_seconds


def build_workflow_nodes(
    *,
    overview_chain_factory: Callable[..., StoryOverviewChain],
    beat_chain_factory: Callable[..., BeatGenerationChain],
    policy: AuthorWorkflowPolicy,
    beat_context_builder: Callable[..., BeatGenerationContext] = build_beat_generation_context,
) -> dict[str, AuthorWorkflowNodeHandler]:
    async def generate_story_overview(state: AuthorWorkflowState) -> dict[str, Any]:
        overview_phase = get_overview_phase(state)
        raw_brief = state["raw_brief"]
        if overview_phase.errors:
            raw_brief = f"{raw_brief}\n\nPrevious feedback to fix:\n- " + "\n- ".join(overview_phase.errors)
        chain = _build_chain(overview_chain_factory, policy=policy)
        timeout_seconds = float(getattr(chain, "workflow_timeout_seconds", DEFAULT_AUTHOR_NODE_TIMEOUT_SECONDS))
        overview_kwargs: dict[str, Any] = {
            "raw_brief": raw_brief,
            "timeout_seconds": timeout_seconds,
        }
        if _accepts_kwarg(chain.compile, "run_id"):
            overview_kwargs["run_id"] = state["run_id"]
        overview = await chain.compile(**overview_kwargs)
        overview_errors = check_story_overview(overview)
        return build_overview_generation_update(
            overview=overview,
            overview_errors=overview_errors,
            prior_attempts=overview_phase.attempts,
        )

    def plan_beats(state: AuthorWorkflowState) -> dict[str, Any]:
        blueprints = plan_beat_blueprints_from_overview(state["overview"])
        beat_plan_errors = check_beat_blueprints(blueprints)
        update = build_beat_plan_update(
            beat_blueprints=blueprints,
            beat_plan_errors=beat_plan_errors,
            prior_attempts=int(state.get("beat_plan_attempts", 0)),
        )
        if beat_plan_errors:
            return update
        update.update(build_beat_phase_seed_update())
        return update

    async def plan_beat_scenes(state: AuthorWorkflowState) -> dict[str, Any]:
        beat_phase = get_beat_phase(state)
        beat_index = beat_phase.index
        beat_blueprints = list(state.get("beat_blueprints") or [])
        if beat_index >= len(beat_blueprints):
            return {"beat_generation_errors": ["current beat index is outside beat_blueprints"]}
        context = beat_context_builder(
            overview=state["overview"],
            prior_beats=beat_phase.drafts,
        )
        chain = _build_chain(beat_chain_factory, policy=policy)
        timeout_seconds = float(
            getattr(chain, "scene_plan_timeout_seconds", DEFAULT_AUTHOR_NODE_TIMEOUT_SECONDS)
        )
        beat_kwargs: dict[str, Any] = {
            "story_id": state["story_id"],
            "overview_context": context.overview_context,
            "blueprint": beat_blueprints[beat_index].model_dump(mode="json"),
            "last_accepted_beat": context.last_accepted_beat,
            "prefix_summary": context.prefix_summary,
            "author_memory": context.author_memory,
            "lint_feedback": list(state.get("beat_lint_errors") or []),
            "timeout_seconds": timeout_seconds,
        }
        if _accepts_kwarg(chain.compile_beat_scene_plan, "run_id"):
            beat_kwargs["run_id"] = state["run_id"]
        scene_plan = await chain.compile_beat_scene_plan(**beat_kwargs)
        return build_beat_scene_plan_update(
            overview_context=context.overview_context,
            scene_plan=scene_plan,
            prefix_summary=context.prefix_summary,
            author_memory=context.author_memory,
            prior_attempts=beat_phase.attempts,
            current_beat_index=beat_index,
        )

    async def generate_scene(state: AuthorWorkflowState) -> dict[str, Any]:
        beat_phase = get_beat_phase(state)
        beat_index = beat_phase.index
        beat_blueprints = list(state.get("beat_blueprints") or [])
        if beat_index >= len(beat_blueprints):
            return {"beat_generation_errors": ["current beat index is outside beat_blueprints"]}
        scene_plan = beat_phase.scene_plan
        if scene_plan is None:
            return {"beat_generation_errors": ["current beat scene plan missing"]}
        if beat_phase.scene_index >= len(scene_plan.scenes):
            return {"beat_generation_errors": []}
        overview_context = state.get("beat_overview_context")
        if overview_context is None:
            return {"beat_generation_errors": ["beat overview context missing before scene generation"]}
        scene_context = build_scene_generation_context(
            scene_plan=scene_plan,
            scene_index=beat_phase.scene_index,
            generated_scenes=beat_phase.generated_scenes,
        )

        chain = _build_chain(beat_chain_factory, policy=policy)
        timeout_seconds = float(
            getattr(chain, "scene_generation_timeout_seconds", DEFAULT_AUTHOR_NODE_TIMEOUT_SECONDS)
        )
        scene_kwargs: dict[str, Any] = {
            "story_id": state["story_id"],
            "overview_context": overview_context,
            "blueprint": beat_blueprints[beat_index].model_dump(mode="json"),
            "scene_plan_item": scene_context.scene_plan_item,
            "scene_count": len(scene_plan.scenes),
            "scene_index": beat_phase.scene_index,
            "prior_generated_scenes": scene_context.prior_scene_memory,
            "prefix_summary": state["prefix_summary"],
            "author_memory": state.get("author_memory"),
            "lint_feedback": list(state.get("beat_lint_errors") or []),
            "timeout_seconds": timeout_seconds,
        }
        if _accepts_kwarg(chain.compile_scene, "run_id"):
            scene_kwargs["run_id"] = state["run_id"]
        generated_scene = await chain.compile_scene(**scene_kwargs)
        return build_scene_generation_update(
            current_beat_index=beat_index,
            scene_index=beat_phase.scene_index + 1,
            generated_scenes=[*beat_phase.generated_scenes, generated_scene],
        )

    def assemble_beat_node(state: AuthorWorkflowState) -> dict[str, Any]:
        beat_phase = get_beat_phase(state)
        beat_index = beat_phase.index
        beat_blueprints = list(state.get("beat_blueprints") or [])
        if beat_index >= len(beat_blueprints):
            return {"beat_generation_errors": ["current beat index is outside beat_blueprints"]}
        scene_plan = beat_phase.scene_plan
        if scene_plan is None:
            return {"beat_generation_errors": ["current beat scene plan missing before assembly"]}
        try:
            draft = assemble_beat(
                blueprint=beat_blueprints[beat_index],
                scene_plan=scene_plan,
                generated_scenes=beat_phase.generated_scenes,
            )
        except Exception as exc:  # noqa: BLE001
            return {"beat_generation_errors": [str(exc)]}
        return build_beat_assembly_update(current_beat_index=beat_index, draft=draft)

    def beat_lint(state: AuthorWorkflowState) -> dict[str, Any]:
        beat_phase = get_beat_phase(state)
        beat_index = beat_phase.index
        draft = state.get("current_beat_draft")
        if draft is None:
            return {"beat_lint_errors": ["current beat draft missing"], "beat_lint_warnings": []}
        report = lint_beat_draft(
            overview=state["overview"],
            blueprint=state["beat_blueprints"][beat_index],
            draft=draft,
            prior_beats=beat_phase.drafts,
        )
        update: dict[str, Any] = {
            "beat_lint_errors": list(report.errors),
            "beat_lint_warnings": list(report.warnings),
        }
        if report.ok:
            accepted = [*beat_phase.drafts, draft]
            accepted_context = beat_context_builder(
                overview=state["overview"],
                prior_beats=accepted,
            )
            update.update(
                build_accepted_beat_update(
                    accepted_drafts=accepted,
                    next_beat_index=beat_index + 1,
                    prefix_summary=accepted_context.prefix_summary,
                    author_memory=accepted_context.author_memory,
                )
            )
        return update

    def assemble_story_pack_node(state: AuthorWorkflowState) -> dict[str, Any]:
        pack = assemble_story_pack(
            story_id=state["story_id"],
            overview=state["overview"],
            beat_blueprints=list(state.get("beat_blueprints") or []),
            beat_drafts=list(state.get("beat_drafts") or []),
        )
        return {
            "story_pack": pack,
        }

    def normalize_story_pack(state: AuthorWorkflowState) -> dict[str, Any]:
        normalized_pack, normalization_errors = try_normalize_story_pack_payload(state["story_pack"])
        return {
            "story_pack": normalized_pack,
            "story_pack_normalization_errors": normalization_errors,
        }

    def final_lint(state: AuthorWorkflowState) -> dict[str, Any]:
        report = lint_story_pack(state["story_pack"])
        return {"final_lint_errors": list(report.errors), "final_lint_warnings": list(report.warnings)}

    def review_ready(_: AuthorWorkflowState) -> dict[str, Any]:
        return {"status": AuthorWorkflowStatus.REVIEW_READY}

    def workflow_failed(_: AuthorWorkflowState) -> dict[str, Any]:
        return {"status": AuthorWorkflowStatus.FAILED}

    return {
        AuthorWorkflowNode.GENERATE_STORY_OVERVIEW: generate_story_overview,
        AuthorWorkflowNode.PLAN_BEATS: plan_beats,
        AuthorWorkflowNode.PLAN_BEAT_SCENES: plan_beat_scenes,
        AuthorWorkflowNode.GENERATE_SCENE: generate_scene,
        AuthorWorkflowNode.ASSEMBLE_BEAT: assemble_beat_node,
        AuthorWorkflowNode.BEAT_LINT: beat_lint,
        AuthorWorkflowNode.ASSEMBLE_STORY_PACK: assemble_story_pack_node,
        AuthorWorkflowNode.NORMALIZE_STORY_PACK: normalize_story_pack,
        AuthorWorkflowNode.FINAL_LINT: final_lint,
        AuthorWorkflowNode.REVIEW_READY: review_ready,
        AuthorWorkflowNode.WORKFLOW_FAILED: workflow_failed,
    }

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from rpg_backend.config.settings import get_settings
from rpg_backend.domain.conflict_tags import NPC_CONFLICT_TAG_CATALOG
from rpg_backend.generator.author_workflow_models import BeatBlueprint, BeatDraft, BeatDraftLLM, BeatOverviewContext, BeatPrefixSummary, StoryOverview
from rpg_backend.domain.pack_schema import StoryPack
from rpg_backend.generator.outcome_materialization import PALETTE_IDS_BY_RESULT
from rpg_backend.generator.author_workflow_normalizer import normalize_beat_draft
from rpg_backend.generator.author_workflow_errors import PromptCompileError
from rpg_backend.llm.factory import resolve_openai_generator_model
from rpg_backend.llm.json_gateway import JsonGateway, JsonGatewayResult


class _JsonSchemaChain:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = resolve_openai_generator_model(
            settings.llm_openai_generator_model,
            settings.llm_openai_model,
        )
        self.timeout_seconds = settings.llm_openai_timeout_seconds
        self.temperature = settings.llm_openai_generator_temperature
        self.max_retries = settings.llm_openai_generator_max_retries
        self._json_gateway: JsonGateway | None = None

    def _get_json_gateway(self) -> JsonGateway:
        if self._json_gateway is None:
            self._json_gateway = JsonGateway(default_timeout_seconds=self.timeout_seconds)
        return self._json_gateway

    @staticmethod
    def _stringify_message_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "\n".join(part for part in parts if part)
        return str(content)

    async def _invoke_prompt_value(self, prompt_value: Any) -> JsonGatewayResult:
        messages = list(prompt_value.messages if hasattr(prompt_value, "messages") else prompt_value.to_messages())
        if len(messages) < 2:
            raise RuntimeError("langchain prompt did not produce system and user messages")
        return await self._get_json_gateway().call_json_object(
            system_prompt=self._stringify_message_content(messages[0].content),
            user_prompt=self._stringify_message_content(messages[1].content),
            model=self.model,
            temperature=self.temperature,
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds,
        )

    async def _invoke_chain(self, *, system_prompt: str, user_payload: dict[str, Any]) -> JsonGatewayResult:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnableLambda

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{user_prompt}"),
            ]
        )
        chain = prompt | RunnableLambda(self._invoke_prompt_value)
        return await chain.ainvoke(
            {
                "system_prompt": system_prompt,
                "user_prompt": json.dumps(user_payload, ensure_ascii=False, sort_keys=True),
            }
        )

    async def _run_structured_generation(
        self,
        *,
        output_model: type[BaseModel],
        system_prompt: str,
        user_payload: dict[str, Any],
        invalid_error_code: str,
        invalid_notes_prefix: str,
    ) -> BaseModel:
        if not self.model:
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=["openai generator config missing model"],
                notes=["check APP_LLM_OPENAI_GENERATOR_MODEL / APP_LLM_OPENAI_MODEL"],
            )
        try:
            result = await self._invoke_chain(system_prompt=system_prompt, user_payload=user_payload)
        except Exception as exc:  # noqa: BLE001
            raise PromptCompileError(
                error_code="prompt_compile_failed",
                errors=[str(exc)],
                notes=[f"{invalid_notes_prefix} gateway execution failed"],
            ) from exc
        try:
            return output_model.model_validate(result.payload)
        except ValidationError as exc:
            raise PromptCompileError(
                error_code=invalid_error_code,
                errors=[str(exc)],
                notes=[f"{invalid_notes_prefix} schema validation failed"],
            ) from exc

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


class StoryOverviewChain(_JsonSchemaChain):
    async def compile(self, *, raw_brief: str) -> StoryOverview:
        catalog_markdown = "\n".join(
            f"- `{key}`: {value}" for key, value in dict(NPC_CONFLICT_TAG_CATALOG).items()
        )
        system_prompt = (
            "# Role & Intent\n"
            "You transform a raw author brief into one strict StoryOverview JSON object.\n"
            "Do NOT output any text outside JSON.\n\n"
            "# Hard Constraints\n"
            "- target_minutes must be between 8 and 12 inclusive.\n"
            "- npc_count must be between 3 and 5 inclusive.\n"
            "- npc_roster length must equal npc_count.\n"
            "- ending_shape must be one of triumph, pyrrhic, uncertain, sacrifice.\n"
            "- move_bias values must come from the provided enum.\n"
            "- npc conflict tags must come from the provided enum.\n\n"
            "# NPC Conflict Tags\n"
            f"{catalog_markdown}\n"
        )
        return await self._run_structured_generation(
            output_model=StoryOverview,
            system_prompt=system_prompt,
            user_payload={
                "task": "compile_story_overview",
                "raw_brief": raw_brief,
                "output_schema": StoryOverview.model_json_schema(),
            },
            invalid_error_code="overview_invalid",
            invalid_notes_prefix="story overview",
        )


class BeatGenerationChain(_JsonSchemaChain):
    def __init__(self) -> None:
        super().__init__()
        self.last_beat_draft_llm: BeatDraftLLM | None = None

    async def compile(
        self,
        *,
        story_id: str,
        overview_context: BeatOverviewContext,
        blueprint: dict[str, Any],
        last_accepted_beat: dict[str, Any] | None,
        prefix_summary: BeatPrefixSummary,
        lint_feedback: list[str] | None = None,
    ) -> BeatDraft:
        palette_constraints = "\n".join(
            [
                "Allowed palette_id values:",
                f"- success: {', '.join(PALETTE_IDS_BY_RESULT['success'])}",
                f"- partial: {', '.join(PALETTE_IDS_BY_RESULT['partial'])}",
                f"- fail_forward: {', '.join(PALETTE_IDS_BY_RESULT['fail_forward'])}",
            ]
        )
        system_prompt = (
            "# Role & Intent\n"
            "Generate one strict BeatDraftLLM JSON object for the current beat blueprint.\n"
            "Read the projected overview, the current beat blueprint, the last accepted beat if present, and the structured prefix summary.\n"
            "The new beat must continue those exact details; do not contradict prior beats.\n"
            "Do NOT output any text outside JSON.\n\n"
            "# Hard Constraints\n"
            "- Do NOT output beat_id, title, objective, conflict, required_event, entry_scene_id, or any IDs.\n"
            "- Do NOT output always_available_moves; the backend injects global moves automatically.\n"
            "- Each scene must reference local moves only via enabled_move_indexes.\n"
            "- next_scene_index must be a 0-based index into the scenes list when present.\n"
            "- every move must contain success and fail_forward outcomes.\n"
            "- every outcome must provide a palette_id matching its result.\n"
            "- every non-global scene move set must cover the 3 strategy styles.\n"
            f"{palette_constraints}\n"
        )
        base_payload = {
            "task": "generate_beat_draft",
            "story_id": story_id,
            "overview_context": overview_context.model_dump(mode="json"),
            "blueprint": blueprint,
            "last_accepted_beat": last_accepted_beat,
            "prefix_summary": prefix_summary.model_dump(mode="json"),
            "lint_feedback": list(lint_feedback or []),
            "output_schema": BeatDraftLLM.model_json_schema(),
        }
        feedback: list[str] = []
        last_error: Exception | None = None
        for attempt in range(2):
            payload = dict(base_payload)
            payload["validation_feedback"] = list(feedback)
            if feedback:
                payload["retry_instruction"] = (
                    "Previous beat draft failed validation. Regenerate the full BeatDraftLLM JSON and fix every listed issue."
                )
            try:
                result = await self._invoke_chain(system_prompt=system_prompt, user_payload=payload)
            except Exception as exc:  # noqa: BLE001
                raise PromptCompileError(
                    error_code="prompt_compile_failed",
                    errors=[str(exc)],
                    notes=["beat draft gateway execution failed"],
                ) from exc
            try:
                llm_draft = BeatDraftLLM.model_validate(result.payload)
                self.last_beat_draft_llm = llm_draft
                return normalize_beat_draft(
                    blueprint=blueprint if isinstance(blueprint, BeatBlueprint) else BeatBlueprint.model_validate(blueprint),
                    llm_draft=llm_draft,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                feedback = self._build_validation_feedback(exc)
        raise PromptCompileError(
            error_code="beat_invalid",
            errors=feedback or ([str(last_error)] if last_error is not None else ["beat generation failed"]),
            notes=["beat draft generation failed after schema feedback retry"],
        )


class PackRepairChain(_JsonSchemaChain):
    async def compile(
        self,
        *,
        story_pack: dict[str, Any],
        lint_errors: list[str],
        lint_warnings: list[str],
        repair_count: int,
    ) -> StoryPack:
        system_prompt = (
            "# Role & Intent\n"
            "Repair the provided StoryPack JSON so it passes the final deterministic linter.\n"
            "Fix every lint error while preserving the story's overall intent.\n"
            "Do NOT output any text outside JSON.\n"
        )
        return await self._run_structured_generation(
            output_model=StoryPack,
            system_prompt=system_prompt,
            user_payload={
                "task": "repair_story_pack",
                "repair_count": repair_count,
                "story_pack": story_pack,
                "lint_errors": list(lint_errors),
                "lint_warnings": list(lint_warnings),
                "output_schema": StoryPack.model_json_schema(),
            },
            invalid_error_code="repair_invalid",
            invalid_notes_prefix="pack repair",
        )

from __future__ import annotations

from dataclasses import dataclass
import re

from pydantic import ValidationError

from rpg_backend.author.normalize import trim_ellipsis
from rpg_backend.play.contracts import PlayPlan, PlayResolutionEffect, PlaySuggestedAction
from rpg_backend.play.gateway import PlayGatewayError, PlayLLMGateway
from rpg_backend.play.runtime import (
    PlaySessionState,
    build_session_snapshot,
    build_suggested_actions,
    deterministic_narration,
)


_PROTAGONIST_ALIAS_STOPWORDS = {
    "the",
    "high",
    "steward",
    "councilor",
    "councillor",
    "archivist",
    "harbor",
    "inspector",
    "bridge",
    "engineer",
    "ombudsman",
    "envoy",
    "captain",
    "warden",
}

_PROTAGONIST_HONORIFIC_TOKENS = {
    "captain",
    "chancellor",
    "councilor",
    "councillor",
    "doctor",
    "dr",
    "inspector",
    "keeper",
    "lord",
    "lady",
    "mayor",
}


@dataclass(frozen=True)
class RenderTurnResult:
    narration: str
    suggestions: list[PlaySuggestedAction]
    source: str
    attempts: int = 0
    failure_reason: str | None = None
    response_id: str | None = None
    usage: dict[str, int | str] | None = None


def _invoke_render_json(
    gateway: PlayLLMGateway,
    *,
    system_prompt: str,
    user_payload: dict[str, object],
    max_output_tokens: int | None,
    previous_response_id: str | None,
    operation_name: str,
):
    try:
        return gateway._invoke_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
            operation_name=operation_name,
            plaintext_fallback_key="narration",
        )
    except TypeError:
        return gateway._invoke_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
            operation_name=operation_name,
        )


def _narration_from_response_payload(payload: object) -> str:
    if isinstance(payload, dict):
        return str(payload.get("narration") or "")
    if isinstance(payload, str):
        return payload
    return ""


def _render_output_budget(
    *,
    gateway: PlayLLMGateway,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> int | None:
    budget = gateway.max_output_tokens_render
    if state.status != "active" or resolution.ending_id is not None:
        cap = 220
    elif resolution.execution_frame in {"public", "coercive"} or len(state.last_turn_consequences) >= 3:
        cap = 220
    else:
        cap = 180
    if budget is None:
        return cap
    return min(int(budget), cap)


def _render_repair_output_budget(
    *,
    gateway: PlayLLMGateway,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> int | None:
    budget = gateway.max_output_tokens_render_repair
    if state.status != "active" or resolution.ending_id is not None:
        cap = 240
    elif resolution.execution_frame in {"public", "coercive"} or len(state.last_turn_consequences) >= 3:
        cap = 240
    else:
        cap = 200
    if budget is None:
        return cap
    return min(int(budget), cap)


def _compact_consequence_lines(state: PlaySessionState) -> list[str]:
    return [trim_ellipsis(item, 96) for item in state.last_turn_consequences[:2] if item]


def _compact_resolution_payload(resolution: PlayResolutionEffect) -> dict[str, object]:
    return {
        "affordance_tag": resolution.affordance_tag,
        "risk_level": resolution.risk_level,
        "execution_frame": resolution.execution_frame,
        "tactic_summary": trim_ellipsis(resolution.tactic_summary, 120),
        "axis_changes": {key: value for key, value in resolution.axis_changes.items() if value},
        "stance_changes": {key: value for key, value in resolution.stance_changes.items() if value},
        "flag_changes": {key: value for key, value in resolution.flag_changes.items() if value},
        "revealed_truth_ids": list(resolution.revealed_truth_ids[:2]),
        "added_event_ids": list(resolution.added_event_ids[:2]),
        "beat_completed": resolution.beat_completed,
        "advanced_to_next_beat": resolution.advanced_to_next_beat,
        "ending_id": resolution.ending_id,
        "pressure_note": trim_ellipsis(resolution.pressure_note, 96),
    }


def _build_render_payload(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_prompt: str | None,
) -> dict[str, object]:
    beat = plan.beats[state.beat_index]
    payload: dict[str, object] = {
        "story_title": trim_ellipsis(plan.story_title, 80),
        "tone": trim_ellipsis(plan.tone, 80),
        "runtime_policy_profile": plan.runtime_policy_profile,
        "current_beat": {
            "title": trim_ellipsis(beat.title, 64),
            "goal": trim_ellipsis(beat.goal, 96),
        },
        "player_input": trim_ellipsis(input_text, 360),
        "selected_suggestion_prompt": trim_ellipsis(selected_prompt, 180) if selected_prompt else None,
        "resolution": _compact_resolution_payload(resolution),
        "last_turn_consequences": _compact_consequence_lines(state),
        "target_npcs": _render_target_summary(plan, resolution),
        "state_bars": _render_state_bar_summary(plan, state)[:4],
        "session_status": state.status,
    }
    return payload

def _render_state_bar_summary(plan: PlayPlan, state: PlaySessionState) -> list[dict[str, int | str]]:
    summary = []
    for bar in build_session_snapshot(plan, state).state_bars:
        if bar.category == "axis" and bar.current_value != 0:
            summary.append({"label": bar.label, "value": bar.current_value})
        elif bar.category == "stance" and abs(bar.current_value) >= 1:
            summary.append({"label": bar.label, "value": bar.current_value})
    return summary[:6]


def _render_target_summary(plan: PlayPlan, resolution: PlayResolutionEffect) -> list[str]:
    if not resolution.target_npc_ids:
        return []
    return [
        npc.name
        for npc in plan.cast
        if npc.npc_id in resolution.target_npc_ids and npc.npc_id != plan.protagonist_npc_id
    ][:3]


def _protagonist_aliases(plan: PlayPlan) -> list[str]:
    protagonist_name = (plan.protagonist_name or "").strip()
    if not protagonist_name:
        aliases: list[str] = []
    else:
        aliases = [protagonist_name]
    name_tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", protagonist_name)
    if len(name_tokens) >= 2:
        aliases.append(" ".join(name_tokens[-2:]))
    if len(name_tokens) >= 3:
        aliases.append(" ".join(name_tokens[1:]))
    surname = name_tokens[-1] if name_tokens else ""
    if surname:
        aliases.append(surname)
    if len(name_tokens) >= 3 and name_tokens[0].casefold().rstrip(".") in _PROTAGONIST_HONORIFIC_TOKENS:
        aliases.append(f"{name_tokens[0]} {surname}")
    title = (plan.protagonist.title or "").strip()
    other_name_tokens = {
        token.casefold()
        for npc in plan.cast
        if npc.npc_id != plan.protagonist_npc_id
        for token in re.findall(r"[A-Za-z][A-Za-z'-]+", npc.name)
    }
    title_phrase = f"the {title.lower()}" if title else ""
    title_in_other_roles = any(
        title
        and npc.npc_id != plan.protagonist_npc_id
        and title.casefold() in (npc.role or "").casefold()
        for npc in plan.cast
    )
    if title_phrase and not title_in_other_roles:
        aliases.append(title_phrase)
    if title and surname and title.casefold() not in _PROTAGONIST_ALIAS_STOPWORDS:
        aliases.append(f"{title} {surname}")
    for token in name_tokens:
        lowered = token.casefold()
        if len(token) < 4 or lowered in _PROTAGONIST_ALIAS_STOPWORDS:
            continue
        if lowered in other_name_tokens and token != surname:
            continue
        aliases.append(token)
    seen: set[str] = set()
    ordered: list[str] = []
    for alias in sorted(aliases, key=len, reverse=True):
        lowered = alias.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(alias)
    return ordered


def _text_mentions_protagonist(plan: PlayPlan, text: str) -> bool:
    if not text.strip():
        return False
    for alias in _protagonist_aliases(plan):
        if re.search(rf"\b{re.escape(alias)}(?:'s)?\b", text, flags=re.IGNORECASE):
            return True
    return False


def _sanitize_narration(plan: PlayPlan, narration: str) -> str:
    text = trim_ellipsis(narration, 4000)
    aliases = _protagonist_aliases(plan)
    if aliases:
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        sentence_pattern = re.compile(
            rf"([^.!?]*\b(?:{alias_pattern})(?:'s)?\b[^.!?]*[.!?]?)",
            flags=re.IGNORECASE,
        )

        def _rewrite_sentence(match: re.Match[str]) -> str:
            updated = match.group(0)
            for alias in aliases:
                updated = re.sub(rf"\b{re.escape(alias)}'s\b", "your", updated, flags=re.IGNORECASE)
                updated = re.sub(rf"\b{re.escape(alias)}\b", "you", updated, flags=re.IGNORECASE)
            updated = re.sub(
                r"\b(?:his|her)\s+(voice|hand|hands|gaze|eyes|mouth|jaw|face|shoulder|shoulders)\b",
                r"your \1",
                updated,
                flags=re.IGNORECASE,
            )
            verb_map = {
                "is": "are",
                "was": "were",
                "has": "have",
                "does": "do",
                "steps": "step",
                "turns": "turn",
                "moves": "move",
                "forces": "force",
                "orders": "order",
                "brings": "bring",
                "takes": "take",
                "holds": "hold",
                "keeps": "keep",
                "speaks": "speak",
                "asks": "ask",
                "tries": "try",
                "works": "work",
                "leans": "lean",
                "watches": "watch",
                "stands": "stand",
                "stares": "stare",
                "knows": "know",
                "realizes": "realize",
                "narrows": "narrow",
                "seethes": "seethe",
                "glances": "glance",
            }
            for singular, base in verb_map.items():
                updated = re.sub(rf"\byou\s+{singular}\b", f"you {base}", updated, flags=re.IGNORECASE)
            updated = re.sub(r"\b(?:the|a|an)\s+you\b", "you", updated, flags=re.IGNORECASE)
            updated = re.sub(
                r"\b(?:councilor|councillor|high steward|steward|captain|warden)\s+you\b",
                "you",
                updated,
                flags=re.IGNORECASE,
            )
            return updated

        text = sentence_pattern.sub(_rewrite_sentence, text)
    text = re.sub(r"\byou's\b", "your", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(^|[.!?]\s+)(you|your)\b",
        lambda match: f"{match.group(1)}{match.group(2).capitalize()}",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _has_protagonist_grammar_issue(narration: str) -> bool:
    lowered = narration.casefold()
    grammar_patterns = (
        r"\byou\s+(?:is|was|has|does|steps|turns|moves|forces|orders|brings|takes|holds|keeps|speaks|asks|tries|works|leans|watches|stands|stares|knows|realizes|narrows|seethes|glances)\b",
        r"\byou\b[^.!?]{0,40}\b(?:his|her)\s+(?:voice|hand|hands|gaze|eyes|mouth|jaw|face|shoulder|shoulders)\b",
        r"\byour\s+(?:voice|hand|hands|gaze|eyes|mouth|jaw|face|shoulder|shoulders)\b[^.!?]{0,60}\b(?:as|while)\s+(?:he|she|they)\s+\w+\b",
    )
    return any(re.search(pattern, lowered) for pattern in grammar_patterns)


def _suggestions_target_protagonist(plan: PlayPlan, suggestions: list[PlaySuggestedAction]) -> bool:
    for item in suggestions:
        if _text_mentions_protagonist(plan, f"{item.label} {item.prompt}"):
            return True
    return False


def _sanitize_suggestions_or_fallback(
    plan: PlayPlan,
    state: PlaySessionState,
    suggestions: list[PlaySuggestedAction],
) -> list[PlaySuggestedAction]:
    if state.status != "active":
        return []
    if _suggestions_target_protagonist(plan, suggestions):
        return build_suggested_actions(plan, state)
    labels = [item.label.casefold().strip() for item in suggestions]
    prompts = [item.prompt.casefold().strip() for item in suggestions]
    if len(set(labels)) != len(labels) or len(set(prompts)) != len(prompts):
        return build_suggested_actions(plan, state)
    return suggestions


def deterministic_render(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
) -> RenderTurnResult:
    narration = _sanitize_narration(
        plan,
        deterministic_narration(plan=plan, state=state, resolution=resolution),
    )
    suggestions = [] if state.status != "active" else build_suggested_actions(plan, state)
    return RenderTurnResult(
        narration=narration,
        suggestions=suggestions,
        source="fallback",
        attempts=0,
    )


def render_quality_reason(
    narration: str,
    suggestions: list[PlaySuggestedAction],
) -> str | None:
    normalized = narration.casefold()
    if " you " not in f" {normalized} " and not normalized.startswith("you "):
        return "missing_second_person"
    if narration.startswith("You act through"):
        return "deterministic_fallback_style"
    if len(narration.strip()) < 100:
        return "narration_too_short"
    labels = [item.label.casefold().strip() for item in suggestions]
    prompts = [item.prompt.casefold().strip() for item in suggestions]
    if len(set(labels)) != len(labels) or len(set(prompts)) != len(prompts):
        return "duplicate_suggestions"
    return None


def _state_payoff_terms(plan: PlayPlan, state: PlaySessionState, resolution: PlayResolutionEffect) -> set[str]:
    terms: set[str] = set()
    if resolution.affordance_tag == "reveal_truth":
        terms.update({"truth", "fact", "evidence", "proof", "ledger", "record", "open"})
    elif resolution.affordance_tag == "secure_resources":
        terms.update({"supply", "grain", "shipment", "ration", "dock", "harbor", "bridge"})
    elif resolution.affordance_tag in {"build_trust", "unlock_ally"}:
        terms.update({"ally", "coalition", "trust", "agreement", "backs"})
    elif resolution.affordance_tag == "shift_public_narrative":
        terms.update({"public", "speech", "mandate", "authority", "story"})
    for axis_id, delta in resolution.axis_changes.items():
        if delta == 0:
            continue
        axis = next((item for item in plan.axes if item.axis_id == axis_id), None)
        if axis is not None:
            for token in re.findall(r"[a-z]{4,}", axis.label.casefold()):
                terms.add(token)
        if axis_id == "public_panic":
            terms.update({"public", "panic", "crowd", "street"})
        elif axis_id == "political_leverage":
            terms.update({"vote", "mandate", "authority", "council", "leverage"})
        elif axis_id == "system_integrity":
            terms.update({"record", "archive", "seal", "procedure", "charter"})
        elif axis_id == "resource_strain":
            terms.update({"grain", "supply", "shipment", "ration", "dock", "bridge", "harbor"})
        elif axis_id == "exposure_risk":
            terms.update({"evidence", "proof", "ledger", "witness", "exposed"})
    if any(delta != 0 for delta in resolution.stance_changes.values()):
        terms.update({"ally", "coalition", "trust", "backs", "turns"})
    for consequence in state.last_turn_consequences:
        for token in re.findall(r"[a-z]{5,}", consequence.casefold()):
            terms.add(token)
    for npc in plan.cast:
        if npc.npc_id not in resolution.target_npc_ids:
            continue
        for token in re.findall(r"[a-z]{3,}", npc.name.casefold()):
            terms.add(token)
    return terms


def state_payoff_quality_reason(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    narration: str,
) -> str | None:
    if not (resolution.axis_changes or resolution.stance_changes or state.last_turn_consequences):
        return None
    lowered = narration.casefold()
    payoff_terms = _state_payoff_terms(plan, state, resolution)
    if payoff_terms and not any(term in lowered for term in payoff_terms):
        return "missing_state_payoff"
    generic_markers = (
        "the situation bends, but it does not stall",
        "you force the issue and raise the temperature",
        "the next pressure point comes into focus",
    )
    if any(marker in lowered for marker in generic_markers) and len(narration.strip()) < 180:
        return "generic_feedback_echo"
    return None


def _auto_repair_narration(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    narration: str,
    failure_reason: str,
) -> str | None:
    candidate = _sanitize_narration(plan, narration)
    if failure_reason in {"missing_second_person", "third_person_protagonist_grammar"}:
        lowered = candidate.casefold()
        if " you " not in f" {lowered} " and not lowered.startswith("you "):
            stitched = candidate[0].lower() + candidate[1:] if candidate else ""
            candidate = trim_ellipsis(f"You feel the room change as {stitched}", 4000)
            lowered = candidate.casefold()
        if " you " in f" {lowered} " or lowered.startswith("you "):
            return candidate
    if failure_reason in {"missing_state_payoff", "generic_feedback_echo"}:
        if state.last_turn_consequences:
            payoff_line = state.last_turn_consequences[0].rstrip(".")
            if payoff_line and payoff_line.casefold() not in candidate.casefold():
                candidate = trim_ellipsis(f"{candidate.rstrip('.')} {payoff_line}.", 4000)
        if state_payoff_quality_reason(
            plan=plan,
            state=state,
            resolution=resolution,
            narration=candidate,
        ) is None:
            return candidate
    return None


def repair_render_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: PlayLLMGateway,
    previous_response_id: str | None,
    failure_reason: str,
    draft_narration: str | None,
    draft_suggestions: list[PlaySuggestedAction] | None,
) -> RenderTurnResult | None:
    payload = {
        "failure_reason": failure_reason,
        **_build_render_payload(
            plan=plan,
            state=state,
            resolution=resolution,
            input_text=input_text,
            selected_prompt=selected_action.prompt if selected_action is not None else None,
        ),
        "draft_narration": draft_narration,
        "draft_suggestions": [item.model_dump(mode="json") for item in (draft_suggestions or [])],
    }
    system_prompt = (
        "Repair a failed turn render for a second-person GM story game. "
        "Return strict JSON with one key: narration. "
        "Narration must be vivid, second person, 2-4 sentences, and explicitly realize one or two concrete state consequences from the move. "
        "Never refer to the protagonist by proper name or third-person pronouns. "
        "Do not return suggested actions."
    )
    try:
        response = _invoke_render_json(
            gateway,
            system_prompt=system_prompt,
            user_payload=payload,
            max_output_tokens=_render_repair_output_budget(
                gateway=gateway,
                state=state,
                resolution=resolution,
            ),
            previous_response_id=previous_response_id,
            operation_name="play_render_repair",
        )
        active_suggestions = [] if state.status != "active" else build_suggested_actions(plan, state)
        sanitized_narration = _sanitize_narration(plan, _narration_from_response_payload(response.payload))
        quality_reason = None
        if _text_mentions_protagonist(plan, sanitized_narration):
            quality_reason = "named_protagonist_narration"
        elif _has_protagonist_grammar_issue(sanitized_narration):
            quality_reason = "third_person_protagonist_grammar"
        else:
            quality_reason = state_payoff_quality_reason(
                plan=plan,
                state=state,
                resolution=resolution,
                narration=sanitized_narration,
            )
        if quality_reason is None:
            quality_reason = render_quality_reason(sanitized_narration, active_suggestions)
        if quality_reason:
            auto_repaired = _auto_repair_narration(
                plan=plan,
                state=state,
                resolution=resolution,
                narration=sanitized_narration,
                failure_reason=quality_reason,
            )
            if auto_repaired is not None:
                return RenderTurnResult(
                    narration=auto_repaired,
                    suggestions=active_suggestions,
                    source="llm_repair",
                    attempts=2,
                    failure_reason=failure_reason,
                    response_id=response.response_id,
                    usage=response.usage,
                )
            return None
        return RenderTurnResult(
            narration=sanitized_narration,
            suggestions=active_suggestions,
            source="llm_repair",
            attempts=2,
            failure_reason=failure_reason,
            response_id=response.response_id,
            usage=response.usage,
        )
    except (PlayGatewayError, ValidationError):
        return None


def render_turn(
    *,
    plan: PlayPlan,
    state: PlaySessionState,
    resolution: PlayResolutionEffect,
    input_text: str,
    selected_action: PlaySuggestedAction | None,
    gateway: PlayLLMGateway | None,
    previous_response_id: str | None,
    enable_render_repair: bool,
) -> RenderTurnResult:
    if gateway is None:
        return deterministic_render(plan=plan, state=state, resolution=resolution)
    payload = _build_render_payload(
        plan=plan,
        state=state,
        resolution=resolution,
        input_text=input_text,
        selected_prompt=selected_action.prompt if selected_action is not None else None,
    )
    system_prompt = (
        "You are a second-person GM for a dramatic short-form story game. "
        "Return strict JSON with one key: narration. "
        "Use runtime_policy_profile to keep the narration and follow-up actions aligned with the actual crisis domain. "
        "narration should be vivid but concise, 2-4 sentences, second person, and must clearly realize one or two concrete consequences from last_turn_consequences or changed state bars. "
        "Never describe the protagonist by proper name or third-person pronouns; always use you/your for the player character. "
        "Do not return suggested actions."
    )
    try:
        response = _invoke_render_json(
            gateway,
            system_prompt=system_prompt,
            user_payload=payload,
            max_output_tokens=_render_output_budget(
                gateway=gateway,
                state=state,
                resolution=resolution,
            ),
            previous_response_id=previous_response_id,
            operation_name="play_render_turn",
        )
        narration = _sanitize_narration(plan, _narration_from_response_payload(response.payload))
        active_suggestions = [] if state.status != "active" else build_suggested_actions(plan, state)
        quality_reason = None
        if _text_mentions_protagonist(plan, narration):
            quality_reason = "named_protagonist_narration"
        elif _has_protagonist_grammar_issue(narration):
            quality_reason = "third_person_protagonist_grammar"
        else:
            quality_reason = state_payoff_quality_reason(
                plan=plan,
                state=state,
                resolution=resolution,
                narration=narration,
            )
        if quality_reason is None:
            quality_reason = render_quality_reason(narration, active_suggestions)
        if quality_reason:
            auto_repaired = _auto_repair_narration(
                plan=plan,
                state=state,
                resolution=resolution,
                narration=narration,
                failure_reason=quality_reason,
            )
            if auto_repaired is not None:
                return RenderTurnResult(
                    narration=auto_repaired,
                    suggestions=active_suggestions,
                    source="llm_repair",
                    attempts=1,
                    failure_reason=quality_reason,
                    response_id=response.response_id,
                    usage=response.usage,
                )
        if quality_reason and enable_render_repair:
            repaired = repair_render_turn(
                plan=plan,
                state=state,
                resolution=resolution,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=response.response_id or previous_response_id,
                failure_reason=quality_reason,
                draft_narration=narration,
                draft_suggestions=active_suggestions,
            )
            if repaired is not None:
                return repaired
        if quality_reason:
            fallback = deterministic_render(plan=plan, state=state, resolution=resolution)
            return RenderTurnResult(
                narration=fallback.narration,
                suggestions=fallback.suggestions,
                source="fallback",
                attempts=2 if enable_render_repair else 1,
                failure_reason=quality_reason,
            )
        return RenderTurnResult(
            narration=narration,
            suggestions=active_suggestions,
            source="llm",
            attempts=1,
            response_id=response.response_id,
            usage=response.usage,
        )
    except (PlayGatewayError, ValidationError) as exc:
        failure_reason = exc.code if isinstance(exc, PlayGatewayError) else "play_render_schema_invalid"
        if enable_render_repair and gateway is not None:
            repaired = repair_render_turn(
                plan=plan,
                state=state,
                resolution=resolution,
                input_text=input_text,
                selected_action=selected_action,
                gateway=gateway,
                previous_response_id=previous_response_id,
                failure_reason=failure_reason,
                draft_narration=None,
                draft_suggestions=None,
            )
            if repaired is not None:
                return repaired
        fallback = deterministic_render(plan=plan, state=state, resolution=resolution)
        return RenderTurnResult(
            narration=fallback.narration,
            suggestions=fallback.suggestions,
            source="fallback",
            attempts=2 if enable_render_repair else 1,
            failure_reason=failure_reason,
        )

from __future__ import annotations

from pathlib import Path
from typing import Literal

from rpg_backend.author.contracts import (
    AuthorCastPortraitPlanResponse,
    AuthorCastPortraitPlanRequest,
    AuthorCastPortraitSubject,
    AuthorCastPortraitTask,
    AuthorEditorCastEntry,
    AuthorEditorStateResponse,
)
from rpg_backend.config import Settings
from rpg_backend.portraits.prompting import (
    DEFAULT_IMAGE_API_BASE_URL,
    DEFAULT_IMAGE_MODEL,
    PortraitPromptSubject,
    build_asset_id,
    build_portrait_art_direction_payload,
    build_portrait_prompt,
    prompt_hash,
)
from rpg_backend.roster.service import get_character_roster_service

PortraitTaskSourceKind = Literal["roster", "author_cast"]


def _author_subject_id(job_id: str, npc_id: str) -> str:
    return f"author_{job_id}_{npc_id}"


def _author_relative_output_path(npc_id: str, variant_key: str, asset_id: str) -> str:
    return f"images/{npc_id}/{variant_key}/{asset_id}.png"


def _normalize_variants(request: AuthorCastPortraitPlanRequest) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for variant in request.variants:
        if variant in seen:
            continue
        seen.add(variant)
        ordered.append(variant)
    return tuple(ordered)


def _selected_cast_entries(
    editor_state: AuthorEditorStateResponse,
    request: AuthorCastPortraitPlanRequest,
) -> tuple[AuthorEditorCastEntry, ...]:
    if not request.npc_ids:
        return tuple(editor_state.cast_view)
    cast_by_id = {item.npc_id: item for item in editor_state.cast_view}
    selected: list[AuthorEditorCastEntry] = []
    missing: list[str] = []
    seen: set[str] = set()
    for npc_id in request.npc_ids:
        if npc_id in seen:
            continue
        seen.add(npc_id)
        member = cast_by_id.get(npc_id)
        if member is None:
            missing.append(npc_id)
            continue
        selected.append(member)
    if missing:
        raise ValueError(",".join(missing))
    return tuple(selected)


def _build_subject_profile(
    *,
    job_id: str,
    editor_state: AuthorEditorStateResponse,
    member: AuthorEditorCastEntry,
) -> tuple[PortraitTaskSourceKind, PortraitPromptSubject, AuthorCastPortraitSubject]:
    roster_entry = None
    if member.roster_character_id:
        roster_service = get_character_roster_service()
        roster_entry = next((item for item in roster_service.catalog if item.character_id == member.roster_character_id), None)
    source_kind: PortraitTaskSourceKind = "roster" if member.roster_character_id else "author_cast"
    character_id = member.roster_character_id or _author_subject_id(job_id, member.npc_id)
    source_ref = member.roster_character_id or f"{job_id}:{member.npc_id}"
    subject = PortraitPromptSubject(
        character_id=character_id,
        name_primary=member.name,
        name_secondary=(
            (roster_entry.name_zh if editor_state.language == "en" else roster_entry.name_en)
            if roster_entry is not None
            else None
        ),
        role=member.role,
        public_summary=member.roster_public_summary,
        agenda=member.agenda,
        red_line=member.red_line,
        pressure_signature=member.pressure_signature,
        story_title=editor_state.story_frame_view.title,
        story_premise=editor_state.story_frame_view.premise,
        story_tone=editor_state.story_frame_view.tone,
        story_style_guard=editor_state.story_frame_view.style_guard,
        world_rules=tuple(editor_state.story_frame_view.world_rules[:3]),
        thematic_pressure=((editor_state.summary.theme,) if editor_state.summary.theme else ()),
        setting_anchors=(editor_state.focused_brief.setting_signal,),
        tonal_field=(editor_state.story_frame_view.tone,),
        roster_anchor=roster_entry.role_hint_en if roster_entry is not None else None,
    )
    response_subject = AuthorCastPortraitSubject(
        character_id=character_id,
        source_kind=source_kind,
        source_ref=source_ref,
        npc_id=member.npc_id,
        roster_character_id=member.roster_character_id,
        name=member.name,
        secondary_name=subject.name_secondary,
        role=member.role,
        public_summary=member.roster_public_summary,
        agenda=member.agenda,
        red_line=member.red_line,
        pressure_signature=member.pressure_signature,
        story_title=editor_state.story_frame_view.title,
        story_premise=editor_state.story_frame_view.premise,
        story_tone=editor_state.story_frame_view.tone,
        story_style_guard=editor_state.story_frame_view.style_guard,
        world_rules=list(editor_state.story_frame_view.world_rules[:3]),
        visual_tags=[
            item
            for item in (
                editor_state.summary.theme,
                editor_state.focused_brief.setting_signal,
                editor_state.story_frame_view.tone,
                roster_entry.role_hint_en if roster_entry is not None else None,
            )
            if item
        ],
    )
    return source_kind, subject, response_subject


def build_author_cast_portrait_plan(
    *,
    job_id: str,
    editor_state: AuthorEditorStateResponse,
    request: AuthorCastPortraitPlanRequest,
    settings: Settings,
) -> AuthorCastPortraitPlanResponse:
    selected_cast = _selected_cast_entries(editor_state, request)
    variants = _normalize_variants(request)
    subjects: list[AuthorCastPortraitSubject] = []
    jobs: list[AuthorCastPortraitTask] = []
    batch_id = f"author_cast_{job_id}_{editor_state.revision.replace(':', '').replace('-', '')[:16]}"
    image_api_base_url = DEFAULT_IMAGE_API_BASE_URL
    image_model = DEFAULT_IMAGE_MODEL
    output_dir = str((Path(settings.local_author_portrait_dir).expanduser().resolve() / job_id).resolve())
    for member in selected_cast:
        source_kind, prompt_subject, response_subject = _build_subject_profile(
            job_id=job_id,
            editor_state=editor_state,
            member=member,
        )
        subjects.append(response_subject)
        for variant_key in variants:
            for candidate_index in range(1, request.candidates_per_variant + 1):
                prompt_text = build_portrait_prompt(
                    prompt_subject,
                    variant_key=variant_key,
                    prompt_version=request.prompt_version,
                )
                hashed = prompt_hash(prompt_text)
                asset_id = build_asset_id(
                    character_id=prompt_subject.character_id,
                    variant_key=variant_key,
                    candidate_index=candidate_index,
                    prompt_hash=hashed,
                )
                relative_output_path = _author_relative_output_path(member.npc_id, variant_key, asset_id)
                jobs.append(
                    AuthorCastPortraitTask(
                        asset_id=asset_id,
                        character_id=prompt_subject.character_id,
                        npc_id=member.npc_id,
                        variant_key=variant_key,
                        candidate_index=candidate_index,
                        prompt_text=prompt_text,
                        prompt_hash=hashed,
                        relative_output_path=relative_output_path,
                    )
                )
    return AuthorCastPortraitPlanResponse(
        job_id=job_id,
        revision=editor_state.revision,
        language=editor_state.language,
        batch_id=batch_id,
        prompt_version=request.prompt_version,
        image_model=image_model,
        image_api_base_url=image_api_base_url,
        output_dir=output_dir,
        art_direction=build_portrait_art_direction_payload(),
        subjects=subjects,
        jobs=jobs,
    )

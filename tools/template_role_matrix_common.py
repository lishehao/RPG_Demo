from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.content_language import prompt_role_instruction
from rpg_backend.llm_gateway import CapabilityGatewayCore, GatewayCapabilityError, TextCapabilityRequest

TemplateName = Literal[
    "blackout_referendum_story",
    "bridge_ration_story",
    "harbor_quarantine_story",
    "logistics_story",
    "warning_record_story",
    "archive_vote_story",
    "truth_record_story",
    "legitimacy_story",
    "public_order_story",
    "generic_civic_story",
]

RoleFunction = Literal["anchor", "guardian", "witness", "broker", "civic"]


class TemplateRoleDraftEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provisional_role: str = Field(min_length=1, max_length=80)
    name_en: str = Field(min_length=1, max_length=80)
    name_zh: str = Field(min_length=1, max_length=80)
    public_summary_en: str = Field(min_length=1, max_length=220)
    public_summary_zh: str = Field(min_length=1, max_length=220)
    role_hint_en: str = Field(min_length=1, max_length=120)
    role_hint_zh: str = Field(min_length=1, max_length=120)
    agenda_seed_en: str = Field(min_length=1, max_length=220)
    agenda_seed_zh: str = Field(min_length=1, max_length=220)
    red_line_seed_en: str = Field(min_length=1, max_length=220)
    red_line_seed_zh: str = Field(min_length=1, max_length=220)
    pressure_signature_seed_en: str = Field(min_length=1, max_length=220)
    pressure_signature_seed_zh: str = Field(min_length=1, max_length=220)
    visual_anchor: str = Field(min_length=1, max_length=160)
    silhouette_note: str = Field(min_length=1, max_length=160)
    avoid_overlap_with_other_two: str = Field(min_length=1, max_length=220)


class TemplateRoleDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_name: TemplateName
    roles: list[TemplateRoleDraftEntry] = Field(min_length=3, max_length=3)


@dataclass(frozen=True)
class TemplateRoleSlotSpec:
    slot_key: str
    function: RoleFunction
    role_focus: str
    pressure_mode: str
    visual_anchor: str
    silhouette_anchor: str
    avoid_overlap: str
    slot_tags: tuple[RoleFunction, ...]


@dataclass(frozen=True)
class TemplateRoleSpec:
    template_name: TemplateName
    cast_strategy: str
    beat_strategy: str
    primary_theme: str
    trio_relationship: str
    avoid_shapes: tuple[str, ...]
    visual_anchors: tuple[str, ...]
    theme_tags: tuple[str, ...]
    setting_tags: tuple[str, ...]
    tone_tags: tuple[str, ...]
    conflict_tags: tuple[str, ...]
    retrieval_terms: tuple[str, ...]
    slots: tuple[TemplateRoleSlotSpec, ...]


TEMPLATE_ROLE_CATALOG: tuple[TemplateRoleSpec, ...] = (
    TemplateRoleSpec(
        template_name="blackout_referendum_story",
        cast_strategy="blackout_referendum_cast",
        beat_strategy="blackout_referendum_compile",
        primary_theme="logistics_quarantine_crisis",
        trio_relationship="A procedural blackout vote needs one legitimacy guardian, one public witness of outage inequity, and one broker who profits from selective restoration.",
        avoid_shapes=("three interchangeable clerks", "three neutral committee members"),
        visual_anchors=("lampglass", "ward sashes", "portable grid maps"),
        theme_tags=("logistics_quarantine_crisis", "public_order_crisis", "legitimacy_crisis"),
        setting_tags=("blackout", "referendum", "council"),
        tone_tags=("tense", "procedural", "restrained"),
        conflict_tags=("public_order", "legitimacy", "public_record"),
        retrieval_terms=("blackout", "referendum", "ward", "grid", "ballot", "council"),
        slots=(
            TemplateRoleSlotSpec("tally_guardian", "guardian", "keep the vote count and procedural legitimacy intact", "procedural pressure", "seal ledger, tally table, ward lamp maps", "trim formal layers and registry tools", "Do not duplicate a crowd-facing witness or a profiteering broker.", ("guardian", "anchor")),
            TemplateRoleSlotSpec("public_outage_witness", "witness", "voice visible outage harm from the wards", "public emotion pressure", "petition slips, soot-stained coat, public queue tokens", "street-facing layered clothing and visible wear", "Do not sound like a clerk or a formal council officer.", ("witness", "civic")),
            TemplateRoleSlotSpec("grid_bargain_broker", "broker", "profit from selective restoration and negotiated access", "political leverage pressure", "restoration schedules, brass keys, compact folios", "sharper silhouette with controlled luxury details", "Do not overlap with either procedural guardian or public witness.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="bridge_ration_story",
        cast_strategy="bridge_ration_cast",
        beat_strategy="bridge_ration_compile",
        primary_theme="logistics_quarantine_crisis",
        trio_relationship="A stressed bridge-ration story needs one material constraint reader, one queue witness, and one toll/access dealmaker.",
        avoid_shapes=("three engineers", "three bridge bureaucrats"),
        visual_anchors=("bridge gauges", "ration queue markers", "toll ribbons"),
        theme_tags=("logistics_quarantine_crisis", "resource_allocation_crisis"),
        setting_tags=("bridge", "ration", "ward_line"),
        tone_tags=("tense", "procedural", "urgent"),
        conflict_tags=("resource", "public_order", "legitimacy"),
        retrieval_terms=("bridge", "ration", "queue", "toll", "ward", "crossing"),
        slots=(
            TemplateRoleSlotSpec("load_guardian", "guardian", "read true capacity and physical risk", "infrastructure pressure", "survey rods, load diagrams, flood markers", "structured outerwear with practical tools", "Do not collapse into crowd witness or silver-tongued toll broker.", ("guardian", "anchor")),
            TemplateRoleSlotSpec("queue_witness", "witness", "remember who waited and who was bypassed", "public emotion pressure", "number tokens, queue slips, worn satchel", "thinner public-facing silhouette with carried scraps", "Do not sound like an engineer or a trader.", ("witness", "civic")),
            TemplateRoleSlotSpec("toll_broker", "broker", "turn crossings into leverage and selective access", "political leverage pressure", "toll cords, ferry insignia, access seals", "lean broker silhouette with calculated polish", "Do not repeat the witness's moral framing or guardian's technical framing.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="harbor_quarantine_story",
        cast_strategy="harbor_quarantine_cast",
        beat_strategy="harbor_quarantine_compile",
        primary_theme="logistics_quarantine_crisis",
        trio_relationship="A harbor quarantine story needs one manifest/procedure guardian, one dockside social witness, and one credit-clearance broker.",
        avoid_shapes=("three manifest clerks", "three dock workers"),
        visual_anchors=("manifest boards", "crane hooks", "credit slips"),
        theme_tags=("logistics_quarantine_crisis", "public_order_crisis"),
        setting_tags=("harbor", "quarantine", "manifest"),
        tone_tags=("tense", "procedural", "forensic"),
        conflict_tags=("resource", "public_record", "containment"),
        retrieval_terms=("harbor", "manifest", "quarantine", "cargo", "dock", "clearance"),
        slots=(
            TemplateRoleSlotSpec("manifest_guardian", "guardian", "enforce documented quarantine legitimacy", "procedural pressure", "manifests, seals, cargo stamps", "upright ledger-driven silhouette", "Do not become a crowd witness or a money broker.", ("guardian", "witness")),
            TemplateRoleSlotSpec("dockside_witness", "witness", "make visible who pays the human cost", "public emotion pressure", "dock tags, rope burn gloves, crew insignia", "worker silhouette with practical wear and public trace", "Do not feel like an office clerk.", ("witness", "civic")),
            TemplateRoleSlotSpec("customs_broker", "broker", "translate blocked cargo into bargaining power", "political leverage pressure", "credit folios, customs wax, signet token", "measured luxury and mercantile detail", "Do not mirror the dockside witness's morality or the guardian's procedural rigidity.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="logistics_story",
        cast_strategy="logistics_cast",
        beat_strategy="single_semantic_compile",
        primary_theme="logistics_quarantine_crisis",
        trio_relationship="A general logistics template needs one route registrar, one relief mover, and one scarcity dealmaker.",
        avoid_shapes=("three transport admins", "three convoy operators"),
        visual_anchors=("route slips", "wagon tarp seals", "allotment maps"),
        theme_tags=("logistics_quarantine_crisis", "resource_allocation_crisis"),
        setting_tags=("convoy", "checkpoint", "supply_route"),
        tone_tags=("procedural", "tense"),
        conflict_tags=("resource", "public_record", "public_order"),
        retrieval_terms=("convoy", "route", "supply", "allotment", "checkpoint", "escort"),
        slots=(
            TemplateRoleSlotSpec("route_registrar", "guardian", "protect route legitimacy and documentation", "procedural pressure", "route slips, docket tubes, checkpoint seals", "registry-forward silhouette with carried case", "Do not duplicate the physical route captain or allotment broker.", ("guardian", "anchor")),
            TemplateRoleSlotSpec("relief_captain", "anchor", "keep goods physically moving to exposed people", "infrastructure pressure", "wagon tarp, escort flags, mud-stained coat", "mobile action silhouette with practical load-bearing gear", "Do not sound like a desk official or allocation theorist.", ("anchor", "civic")),
            TemplateRoleSlotSpec("allotment_factor", "broker", "shape who gets what and why", "political leverage pressure", "allocation boards, district maps, quota tabs", "clean calculating silhouette with map or folio presence", "Do not overlap with registrar proceduralism or captain material urgency.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="warning_record_story",
        cast_strategy="warning_record_cast",
        beat_strategy="warning_record_compile",
        primary_theme="truth_record_crisis",
        trio_relationship="A warning-record template needs one bulletin archivist, one bell/tower witness, and one shelter access negotiator.",
        avoid_shapes=("three forecasters", "three archivists"),
        visual_anchors=("warning bulletins", "bell ropes", "storm shelter badges"),
        theme_tags=("truth_record_crisis", "public_order_crisis"),
        setting_tags=("observatory", "bulletin", "storm_shelter"),
        tone_tags=("procedural", "somber", "tense"),
        conflict_tags=("public_record", "evidence", "public_order"),
        retrieval_terms=("warning", "bulletin", "bell", "storm", "shelter", "timestamp"),
        slots=(
            TemplateRoleSlotSpec("bulletin_guardian", "guardian", "protect original warning records", "procedural pressure", "bulletins, archive drawers, timestamp stamps", "archival silhouette with pinned papers", "Do not become a tower witness or access broker.", ("guardian", "anchor")),
            TemplateRoleSlotSpec("tower_witness", "witness", "remember when the city was warned", "public emotion pressure", "bell tower gear, stormcloak, signal notches", "vertical lookout silhouette with weather wear", "Do not sound like an archivist or negotiator.", ("witness", "civic")),
            TemplateRoleSlotSpec("shelter_negotiator", "broker", "profit from or control warning-response access", "political leverage pressure", "shelter ledgers, capacity bands, entry chits", "calm broker silhouette with controlled access items", "Do not duplicate either archive or tower framing.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="archive_vote_story",
        cast_strategy="archive_vote_cast",
        beat_strategy="archive_vote_compile",
        primary_theme="truth_record_crisis",
        trio_relationship="An archive-vote template needs one certifier, one gallery-facing witness, and one mandate broker orbiting the result.",
        avoid_shapes=("three record examiners", "three hearing witnesses"),
        visual_anchors=("certification seals", "gallery petitions", "mandate folios"),
        theme_tags=("truth_record_crisis", "legitimacy_crisis"),
        setting_tags=("archive", "vote_hall", "public_gallery"),
        tone_tags=("procedural", "tense", "forensic"),
        conflict_tags=("public_record", "legitimacy", "evidence"),
        retrieval_terms=("archive", "vote", "certification", "gallery", "mandate", "ledger"),
        slots=(
            TemplateRoleSlotSpec("vote_certifier", "guardian", "certify or block the archival vote", "procedural pressure", "seal press, tally ledger, custody ribbon", "formal certification silhouette", "Do not duplicate witness empathy or broker leverage language.", ("guardian", "anchor")),
            TemplateRoleSlotSpec("gallery_petitioner", "witness", "carry what the public saw and signed", "public emotion pressure", "petition slips, gallery tags, witness ribbons", "public-facing layered silhouette with carried documents", "Do not read like an archivist.", ("witness", "civic")),
            TemplateRoleSlotSpec("mandate_broker", "broker", "negotiate the political afterlife of the certified result", "political leverage pressure", "mandate folders, accord tabs, chamber token", "broker silhouette with ceremonial edge", "Do not mirror either certifier or gallery voice.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="truth_record_story",
        cast_strategy="truth_record_cast",
        beat_strategy="single_semantic_compile",
        primary_theme="truth_record_crisis",
        trio_relationship="A general truth-record template needs one custody-chain guardian, one transcript or testimony witness, and one timing/release intermediary.",
        avoid_shapes=("three archivists", "three witnesses"),
        visual_anchors=("chain seals", "transcript pages", "docket ribbons"),
        theme_tags=("truth_record_crisis",),
        setting_tags=("archive", "record_office", "hearing"),
        tone_tags=("forensic", "procedural", "tense"),
        conflict_tags=("public_record", "evidence", "legitimacy"),
        retrieval_terms=("truth", "record", "custody", "transcript", "docket", "evidence"),
        slots=(
            TemplateRoleSlotSpec("chain_guardian", "guardian", "protect custody-chain integrity", "procedural pressure", "chain seals, witness stamps, archive gloves", "tight formal silhouette with archive tooling", "Do not duplicate transcript witness or manipulative intermediary.", ("guardian", "anchor")),
            TemplateRoleSlotSpec("transcript_witness", "witness", "remember omission and exact phrasing", "public emotion pressure", "transcript leaves, hearing pen, annotated scraps", "observational silhouette with carried papers", "Do not become a certifier or broker.", ("witness", "guardian")),
            TemplateRoleSlotSpec("docket_intermediary", "broker", "control when truth surfaces", "political leverage pressure", "docket tubes, appointment cards, release tags", "broker silhouette with controlled delivery props", "Do not overlap with either direct witness or chain notary.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="legitimacy_story",
        cast_strategy="legitimacy_cast",
        beat_strategy="conservative_direct_draft",
        primary_theme="legitimacy_crisis",
        trio_relationship="A legitimacy template needs one charter-bearing anchor, one ritual/oath witness, and one compact broker who prices stability.",
        avoid_shapes=("three councilors", "three oath officials"),
        visual_anchors=("charter tubes", "oath ribbons", "compact seals"),
        theme_tags=("legitimacy_crisis",),
        setting_tags=("charter_hall", "succession", "compact_chamber"),
        tone_tags=("political", "restrained", "tense"),
        conflict_tags=("legitimacy", "succession", "public_record"),
        retrieval_terms=("legitimacy", "charter", "oath", "compact", "succession", "mandate"),
        slots=(
            TemplateRoleSlotSpec("charter_envoy", "anchor", "hold visible legitimacy together", "procedural pressure", "charter tubes, mandate cord, hall insignia", "upright formal silhouette with visible legal object", "Do not collapse into oath witness or broker dealmaker.", ("anchor", "guardian")),
            TemplateRoleSlotSpec("oath_witness", "witness", "hear when lawful language becomes empty ritual", "public emotion pressure", "oath cords, witness gloves, ritual script", "ritual silhouette with ceremonial but worn detail", "Do not feel like a diplomat or broker.", ("witness", "civic")),
            TemplateRoleSlotSpec("compact_broker", "broker", "extract concessions from unstable settlement", "political leverage pressure", "compact folio, seal ring, accord tabs", "clean political silhouette with bargaining props", "Do not duplicate envoy legality or witness ritual conscience.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="public_order_story",
        cast_strategy="public_order_cast",
        beat_strategy="conservative_direct_draft",
        primary_theme="public_order_crisis",
        trio_relationship="A public-order template needs one order enforcer, one square/crowd witness, and one quietbroker who monetizes stability.",
        avoid_shapes=("three guards", "three riot officers"),
        visual_anchors=("curfew bands", "square watch markers", "supply permit clips"),
        theme_tags=("public_order_crisis",),
        setting_tags=("curfew", "public_square", "checkpoint"),
        tone_tags=("urgent", "tense", "procedural"),
        conflict_tags=("public_order", "legitimacy", "resource"),
        retrieval_terms=("public_order", "curfew", "square", "checkpoint", "crowd", "supply"),
        slots=(
            TemplateRoleSlotSpec("curfew_guardian", "guardian", "keep order enforceable without selective collapse", "procedural pressure", "curfew markers, checkpoint tabs, patrol docket", "enforcement silhouette with visible rule apparatus", "Do not become a crowd witness or a broker.", ("guardian", "anchor")),
            TemplateRoleSlotSpec("square_witness", "witness", "see when a crowd turns from waiting to rupture", "public emotion pressure", "square watch tokens, public notices, weathered scarf", "public-facing silhouette built for observation not command", "Do not sound like an officer.", ("witness", "civic")),
            TemplateRoleSlotSpec("quietbroker", "broker", "price peace and coercion", "political leverage pressure", "supply permits, ration satchel, calm trade pins", "broker silhouette with understated luxury and permit tech", "Do not overlap with either law enforcer or moral witness.", ("broker", "civic")),
        ),
    ),
    TemplateRoleSpec(
        template_name="generic_civic_story",
        cast_strategy="generic_civic_cast",
        beat_strategy="conservative_direct_draft",
        primary_theme="generic_civic_crisis",
        trio_relationship="A generic civic template needs one practical repair anchor, one common ledger witness, and one testimony runner tying spaces together.",
        avoid_shapes=("three generic officials", "three archive workers"),
        visual_anchors=("repair boards", "public ledgers", "market testimony packets"),
        theme_tags=("generic_civic_crisis",),
        setting_tags=("civic_yard", "ledger_office", "market_square"),
        tone_tags=("restrained", "civic", "tense"),
        conflict_tags=("resource", "legitimacy", "public_order"),
        retrieval_terms=("generic_civic", "repair", "ledger", "testimony", "market", "district"),
        slots=(
            TemplateRoleSlotSpec("repair_anchor", "anchor", "keep the city materially repairable", "infrastructure pressure", "repair boards, tool satchel, civic yard markers", "active practical silhouette with work gear", "Do not duplicate ledger keeper or testimony runner.", ("anchor", "civic")),
            TemplateRoleSlotSpec("ledger_guardian", "guardian", "hold shared civic memory in record form", "procedural pressure", "public ledgers, chalk totals, docket straps", "formal but modest bookkeeping silhouette", "Do not become an emotional witness or mover.", ("guardian", "witness")),
            TemplateRoleSlotSpec("testimony_runner", "witness", "move public stories between institutions", "public emotion pressure", "packet satchel, stamped slips, market ribbons", "mobile light silhouette built around carried documents", "Do not overlap with repair crew or ledger office archetype.", ("witness", "civic")),
        ),
    ),
)


def template_role_spec_by_name(template_name: TemplateName) -> TemplateRoleSpec:
    for spec in TEMPLATE_ROLE_CATALOG:
        if spec.template_name == template_name:
            return spec
    raise KeyError(template_name)


def build_template_role_prompt(spec: TemplateRoleSpec) -> str:
    slot_instructions = "\n".join(
        f"- {slot.slot_key}: function={slot.function}; role focus={slot.role_focus}; pressure mode={slot.pressure_mode}; "
        f"visual anchor={slot.visual_anchor}; silhouette anchor={slot.silhouette_anchor}; avoid overlap={slot.avoid_overlap}"
        for slot in spec.slots
    )
    return (
        f"{prompt_role_instruction('en', en_role='a senior ensemble character designer for civic interactive fiction', zh_role='资深中文群像角色策划')} "
        "Return strict JSON only. No markdown. "
        "You are drafting exactly three roles for one story template. "
        "Each role must be internally distinct in function, pressure style, and visual silhouette. "
        "Do not output three variations of the same official, clerk, or witness. "
        "You must provide bilingual fields for every role: English and Chinese. "
        "The trio must serve the named template directly, not generic civic drama. "
        "Portrait style source-of-truth: semi-realistic editorial civic-fantasy dossier portrait, 1:1 source, face readable within the center-safe zone, safe for 4:5 cover crop across author/detail/current play, painterly editorial illustration, restrained realism, muted ivory/rust/slate palette, avoid modern corporate office staging, avoid generic business portrait setups. "
        "Keep every field compact. role_hint should be 2-4 words. public_summary should be one concise sentence. agenda_seed, red_line_seed, and pressure_signature_seed should each be one concise sentence, not a paragraph. "
        "Output one JSON object with keys: template_name, roles. "
        "roles must be an array of exactly 3 objects. "
        "Each role object must contain exactly: provisional_role, name_en, name_zh, public_summary_en, public_summary_zh, role_hint_en, role_hint_zh, agenda_seed_en, agenda_seed_zh, red_line_seed_en, red_line_seed_zh, pressure_signature_seed_en, pressure_signature_seed_zh, visual_anchor, silhouette_note, avoid_overlap_with_other_two. "
        f"Template name: {spec.template_name}. "
        f"Cast strategy: {spec.cast_strategy}. Beat strategy: {spec.beat_strategy}. Primary theme: {spec.primary_theme}. "
        f"Trio relationship: {spec.trio_relationship}. "
        f"Avoid repeated role shapes: {', '.join(spec.avoid_shapes)}. "
        f"Template-level visual anchors: {', '.join(spec.visual_anchors)}. "
        "Required slot intents:\n"
        f"{slot_instructions}\n"
        "Keep public_summary concise but vivid. "
        "Role hints should look like reusable roster role labels, not full sentences. "
        "agenda_seed / red_line_seed / pressure_signature_seed should each feel materially different across the three roles."
    )


def _extract_first_balanced_json_object(text: str) -> dict[str, Any]:
    content = str(text or "").strip()
    start = content.find("{")
    if start < 0:
        raise ValueError("no JSON object found in model output")
    depth = 0
    in_string = False
    escaping = False
    for index in range(start, len(content)):
        char = content[index]
        if in_string:
            if escaping:
                escaping = False
            elif char == "\\":
                escaping = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                snippet = content[start : index + 1]
                payload = json.loads(snippet)
                if not isinstance(payload, dict):
                    raise ValueError("model output JSON root was not an object")
                return payload
    raise ValueError("unterminated JSON object in model output")


def _attempt_template_role_invoke(
    gateway: CapabilityGatewayCore,
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    previous_response_id: str | None,
) -> tuple[dict[str, Any], str | None]:
    result = gateway.invoke_text_capability(
        "author.template_role_draft",
        TextCapabilityRequest(
            system_prompt=system_prompt,
            user_payload=user_payload,
            max_output_tokens=gateway.text_policy("author.template_role_draft").max_output_tokens,
            previous_response_id=previous_response_id,
            operation_name="template_role_draft",
            allow_raw_text_passthrough=True,
        ),
    )
    raw_payload = result.payload if result.payload else _extract_first_balanced_json_object(result.raw_text or "")
    return raw_payload, result.response_id


def _trim(value: Any, limit: int) -> str:
    normalized = str(value or "").strip()
    return normalized[:limit].rstrip()


def _normalize_template_role_payload(raw_payload: dict[str, Any], spec: TemplateRoleSpec) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return raw_payload
    roles = raw_payload.get("roles")
    if not isinstance(roles, list):
        return raw_payload
    normalized_roles: list[dict[str, Any]] = []
    for item in roles[:3]:
        if not isinstance(item, dict):
            continue
        normalized_roles.append(
            {
                "provisional_role": _trim(item.get("provisional_role"), 80),
                "name_en": _trim(item.get("name_en"), 80),
                "name_zh": _trim(item.get("name_zh"), 80),
                "public_summary_en": _trim(item.get("public_summary_en"), 220),
                "public_summary_zh": _trim(item.get("public_summary_zh"), 220),
                "role_hint_en": _trim(item.get("role_hint_en"), 120),
                "role_hint_zh": _trim(item.get("role_hint_zh"), 120),
                "agenda_seed_en": _trim(item.get("agenda_seed_en"), 220),
                "agenda_seed_zh": _trim(item.get("agenda_seed_zh"), 220),
                "red_line_seed_en": _trim(item.get("red_line_seed_en"), 220),
                "red_line_seed_zh": _trim(item.get("red_line_seed_zh"), 220),
                "pressure_signature_seed_en": _trim(item.get("pressure_signature_seed_en"), 220),
                "pressure_signature_seed_zh": _trim(item.get("pressure_signature_seed_zh"), 220),
                "visual_anchor": _trim(item.get("visual_anchor"), 160),
                "silhouette_note": _trim(item.get("silhouette_note"), 160),
                "avoid_overlap_with_other_two": _trim(item.get("avoid_overlap_with_other_two"), 220),
            }
        )
    return {
        "template_name": str(raw_payload.get("template_name") or spec.template_name),
        "roles": normalized_roles,
    }


def draft_template_roles(gateway: CapabilityGatewayCore, spec: TemplateRoleSpec) -> TemplateRoleDraftResponse:
    payload = {"template_name": spec.template_name, "task": "draft_three_distinct_roles"}
    final_retry_payload = {"template_name": spec.template_name}
    prompts = (
        build_template_role_prompt(spec),
        "Return raw JSON only. Exactly one object with template_name and roles. roles must contain exactly 3 objects with all required bilingual fields.",
        "Output strict JSON only. No markdown. Keep the three roles distinct in function, pressure style, and silhouette.",
    )
    previous_response_id: str | None = None
    last_error: Exception | None = None
    for index, prompt in enumerate(prompts):
        request_payload = final_retry_payload if index == len(prompts) - 1 else payload
        try:
            raw_payload, previous_response_id = _attempt_template_role_invoke(
                gateway,
                system_prompt=prompt,
                user_payload=request_payload,
                previous_response_id=previous_response_id,
            )
        except GatewayCapabilityError as exc:
            last_error = AuthorGatewayError(
                code={
                    "gateway_text_provider_failed": "llm_provider_failed",
                    "gateway_text_invalid_response": "llm_invalid_response",
                    "gateway_text_invalid_json": "llm_invalid_json",
                }.get(exc.code, exc.code),
                message=exc.message,
                status_code=exc.status_code,
            )
            if index == len(prompts) - 1:
                raise last_error from exc
            continue
        try:
            return TemplateRoleDraftResponse.model_validate(_normalize_template_role_payload(raw_payload, spec))
        except Exception as exc:  # noqa: BLE001
            last_error = AuthorGatewayError(
                code="llm_schema_invalid",
                message=str(exc),
                status_code=502,
            )
            if index == len(prompts) - 1:
                break
            continue
    repair_prompt = (
        "You previously returned the wrong schema. Rewrite the output as strict JSON only. "
        "Return exactly one object with keys template_name and roles. "
        "roles must be an array of exactly 3 objects and each role must contain: "
        "provisional_role, name_en, name_zh, public_summary_en, public_summary_zh, role_hint_en, role_hint_zh, "
        "agenda_seed_en, agenda_seed_zh, red_line_seed_en, red_line_seed_zh, pressure_signature_seed_en, pressure_signature_seed_zh, "
        "visual_anchor, silhouette_note, avoid_overlap_with_other_two. "
        "Do not return slot_specs. Do not return role_name/function-only summaries. "
        "Keep the trio distinct in function, pressure style, and silhouette."
    )
    repair_payload = {
        "template_name": spec.template_name,
        "invalid_output": raw_payload if "raw_payload" in locals() else {},
        "slot_specs": [
            {
                "slot_key": slot.slot_key,
                "function": slot.function,
                "role_focus": slot.role_focus,
                "pressure_mode": slot.pressure_mode,
                "visual_anchor": slot.visual_anchor,
                "silhouette_anchor": slot.silhouette_anchor,
                "avoid_overlap": slot.avoid_overlap,
            }
            for slot in spec.slots
        ],
    }
    try:
        repaired_payload, _ = _attempt_template_role_invoke(
            gateway,
            system_prompt=repair_prompt,
            user_payload=repair_payload,
            previous_response_id=previous_response_id,
        )
        return TemplateRoleDraftResponse.model_validate(_normalize_template_role_payload(repaired_payload, spec))
    except Exception as exc:  # noqa: BLE001
        if isinstance(last_error, AuthorGatewayError):
            raise last_error from exc
        raise AuthorGatewayError(code="llm_schema_invalid", message=str(exc), status_code=502) from exc
    if isinstance(last_error, AuthorGatewayError):
        raise last_error
    raise AuthorGatewayError(code="llm_schema_invalid", message=str(last_error or "template_role_draft failed"), status_code=502)


def normalize_role_name(value: str) -> str:
    return " ".join(value.strip().split())


def build_character_id(*, template_name: TemplateName, role_index: int, role_hint_en: str) -> str:
    base = (
        role_hint_en.lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace("'", "")
    )
    tokens = [token for token in base.split() if token]
    slug = "_".join(tokens[:4]) if tokens else f"role_{role_index}"
    return f"roster_{template_name.replace('_story', '')}_{slug}_{role_index}"


def _merge_unique_tokens(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in list(left) + list(right):
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def finalize_draft_entry(
    *,
    spec: TemplateRoleSpec,
    slot: TemplateRoleSlotSpec,
    role_index: int,
    draft: TemplateRoleDraftEntry,
) -> dict[str, Any]:
    role_hint_en = normalize_role_name(draft.role_hint_en)
    role_hint_zh = normalize_role_name(draft.role_hint_zh)
    retrieval_terms = _merge_unique_tokens(
        spec.retrieval_terms,
        tuple(
            token.strip()
            for token in (
                draft.provisional_role,
                draft.visual_anchor,
                draft.silhouette_note,
                role_hint_en,
            )
            if token and token.strip()
        ),
    )
    setting_tags = _merge_unique_tokens(
        spec.setting_tags,
        tuple(word for word in role_hint_en.lower().replace("-", " ").split() if word.isascii()),
    )
    tone_tags = spec.tone_tags
    conflict_tags = spec.conflict_tags
    return {
        "character_id": build_character_id(
            template_name=spec.template_name,
            role_index=role_index,
            role_hint_en=role_hint_en,
        ),
        "slug": build_character_id(
            template_name=spec.template_name,
            role_index=role_index,
            role_hint_en=role_hint_en,
        ).replace("roster_", "").replace("_", "-"),
        "name_en": normalize_role_name(draft.name_en),
        "name_zh": normalize_role_name(draft.name_zh),
        "public_summary_en": draft.public_summary_en.strip(),
        "public_summary_zh": draft.public_summary_zh.strip(),
        "role_hint_en": role_hint_en,
        "role_hint_zh": role_hint_zh,
        "agenda_seed_en": draft.agenda_seed_en.strip(),
        "agenda_seed_zh": draft.agenda_seed_zh.strip(),
        "red_line_seed_en": draft.red_line_seed_en.strip(),
        "red_line_seed_zh": draft.red_line_seed_zh.strip(),
        "pressure_signature_seed_en": draft.pressure_signature_seed_en.strip(),
        "pressure_signature_seed_zh": draft.pressure_signature_seed_zh.strip(),
        "theme_tags": list(spec.theme_tags),
        "setting_tags": list(setting_tags),
        "tone_tags": list(tone_tags),
        "conflict_tags": list(conflict_tags),
        "slot_tags": list(slot.slot_tags),
        "retrieval_terms": list(retrieval_terms[:8]),
        "rarity_weight": 1.0,
    }


def build_role_matrix_markdown(
    *,
    specs: tuple[TemplateRoleSpec, ...],
    final_entries_by_template: dict[TemplateName, list[dict[str, Any]]],
) -> str:
    lines = [
        "# Template Role Matrix",
        "",
        "This matrix is the role-design source of truth for template-aligned cast expansion.",
        "",
    ]
    for spec in specs:
        lines.append(f"## `{spec.template_name}`")
        lines.append("")
        lines.append(f"- Primary theme: `{spec.primary_theme}`")
        lines.append(f"- Cast strategy: `{spec.cast_strategy}`")
        lines.append(f"- Beat strategy: `{spec.beat_strategy}`")
        lines.append(f"- Trio relationship: {spec.trio_relationship}")
        lines.append(f"- Avoid repeated shapes: {', '.join(spec.avoid_shapes)}")
        lines.append(f"- Visual anchors: {', '.join(spec.visual_anchors)}")
        lines.append("")
        for slot, entry in zip(spec.slots, final_entries_by_template[spec.template_name], strict=True):
            lines.append(
                f"- `{slot.slot_key}` [{slot.function}] {entry['name_en']} / {entry['name_zh']} — {entry['role_hint_en']}"
            )
            lines.append(f"  role focus: {slot.role_focus}")
            lines.append(f"  pressure mode: {slot.pressure_mode}")
            lines.append(f"  visual anchor: {slot.visual_anchor}")
            lines.append(f"  silhouette anchor: {slot.silhouette_anchor}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_json(path: str | Path, payload: Any) -> Path:
    resolved_path = Path(path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resolved_path


def write_text(path: str | Path, content: str) -> Path:
    resolved_path = Path(path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(content, encoding="utf-8")
    return resolved_path

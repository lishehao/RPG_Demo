from __future__ import annotations

from dataclasses import dataclass
import hashlib

from rpg_backend.roster.portrait_registry import PortraitVariantKey

DEFAULT_IMAGE_API_BASE_URL = "https://vip.123everything.com"
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_PROMPT_VERSION = "v1_editorial_dossier"

_STYLE_LABEL = "semi-realistic editorial civic-fantasy dossier portrait"
_CROP_GUIDANCE = (
    "Square 1:1 source image, chest-up to waist-up framing, face fully readable within the center-safe zone, "
    "safe for 4:5 cover crop across author, detail, and current play presentation."
)
_STYLE_LOCK = (
    "Painterly editorial illustration, restrained realism, civic-institutional atmosphere, muted ivory/rust/slate palette, "
    "paper-dossier mood, coherent but restrained background, readable silhouette."
)
_NEGATIVE_GUIDANCE = (
    "Avoid glossy photography, stock headshots, corporate portrait poses, celebrity beauty retouching, anime styling, "
    "blockbuster poster lighting, text overlays, watermarks, extreme close-ups, face-obscuring props, modern corporate office staging, "
    "generic business portrait setups, and off-center crops "
    "that would lose the face after object-fit cover."
)


@dataclass(frozen=True)
class PortraitPromptSubject:
    character_id: str
    name_primary: str
    name_secondary: str | None
    role: str
    public_summary: str | None
    agenda: str
    red_line: str
    pressure_signature: str
    story_title: str | None = None
    story_premise: str | None = None
    story_tone: str | None = None
    story_style_guard: str | None = None
    world_rules: tuple[str, ...] = ()
    thematic_pressure: tuple[str, ...] = ()
    setting_anchors: tuple[str, ...] = ()
    tonal_field: tuple[str, ...] = ()
    roster_anchor: str | None = None


def _variant_overlay(variant_key: PortraitVariantKey) -> str:
    if variant_key == "negative":
        return (
            "Variant overlay: clearly negative stance, visibly guarded posture, defensive or withdrawn hand placement, colder emotional distance, "
            "more closed body language, more suspicious or tense gaze, harsher shadow edges, and a more pressurized setting. "
            "Expression priority: use a noticeably tightened jaw, compressed or unsmiling mouth, tenser brow, narrower eyes, and more defensive shoulders. "
            "The negative state should read immediately at thumbnail size, not as a subtle mood shift. "
            "Allow stronger wardrobe changes such as heavier outer layers, buttoned collars, gloves, wraps, badges, or protective accessories. "
            "Allow stronger background changes such as darker archive corners, tighter corridors, harsher workrooms, night exteriors, or more claustrophobic civic interiors. "
            "Preserve the same character identity while making the social distance and distrust unmistakable."
        )
    if variant_key == "positive":
        return (
            "Variant overlay: positive stance, more open gaze, slightly warmer light, clearer alliance signal, more relaxed or receptive hand posture, "
            "and a more open or hopeful immediate environment. "
            "Expression priority: use a visibly softened brow, calmer eyes, more open jawline, slightly lifted mouth corners or a restrained smile, and less defensive shoulders. "
            "Allow wardrobe variation toward lighter layers, softened collars, visible insignia, or cleaner working dress. "
            "Allow background variation toward brighter chambers, more open desks, window light, lamps, or civic spaces that feel less compressed. "
            "measured trust rather than friendliness."
        )
    return (
        "Variant overlay: neutral stance, institutional baseline, composed public-facing restraint, "
        "balanced light, readable but not warm. Expression priority: controlled, unsmiling or near-neutral mouth, balanced brow, steady gaze, and professional posture."
    )


def build_portrait_art_direction_payload() -> dict[str, object]:
    return {
        "style_label": _STYLE_LABEL,
        "generation_aspect_ratio": "1:1",
        "generation_resolution": "512",
        "display_ratios": ["4:5 author/detail/play"],
        "crop_guidance": _CROP_GUIDANCE,
        "style_lock": _STYLE_LOCK,
        "negative_guidance": _NEGATIVE_GUIDANCE,
        "ui_grade_notes": "UI applies object-fit cover, light editorial grading, and optional overlay shadow.",
    }


def build_portrait_prompt(
    subject: PortraitPromptSubject,
    *,
    variant_key: PortraitVariantKey,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> str:
    del prompt_version
    identity = (
        f"{subject.name_primary} ({subject.name_secondary})"
        if subject.name_secondary and subject.name_secondary != subject.name_primary
        else subject.name_primary
    )
    story_context = " ".join(
        item
        for item in (
            f"Story title: {subject.story_title}." if subject.story_title else "",
            f"Story premise: {subject.story_premise}." if subject.story_premise else "",
            f"Story tone: {subject.story_tone}." if subject.story_tone else "",
            f"Style guard: {subject.story_style_guard}." if subject.story_style_guard else "",
        )
        if item
    )
    world_context = " ".join(subject.world_rules[:3])
    tags_context = " ".join(
        item
        for item in (
            f"Thematic pressure: {' '.join(subject.thematic_pressure)}." if subject.thematic_pressure else "",
            f"Setting anchors: {' '.join(subject.setting_anchors)}." if subject.setting_anchors else "",
            f"Tonal field: {' '.join(subject.tonal_field)}." if subject.tonal_field else "",
            f"Roster anchor: {subject.roster_anchor}." if subject.roster_anchor else "",
        )
        if item
    )
    return (
        f"Create a {_STYLE_LABEL}. "
        f"{_CROP_GUIDANCE} "
        "Readable face, no text, no watermark. "
        f"Character identity: {identity}. "
        f"Role: {subject.role}. "
        f"Public summary: {subject.public_summary or 'No formal public summary; infer from the role and story pressure.'} "
        f"Agenda: {subject.agenda} "
        f"Red line: {subject.red_line} "
        f"Pressure signature: {subject.pressure_signature} "
        f"{story_context} "
        f"World rules: {world_context} "
        f"{tags_context} "
        f"{_variant_overlay(variant_key)} "
        f"Style lock: {_STYLE_LOCK} "
        f"Avoid: {_NEGATIVE_GUIDANCE}"
    )


def build_reference_locked_variant_prompt(prompt_text: str) -> str:
    return (
        f"{prompt_text} "
        "Identity lock: use the attached reference portrait as the same character identity. "
        "Preserve facial structure, apparent age band, skin tone, and core hair identity so the subject still reads as the same person. "
        "You may vary clothing layers, accessories, posture, and background context much more aggressively to strengthen the requested variant, "
        "but do not drift into a different person or different facial identity. "
        "Make the expression and upper-body pose change more obvious than the wardrobe/background change. "
        "Use outfit and background changes as major supporting cues; the face and core identity must remain stable."
    )


def prompt_hash(prompt_text: str) -> str:
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def build_asset_id(
    *,
    character_id: str,
    variant_key: PortraitVariantKey,
    candidate_index: int,
    prompt_hash: str,
) -> str:
    return f"prt_{character_id}_{variant_key}_{candidate_index}_{prompt_hash[:8]}"

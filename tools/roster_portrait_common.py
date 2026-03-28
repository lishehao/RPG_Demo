from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from rpg_backend.config import get_settings
from rpg_backend.portraits.prompting import (
    DEFAULT_IMAGE_API_BASE_URL,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_PROMPT_VERSION,
    PortraitPromptSubject,
    build_asset_id,
    build_portrait_prompt as build_subject_portrait_prompt,
    build_reference_locked_variant_prompt,
    prompt_hash,
)
from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from rpg_backend.roster.portrait_registry import PortraitVariantKey

DEFAULT_VARIANTS: tuple[PortraitVariantKey, ...] = ("negative", "neutral", "positive")
DEFAULT_CANDIDATES_PER_VARIANT = 2


@dataclass(frozen=True)
class PortraitGenerationJob:
    asset_id: str
    character_id: str
    variant_key: PortraitVariantKey
    candidate_index: int
    prompt_text: str
    prompt_hash: str
    relative_output_path: str
    reference_relative_output_path: str | None = None


@dataclass(frozen=True)
class PortraitBatchPlan:
    batch_id: str
    prompt_version: str
    image_model: str
    image_api_base_url: str
    output_dir: str
    jobs: tuple[PortraitGenerationJob, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "prompt_version": self.prompt_version,
            "image_model": self.image_model,
            "image_api_base_url": self.image_api_base_url,
            "output_dir": self.output_dir,
            "jobs": [asdict(job) for job in self.jobs],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PortraitBatchPlan":
        return cls(
            batch_id=str(payload["batch_id"]),
            prompt_version=str(payload["prompt_version"]),
            image_model=str(payload["image_model"]),
            image_api_base_url=str(payload["image_api_base_url"]),
            output_dir=str(payload["output_dir"]),
            jobs=tuple(PortraitGenerationJob(**dict(item)) for item in payload.get("jobs") or ()),
        )


def default_jobs_dir() -> Path:
    return Path("artifacts/portraits/jobs").resolve()


def default_output_dir() -> Path:
    return Path(get_settings().local_portrait_dir).expanduser().resolve()


def build_batch_id(prefix: str = "portrait") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}_{uuid4().hex[:6]}"


def build_portrait_subject_from_roster_entry(entry: CharacterRosterSourceEntry) -> PortraitPromptSubject:
    return PortraitPromptSubject(
        character_id=entry.character_id,
        name_primary=entry.name_en,
        name_secondary=entry.name_zh,
        role=entry.role_hint_en,
        public_summary=entry.public_summary_en,
        agenda=entry.agenda_seed_en,
        red_line=entry.red_line_seed_en,
        pressure_signature=entry.pressure_signature_seed_en,
        world_rules=(),
        thematic_pressure=entry.theme_tags,
        setting_anchors=entry.setting_tags,
        tonal_field=entry.tone_tags,
    )


def build_portrait_prompt(
    entry: CharacterRosterSourceEntry,
    *,
    variant_key: PortraitVariantKey,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> str:
    return build_subject_portrait_prompt(
        build_portrait_subject_from_roster_entry(entry),
        variant_key=variant_key,
        prompt_version=prompt_version,
    )


def build_image_request_payload(
    prompt_text: str,
    *,
    reference_image_bytes: bytes | None = None,
    reference_mime_type: str | None = None,
) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [
        {
            "text": prompt_text,
        }
    ]
    if reference_image_bytes is not None:
        parts.append(
            {
                "inline_data": {
                    "mime_type": reference_mime_type or "image/png",
                    "data": base64.b64encode(reference_image_bytes).decode("utf-8"),
                }
            }
        )
    return {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {
                "aspectRatio": "1:1",
                "imageSize": "512",
            },
        },
    }


def extract_image_part(payload: dict[str, Any]) -> tuple[bytes, str]:
    for candidate in list(payload.get("candidates") or []):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            continue
        for part in list(content.get("parts") or []):
            if not isinstance(part, dict):
                continue
            inline = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline, dict):
                continue
            data = inline.get("data")
            if not isinstance(data, str) or not data.strip():
                continue
            mime_type = str(inline.get("mimeType") or inline.get("mime_type") or "image/png")
            return base64.b64decode(data), mime_type
    raise RuntimeError(
        "image response did not include an inline image part: "
        + json.dumps({"candidates": payload.get("candidates")}, ensure_ascii=False)[:800]
    )


def generate_portrait_image(
    session: requests.Session,
    *,
    api_key: str,
    image_api_base_url: str,
    image_model: str,
    request_timeout_seconds: float,
    prompt_text: str,
    reference_image_bytes: bytes | None = None,
    reference_mime_type: str | None = None,
) -> tuple[bytes, str]:
    url = f"{image_api_base_url}/v1beta/models/{image_model}:generateContent?key={api_key}"
    resolved_prompt = (
        build_reference_locked_variant_prompt(prompt_text)
        if reference_image_bytes is not None
        else prompt_text
    )
    payload = build_image_request_payload(
        resolved_prompt,
        reference_image_bytes=reference_image_bytes,
        reference_mime_type=reference_mime_type,
    )
    response = session.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=request_timeout_seconds,
    )
    if not response.ok:
        try:
            body = response.json()
        except ValueError:
            body = response.text
        raise RuntimeError(f"portrait generation failed: {body}")
    return extract_image_part(response.json())


def detect_image_mime_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return "application/octet-stream"
def build_relative_output_path(
    *,
    character_id: str,
    variant_key: PortraitVariantKey,
    asset_id: str,
) -> str:
    return f"{character_id}/{variant_key}/{asset_id}.png"


def build_reference_relative_output_path(
    *,
    character_id: str,
    candidate_index: int,
) -> str:
    return f"{character_id}/neutral/reference_{candidate_index}.png"


def build_published_relative_path(
    *,
    character_id: str,
    variant_key: PortraitVariantKey,
) -> str:
    return f"{character_id}/{variant_key}/current.png"


def build_public_url(
    *,
    local_portrait_base_url: str,
    relative_path: str,
) -> str:
    return f"{local_portrait_base_url.rstrip('/')}/portraits/roster/{relative_path.lstrip('/')}"


def write_plan_file(path: str | Path, plan: PortraitBatchPlan) -> Path:
    resolved_path = Path(path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(plan.to_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resolved_path


def load_plan_file(path: str | Path) -> PortraitBatchPlan:
    resolved_path = Path(path).expanduser().resolve()
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("portrait batch plan must be a JSON object")
    return PortraitBatchPlan.from_payload(payload)

from __future__ import annotations

LEGACY_ROSTER_ID_MAP: dict[str, str] = {
    "roster_archive_certifier": "roster_archive_vote_certifier",
    "roster_blackout_grid_broker": "roster_blackout_grid_compact_broker",
    "roster_harbor_manifest_clerk": "roster_harbor_manifest_keeper",
    "roster_dock_union_organizer": "roster_harbor_dockside_delegate",
    "roster_emergency_ombud": "roster_truth_chain_notary",
    "roster_courtyard_witness": "roster_archive_gallery_petitioner",
}


def resolve_legacy_roster_character_id(character_id: str | None) -> str:
    normalized = str(character_id or "").strip()
    if not normalized:
        return ""
    return LEGACY_ROSTER_ID_MAP.get(normalized, normalized)

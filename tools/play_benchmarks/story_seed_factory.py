from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random


@dataclass(frozen=True)
class GeneratedStorySeed:
    bucket_id: str
    slug: str
    seed: str
    generated_at: str


def _timestamp(now: datetime | None = None) -> str:
    resolved = now or datetime.now(timezone.utc)
    return resolved.isoformat()


def build_story_seed_batch(
    *,
    rng: Random | None = None,
    now: datetime | None = None,
    story_count: int = 5,
) -> list[GeneratedStorySeed]:
    resolved_rng = rng or Random()
    generated_at = _timestamp(now)
    templates = [
        GeneratedStorySeed(
            bucket_id="legitimacy_warning",
            slug="legitimacy_warning",
            seed=(
                f"When a {resolved_rng.choice(['lunar', 'storm', 'river', 'watchtower'])} warning is buried to protect "
                f"a {resolved_rng.choice(['council vote', 'succession bargain', 'emergency mandate'])}, "
                f"a {resolved_rng.choice(['royal archivist', 'civic envoy', 'records magistrate'])} must prove the threat is real "
                f"before {resolved_rng.choice(['courtiers rewrite the public story', 'the capital locks itself into denial', 'the city accepts a false calm as law'])}."
            ),
            generated_at=generated_at,
        ),
        GeneratedStorySeed(
            bucket_id="ration_infrastructure",
            slug="ration_infrastructure",
            seed=(
                f"After {resolved_rng.choice(['forged ration counts', 'tampered bridge ledgers', 'hidden reserve tallies'])} split "
                f"{resolved_rng.choice(['the upper wards and the river docks', 'the bridge crews and the market districts', 'the flood board and the grain stewards'])}, "
                f"a {resolved_rng.choice(['bridge engineer', 'public works marshal', 'levee comptroller'])} must keep the "
                f"{resolved_rng.choice(['flood defense coalition', 'cross-river relief pact', 'emergency works charter'])} intact before "
                f"{resolved_rng.choice(['the crossing fails under panic', 'scarcity turns maintenance into factional leverage', 'the city blames the wrong ward for the collapse'])}."
            ),
            generated_at=generated_at,
        ),
        GeneratedStorySeed(
            bucket_id="blackout_panic",
            slug="blackout_panic",
            seed=(
                f"During a {resolved_rng.choice(['blackout referendum', 'rolling power crisis', 'night-curfew recall vote'])}, "
                f"a {resolved_rng.choice(['city ombudsman', 'ward mediator', 'public audit officer'])} must stop "
                f"{resolved_rng.choice(['forged supply reports', 'staged shortage bulletins', 'panic-rich rumor ledgers'])} from "
                f"breaking apart {resolved_rng.choice(['the neighborhood councils', 'the ward coalition', 'the emergency compact'])} before "
                f"{resolved_rng.choice(['street patrols turn rumor into authority', 'the districts seize the grid room by force', 'panic becomes the only public language left'])}."
            ),
            generated_at=generated_at,
        ),
        GeneratedStorySeed(
            bucket_id="harbor_quarantine",
            slug="harbor_quarantine",
            seed=(
                f"In a port city under quarantine, a {resolved_rng.choice(['harbor inspector', 'dock auditor', 'quarantine liaison'])} must keep "
                f"{resolved_rng.choice(['the harbor compact', 'the dock coalition', 'the relief corridor'])} alive after "
                f"{resolved_rng.choice(['missing manifests', 'staged scarcity reports', 'quietly redirected medical crates'])} threaten to hand "
                f"{resolved_rng.choice(['private trade brokers', 'emergency wardens', 'supply syndicates'])} the right to rule by exception."
            ),
            generated_at=generated_at,
        ),
        GeneratedStorySeed(
            bucket_id="archive_vote_record",
            slug="archive_vote_record",
            seed=(
                f"When {resolved_rng.choice(['vote ledgers', 'emergency transcripts', 'sealed chain-of-custody records'])} are altered during "
                f"{resolved_rng.choice(['an emergency council vote', 'a succession settlement', 'a public legitimacy hearing'])}, "
                f"a {resolved_rng.choice(['city archivist', 'records advocate', 'civic witness clerk'])} must restore one binding public record before "
                f"{resolved_rng.choice(['rumor hardens into law', 'the council governs from a forged mandate', 'every faction claims a different city truth'])}."
            ),
            generated_at=generated_at,
        ),
    ]
    normalized_count = max(1, min(int(story_count), len(templates)))
    if normalized_count >= len(templates):
        return templates
    selected = resolved_rng.sample(templates, k=normalized_count)
    return sorted(selected, key=lambda item: item.bucket_id)

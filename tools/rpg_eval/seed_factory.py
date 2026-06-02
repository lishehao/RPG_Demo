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


_SEED_BUCKETS: tuple[tuple[str, str, str, str], ...] = (
    (
        "wealth_public_heir",
        "wealth_public_heir",
        "At a family banquet, an heirship recording, an old lover, and a succession lawyer force the protagonist to choose a side in public.",
        "豪门家宴上，继承录音、旧爱和法务同时逼主角公开站队。",
    ),
    (
        "entertainment_live_scandal",
        "entertainment_live_scandal",
        "Minutes before an awards livestream, a hidden relationship video and a sponsor contract collide in front of the cameras.",
        "颁奖礼直播前，隐恋偷拍视频和代言合同同时在镜头前失控。",
    ),
    (
        "office_merger_blackmail",
        "office_merger_blackmail",
        "Before a merger announcement, a black-ledger recording lets the protagonist protect the job, expose the truth, or save one relationship.",
        "并购发布会前，黑账录音迫使主角在职位、真相和关系之间选择。",
    ),
    (
        "campus_recording_vote",
        "campus_recording_vote",
        "During homecoming preparations, an old recording and a scholarship vote turn a private breakup into a public loyalty test.",
        "校庆筹备夜，旧录音和奖学金投票把私下分手变成公开站队。",
    ),
    (
        "supernatural_contract_debt",
        "supernatural_contract_debt",
        "A night patrol contract resurfaces with an old emotional debt, forcing the protagonist to trade secrecy for protection.",
        "夜巡契约带着旧情债回潮，主角必须用秘密交换保护。",
    ),
)


def _timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def build_story_seed_batch(
    *,
    rng: Random | None = None,
    now: datetime | None = None,
    story_count: int = 5,
    language: str = "en",
) -> list[GeneratedStorySeed]:
    resolved_rng = rng or Random()
    generated_at = _timestamp(now)
    is_chinese = language.casefold().startswith("zh")
    seeds = [
        GeneratedStorySeed(
            bucket_id=bucket_id,
            slug=slug,
            seed=seed_zh if is_chinese else seed_en,
            generated_at=generated_at,
        )
        for bucket_id, slug, seed_en, seed_zh in _SEED_BUCKETS
    ]
    normalized_count = max(1, min(int(story_count), len(seeds)))
    if normalized_count >= len(seeds):
        return seeds
    return sorted(resolved_rng.sample(seeds, k=normalized_count), key=lambda item: item.bucket_id)

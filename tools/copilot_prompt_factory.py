from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Literal


PromptLanguage = Literal["en", "zh"]
PromptFamily = Literal[
    "story_frame_emphasis",
    "political_texture",
    "protagonist_pressure_style",
    "cast_texture",
    "beat_pressure_shape",
    "truth_exposure_emphasis",
    "ending_tilt",
    "rule_semantics_emphasis",
]

_PROMPT_FAMILIES: tuple[PromptFamily, ...] = (
    "story_frame_emphasis",
    "political_texture",
    "protagonist_pressure_style",
    "cast_texture",
    "beat_pressure_shape",
    "truth_exposure_emphasis",
    "ending_tilt",
    "rule_semantics_emphasis",
)


@dataclass(frozen=True)
class GeneratedCopilotPrompt:
    prompt_id: str
    language: PromptLanguage
    prompt_text: str
    families: list[PromptFamily]


def _family_fragment(language: PromptLanguage, family: PromptFamily, rng: Random) -> str:
    if language == "zh":
        zh_fragments: dict[PromptFamily, tuple[str, ...]] = {
            "story_frame_emphasis": (
                "把世界规则写得更鲜明，强调公开记录会反过来塑造整场局势。",
                "让故事框架更明确地围绕世界规则和公共合法性运转。",
                "强化世界规则，让记录、规章和公开叙事真正影响故事走向。",
            ),
            "political_texture": (
                "强化政治拉扯，让派系、联盟和公开问责都更明显。",
                "让整部故事更有政治肌理，而不是只是程序流程。",
                "把局势推向更明确的派系博弈与公共权力冲突。",
            ),
            "protagonist_pressure_style": (
                "把主角写得更强硬，更敢当众逼人表态。",
                "让主角更像一个别人绕不过去的程序锚点。",
                "让主角在公开场合更直接、更能制造压力。",
            ),
            "cast_texture": (
                "把角色关系写得更尖锐，别让配角都显得太中性。",
                "让配角更像彼此牵制的派系节点，而不是平铺的职能角色。",
                "让 cast 的立场张力更强，关系更容易互相咬合。",
            ),
            "beat_pressure_shape": (
                "让节拍推进更强调公开压力与持续升级。",
                "让前两幕更像一连串被逼到公开对照和解释的压力链。",
                "让节拍反馈更有代价感，不要只是平铺推进。",
            ),
            "truth_exposure_emphasis": (
                "强化公开记录曝光，让账本、名册和证词更像真正的压力源。",
                "让真相揭露更围绕被篡改的记录与证据链展开。",
                "把记录曝光写成推动局势变化的核心手段。",
            ),
            "ending_tilt": (
                "让第三幕更偏惨胜，让代价更可见。",
                "把结局往更有公共代价的方向推，但别改变玩法轮廓。",
                "让结局更像带着损伤的稳定，而不是干净收束。",
            ),
            "rule_semantics_emphasis": (
                "强化玩法语义，让曝光路线和公开问责更值得走。",
                "让 route 与 ending 规则更明确地奖励记录曝光和公共解释。",
                "把 rule semantics 调成更偏向揭露、问责和代价结算。",
            ),
        }
        return rng.choice(zh_fragments[family])

    en_fragments: dict[PromptFamily, tuple[str, ...]] = {
        "story_frame_emphasis": (
            "Broaden the world rules so public records and civic legitimacy shape the whole draft more explicitly.",
            "Make the story frame lean harder on world rules and visible civic constraints.",
            "Strengthen the story frame so records, procedure, and legitimacy feel structurally important.",
        ),
        "political_texture": (
            "Push the political texture toward sharper factional pressure and public accountability.",
            "Make the draft feel more politically charged and less purely procedural.",
            "Lean into coalition strain, public bargaining, and visible power struggle.",
        ),
        "protagonist_pressure_style": (
            "Make the protagonist more assertive in public-facing pressure.",
            "Make the protagonist feel more procedurally hard to maneuver around.",
            "Push the protagonist toward sharper direct confrontation when the fiction supports it.",
        ),
        "cast_texture": (
            "Sharpen the cast relationships so the supporting roles feel less neutral and more frictional.",
            "Make the cast read more like competing factions than parallel institutions.",
            "Give the cast more tension, leverage, and mutually constraining agendas.",
        ),
        "beat_pressure_shape": (
            "Make the beat progression feel more like a public pressure chain with escalation.",
            "Shape the beats so the opening acts build a stronger reveal-and-escalation rhythm.",
            "Add more visible civic cost and pressure to the beat flow without changing beat count.",
        ),
        "truth_exposure_emphasis": (
            "Push the rewrite toward public-record exposure and ledger-based truth pressure.",
            "Make truth exposure rely more on altered records, witness chains, and public comparison.",
            "Turn record exposure into a more central engine for the story.",
        ),
        "ending_tilt": (
            "Push the third act toward a more pyrrhic outcome with visible public cost.",
            "Make the ending harsher and more visibly costly without changing the runtime lane.",
            "Tilt the ending toward costly stabilization rather than clean closure.",
        ),
        "rule_semantics_emphasis": (
            "Make the route and ending semantics reward exposure and public accountability more clearly.",
            "Strengthen rule semantics around reveal routes, accountability, and costly settlement.",
            "Push the gameplay semantics toward exposure-first routes and visible civic tradeoffs.",
        ),
    }
    return rng.choice(en_fragments[family])


def build_copilot_prompt_batch(
    *,
    rng: Random | None = None,
    language: PromptLanguage = "en",
    prompt_count: int = 40,
) -> list[GeneratedCopilotPrompt]:
    resolved_rng = rng or Random()
    normalized_count = max(1, int(prompt_count))
    prompts: list[GeneratedCopilotPrompt] = []
    for index in range(normalized_count):
        family_count = resolved_rng.randint(1, 3)
        families = sorted(resolved_rng.sample(list(_PROMPT_FAMILIES), k=family_count))
        fragments = [_family_fragment(language, family, resolved_rng) for family in families]
        prompt_text = " ".join(fragments)
        prompts.append(
            GeneratedCopilotPrompt(
                prompt_id=f"{language}_prompt_{index + 1:03d}",
                language=language,
                prompt_text=prompt_text,
                families=families,
            )
        )
    return prompts

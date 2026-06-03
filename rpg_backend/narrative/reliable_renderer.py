from __future__ import annotations

import re

from rpg_backend.author.normalize import normalize_whitespace
from rpg_backend.narrative.contracts import (
    AgentPlan,
    CastMember,
    FailureCondition,
    NarrativeTemplate,
    NPCLeverageOverNPC,
    NPCPulse,
    PlayedLeverageCard,
    PlayerGoal,
    PlayerLeverageOverNPC,
    PlayerRole,
    StoryBrief,
    StoryMessage,
    StoryOption,
)
from rpg_backend.narrative.engine import OpeningResult, TurnResult, build_agent_plan
from rpg_backend.narrative.profile_vocabulary import reliable_profile_vocabulary


def render_reliable_turn(
    *,
    template: NarrativeTemplate,
    history: list[StoryMessage],
    player_action: str,
    next_ord: int,
    turn_index: int,
    turn_budget: int,
    difficulty: str,
    player_role: PlayerRole | None,
    current_inventory: list[str] | None,
    played_leverage: PlayedLeverageCard | None,
) -> TurnResult:
    """Small deterministic narrator beat for beta/reviewer continuity.

    This only runs when the live narrator gateway cannot be called or returns
    unusable data. It keeps the scene playable without presenting itself as a
    full model-authored turn.
    """
    agent_plan = build_agent_plan(
        cast=template.cast,
        history=history,
        turn_index=turn_index,
        turn_budget=turn_budget,
        difficulty=difficulty,
        player_role=player_role,
        current_inventory=current_inventory,
        played_leverage=played_leverage,
        narrator_ord=next_ord,
    )
    profile = infer_template_tension_profile(template)
    pulses = _fallback_turn_pulses(
        template=template,
        agent_plan=agent_plan,
        played_leverage=played_leverage,
        profile=profile,
    )
    passage = _fallback_turn_passage(
        template=template,
        player_action=player_action,
        agent_plan=agent_plan,
        pulses=pulses,
        profile=profile,
    )
    return TurnResult(
        narrator_message=StoryMessage(
            ord=next_ord,
            role="narrator",
            content=passage,
            options=_fallback_turn_options(template, profile),
            chosen_option_index=None,
            npc_pulse=pulses,
            inventory_delta=None,
        ),
        agent_plan=agent_plan,
    )


def infer_template_tension_profile(template: NarrativeTemplate) -> str:
    text = " ".join(
        [
            getattr(template, "seed", ""),
            getattr(template, "title", ""),
            getattr(template, "opening_passage", ""),
        ]
    ).casefold()
    fantasy_world_terms = (
        "fantasy",
        "dragon",
        "eclipse",
        "library",
        "spell",
        "magic",
        "star map",
        "cursed index",
        "ink sprites",
        "banished clan",
        "sky pirates",
        "oracle",
        "artifact",
    )
    has_fantasy_world = any(term in text for term in fantasy_world_terms)
    has_mars_comedy = "mars" in text and any(term in text for term in ("talent show", "comedy", "callback", "playful"))
    if has_fantasy_world and not has_mars_comedy:
        return "fantasy_sci_fi"
    if any(term in text for term in ("cozy", "bake sale", "cupcake", "recipe", "gentle mystery")):
        return "cozy_mystery"
    if any(term in text for term in ("comedy", "talent show", "callback", "misunderstanding", "playful")):
        return "comedy"
    if any(term in text for term in ("fantasy", "sci-fi", "science fiction", "dragon", "eclipse", "library", "mars", "colony")):
        return "fantasy_sci_fi"
    if any(term in text for term in ("family", "wedding", "parents", "dinner")):
        return "family_social"
    return "high_drama"


def _fallback_turn_pulses(
    *,
    template: NarrativeTemplate,
    agent_plan: AgentPlan,
    played_leverage: PlayedLeverageCard | None,
    profile: str,
) -> list[NPCPulse]:
    cast_by_id = {member.character_id: member for member in template.cast}
    candidate_ids: list[str] = []
    if played_leverage is not None and played_leverage.npc_id in cast_by_id:
        candidate_ids.append(played_leverage.npc_id)
    candidate_ids.extend(
        npc_id for npc_id in agent_plan.director.active_npc_ids if npc_id in cast_by_id
    )
    candidate_ids.extend(
        npc_id for npc_id in agent_plan.director.focus_window_npc_ids if npc_id in cast_by_id
    )
    if not candidate_ids:
        candidate_ids = [member.character_id for member in template.cast[:2]]

    seen: set[str] = set()
    pulses: list[NPCPulse] = []
    for npc_id in candidate_ids:
        if npc_id in seen:
            continue
        seen.add(npc_id)
        member = cast_by_id[npc_id]
        pulses.append(
            NPCPulse(
                npc_id=npc_id,
                state=_fallback_turn_pulse_state(profile, played=played_leverage is not None and npc_id == played_leverage.npc_id),
                shift=_fallback_turn_pulse_shift(profile),
                reason=_fallback_turn_pulse_reason(profile),
            )
        )
        if len(pulses) >= 2:
            break
    return pulses


def _fallback_turn_pulse_state(profile: str, *, played: bool) -> str:
    if played:
        return "reacting to the shown card"
    return reliable_profile_vocabulary(profile).pulse_state


def _fallback_turn_pulse_shift(profile: str) -> str:
    return reliable_profile_vocabulary(profile).pulse_shift


def _fallback_turn_pulse_reason(profile: str) -> str:
    return reliable_profile_vocabulary(profile).pulse_reason


def _fallback_turn_passage(
    *,
    template: NarrativeTemplate,
    player_action: str,
    agent_plan: AgentPlan,
    pulses: list[NPCPulse],
    profile: str,
) -> str:
    scene = _fallback_turn_scene_label(template)
    names = _fallback_turn_names(template, pulses)
    first = names[0] if names else "the closest witness"
    second = names[1] if len(names) > 1 else "the room"
    first_subject = _fallback_sentence_start(first)
    action = _fallback_turn_action_phrase(player_action)
    after_action = _fallback_turn_after_phrase(action)
    stage_line = _fallback_turn_stage_line(agent_plan.director.stage_phase, profile)
    turn_variant = agent_plan.turn_index % 3
    object_label = _fallback_turn_object_label(template)
    fantasy_rule = _fallback_fantasy_rule_label(template)
    fantasy_sign = _fallback_fantasy_sign_label(template, object_label)
    if profile in {"cozy_mystery", "comedy"}:
        if turn_variant == 1:
            text = (
                f"After {after_action}, the {scene} pauses around the {object_label}. "
                f"{first_subject} {_fallback_verb(first, 'points', 'point')} to a small timing detail, and "
                f"{second} {_fallback_verb(second, 'keeps', 'keep')} the explanation light enough for repair. "
                f"{stage_line} The next move can check the timing trail, invite a quieter voice, or turn the table mistake into a payoff."
            )
        elif turn_variant == 2:
            object_verb = _fallback_verb(object_label, "becomes", "become")
            text = (
                f"The {object_label} {object_verb} easier to read after {after_action}. "
                f"{first_subject} {_fallback_verb(first, 'softens', 'soften')} first, while {second} "
                f"{_fallback_verb(second, 'notices', 'notice')} who is still hesitating. "
                f"{stage_line} The next beat can compare versions gently or let the room laugh before blame settles."
            )
        else:
            text = (
                f"The {scene} shifts after {after_action}. {first_subject} {_fallback_verb(first, 'catches', 'catch')} the detail first, "
                f"and {second} {_fallback_verb(second, 'leaves', 'leave')} room for a less dramatic explanation instead of "
                f"turning the moment into a pile-on. {stage_line} The next beat can test "
                f"the {object_label}, invite the quiet party in, or let the callback land before "
                f"anyone chooses a version of events."
            )
    elif profile == "fantasy_sci_fi":
        if turn_variant == 1:
            text = (
                f"After {after_action}, the {object_label} draws the {scene} inward. "
                f"{first_subject} {_fallback_verb(first, 'reads', 'read')} how the {fantasy_sign} changes the stacks, while {second} "
                f"{_fallback_verb(second, 'tests', 'test')} which {fantasy_rule} still holds. "
                f"{stage_line} The next beat can ask a quieter faction to interpret the eclipse mark."
            )
        elif turn_variant == 2:
            text = (
                f"The {scene} gives back a clearer {fantasy_sign} after {after_action}. "
                f"{first_subject} {_fallback_verb(first, 'moves', 'move')} toward the {object_label}, and {second} "
                f"{_fallback_verb(second, 'tracks', 'track')} the faction claim behind it. "
                f"{stage_line} The next beat can place the artifact under the eclipse light where every faction can answer."
            )
        else:
            text = (
                f"The {scene} answers after {after_action}. {first_subject} {_fallback_verb(first, 'turns', 'turn')} toward the {fantasy_sign}, "
                f"while {second} {_fallback_verb(second, 'notices', 'notice')} which artifact or faction moved in the margins. "
                f"{stage_line} The next beat can question the change, share the eclipse mark with a quieter party, "
                f"or hold the {object_label} where everyone can read it."
            )
    elif profile == "family_social":
        text = (
            f"The {scene} quiets after {after_action}. {first_subject} {_fallback_verb(first, 'reacts', 'react')} first, and {second} "
            f"{_fallback_verb(second, 'starts', 'start')} weighing whether this is an old wound or a repairable mistake. "
            f"{stage_line} The next beat can ask for the missing context, protect a "
            f"fragile bond, or let someone else speak before the room hardens."
        )
    else:
        text = (
            f"The {scene} absorbs {action}. {first_subject} {_fallback_verb(first, 'recalculates', 'recalculate')} in public, and "
            f"{second} {_fallback_verb(second, 'watches', 'watch')} who benefits from the new version of events. "
            f"{stage_line} The next beat can press for a concrete answer, place one "
            f"fact on the table, or wait for the next stakeholder to reveal their stake."
        )
    return normalize_whitespace(text)


def _fallback_turn_object_label(template: NarrativeTemplate) -> str:
    seed = template.seed.casefold()
    if "cupcake labels" in seed:
        return "cupcake labels"
    if "recipe card" in seed:
        return "recipe card"
    if "star map" in seed:
        return "star map"
    if "cursed index" in seed:
        return "cursed index"
    if "oxygen" in seed:
        return "oxygen rumor"
    if "talent show" in seed:
        return "talent-show cue"
    if "cupcake" in seed:
        return "cupcake clue"
    if "prop" in seed:
        return "shared prop"
    if "artifact" in seed:
        return "artifact"
    return "visible detail"


def _fallback_fantasy_rule_label(template: NarrativeTemplate) -> str:
    text = " ".join([template.seed, template.title, template.opening_passage]).casefold()
    if "eclipse" in text and "library" in text:
        return "eclipse rule"
    if "star map" in text:
        return "star-map rule"
    if "cursed index" in text:
        return "index rule"
    return "world rule"


def _fallback_fantasy_sign_label(template: NarrativeTemplate, object_label: str) -> str:
    text = " ".join([template.seed, template.title, template.opening_passage]).casefold()
    if "eclipse" in text and "library" in text:
        return "eclipse mark"
    if "star map" in text:
        return "star-map sign"
    if "cursed index" in text:
        return "index mark"
    if object_label and object_label != "visible detail":
        return f"{object_label} sign"
    return "world sign"


def _fallback_turn_scene_label(template: NarrativeTemplate) -> str:
    text = " ".join([template.seed, template.title, template.opening_passage]).casefold()
    if "mars" in text and "talent show" in text:
        return "Mars colony talent-show floor"
    if "bake sale" in text or "cupcake" in text:
        return "neighborhood bake-sale table"
    if "eclipse" in text and "library" in text:
        return "eclipse-lit library"
    if "library" in text:
        return "library hall"
    if "board" in text or "vote" in text:
        return "boardroom"
    if "dinner" in text:
        return "family table"
    return "room"


def _fallback_turn_names(template: NarrativeTemplate, pulses: list[NPCPulse]) -> list[str]:
    cast_by_id = {member.character_id: member for member in template.cast}
    names = [
        cast_by_id[pulse.npc_id].display_name
        for pulse in pulses
        if pulse.npc_id in cast_by_id
    ]
    if len(names) < 2:
        for member in template.cast:
            if member.display_name not in names:
                names.append(member.display_name)
            if len(names) >= 2:
                break
    return names


def _fallback_name_is_plural(name: str) -> bool:
    lower = name.strip().casefold()
    if not lower or lower in {"the room", "the boardroom", "the family table"}:
        return False
    if lower in {"hydroponics", "communications", "finance", "transit", "medical", "education", "security"}:
        return False
    if any(token in lower for token in (" and ", ",", "&")):
        return True
    last = re.sub(r"[^a-z]+", "", lower.split()[-1]) if lower.split() else lower
    if last.endswith(("ss", "us")):
        return False
    return last.endswith("s")


def _fallback_verb(name: str, singular: str, plural: str) -> str:
    return plural if _fallback_name_is_plural(name) else singular


def _fallback_turn_action_phrase(player_action: str) -> str:
    text = normalize_whitespace(re.sub(r"^\[[^\]]+\]\s*", "", player_action or "your move"))
    if not text:
        return "your move"
    if len(text) > 120:
        text = f"{text[:117].rstrip()}..."
    if text[:1].isupper() and " " in text[:40]:
        text = text[:1].lower() + text[1:]
    return f"your move to {text}" if not text.startswith("your ") else text


def _fallback_turn_after_phrase(action_phrase: str) -> str:
    if action_phrase.startswith("your move to "):
        return f"you {action_phrase.removeprefix('your move to ')}"
    if action_phrase.startswith("your move"):
        return "your move"
    return action_phrase


def _fallback_turn_stage_line(stage_phase: str, profile: str) -> str:
    return reliable_profile_vocabulary(profile).stage_line(stage_phase)


def _fallback_turn_options(template: NarrativeTemplate, profile: str) -> list[StoryOption]:
    object_label = _fallback_turn_object_label(template)
    if profile == "cozy_mystery":
        return [
            StoryOption(label=f"[Ally] Let the shy witness describe the {object_label}", hint="Keeps the mystery gentle", handle="ask witness"),
            StoryOption(label=f"[Probe] Check the {object_label} without blaming anyone", hint="Tests the clue first", handle="check clue"),
            StoryOption(label="[Watch] Give the room a softer reset", hint="Buys a calmer beat", handle="soft reset"),
        ]
    if profile == "comedy":
        return [
            StoryOption(label="[Ally] Invite the overlooked group into the test", hint="Keeps the joke shared", handle="invite group"),
            StoryOption(label=f"[Probe] Ask who noticed the {object_label} change", hint="Turns timing into evidence", handle="ask prop"),
            StoryOption(label="[Watch] Let the callback settle before moving", hint="Waits for the room to react", handle="let land"),
        ]
    if profile == "fantasy_sci_fi":
        if "eclipse" in template.seed.casefold() and "library" in template.seed.casefold():
            return [
                StoryOption(label="[Probe] Ask what the eclipse changed in the stacks", hint="Turns the mark into a clue", handle="ask rule"),
                StoryOption(label="[Ally] Let the quieter faction read the eclipse mark", hint="Gives background pressure a voice", handle="quiet voice"),
                StoryOption(label=f"[Watch] Hold the {object_label} under the eclipse light", hint="Keeps the room honest", handle="show object"),
            ]
        return [
            StoryOption(label="[Probe] Ask which old rule changed", hint="Turns the sign into a clue", handle="ask rule"),
            StoryOption(label="[Ally] Let the quieter faction interpret the sign", hint="Gives background pressure a voice", handle="quiet voice"),
            StoryOption(label=f"[Watch] Hold the {object_label} where everyone can see it", hint="Keeps the room honest", handle="show object"),
        ]
    if profile == "family_social":
        return [
            StoryOption(label="[Ally] Give the hurt party room to explain", hint="Protects repair before rupture", handle="give room"),
            StoryOption(label="[Probe] Ask what was misunderstood first", hint="Looks for the old wound", handle="ask wound"),
            StoryOption(label="[Watch] Let someone else name the cost", hint="Tests who still cares", handle="wait cost"),
        ]
    return [
        StoryOption(label="[Probe] Ask who benefits from this version", hint="Tests the public account", handle="ask benefit"),
        StoryOption(label="[Counter] Put one concrete fact on the table", hint="Makes the room answer", handle="show fact"),
        StoryOption(label="[Watch] Let the next speaker expose their stake", hint="Delays without yielding", handle="watch stake"),
    ]


def render_reliable_opening(brief: StoryBrief, *, language: str) -> OpeningResult:
    """Deterministic repair opening used only after LLM brief generation fails.

    It preserves the reviewed brief contract instead of silently relaxing user
    constraints. The result is intentionally plain but playable.
    """
    del language
    primary_entities = [
        entity
        for entity in brief.cast_plan.primary_active_entities
        if entity.kind in {"character", "faction", "object"}
    ]
    if len(primary_entities) < 3:
        primary_entities = [
            entity
            for entity in [*brief.cast_plan.primary_active_entities, *brief.cast_plan.secondary_background_entities]
            if entity.kind in {"character", "faction", "object"}
        ]
    cast_names = [entity.display_name for entity in primary_entities[:5]]
    if len(cast_names) < 3:
        cast_names = ["Organizer", "Concerned witness", "Deadline holder", "Outside voice"]
    background_names = [
        entity.display_name
        for entity in brief.cast_plan.secondary_background_entities
        if entity.display_name not in cast_names
    ]
    protected_background_names = {
        entity.display_name
        for entity in brief.cast_plan.secondary_background_entities
        if "explicitly emphasized" in entity.rationale.casefold()
    }
    cast = _fallback_cast_members(
        cast_names,
        background_names=background_names,
        protected_background_names=protected_background_names,
    )
    pressure_labels = _fallback_pressure_labels(brief)
    opening_text = _fallback_opening_passage(
        brief=brief,
        cast_names=_fallback_opening_focus_names(cast_names),
        background_names=background_names,
        protected_background_names=protected_background_names,
        pressure_labels=pressure_labels,
    )
    options = _fallback_opening_options(brief)
    player_roles = _fallback_player_roles(brief, cast[: len(cast_names)])
    return OpeningResult(
        title=_fallback_title(brief, pressure_labels),
        advisor_persona="A careful advisor watches who is heard, what pressure is visible, and how the tone stays on track.",
        cast=cast,
        opening_message=StoryMessage(ord=0, role="narrator", content=opening_text, options=options),
        player_goals=[
            PlayerGoal(
                goal="Keep the key parties in the room before one side controls the first decision.",
                stakes="If a quiet party disappears, the opening turns into a generic argument.",
            ),
            PlayerGoal(
                goal="Create one concrete payoff that matches the selected profile.",
                stakes="The first exchange needs a clue, prop, decision, or callback that the next turn can use.",
            ),
        ],
        failure_conditions=[
            FailureCondition(
                label="One-sided room",
                description="Several turns pass while important parties remain invisible or unheard.",
            ),
            FailureCondition(
                label="No payoff",
                description="The room circles the premise without a visible clue, prop, decision, or callback.",
            ),
        ],
        player_role_options=player_roles,
    )


def _fallback_cast_members(
    names: list[str],
    *,
    background_names: list[str] | None = None,
    protected_background_names: set[str] | None = None,
) -> list[CastMember]:
    all_names = [*names, *(background_names or [])[: max(0, 10 - len(names))]]
    ids = [_fallback_slug(name) or f"party_{idx + 1}" for idx, name in enumerate(all_names)]
    protected = protected_background_names or set()
    cast: list[CastMember] = []
    for idx, name in enumerate(all_names):
        target_ids = [target_id for target_id in ids if target_id != ids[idx]][:2]
        is_background = idx >= len(names)
        is_protected_background = is_background and name in protected
        cast.append(
            CastMember(
                character_id=ids[idx],
                display_name=_fallback_label(name, limit=40),
                role=(
                    "Protected background stakeholder"
                    if is_protected_background
                    else "Background stakeholder"
                    if is_background
                    else "Involved party"
                ),
                relation_to_protagonist=(
                    "Protected context the prompt emphasized; kept visible outside the active focus window."
                    if is_protected_background
                    else
                    "Visible context kept in the room for later turns."
                    if is_background
                    else "A party whose reaction can shift the next choice."
                ),
                hidden_objective=(
                    None
                    if is_background
                    else f"Make sure {name[:70]} is heard before the decision lands."
                ),
                leverage_over_player=None if is_background else "Knows which detail the room keeps avoiding.",
                leverages_over_other_npcs=[] if is_background else [
                    NPCLeverageOverNPC(
                        target_npc_id=target_id,
                        leverage="Can point to the missing detail that changes who gets heard.",
                    )
                    for target_id in target_ids
                ],
            )
        )
    return cast


def _fallback_player_roles(brief: StoryBrief, cast: list[CastMember]) -> list[PlayerRole]:
    role_names = _fallback_role_names(brief)
    object_label = _fallback_contested_object(brief.original_seed)
    roles: list[PlayerRole] = []
    for idx, role_name in enumerate(role_names):
        target = cast[idx % len(cast)]
        roles.append(
            PlayerRole(
                role_id=_fallback_slug(role_name)[:32] or f"role_{idx + 1}",
                label=_fallback_label(role_name, limit=24),
                public_persona=_fallback_role_persona(role_name, brief, object_label),
                hidden_objective=_fallback_role_objective(brief, object_label),
                leverages_over_npcs=[
                    PlayerLeverageOverNPC(
                        npc_id=target.character_id,
                        leverage=_fallback_role_leverage(target.display_name, brief, object_label),
                    )
                ],
                starting_assets=[_fallback_label(_fallback_starting_asset(brief, object_label), limit=80)],
            )
        )
    return roles


def _fallback_role_names(brief: StoryBrief) -> list[str]:
    seed = brief.original_seed.casefold()
    if "bake sale" in seed or "cupcake" in seed:
        return ["Label checker", "Bake-sale host", "Volunteer ally"]
    if "mars" in seed and "talent show" in seed:
        return ["Talent-show liaison", "Rumor handler", "Audience mediator"]
    if "eclipse" in seed and "library" in seed:
        return ["Star-map witness", "Eclipse steward", "Spellbook ally"]
    if brief.tension_profile == "cozy_mystery":
        return ["Clue keeper", "Gentle witness", "Calm host"]
    if brief.tension_profile == "comedy":
        return ["Callback keeper", "Timing witness", "Audience ally"]
    if brief.tension_profile == "fantasy_sci_fi":
        return ["Artifact witness", "Faction go-between", "Rule steward"]
    return ["Room mediator", "Scene witness", "Pressure holder"]


def _fallback_role_persona(role_name: str, brief: StoryBrief, object_label: str) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return f"You are the {role_name.lower()} watching how the {object_label} changes the room's old rules."
    if brief.tension_profile in {"cozy_mystery", "comedy"}:
        return f"You are the {role_name.lower()} keeping the {object_label} concrete without turning the room against anyone."
    return f"You are the {role_name.lower()} trying to keep the exchange concrete and fair."


def _fallback_role_objective(brief: StoryBrief, object_label: str) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return f"Use the {object_label} to make the artifact, faction, or old rule visible before the room hardens."
    if brief.tension_profile in {"cozy_mystery", "comedy"}:
        return f"Use the {object_label} to create a payoff without blame taking over."
    return "Bring the quiet parties, pressure, and payoff into view before one side controls the room."


def _fallback_role_leverage(target_name: str, brief: StoryBrief, object_label: str) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return f"You noticed how the {object_label} points back to {target_name}'s faction or old rule."
    if brief.tension_profile in {"cozy_mystery", "comedy"}:
        return f"You noticed a harmless detail about the {object_label} that gives {target_name} a way to explain."
    return f"You know why {target_name} needs to be heard before the choice lands."


def _fallback_starting_asset(brief: StoryBrief, object_label: str) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return f"{brief.intervention_card_label}: {object_label} sign"
    if brief.tension_profile in {"cozy_mystery", "comedy"}:
        return f"{brief.intervention_card_label}: {object_label} note"
    return brief.intervention_card_label


def _fallback_opening_passage(
    *,
    brief: StoryBrief,
    cast_names: list[str],
    background_names: list[str],
    protected_background_names: set[str] | None = None,
    pressure_labels: list[str],
) -> str:
    active_cast_names, context_names = _fallback_opening_name_groups(
        cast_names,
        background_names,
        protected_background_names=protected_background_names or set(),
    )
    cast_text = _fallback_names_text(active_cast_names)
    cast_text_mid_sentence = _fallback_names_text(active_cast_names, sentence_start=False)
    seed = brief.original_seed
    scene = _fallback_scene_label(brief, pressure_labels)
    contested = _fallback_contested_object(seed)
    secondary_event = _fallback_secondary_event_clause(pressure_labels, scene)
    background_text = _fallback_background_sentence(context_names, brief=brief)
    profile_clause = _fallback_profile_clause(brief, contested=contested)
    first_move = _fallback_first_move_clause(brief)
    if _fallback_uses_fantasy_scene(brief):
        return (
            f"In {scene}, {_fallback_contested_status(contested)} just as {_fallback_event_phrase(pressure_labels)} starts to matter{secondary_event}. "
            f"{cast_text} {_fallback_verb(cast_text, 'is', 'are')} trying to read what the old rule means now.{background_text} "
            f"{profile_clause} {first_move}"
        )
    if brief.tension_profile in {"comedy", "cozy_mystery"}:
        uncertainty = reliable_profile_vocabulary(brief.tension_profile).opening_uncertainty
        return (
            f"At {scene}, the {contested} {_fallback_verb(contested, 'has', 'have')} pulled {cast_text_mid_sentence} into the same public moment while the room is still deciding "
            f"{uncertainty}{secondary_event}.{background_text} "
            f"{profile_clause} {first_move}"
        )
    return (
        f"At {scene}, {cast_text} are already circling the {contested}, each trying to make the first public account stick{secondary_event}."
        f"{background_text} {profile_clause} {first_move}"
    )


def _fallback_opening_name_groups(
    cast_names: list[str],
    background_names: list[str],
    *,
    protected_background_names: set[str],
) -> tuple[list[str], list[str]]:
    active_limit = 3 if len(cast_names) > 4 else 5
    active = cast_names[:active_limit]
    ordered_background_names = sorted(
        [*cast_names[active_limit:], *background_names],
        key=lambda name: (0 if name in protected_background_names else 1, name.casefold()),
    )
    seen: set[str] = set()
    background: list[str] = []
    for name in ordered_background_names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        background.append(name)
    return active or cast_names[:5] or ["the key parties"], background


def _fallback_scene_label(brief: StoryBrief, pressure_labels: list[str]) -> str:
    seed = brief.original_seed.lower()
    event = _fallback_event_label(pressure_labels)
    setting = _fallback_setting_label(brief, pressure_labels)
    if "mars" in seed and event and "talent show" in event.lower():
        return "the Mars colony talent show"
    if "bake sale" in seed:
        return "the neighborhood bake sale" if "neighborhood" in seed else "the bake sale"
    if "floating dragon library" in seed:
        return "the floating dragon library"
    if "library" in seed:
        return "the library"
    if setting and event and setting.lower() not in event.lower():
        return f"the {setting} {event}"
    if event:
        return f"the {event}"
    if setting:
        return f"the {setting}"
    return "the public room"


def _fallback_setting_label(brief: StoryBrief, pressure_labels: list[str]) -> str:
    labels = [
        label
        for label in [*[item.label for item in brief.world_setting_pressure], *pressure_labels]
        if any(token in label.lower() for token in ("mars", "colony", "library", "school", "sale", "setting"))
    ]
    if not labels:
        return ""
    label = labels[0]
    if label.lower() == "library setting":
        return "library"
    return label


def _fallback_event_label(pressure_labels: list[str]) -> str:
    setting_terms = ("mars", "colony", "library", "school", "setting")
    for label in pressure_labels:
        lower = label.lower()
        if not any(token in lower for token in setting_terms):
            return label
    return ""


def _fallback_event_phrase(pressure_labels: list[str]) -> str:
    event = _fallback_event_label(pressure_labels)
    if event:
        return f"the {event}"
    return "the deadline"


def _fallback_secondary_event_clause(pressure_labels: list[str], scene: str) -> str:
    scene_lower = scene.lower()
    primary = _fallback_event_label(pressure_labels).lower()
    setting_terms = ("mars", "colony", "library", "school", "sale", "setting")
    for label in pressure_labels:
        lower = label.lower()
        if any(token in lower for token in setting_terms):
            continue
        if lower and lower not in scene_lower and lower != primary:
            return f" before the {label}"
    return ""


def _fallback_contested_object(seed: str) -> str:
    lower = seed.lower()
    if "recipe card" in lower:
        return "missing recipe card"
    if "star map" in lower:
        return "missing star map"
    if "stealing oxygen" in lower or "stolen oxygen" in lower:
        return "oxygen rumor"
    if "missing cupcake" in lower:
        return "missing cupcake"
    if "prop" in lower:
        return "shared prop"
    phrase_patterns = [
        r"\bmissing\s+([a-z][a-z\s-]{2,60}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
        r"\bstolen\s+([a-z][a-z\s-]{2,60}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
        r"\bstealing\s+([a-z][a-z\s-]{2,60}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
        r"\bswapped\s+([a-z][a-z\s-]{2,60}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
        r"\bsame\s+([a-z][a-z\s-]{2,40}?)(?:\s+before|\s+during|\s+at|\s+with|[,.!:;]|$)",
    ]
    for pattern in phrase_patterns:
        match = re.search(pattern, lower)
        if match:
            return _fallback_object_label(match.group(1))
    if "oxygen" in lower:
        return "oxygen rumor"
    if "cupcake" in lower:
        return "cupcake mix-up"
    return "contested detail"


def _fallback_object_label(value: str) -> str:
    text = normalize_whitespace(value).strip(" -—:;,.!?")
    stop_phrases = (
        "with no",
        "with lower",
        "only misunderstandings",
        "keep it",
        "no violence",
        "no blackmail",
        "no betrayal",
    )
    lower = text.lower()
    for stop in stop_phrases:
        idx = lower.find(stop)
        if idx > 0:
            text = text[:idx].strip()
            lower = text.lower()
    text = re.sub(r"^(?:a|an|the)\s+", "", text, flags=re.I)
    lower = text.lower()
    words = text.split()
    if len(words) > 6:
        text = " ".join(words[:6])
    return text or "contested detail"


def _fallback_contested_status(contested: str) -> str:
    lower = contested.lower()
    if lower.startswith("missing "):
        return f"the {contested} is still unaccounted for"
    if lower.endswith("rumor"):
        return f"the {contested} is spreading"
    return f"the {contested} has become the room's hinge"


def _fallback_uses_fantasy_scene(brief: StoryBrief) -> bool:
    lower = " ".join(
        [
            brief.original_seed,
            brief.genre_tone,
            brief.story_kernel,
            *[item.label for item in brief.world_setting_pressure],
        ]
    ).lower()
    return any(token in lower for token in ("fantasy", "dragon", "spell", "magic", "library", "eclipse", "star map"))


def _fallback_background_sentence(background_names: list[str], *, brief: StoryBrief) -> str:
    visible_background_names = [
        name
        for name in background_names
        if not _fallback_is_scaffold_party_name(name)
    ]
    if not visible_background_names:
        return ""
    names = visible_background_names[:5]
    visible = _fallback_names_text(names)
    if brief.tension_profile == "comedy":
        return f" {visible} {_fallback_verb(visible, 'stays', 'stay')} close enough to react, heckle gently, or turn the next beat into a callback."
    if _fallback_uses_fantasy_scene(brief):
        return f" {visible} {_fallback_verb(visible, 'remains', 'remain')} at the edge of the stacks, close enough for one old rule or faction claim to matter."
    return f" {visible} {_fallback_verb(visible, 'stays', 'stay')} close enough to object, react, or pull one missing detail back into view."


def _fallback_names_text(names: list[str], *, sentence_start: bool = True) -> str:
    if not names:
        return ""
    display_names = [
        _fallback_sentence_start(name) if index == 0 and sentence_start else name
        for index, name in enumerate(names)
    ]
    if len(display_names) == 1:
        return display_names[0]
    if len(display_names) == 2:
        return f"{display_names[0]} and {display_names[1]}"
    return f"{', '.join(display_names[:-1])}, and {display_names[-1]}"


def _fallback_opening_focus_names(cast_names: list[str]) -> list[str]:
    focused = [
        name
        for name in cast_names
        if not _fallback_is_scaffold_party_name(name)
    ]
    if len(focused) >= 2:
        return focused[:5]
    return cast_names[:5] or ["the key parties"]


def _fallback_is_scaffold_party_name(name: str) -> bool:
    return name.strip().casefold() in {
        "player",
        "mix-up witness",
        "embarrassed helper",
        "deadline host",
        "deadline holder",
        "concerned witness",
        "outside voice",
        "organizer",
    }


def _fallback_sentence_start(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    return text[0].upper() + text[1:] if text[0].islower() else text


def _fallback_profile_clause(brief: StoryBrief, *, contested: str) -> str:
    if brief.tension_profile == "comedy":
        callback_verb = _fallback_verb(contested, "becomes", "become")
        return (
            f"The trouble stays social: timing, embarrassment, and whether the {contested} {callback_verb} a harmless callback "
            "instead of a culprit hunt."
        )
    if brief.tension_profile == "cozy_mystery":
        return (
            f"The trouble stays gentle and concrete: the {contested}, mixed signals, and a reveal that can repair trust "
            "instead of breaking it."
        )
    if brief.tension_profile == "fantasy_sci_fi":
        return (
            "A rule of the world is under strain, and the next choice will show whether the artifact, faction, or setting bends first."
        )
    if brief.tension_profile == "family_social":
        return "Old loyalties and misread intentions press against the room, but the first choice can still steer toward repair."
    return "The first choice will turn hidden pressure into a public shift."


def _fallback_first_move_clause(brief: StoryBrief) -> str:
    if _fallback_uses_fantasy_scene(brief):
        return reliable_profile_vocabulary("fantasy_sci_fi").first_move_clause
    return reliable_profile_vocabulary(brief.tension_profile).first_move_clause


def _fallback_opening_options(brief: StoryBrief) -> list[StoryOption]:
    seed = brief.original_seed.casefold()
    contested = _fallback_contested_object(brief.original_seed)
    background = _fallback_background_label(brief)
    fantasy_party = (
        _fallback_named_party(brief, "clan")
        or _fallback_named_party(brief, "sprites")
        or _fallback_named_party(brief, "spellbook")
        or background
    )
    volunteer = _fallback_named_party(brief, "volunteer") or "quiet witness"
    if _fallback_uses_fantasy_scene(brief):
        if "eclipse" in seed and "library" in seed:
            return [
                StoryOption(label=f"Ask what changed when the eclipse touched the {contested}", hint="Name the old rule", handle="rule"),
                StoryOption(label=f"Invite {fantasy_party} to interpret the sign", hint="Broaden the room", handle="faction"),
                StoryOption(label=f"Hold the {contested} where every faction can read it", hint="Find the hinge", handle="artifact"),
            ]
        return [
            StoryOption(label="Ask which old rule changed first", hint="Name the world pressure", handle="rule"),
            StoryOption(label=f"Invite {fantasy_party} to answer", hint="Broaden the room", handle="faction"),
            StoryOption(label=f"Inspect the {contested} everyone keeps avoiding", hint="Find the hinge", handle="artifact"),
        ]
    if brief.tension_profile == "comedy":
        if "mars" in seed and "talent show" in seed:
            return [
                StoryOption(label="Ask who last handled the talent-show cue", hint="Keep the comedy concrete", handle="ask_cue"),
                StoryOption(label=f"Invite {background} to answer from the side", hint="Keep background concerns visible", handle="invite_bg"),
                StoryOption(label="Turn the oxygen rumor into a shared callback", hint="Lower the stakes", handle="callback"),
            ]
        return [
            StoryOption(label=f"Ask what actually happened to the {contested}", hint="Keep it concrete", handle="ask_prop"),
            StoryOption(label="Give the quiet party a harmless way in", hint="Soften the room", handle="invite"),
            StoryOption(label="Turn the mistake into a callback", hint="Aim for payoff", handle="callback"),
        ]
    if brief.tension_profile == "cozy_mystery":
        return [
            StoryOption(label=f"Ask where the {contested} was last seen", hint="Follow the object", handle="ask_clue"),
            StoryOption(label=f"Let the {volunteer} explain the clue trail", hint="Lower worry", handle="witness"),
            StoryOption(label="Compare the table versions gently", hint="Repair trust", handle="compare"),
        ]
    return [
        StoryOption(label="Ask who is being left out", hint="Bring in a quiet party", handle="ask"),
        StoryOption(label="Name the pressure everyone is avoiding", hint="Focus the room", handle="name"),
        StoryOption(label="Invite the quiet party to speak", hint="Shift attention", handle="invite"),
    ]


def _fallback_background_label(brief: StoryBrief) -> str:
    for entity in brief.cast_plan.secondary_background_entities:
        if "explicitly emphasized" in entity.rationale.casefold() and entity.display_name:
            return entity.display_name
    for entity in brief.cast_plan.secondary_background_entities:
        if entity.display_name:
            return entity.display_name
    return "background group"


def _fallback_named_party(brief: StoryBrief, token: str) -> str:
    token_lower = token.casefold()
    for entity in [*brief.cast_plan.primary_active_entities, *brief.cast_plan.secondary_background_entities]:
        if token_lower in entity.display_name.casefold():
            return entity.display_name
    return ""


def _fallback_pressure_labels(brief: StoryBrief) -> list[str]:
    labels = [
        item.label
        for item in [*brief.time_event_anchors, *brief.world_setting_pressure]
        if item.label.lower() != "core premise"
    ]
    return labels[:5]


def _fallback_title(brief: StoryBrief, pressure_labels: list[str]) -> str:
    if pressure_labels:
        return _fallback_label(pressure_labels[0].title(), limit=120)
    return _fallback_label(f"{brief.tension_profile.replace('_', ' ').title()} First Scene", limit=120)


def _fallback_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:64]


def _fallback_label(value: str, *, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"

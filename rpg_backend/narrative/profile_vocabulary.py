from __future__ import annotations

from dataclasses import dataclass


_LATE_STAGE_PHASES = {"reversal", "climax", "pre_finale", "pre_finale_open"}


@dataclass(frozen=True)
class ReliableProfileVocabulary:
    """Player-facing vocabulary for deterministic reliable-path narration.

    This keeps tone/profile policy out of NarrativeService orchestration so the
    beta fallback can be polished without changing persistence or API flow.
    """

    pulse_state: str
    pulse_shift: str
    pulse_reason: str
    early_stage_line: str
    late_stage_line: str
    opening_uncertainty: str
    first_move_clause: str

    def stage_line(self, stage_phase: str) -> str:
        if stage_phase in _LATE_STAGE_PHASES:
            return self.late_stage_line
        return self.early_stage_line


_DEFAULT_VOCABULARY = ReliableProfileVocabulary(
    pulse_state="recalculating their public stance",
    pulse_shift="wary",
    pulse_reason="Your move changed the public account.",
    early_stage_line="The pressure stays visible enough that the room has to answer.",
    late_stage_line="The pressure stays visible enough that the room has to answer.",
    opening_uncertainty="whether one public account will control the room",
    first_move_clause="Your first move can bring in the quiet party before the loudest version hardens.",
)


_PROFILE_VOCABULARY: dict[str, ReliableProfileVocabulary] = {
    "cozy_mystery": ReliableProfileVocabulary(
        pulse_state="tracking the gentle clue",
        pulse_shift="warmer",
        pulse_reason="Your move kept the room curious.",
        early_stage_line="The tension stays public and gentle enough to keep moving.",
        late_stage_line="The social stakes rise, but they stay tied to clues, timing, and repair.",
        opening_uncertainty="whether this is a concrete clue, a harmless swap, or a nervous misunderstanding",
        first_move_clause="Your first move can follow a concrete clue, lower the room's worry, or give the nervous witness room to speak.",
    ),
    "comedy": ReliableProfileVocabulary(
        pulse_state="tracking the social cue",
        pulse_shift="warmer",
        pulse_reason="Your move kept the room curious.",
        early_stage_line="The tension stays public and playful enough to keep moving.",
        late_stage_line="The social stakes rise, but they stay tied to embarrassment, timing, and repair.",
        opening_uncertainty="whether this is timing trouble, a performance note, or a public embarrassment",
        first_move_clause="Your first move can name the harmless cue, invite the quiet voice in, or set up the joke before blame takes over.",
    ),
    "fantasy_sci_fi": ReliableProfileVocabulary(
        pulse_state="watching the rule shift",
        pulse_shift="wary",
        pulse_reason="Your move made the rule visible.",
        early_stage_line="The pressure comes from the old rule in view, not from sudden blame.",
        late_stage_line="The pressure comes from the old rule in view, not from sudden blame.",
        opening_uncertainty="what the old rule means now",
        first_move_clause="Your first move can test the rule, ask an overlooked faction to interpret the sign, or inspect the artifact everyone is avoiding.",
    ),
    "family_social": ReliableProfileVocabulary(
        pulse_state="weighing the loyalty test",
        pulse_shift="wary",
        pulse_reason="Your move tested the shared bond.",
        early_stage_line="The pressure stays personal, but nobody has to turn it into spectacle yet.",
        late_stage_line="The pressure stays personal, but nobody has to turn it into spectacle yet.",
        opening_uncertainty="whether this is an old wound or a repairable mistake",
        first_move_clause="Your first move can bring in the quiet party before the loudest version hardens.",
    ),
}


def reliable_profile_vocabulary(profile: str) -> ReliableProfileVocabulary:
    return _PROFILE_VOCABULARY.get(profile, _DEFAULT_VOCABULARY)

from rpg_backend.narrative.contracts import STORY_OPTION_LABEL_MAX_LENGTH
from rpg_backend.narrative.engine import _parse_branches, _parse_options


def test_parse_options_normalizes_chinese_intent_tags_for_english_templates() -> None:
    options = _parse_options(
        [
            {"label": "[反将] Show the burner phone feed", "hint": "Risk", "handle": "show feed"},
            {"label": "[挑拨] Signal Chen to stand up", "hint": "", "handle": "signal Chen"},
            {"label": "[妥协] Take the pen and sign", "hint": "", "handle": "sign"},
        ],
        language="en",
    )

    assert [o.label for o in options] == [
        "[Counter] Show the burner phone feed",
        "[Provoke] Signal Chen to stand up",
        "[Yield] Take the pen and sign",
    ]


def test_parse_options_normalizes_english_intent_tags_for_chinese_templates() -> None:
    options = _parse_options(
        [
            {"label": "[Counter] 亮出手机证据", "hint": "", "handle": "亮证据"},
            {"label": "[Probe] 试探董事态度", "hint": "", "handle": "试探"},
        ],
        language="zh",
    )

    assert [o.label for o in options] == [
        "[反将] 亮出手机证据",
        "[试探] 试探董事态度",
    ]


def test_parse_options_preserves_complete_english_action_labels() -> None:
    options = _parse_options(
        [
            {
                "label": "[Counter] Threaten to leak Chen's embezzlement evidence publicly at the podium",
                "hint": "High risk",
                "handle": "leak evidence",
            }
        ],
        language="en",
    )

    assert options[0].label == "[Counter] Threaten to leak Chen's embezzlement evidence publicly at the podium"
    assert len(options[0].label) <= STORY_OPTION_LABEL_MAX_LENGTH


def test_parse_options_clips_very_long_labels_at_word_boundary() -> None:
    options = _parse_options(
        [
            {
                "label": (
                    "[Counter] Threaten to leak Chen's embezzlement evidence publicly at the podium "
                    "while forcing the board chair to answer on camera before Jules can regain control"
                ),
                "hint": "High risk",
                "handle": "leak evidence",
            }
        ],
        language="en",
    )

    assert options[0].label == (
        "[Counter] Threaten to leak Chen's embezzlement evidence publicly at the podium "
        "while forcing the board chair to answer on..."
    )
    assert len(options[0].label) <= STORY_OPTION_LABEL_MAX_LENGTH


def test_parse_branches_drops_dangling_fragments_and_adds_punctuation() -> None:
    branches = _parse_branches(
        [
            {
                "pivot_beat_ord": 2,
                "chosen_path_summary": "You stalled",
                "alternate_path_summary": "This path leads to...",
                "alternate_ending_label": "和解",
                "rationale": "This path leads to...",
            },
            {
                "pivot_beat_ord": 4,
                "chosen_path_summary": "You exposed the forged note",
                "alternate_path_summary": "You apologized before naming the thief",
                "alternate_ending_label": "和解",
                "rationale": "That softer move would likely keep the room from splitting",
            },
        ],
        valid_ords={2, 4},
        actual_ending_label="夺回",
    )

    assert len(branches) == 1
    assert branches[0].pivot_beat_ord == 4
    assert branches[0].chosen_path_summary.endswith(".")
    assert branches[0].alternate_path_summary.endswith(".")
    assert branches[0].rationale.endswith(".")

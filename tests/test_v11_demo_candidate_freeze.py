from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_v11_completed_play_payoff_has_scroll_focus_contract() -> None:
    play_page = _read("frontend2/src/pages/play/play-page.tsx")

    assert 'data-play-ending-payoff="true"' in play_page
    assert "endingPayoffRef" in play_page
    assert "previousCompletionKeyRef" in play_page
    assert "scrollToPayoff" in play_page
    assert "target.focus({ preventScroll: true })" in play_page
    assert "root.scrollTo" in play_page
    assert "scrollMarginTop" in play_page


def test_v11_replay_private_title_and_entity_display_contract() -> None:
    replay_page = _read("frontend2/src/pages/replay/replay-page.tsx")
    i18n = _read("frontend2/src/shared/lib/i18n.ts")

    assert "function replayDisplayTitle" in replay_page
    assert "replay.private_completed_title" in replay_page
    assert "replay.private_in_progress_title" in replay_page
    assert "replaySeedText ? <p" in replay_page
    assert '<h1 style={rpStyles.title}>{replayTitle}</h1>' in replay_page
    assert "function replayDisplayNameForEntity" in replay_page
    assert "function replayHumanizeEntityId" in replay_page
    assert "replayNormalizeEntityKey(displayName)" in replay_page
    assert 'castNameById[pulse.npc_id] ?? pulse.npc_id' not in replay_page
    assert '"replay.private_completed_title": "Shared {label} run"' in i18n
    assert '"replay.private_in_progress_title": "Shared run in progress"' in i18n

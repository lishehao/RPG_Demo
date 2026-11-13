from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_backend.config import get_settings
from rpg_backend.narrative.contracts import (
    AdvanceTurnRequest,
    AdvisorAskRequest,
    CreateTemplateRequest,
)
from rpg_backend.narrative.fake_gateway import FAKE_NARRATIVE_SEED, FakeNarrativeGateway
from rpg_backend.narrative.gateway import get_narrative_gateway
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService


DEFAULT_SEED = FAKE_NARRATIVE_SEED
DEFAULT_FIRST_TURN_INPUT = (
    "I ask the dean to read the ledger timestamp aloud before anyone can move the files."
)


@dataclass(frozen=True)
class NarrativeReleaseGateConfig:
    mode: Literal["fake", "live"]
    db_path: Path | None
    seed: str
    first_turn_input: str
    output_path: Path | None


def parse_args(argv: list[str] | None = None) -> NarrativeReleaseGateConfig:
    parser = argparse.ArgumentParser(
        description="Run the current narrative core release gate."
    )
    parser.add_argument("--mode", choices=("fake", "live"), default="fake")
    parser.add_argument("--db-path")
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--first-turn-input", default=DEFAULT_FIRST_TURN_INPUT)
    parser.add_argument("--output-path")
    args = parser.parse_args(argv)
    return NarrativeReleaseGateConfig(
        mode=args.mode,
        db_path=Path(args.db_path).expanduser().resolve() if args.db_path else None,
        seed=str(args.seed),
        first_turn_input=str(args.first_turn_input),
        output_path=Path(args.output_path).expanduser().resolve() if args.output_path else None,
    )


def _timed_step(summary: dict[str, Any], name: str, fn):
    started_at = time.perf_counter()
    result = fn()
    summary["steps"][name] = {"elapsed_seconds": round(time.perf_counter() - started_at, 3)}
    return result


def _build_service(config: NarrativeReleaseGateConfig, db_path: Path) -> tuple[NarrativeService, Any]:
    repo = NarrativeRepository(str(db_path))
    if config.mode == "fake":
        gateway = FakeNarrativeGateway()
    else:
        gateway = get_narrative_gateway(get_settings())
        if gateway is None:
            raise RuntimeError(
                "live mode requires APP_RESPONSES_PLAY_BASE_URL, APP_RESPONSES_PLAY_API_KEY, "
                "and APP_RESPONSES_PLAY_MODEL"
            )
    return NarrativeService(repository=repo, gateway=gateway), gateway


def run_release_gate(config: NarrativeReleaseGateConfig) -> dict[str, Any]:
    if config.db_path is None:
        with tempfile.TemporaryDirectory(prefix="tiny-stories-release-gate-") as tmpdir:
            return _run_release_gate_with_db(config, Path(tmpdir) / "narrative.sqlite3")
    return _run_release_gate_with_db(config, config.db_path)


def _run_release_gate_with_db(config: NarrativeReleaseGateConfig, db_path: Path) -> dict[str, Any]:
    service, gateway = _build_service(config, db_path)
    summary: dict[str, Any] = {
        "ok": False,
        "mode": config.mode,
        "db_path": str(db_path),
        "seed": config.seed,
        "steps": {},
        "ids": {},
        "contracts": {},
        "replay": {},
        "distribution": {},
        "llm_operations": [],
    }

    create_response = _timed_step(
        summary,
        "create_template",
        lambda: service.create_template(
            CreateTemplateRequest(
                seed=config.seed,
                visibility="public",
                turn_budget=4,
                difficulty="story",
                language="en",
            ),
            owner_user_id="release_owner",
        ),
    )
    template_id = create_response.template.template_id
    summary["ids"]["template_id"] = template_id
    summary["ids"]["owner_session_id"] = create_response.session.session_id
    summary["contracts"]["template_language_en"] = create_response.template.language == "en"
    summary["contracts"]["opening_has_three_options"] = len(create_response.opening.options) >= 3
    summary["contracts"]["role_cards_available"] = len(create_response.template.player_role_options) >= 3
    summary["contracts"]["public_template"] = create_response.template.visibility == "public"

    fork_response = _timed_step(
        summary,
        "start_fork_session",
        lambda: service.start_session(
            template_id,
            player_user_id="release_player",
            turn_budget=4,
            difficulty="story",
            player_role_index=1,
        ),
    )
    session_id = fork_response.session.session_id
    summary["ids"]["session_id"] = session_id
    summary["contracts"]["fork_keeps_template_id"] = fork_response.session.template_id == template_id
    summary["contracts"]["fork_session_is_distinct"] = session_id != create_response.session.session_id
    summary["contracts"]["fork_role_selected"] = fork_response.session.player_role is not None

    first_history = _timed_step(
        summary,
        "get_initial_history",
        lambda: service.get_story_history(session_id, player_user_id="release_player"),
    )
    summary["contracts"]["history_starts_with_opening"] = (
        len(first_history.messages) == 1 and first_history.messages[0].role == "narrator"
    )

    turn_requests = [
        AdvanceTurnRequest(free_input=config.first_turn_input, diary="Stay calm; make them read it."),
        AdvanceTurnRequest(chosen_option_index=1),
        AdvanceTurnRequest(chosen_option_index=0),
        AdvanceTurnRequest(free_input="I keep the recorder visible and ask each member to confirm the timestamp."),
    ]
    final_turn = None
    for index, request in enumerate(turn_requests, start=1):
        final_turn = _timed_step(
            summary,
            f"advance_turn_{index}",
            lambda request=request: service.advance(
                session_id,
                request,
                player_user_id="release_player",
            ),
        )
        if index == 2:
            advisor = _timed_step(
                summary,
                "ask_advisor",
                lambda: service.ask_advisor(
                    session_id,
                    AdvisorAskRequest(question="Is Hale stalling or looking for a way out?"),
                    player_user_id="release_player",
                ),
            )
            summary["contracts"]["advisor_replied"] = bool(advisor.advisor_message.content)
    assert final_turn is not None
    summary["contracts"]["final_turn_completed"] = final_turn.is_complete
    summary["contracts"]["final_turn_has_ending"] = final_turn.ending is not None

    ending = _timed_step(
        summary,
        "get_ending",
        lambda: service.get_session_ending(session_id, player_user_id="release_player"),
    )
    summary["contracts"]["ending_persisted"] = ending is not None
    if ending is not None:
        summary["contracts"]["ending_has_highlights"] = len(ending.highlights) >= 2
        summary["contracts"]["ending_has_branches"] = len(ending.branches) >= 2

    replay = _timed_step(summary, "get_public_replay", lambda: service.get_public_replay(session_id))
    summary["replay"] = {
        "completed": replay.completed,
        "message_count": len(replay.messages),
        "advisor_message_count": len(replay.advisor_messages),
        "ending_label": replay.ending.label if replay.ending else None,
        "highlight_count": len(replay.ending.highlights) if replay.ending else 0,
        "branch_count": len(replay.ending.branches) if replay.ending else 0,
    }
    summary["contracts"]["replay_has_template_id"] = replay.template_id == template_id
    summary["contracts"]["replay_completed"] = replay.completed
    summary["contracts"]["replay_has_story_and_advisor"] = (
        len(replay.messages) >= 9 and len(replay.advisor_messages) == 2
    )

    distribution = _timed_step(
        summary,
        "get_ending_distribution",
        lambda: service.get_ending_distribution(template_id, viewer_user_id="release_player"),
    )
    summary["distribution"] = {
        "total_completed": distribution.total_completed,
        "entries": [entry.model_dump() for entry in distribution.entries],
    }
    summary["contracts"]["distribution_counts_completed_run"] = distribution.total_completed == 1

    if hasattr(gateway, "calls"):
        summary["llm_operations"] = [str(call["operation_name"]) for call in gateway.calls]

    failed = [name for name, ok in summary["contracts"].items() if not ok]
    if failed:
        summary["failed_contracts"] = failed
        raise RuntimeError(f"narrative release gate failed contracts: {', '.join(failed)}")
    summary["ok"] = True
    return summary


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    payload = run_release_gate(config)
    if config.output_path is not None:
        write_output(config.output_path, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

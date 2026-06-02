from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.rpg_eval.catalog import default_case_catalog, default_player_policies
from tools.rpg_eval.contracts import EvalCase, EvalEvent, EvalPlayerPolicy, EvalRunManifest
from tools.rpg_eval.oracles import build_dry_run_case_summary, build_runtime_case_summary, summarize_gate_results


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "eval_v3" / "dry_run"
DEFAULT_RUNTIME_OUTPUT_DIR = REPO_ROOT / "artifacts" / "eval_v3" / "runtime"


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n")


def _write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for row in rows:
        if hasattr(row, "model_dump"):
            row = row.model_dump(mode="json")
        lines.append(json.dumps(row, ensure_ascii=False, default=_json_default))
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None


@contextmanager
def _deterministic_runtime_settings(enabled: bool):
    if not enabled:
        yield
        return
    from rpg_backend.config import get_settings

    settings = get_settings()
    fields = (
        "play_v2_intent_compiler_use_llm",
        "play_v2_micro_sim_use_llm",
        "play_v2_dramatic_rewrite_use_llm",
    )
    previous = {field: getattr(settings, field) for field in fields}
    try:
        for field in fields:
            setattr(settings, field, False)
        yield
    finally:
        for field, value in previous.items():
            setattr(settings, field, value)


def _play_length_preset(case: EvalCase) -> str:
    if case.play_length == "short":
        return "5_8"
    if case.play_length == "standard":
        return "12_15"
    return "30_45"


def _choose_action(policy: EvalPlayerPolicy, actions: list[Any], *, turn_index: int) -> Any:
    if not actions:
        raise ValueError("cannot choose from empty action list")

    def score(action: Any) -> tuple[int, int]:
        lane_id = str(getattr(action, "lane_id", "") or "")
        move_family = str(getattr(action, "move_family", "") or "")
        scene_frame = str(getattr(action, "scene_frame", "") or "")
        text = " ".join(
            str(value or "")
            for value in (
                lane_id,
                move_family,
                scene_frame,
                getattr(action, "label", ""),
                getattr(action, "prompt", ""),
            )
        ).casefold()
        value = 0
        if policy.policy_id == "truth_revealer":
            value += 12 if "reveal" in move_family or "truth" in text or "秘密" in text or "证据" in text else 0
            value += 6 if scene_frame == "public" else 0
            value += 4 if lane_id == "burst" else 0
        elif policy.policy_id == "relationship_loyalist":
            value += 12 if lane_id == "relationship" else 0
            value += 7 if scene_frame == "private" else 0
            value += 4 if any(token in text for token in ("trust", "ally", "confession", "关系", "坦白", "站队")) else 0
        elif policy.policy_id == "chaos_escalator":
            value += 12 if lane_id == "burst" else 0
            value += 10 if scene_frame == "public" else 0
            value += 6 if any(token in move_family for token in ("reveal", "accuse", "betray", "detonate")) else 0
        elif policy.policy_id == "cautious_survivor":
            value += 10 if lane_id in {"relationship", "side"} else 0
            value += 8 if scene_frame != "public" else -8
            value -= 6 if "reveal" in move_family or "betray" in move_family else 0
        else:
            value += 10 if lane_id in {"side", "burst"} else 0
            value += 5 if any(token in move_family for token in ("accuse", "reveal", "pressure", "probe")) else 0
            value += 2 if scene_frame == "public" else 0
        # Deterministic tie-breaker rotates slightly by turn so a policy does
        # not get stuck on the first card if several cards score equally.
        return value, -((actions.index(action) - turn_index) % max(len(actions), 1))

    return max(actions, key=score)


def _state_delta_payload(state: Any) -> dict[str, int | str]:
    relationship_stance = 0
    relationships = getattr(state, "relationships", {}) or {}
    if isinstance(relationships, dict):
        for relation in relationships.values():
            relationship_stance += int(getattr(relation, "trust", 0) or 0)
            relationship_stance += int(getattr(relation, "affection", 0) or 0)
            relationship_stance -= int(getattr(relation, "tension", 0) or 0)
    scene_heat = int(getattr(state, "scene_heat", 0) or 0)
    secret_exposure = int(getattr(state, "secret_exposure", 0) or 0)
    public_wave_pressure = int(getattr(state, "public_wave_pressure", 0) or 0)
    public_image = int(getattr(state, "public_image", 0) or 0)
    route_lock = int(getattr(state, "route_lock", 0) or 0)
    public_pressure = max(scene_heat, secret_exposure + public_wave_pressure)
    career_security = max(0, public_image + route_lock - scene_heat)
    public_event_ids = getattr(state, "public_event_ids", []) or []
    return {
        "turn_index": int(getattr(state, "turn_index", 0) or 0),
        "segment_index": int(getattr(state, "segment_index", 0) or 0),
        "status": str(getattr(state, "status", "") or ""),
        "scene_heat": scene_heat,
        "secret_exposure": secret_exposure,
        "route_lock": route_lock,
        "public_image": public_image,
        "public_pressure": public_pressure,
        "protagonist_control": route_lock + len(public_event_ids),
        "relationship_stance": relationship_stance,
        "reputation": public_image,
        "career_security": career_security,
        "relationship_debt_pressure": int(getattr(state, "relationship_debt_pressure", 0) or 0),
        "public_wave_pressure": public_wave_pressure,
        "secret_pressure": int(getattr(state, "secret_pressure", 0) or 0),
        "npc_action_pressure": int(getattr(state, "npc_action_pressure", 0) or 0),
    }


def _plan_payload(plan: Any, author_payload: dict[str, Any]) -> dict[str, Any]:
    quality_report = author_payload.get("quality_report")
    return {
        "story_id": str(getattr(plan, "story_id", "") or ""),
        "story_shell_id": str(getattr(plan, "story_shell_id", "") or ""),
        "template_id": str(getattr(plan, "template_id", "") or ""),
        "fit_mode": str(getattr(plan, "fit_mode", "") or ""),
        "title": str(getattr(plan, "title", "") or ""),
        "author_version": str(getattr(plan, "author_version", "") or ""),
        "play_length_preset": str(getattr(plan, "play_length_preset", "") or ""),
        "max_turns": int(getattr(plan, "max_turns", 0) or 0),
        "cast_count": len(getattr(plan, "cast", []) or []),
        "segment_count": len(getattr(plan, "segments", []) or []),
        "route_target_count": len(getattr(plan, "route_target_ids", []) or []),
        "storylet_count": len(getattr(plan, "storylet_pool", []) or []),
        "organic_secret_count": len(getattr(plan, "organic_secrets", []) or []),
        "quality_score": getattr(quality_report, "score", None),
    }


def _runtime_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "run_manifest": output_dir / "run_manifest.json",
        "cases": output_dir / "cases.json",
        "player_policies": output_dir / "player_policies.json",
        "episode_events": output_dir / "episode_events.json",
        "episode_trace": output_dir / "episode_trace.jsonl",
        "case_summary": output_dir / "case_summary.json",
        "gate_summary": output_dir / "gate_summary.json",
    }


def run_dry_eval(output_dir: Path) -> dict[str, Path]:
    cases = default_case_catalog()
    policies = default_player_policies()
    run_id = datetime.now(timezone.utc).strftime("eval_v3_%Y%m%d_%H%M%S")
    manifest = EvalRunManifest(
        run_id=run_id,
        git_sha=_git_sha(),
        mode="dry_run",
        case_count=len(cases),
        policy_count=len(policies),
        notes=["dry_run validates eval v3 artifact contract without calling an LLM"],
    )
    case_summaries = [build_dry_run_case_summary(case) for case in cases]
    gate_summary = summarize_gate_results(manifest=manifest, case_summaries=case_summaries)

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "run_manifest": output_dir / "run_manifest.json",
        "cases": output_dir / "cases.json",
        "player_policies": output_dir / "player_policies.json",
        "case_summary": output_dir / "case_summary.json",
        "gate_summary": output_dir / "gate_summary.json",
    }
    _write_json(paths["run_manifest"], manifest)
    _write_json(paths["cases"], [case.model_dump(mode="json") for case in cases])
    _write_json(paths["player_policies"], [policy.model_dump(mode="json") for policy in policies])
    _write_json(paths["case_summary"], [summary.model_dump(mode="json") for summary in case_summaries])
    _write_json(paths["gate_summary"], gate_summary)
    return paths


def run_unified_runtime_eval(
    output_dir: Path,
    *,
    case_limit: int | None = None,
    policy_limit: int | None = None,
    max_turns: int | None = None,
    author_mode: str = "deterministic",
    live_runtime: bool = False,
) -> dict[str, Path]:
    from rpg_backend.author_v3.workflow import run_author_v3_pipeline
    from rpg_backend.play_v2.contracts import UrbanTurnIntent
    from rpg_backend.play_v2.runtime import build_initial_world_state, build_suggested_actions, run_turn

    cases = default_case_catalog()[:case_limit] if case_limit else default_case_catalog()
    policies = default_player_policies()[:policy_limit] if policy_limit else default_player_policies()
    run_id = datetime.now(timezone.utc).strftime("eval_v3_runtime_%Y%m%d_%H%M%S")
    manifest = EvalRunManifest(
        run_id=run_id,
        git_sha=_git_sha(),
        mode="runtime",
        case_count=len(cases),
        policy_count=len(policies),
        notes=[
            "unified runtime suite covers seed -> author_v3 -> play_v2 -> oracle gates",
            f"author_mode={author_mode}",
            f"live_runtime={live_runtime}",
        ],
    )
    events: list[EvalEvent] = []

    def emit(
        *,
        event_type: str,
        case_id: str,
        payload: dict[str, Any],
        policy_id: str | None = None,
        trial_index: int = 0,
    ) -> None:
        events.append(
            EvalEvent(
                event_index=len(events),
                event_type=event_type,  # type: ignore[arg-type]
                case_id=case_id,
                policy_id=policy_id,
                trial_index=trial_index,
                payload=payload,
            )
        )

    with _deterministic_runtime_settings(not live_runtime):
        for case in cases:
            try:
                author_result = run_author_v3_pipeline(
                    case.seed,
                    run_mode=author_mode,
                    play_length_preset_override=_play_length_preset(case),  # type: ignore[arg-type]
                )
                plan = author_result["plan"]
                emit(event_type="author_step", case_id=case.case_id, payload=_plan_payload(plan, author_result))
                emit(
                    event_type="publish_step",
                    case_id=case.case_id,
                    payload={
                        "story_id": str(getattr(plan, "story_id", "") or ""),
                        "opening_narration_chars": len(str(getattr(plan, "opening_narration", "") or "")),
                        "suggested_policy_count": len(policies),
                    },
                )
            except Exception as exc:  # noqa: BLE001
                emit(
                    event_type="failure",
                    case_id=case.case_id,
                    payload={"stage": "author_step", "message": f"{type(exc).__name__}: {str(exc)[:300]}"},
                )
                continue

            turn_budget = max_turns if max_turns is not None else int(getattr(plan, "max_turns", 0) or case.oracle.min_turns)
            turn_budget = max(1, min(int(turn_budget), int(getattr(plan, "max_turns", turn_budget) or turn_budget)))
            for trial_index, policy in enumerate(policies):
                try:
                    state = build_initial_world_state(plan, session_id=f"{case.case_id}_{policy.policy_id}")
                    emit(
                        event_type="session_start",
                        case_id=case.case_id,
                        policy_id=policy.policy_id,
                        trial_index=trial_index,
                        payload={
                            "state": _state_delta_payload(state),
                            "initial_suggestion_count": len(getattr(state, "suggested_actions", []) or []),
                        },
                    )
                    for _ in range(turn_budget):
                        if str(getattr(state, "status", "") or "") != "active":
                            break
                        actions = build_suggested_actions(plan, state)
                        if not actions:
                            emit(
                                event_type="failure",
                                case_id=case.case_id,
                                policy_id=policy.policy_id,
                                trial_index=trial_index,
                                payload={"stage": "player_action", "message": "no suggested actions available"},
                            )
                            break
                        action = _choose_action(policy, actions, turn_index=int(getattr(state, "turn_index", 0) or 0))
                        emit(
                            event_type="player_action",
                            case_id=case.case_id,
                            policy_id=policy.policy_id,
                            trial_index=trial_index,
                            payload={
                                "turn_index": int(getattr(state, "turn_index", 0) or 0) + 1,
                                "suggestion_id": action.suggestion_id,
                                "lane_id": action.lane_id,
                                "move_family": action.move_family,
                                "scene_frame": action.scene_frame,
                                "label": action.label,
                                "prompt": action.prompt,
                                "policy_objective": policy.objective,
                            },
                        )
                        result = run_turn(
                            plan,
                            state,
                            action.prompt,
                            selected_suggestion_id=action.suggestion_id,
                            selected_story_action_id=action.suggestion_id,
                            precomputed_intent=UrbanTurnIntent(
                                input_text=action.prompt,
                                lane_id=action.lane_id,
                                move_family=action.move_family,
                                target_id=action.target_id,
                                scene_frame=action.scene_frame,
                                confidence="high",
                                intent_confidence=1.0,
                                intent_compile_source="heuristic_fallback",
                                mapped_suggestion_id=action.suggestion_id,
                            ),
                            precomputed_intent_diagnostics={
                                "precomputed_policy_id": policy.policy_id,
                                "precomputed_suggestion_id": action.suggestion_id,
                            },
                            prefetched_suggestions=tuple(actions),
                        )
                        state = result.state
                        diagnostics = result.intent_stage_diagnostics
                        emit(
                            event_type="runtime_output",
                            case_id=case.case_id,
                            policy_id=policy.policy_id,
                            trial_index=trial_index,
                            payload={
                                "turn_index": int(getattr(state, "turn_index", 0) or 0),
                                "narration": result.narration,
                                "ending_triggered": bool(result.ending_triggered),
                                "lane_id": result.intent.lane_id,
                                "move_family": result.intent.move_family,
                                "target_id": result.intent.target_id,
                                "post_submit_llm_calls": int(diagnostics.get("post_submit_llm_calls") or 0),
                                "play_turn_total_tokens": int(diagnostics.get("play_turn_total_tokens") or 0),
                            },
                        )
                        emit(
                            event_type="state_delta",
                            case_id=case.case_id,
                            policy_id=policy.policy_id,
                            trial_index=trial_index,
                            payload=_state_delta_payload(state),
                        )
                        if result.ending_triggered or str(getattr(state, "status", "") or "") != "active":
                            emit(
                                event_type="ending",
                                case_id=case.case_id,
                                policy_id=policy.policy_id,
                                trial_index=trial_index,
                                payload={
                                    "ending_id": str(getattr(state, "ending_id", "") or ""),
                                    "ending_summary": str(getattr(state, "ending_summary", "") or ""),
                                    "turn_index": int(getattr(state, "turn_index", 0) or 0),
                                },
                            )
                            break
                except Exception as exc:  # noqa: BLE001
                    emit(
                        event_type="failure",
                        case_id=case.case_id,
                        policy_id=policy.policy_id,
                        trial_index=trial_index,
                        payload={"stage": "runtime", "message": f"{type(exc).__name__}: {str(exc)[:300]}"},
                    )

    case_summaries = [build_runtime_case_summary(case, events) for case in cases]
    gate_summary = summarize_gate_results(manifest=manifest, case_summaries=case_summaries)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _runtime_paths(output_dir)
    _write_json(paths["run_manifest"], manifest)
    _write_json(paths["cases"], [case.model_dump(mode="json") for case in cases])
    _write_json(paths["player_policies"], [policy.model_dump(mode="json") for policy in policies])
    _write_json(paths["episode_events"], [event.model_dump(mode="json") for event in events])
    _write_jsonl(paths["episode_trace"], events)
    _write_json(paths["case_summary"], [summary.model_dump(mode="json") for summary in case_summaries])
    _write_json(paths["gate_summary"], gate_summary)
    return paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RPG eval v3 artifact contract.")
    parser.add_argument("--dry-run", action="store_true", help="Write contract artifacts without calling author/play runtime.")
    parser.add_argument("--runtime", action="store_true", help="Run the unified seed -> author -> play -> gate suite.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--policy-limit", type=int, default=None)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--author-mode", default="deterministic")
    parser.add_argument("--live-runtime", action="store_true", help="Allow play_v2 LLM calls during runtime eval.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.runtime and args.dry_run:
        raise SystemExit("Choose only one of --runtime or --dry-run.")
    if args.runtime:
        output_dir = Path(args.output_dir or DEFAULT_RUNTIME_OUTPUT_DIR).expanduser().resolve()
        paths = run_unified_runtime_eval(
            output_dir,
            case_limit=args.case_limit,
            policy_limit=args.policy_limit,
            max_turns=args.max_turns,
            author_mode=str(args.author_mode),
            live_runtime=bool(args.live_runtime),
        )
    else:
        output_dir = Path(args.output_dir or DEFAULT_OUTPUT_DIR).expanduser().resolve()
        paths = run_dry_eval(output_dir)
    print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

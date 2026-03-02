from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from rpg_backend.domain.pack_schema import GLOBAL_MOVE_IDS, StoryPack


@dataclass
class LintReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def classify_lint_errors(errors: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "schema": [],
        "references": [],
        "fail_forward": [],
        "global_moves": [],
        "reachability": [],
        "terminal": [],
        "other": [],
    }

    for err in errors:
        if "schema validation failed" in err:
            buckets["schema"].append(err)
        elif "missing fail_forward" in err:
            buckets["fail_forward"].append(err)
        elif "global moves" in err or "always_available_moves" in err:
            buckets["global_moves"].append(err)
        elif "missing move" in err or "missing scene" in err or "references unknown" in err or "points to missing" in err:
            buckets["references"].append(err)
        elif "unreachable scenes" in err:
            buckets["reachability"].append(err)
        elif "terminal scene" in err or "reach any terminal scene" in err:
            buckets["terminal"].append(err)
        else:
            buckets["other"].append(err)

    return buckets


def _check_condition(scene_id: str, cond, report: LintReport) -> None:
    if cond.condition_kind == "always":
        return
    if cond.key is None:
        report.errors.append(f"scene '{scene_id}' exit condition '{cond.id}' missing key")


def lint_story_pack(pack_json: dict[str, Any]) -> LintReport:
    report = LintReport()
    try:
        pack = StoryPack.model_validate(pack_json)
    except ValidationError as exc:
        report.errors.append(f"schema validation failed: {exc}")
        return report

    scene_map = {scene.id: scene for scene in pack.scenes}
    move_map = {move.id: move for move in pack.moves}
    beat_map = {beat.id: beat for beat in pack.beats}

    if len(scene_map) != len(pack.scenes):
        report.errors.append("duplicate scene ids")
    if len(move_map) != len(pack.moves):
        report.errors.append("duplicate move ids")
    if len(beat_map) != len(pack.beats):
        report.errors.append("duplicate beat ids")

    for beat in pack.beats:
        if beat.entry_scene_id not in scene_map:
            report.errors.append(f"beat '{beat.id}' entry scene '{beat.entry_scene_id}' not found")

    for scene in pack.scenes:
        if scene.beat_id not in beat_map:
            report.errors.append(f"scene '{scene.id}' references unknown beat '{scene.beat_id}'")

        global_moves = set(scene.always_available_moves)
        if len(scene.always_available_moves) < 2 or len(scene.always_available_moves) > 3:
            report.errors.append(f"scene '{scene.id}' must include 2-3 global moves")
        if not global_moves.issubset(GLOBAL_MOVE_IDS):
            report.errors.append(f"scene '{scene.id}' has non-global always_available_moves")

        for move_id in scene.enabled_moves + scene.always_available_moves:
            if move_id not in move_map:
                report.errors.append(f"scene '{scene.id}' references missing move '{move_id}'")

        for cond in scene.exit_conditions:
            _check_condition(scene.id, cond, report)
            if cond.next_scene_id and cond.next_scene_id not in scene_map:
                report.errors.append(
                    f"scene '{scene.id}' exit condition '{cond.id}' points to missing scene '{cond.next_scene_id}'"
                )

    for move in pack.moves:
        outcome_ids = {o.id for o in move.outcomes}
        if len(outcome_ids) != len(move.outcomes):
            report.errors.append(f"move '{move.id}' has duplicate outcome ids")

        has_fail_forward = any(o.result == "fail_forward" for o in move.outcomes)
        if not has_fail_forward:
            report.errors.append(f"move '{move.id}' missing fail_forward outcome")

        for outcome in move.outcomes:
            if outcome.next_scene_id and outcome.next_scene_id not in scene_map:
                report.errors.append(
                    f"move '{move.id}' outcome '{outcome.id}' points to missing scene '{outcome.next_scene_id}'"
                )

    if not pack.beats:
        return report

    entry_scene = pack.beats[0].entry_scene_id
    if entry_scene not in scene_map:
        return report

    graph: dict[str, set[str]] = {scene.id: set() for scene in pack.scenes}
    reverse_graph: dict[str, set[str]] = {scene.id: set() for scene in pack.scenes}

    for scene in pack.scenes:
        for cond in scene.exit_conditions:
            if cond.next_scene_id:
                graph[scene.id].add(cond.next_scene_id)
                reverse_graph[cond.next_scene_id].add(scene.id)
        for move_id in scene.enabled_moves + scene.always_available_moves:
            move = move_map.get(move_id)
            if move is None:
                continue
            for outcome in move.outcomes:
                if outcome.next_scene_id:
                    graph[scene.id].add(outcome.next_scene_id)
                    reverse_graph[outcome.next_scene_id].add(scene.id)

    reachable: set[str] = set()
    stack = [entry_scene]
    while stack:
        node = stack.pop()
        if node in reachable:
            continue
        reachable.add(node)
        stack.extend(graph[node] - reachable)

    unreachable = set(scene_map) - reachable
    if unreachable:
        report.errors.append(f"unreachable scenes from entry '{entry_scene}': {sorted(unreachable)}")

    terminal_scenes = {
        scene.id
        for scene in pack.scenes
        if scene.is_terminal or any(cond.end_story for cond in scene.exit_conditions)
    }
    if not terminal_scenes:
        report.errors.append("no terminal scene defined")
        return report

    can_reach_terminal: set[str] = set()
    stack = list(terminal_scenes)
    while stack:
        node = stack.pop()
        if node in can_reach_terminal:
            continue
        can_reach_terminal.add(node)
        stack.extend(reverse_graph[node] - can_reach_terminal)

    if entry_scene not in can_reach_terminal:
        report.errors.append("entry scene cannot reach any terminal scene")

    total_budget = sum(beat.step_budget for beat in pack.beats)
    if total_budget < len(pack.scenes):
        report.warnings.append(
            "total beat step_budget is lower than scene count; pacing may feel too compressed"
        )

    for npc in pack.npcs:
        appearances = sum(1 for scene in pack.scenes if npc in scene.present_npcs)
        if appearances < 2:
            report.errors.append(f"npc '{npc}' appears fewer than 2 times")

    return report

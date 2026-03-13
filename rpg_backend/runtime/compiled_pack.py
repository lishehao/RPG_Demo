from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from rpg_backend.domain.pack_schema import Beat, Move, NPCProfile, Scene, StoryPack


@dataclass(frozen=True)
class CompiledPlayRuntimePack:
    pack: StoryPack
    scenes_by_id: Mapping[str, Scene]
    moves_by_id: Mapping[str, Move]
    beat_index_by_id: Mapping[str, int]
    npc_profiles_by_name: Mapping[str, NPCProfile]

    def scene(self, scene_id: str) -> Scene:
        return self.scenes_by_id[scene_id]

    def move(self, move_id: str) -> Move:
        return self.moves_by_id[move_id]

    def beat_at_index(self, beat_index: int | None) -> Beat | None:
        if beat_index is None:
            return None
        if 0 <= beat_index < len(self.pack.beats):
            return self.pack.beats[beat_index]
        return None

    def beat_index_for_scene(self, scene_id: str) -> int:
        scene = self.scene(scene_id)
        return int(self.beat_index_by_id[scene.beat_id])

    def scene_move_ids(self, scene_id: str) -> list[str]:
        scene = self.scene(scene_id)
        return list(dict.fromkeys([*scene.enabled_moves, *scene.always_available_moves]))


def compile_play_runtime_pack(pack: StoryPack) -> CompiledPlayRuntimePack:
    scenes_by_id = MappingProxyType({scene.id: scene for scene in pack.scenes})
    moves_by_id = MappingProxyType({move.id: move for move in pack.moves})
    beat_index_by_id = MappingProxyType({beat.id: index for index, beat in enumerate(pack.beats)})
    npc_profiles_by_name = MappingProxyType({profile.name: profile for profile in pack.npc_profiles})
    return CompiledPlayRuntimePack(
        pack=pack,
        scenes_by_id=scenes_by_id,
        moves_by_id=moves_by_id,
        beat_index_by_id=beat_index_by_id,
        npc_profiles_by_name=npc_profiles_by_name,
    )

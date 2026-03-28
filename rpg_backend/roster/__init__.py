from __future__ import annotations

__all__ = [
    "CharacterRosterService",
    "build_character_roster_service",
    "get_character_roster_service",
]


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name in __all__:
        from rpg_backend.roster.service import (
            CharacterRosterService,
            build_character_roster_service,
            get_character_roster_service,
        )

        return {
            "CharacterRosterService": CharacterRosterService,
            "build_character_roster_service": build_character_roster_service,
            "get_character_roster_service": get_character_roster_service,
        }[name]
    raise AttributeError(name)

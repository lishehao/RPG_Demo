from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from rpg_backend.schemas import SessionAction

_LOW_RISK_KEYWORDS = {"look", "observe", "scan", "talk", "ask", "walk", "wait"}
_HIGH_RISK_KEYWORDS = {"attack", "fight", "steal", "break", "burn", "charge", "threaten"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StoryRecord:
    story_id: str
    title: str
    theme: str
    difficulty: str
    created_at: datetime
    published: bool = True


@dataclass
class SessionTurnRecord:
    turn: int
    narration: str
    actions: list[SessionAction]
    risk_hint: str


@dataclass
class SessionRecord:
    session_id: str
    story_id: str
    created_at: datetime
    state: str = "active"
    history: list[SessionTurnRecord] = field(default_factory=list)


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._stories: dict[str, StoryRecord] = {}
        self._sessions: dict[str, SessionRecord] = {}

    def generate_story(self, *, theme: str, difficulty: str) -> StoryRecord:
        with self._lock:
            story_id = str(uuid4())
            normalized_theme = theme.strip()
            normalized_difficulty = difficulty.strip()
            title = f"{normalized_theme.title()} - {normalized_difficulty.title()} Quest"
            record = StoryRecord(
                story_id=story_id,
                title=title,
                theme=normalized_theme,
                difficulty=normalized_difficulty,
                created_at=utc_now(),
                published=True,
            )
            self._stories[story_id] = record
            return record

    def list_stories(self) -> list[StoryRecord]:
        with self._lock:
            items = list(self._stories.values())
            items.sort(key=lambda item: item.created_at, reverse=True)
            return items

    def create_session(self, *, story_id: str) -> SessionRecord | None:
        with self._lock:
            if story_id not in self._stories:
                return None
            session_id = str(uuid4())
            session = SessionRecord(
                session_id=session_id,
                story_id=story_id,
                created_at=utc_now(),
                state="active",
            )
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(session_id)

    def get_history(self, session_id: str) -> list[SessionTurnRecord] | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            return list(session.history)

    def step(self, session_id: str, *, move_id: str | None, free_text: str | None) -> SessionTurnRecord | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            if session.state != "active":
                return None

            next_turn = len(session.history) + 1
            prompt = move_id or free_text or "unknown action"
            risk_hint = _classify_risk(prompt)
            narration = _build_narration(turn=next_turn, move_id=move_id, free_text=free_text)
            actions = _build_actions(turn=next_turn)
            turn_record = SessionTurnRecord(
                turn=next_turn,
                narration=narration,
                actions=actions,
                risk_hint=risk_hint,
            )
            session.history.append(turn_record)

            if move_id in {"end", "finish", "exit"} or next_turn >= 12:
                session.state = "completed"

            return turn_record


def _build_narration(*, turn: int, move_id: str | None, free_text: str | None) -> str:
    if move_id:
        return f"Turn {turn}: You choose '{move_id}'. The world reacts and reveals a new path."
    text = (free_text or "").strip()
    return f"Turn {turn}: \"{text}\" shifts the scene, and new choices appear."


def _build_actions(*, turn: int) -> list[SessionAction]:
    return [
        SessionAction(id=f"look_{turn}", label="Look around"),
        SessionAction(id=f"advance_{turn}", label="Move forward"),
    ]


def _classify_risk(prompt: str) -> str:
    text = prompt.lower()
    if any(keyword in text for keyword in _HIGH_RISK_KEYWORDS):
        return "high"
    if any(keyword in text for keyword in _LOW_RISK_KEYWORDS):
        return "low"
    return "medium"


store = InMemoryStore()


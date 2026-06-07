from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rpg_backend.narrative.contracts import (
    AgentEventPayload,
    AgentEventType,
    AgentPlan,
    AdvisorMessage,
    BranchHypothetical,
    CastMember,
    ContractJudgeResult,
    Difficulty,
    EndingTier,
    FailureCondition,
    Highlight,
    InventoryDelta,
    LLMCallEvent,
    LLMCallSourceLabel,
    LLMCallStatus,
    LocalizedText,
    NarrativeAgentEvent,
    NarrativeSession,
    NarrativeTemplate,
    NPCPulse,
    PlayedLeverageCard,
    PlayerGoal,
    PlayerRole,
    StepJudgeResult,
    StoryMessage,
    StoryOption,
    TemplateLanguage,
    TemplateVisibility,
)


class NarrativeNotFoundError(LookupError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_localized_text(value: LocalizedText | None) -> str | None:
    if value is None:
        return None
    payload = value.model_dump(mode="json", exclude_none=True)
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False)


def _load_localized_text(raw: str | None) -> LocalizedText | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    try:
        value = LocalizedText.model_validate(payload)
    except Exception:  # noqa: BLE001
        return None
    if not value.zh and not value.en:
        return None
    return value


class NarrativeRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        if self._db_path != ":memory:":
            path = Path(self._db_path)
            if path.parent != Path():
                path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema(connection)
        return connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS narrative_templates (
                template_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                seed TEXT NOT NULL,
                title TEXT NOT NULL,
                title_i18n_json TEXT,
                summary_i18n_json TEXT,
                cast_json TEXT NOT NULL,
                advisor_persona TEXT NOT NULL,
                opening_passage TEXT NOT NULL,
                opening_options_json TEXT NOT NULL DEFAULT '[]',
                cover_image_url TEXT,
                visibility TEXT NOT NULL DEFAULT 'private',
                play_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS narrative_sessions (
                session_id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                player_user_id TEXT NOT NULL,
                turn_count INTEGER NOT NULL DEFAULT 0,
                turn_budget INTEGER NOT NULL DEFAULT 12,
                ending_label TEXT,
                ending_subtitle TEXT,
                ending_passage TEXT,
                created_at TEXT NOT NULL,
                last_active_at TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES narrative_templates(template_id) ON DELETE CASCADE
            )
            """
        )
        # Migrate existing sessions/templates — add gauntlet-mode columns
        # if missing. Idempotent: ALTER errors are swallowed by the
        # column-existence check.
        existing_cols = {row[1] for row in connection.execute("PRAGMA table_info(narrative_sessions)").fetchall()}
        for col, ddl in (
            ("turn_budget", "ALTER TABLE narrative_sessions ADD COLUMN turn_budget INTEGER NOT NULL DEFAULT 12"),
            ("ending_label", "ALTER TABLE narrative_sessions ADD COLUMN ending_label TEXT"),
            ("ending_subtitle", "ALTER TABLE narrative_sessions ADD COLUMN ending_subtitle TEXT"),
            ("ending_passage", "ALTER TABLE narrative_sessions ADD COLUMN ending_passage TEXT"),
            ("difficulty", "ALTER TABLE narrative_sessions ADD COLUMN difficulty TEXT NOT NULL DEFAULT 'story'"),
            ("ending_tier", "ALTER TABLE narrative_sessions ADD COLUMN ending_tier TEXT"),
            ("early_terminated", "ALTER TABLE narrative_sessions ADD COLUMN early_terminated INTEGER NOT NULL DEFAULT 0"),
            ("failure_trigger", "ALTER TABLE narrative_sessions ADD COLUMN failure_trigger TEXT"),
            ("selected_player_role_id", "ALTER TABLE narrative_sessions ADD COLUMN selected_player_role_id TEXT"),
            ("ending_highlights_json", "ALTER TABLE narrative_sessions ADD COLUMN ending_highlights_json TEXT"),
            ("ending_branches_json", "ALTER TABLE narrative_sessions ADD COLUMN ending_branches_json TEXT"),
        ):
            if col not in existing_cols:
                connection.execute(ddl)
        existing_template_cols = {row[1] for row in connection.execute("PRAGMA table_info(narrative_templates)").fetchall()}
        for col, ddl in (
            ("player_goals_json", "ALTER TABLE narrative_templates ADD COLUMN player_goals_json TEXT NOT NULL DEFAULT '[]'"),
            ("failure_conditions_json", "ALTER TABLE narrative_templates ADD COLUMN failure_conditions_json TEXT NOT NULL DEFAULT '[]'"),
            ("player_role_options_json", "ALTER TABLE narrative_templates ADD COLUMN player_role_options_json TEXT NOT NULL DEFAULT '[]'"),
            ("cover_image_url", "ALTER TABLE narrative_templates ADD COLUMN cover_image_url TEXT"),
            ("title_i18n_json", "ALTER TABLE narrative_templates ADD COLUMN title_i18n_json TEXT"),
            ("summary_i18n_json", "ALTER TABLE narrative_templates ADD COLUMN summary_i18n_json TEXT"),
            # Pre-i18n templates default to "zh"; this matches the
            # historic behavior where every template was generated in
            # Chinese.
            ("language", "ALTER TABLE narrative_templates ADD COLUMN language TEXT NOT NULL DEFAULT 'zh'"),
        ):
            if col not in existing_template_cols:
                connection.execute(ddl)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS narrative_story_messages (
                session_id TEXT NOT NULL,
                ord INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                options_json TEXT NOT NULL DEFAULT '[]',
                chosen_option_index INTEGER,
                npc_pulse_json TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (session_id, ord),
                FOREIGN KEY (session_id) REFERENCES narrative_sessions(session_id) ON DELETE CASCADE
            )
            """
        )
        existing_msg_cols = {row[1] for row in connection.execute("PRAGMA table_info(narrative_story_messages)").fetchall()}
        if "npc_pulse_json" not in existing_msg_cols:
            connection.execute(
                "ALTER TABLE narrative_story_messages ADD COLUMN npc_pulse_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "inventory_delta_json" not in existing_msg_cols:
            connection.execute(
                "ALTER TABLE narrative_story_messages ADD COLUMN inventory_delta_json TEXT"
            )
        if "diary" not in existing_msg_cols:
            connection.execute(
                "ALTER TABLE narrative_story_messages ADD COLUMN diary TEXT"
            )
        if "played_leverage_json" not in existing_msg_cols:
            connection.execute(
                "ALTER TABLE narrative_story_messages ADD COLUMN played_leverage_json TEXT"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS narrative_advisor_messages (
                session_id TEXT NOT NULL,
                ord INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                PRIMARY KEY (session_id, ord),
                FOREIGN KEY (session_id) REFERENCES narrative_sessions(session_id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS narrative_agent_events (
                session_id TEXT NOT NULL,
                event_index INTEGER NOT NULL,
                ord INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (session_id, event_index),
                FOREIGN KEY (session_id) REFERENCES narrative_sessions(session_id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS narrative_llm_call_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                source_label TEXT NOT NULL,
                latency_ms INTEGER,
                operation_latency_ms INTEGER,
                input_tokens INTEGER,
                cached_input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                retry_count INTEGER NOT NULL DEFAULT 0,
                repair_count INTEGER NOT NULL DEFAULT 0,
                fallback_reason TEXT,
                response_id TEXT,
                user_id TEXT,
                template_id TEXT,
                session_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES narrative_templates(template_id) ON DELETE SET NULL,
                FOREIGN KEY (session_id) REFERENCES narrative_sessions(session_id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_templates_owner "
            "ON narrative_templates(owner_user_id, created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_templates_public "
            "ON narrative_templates(visibility, created_at DESC) WHERE visibility = 'public'"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_sessions_player "
            "ON narrative_sessions(player_user_id, last_active_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_sessions_template "
            "ON narrative_sessions(template_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_agent_events_ord "
            "ON narrative_agent_events(session_id, ord)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_agent_events_type "
            "ON narrative_agent_events(session_id, event_type)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_llm_events_session "
            "ON narrative_llm_call_events(session_id, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_llm_events_user "
            "ON narrative_llm_call_events(user_id, created_at)"
        )
        connection.commit()

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def create_template(
        self,
        *,
        template_id: str,
        owner_user_id: str,
        seed: str,
        title: str,
        cast: list[CastMember],
        advisor_persona: str,
        opening_passage: str,
        opening_options: list[StoryOption],
        player_goals: list[PlayerGoal],
        failure_conditions: list[FailureCondition],
        player_role_options: list[PlayerRole],
        visibility: TemplateVisibility,
        language: TemplateLanguage = "en",
        cover_image_url: str | None = None,
        title_i18n: LocalizedText | None = None,
        summary_i18n: LocalizedText | None = None,
    ) -> NarrativeTemplate:
        created_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO narrative_templates
                (template_id, owner_user_id, seed, title, title_i18n_json, summary_i18n_json, cast_json,
                 advisor_persona, opening_passage, opening_options_json,
                 player_goals_json, failure_conditions_json,
                 player_role_options_json,
                 cover_image_url, visibility, language, play_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    template_id,
                    owner_user_id,
                    seed,
                    title,
                    _dump_localized_text(title_i18n),
                    _dump_localized_text(summary_i18n),
                    json.dumps([c.model_dump() for c in cast], ensure_ascii=False),
                    advisor_persona,
                    opening_passage,
                    json.dumps([o.model_dump() for o in opening_options], ensure_ascii=False),
                    json.dumps([g.model_dump() for g in player_goals], ensure_ascii=False),
                    json.dumps([f.model_dump() for f in failure_conditions], ensure_ascii=False),
                    json.dumps([r.model_dump() for r in player_role_options], ensure_ascii=False),
                    cover_image_url,
                    visibility,
                    language,
                    created_at,
                ),
            )
            conn.commit()
        return NarrativeTemplate(
            template_id=template_id,
            owner_user_id=owner_user_id,
            seed=seed,
            title=title,
            title_i18n=title_i18n,
            summary_i18n=summary_i18n,
            cast=cast,
            advisor_persona=advisor_persona,
            opening_passage=opening_passage,
            opening_options=opening_options,
            cover_image_url=cover_image_url,
            player_goals=player_goals,
            failure_conditions=failure_conditions,
            player_role_options=player_role_options,
            visibility=visibility,
            language=language,
            play_count=0,
            created_at=created_at,
        )

    def get_template(self, template_id: str) -> NarrativeTemplate:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM narrative_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
        if row is None:
            raise NarrativeNotFoundError(f"narrative template not found: {template_id}")
        return _row_to_template(row)

    def list_public_templates(self, limit: int = 50) -> list[NarrativeTemplate]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM narrative_templates
                WHERE visibility = 'public'
                ORDER BY play_count DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_template(r) for r in rows]

    def list_templates_for_owner(self, owner_user_id: str) -> list[NarrativeTemplate]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM narrative_templates
                WHERE owner_user_id = ?
                ORDER BY created_at DESC
                """,
                (owner_user_id,),
            ).fetchall()
        return [_row_to_template(r) for r in rows]

    def update_template_visibility(
        self, template_id: str, visibility: TemplateVisibility
    ) -> None:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE narrative_templates SET visibility = ? WHERE template_id = ?",
                (visibility, template_id),
            )
            if cur.rowcount == 0:
                raise NarrativeNotFoundError(template_id)
            conn.commit()

    def increment_play_count(self, template_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE narrative_templates SET play_count = play_count + 1 WHERE template_id = ?",
                (template_id,),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def create_session(
        self,
        *,
        session_id: str,
        template_id: str,
        player_user_id: str,
        turn_budget: int = 12,
        difficulty: Difficulty = "story",
        selected_player_role_id: str | None = None,
    ) -> NarrativeSession:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO narrative_sessions
                (session_id, template_id, player_user_id, turn_count, turn_budget, difficulty,
                 selected_player_role_id, created_at, last_active_at)
                VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)
                """,
                (session_id, template_id, player_user_id, turn_budget, difficulty,
                 selected_player_role_id, now, now),
            )
            conn.commit()
        return NarrativeSession(
            session_id=session_id,
            template_id=template_id,
            player_user_id=player_user_id,
            turn_count=0,
            turn_budget=turn_budget,
            difficulty=difficulty,
            selected_player_role_id=selected_player_role_id,
            ending_label=None,
            ending_subtitle=None,
            ending_passage=None,
            ending_tier=None,
            early_terminated=False,
            failure_trigger=None,
            created_at=now,
            last_active_at=now,
        )

    def record_session_ending(
        self,
        session_id: str,
        *,
        label: str,
        subtitle: str,
        passage: str,
        tier: EndingTier,
        early_terminated: bool = False,
        failure_trigger: str | None = None,
        highlights: list[Highlight] | None = None,
        branches: list[BranchHypothetical] | None = None,
    ) -> None:
        highlights_json: str | None = None
        if highlights:
            highlights_json = json.dumps(
                [h.model_dump() for h in highlights], ensure_ascii=False,
            )
        branches_json: str | None = None
        if branches:
            branches_json = json.dumps(
                [b.model_dump() for b in branches], ensure_ascii=False,
            )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE narrative_sessions
                SET ending_label = ?, ending_subtitle = ?, ending_passage = ?,
                    ending_tier = ?, early_terminated = ?, failure_trigger = ?,
                    ending_highlights_json = ?, ending_branches_json = ?,
                    last_active_at = ?
                WHERE session_id = ?
                """,
                (
                    label,
                    subtitle,
                    passage,
                    tier,
                    1 if early_terminated else 0,
                    failure_trigger,
                    highlights_json,
                    branches_json,
                    _utc_now(),
                    session_id,
                ),
            )
            conn.commit()

    def get_session_branches(self, session_id: str) -> list[BranchHypothetical]:
        """Read persisted branch hypotheticals. Empty if not generated
        or session isn't done."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ending_branches_json FROM narrative_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None or not row["ending_branches_json"]:
            return []
        try:
            raw = json.loads(row["ending_branches_json"])
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(raw, list):
            return []
        out: list[BranchHypothetical] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                out.append(BranchHypothetical.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
        return out

    def get_session_highlights(self, session_id: str) -> list[Highlight]:
        """Read persisted highlights for a finished session. Empty list
        if the session isn't done or highlights weren't generated."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ending_highlights_json FROM narrative_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None or not row["ending_highlights_json"]:
            return []
        try:
            raw = json.loads(row["ending_highlights_json"])
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(raw, list):
            return []
        out: list[Highlight] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                out.append(Highlight.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
        return out

    def list_completed_endings_for_template(
        self, template_id: str
    ) -> list[tuple[str, int]]:
        """Return [(label, count)] for all completed sessions on this template,
        ordered by count desc."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ending_label, COUNT(*) AS n
                FROM narrative_sessions
                WHERE template_id = ? AND ending_label IS NOT NULL
                GROUP BY ending_label
                ORDER BY n DESC, ending_label ASC
                """,
                (template_id,),
            ).fetchall()
        return [(str(row["ending_label"]), int(row["n"])) for row in rows]

    def count_completed_sessions_for_template(self, template_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM narrative_sessions WHERE template_id = ? AND ending_label IS NOT NULL",
                (template_id,),
            ).fetchone()
        return int(row["n"])

    def get_session(self, session_id: str) -> NarrativeSession:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM narrative_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise NarrativeNotFoundError(f"narrative session not found: {session_id}")
        return _row_to_session(row)

    def list_sessions_for_player(self, player_user_id: str) -> list[NarrativeSession]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM narrative_sessions
                WHERE player_user_id = ?
                ORDER BY last_active_at DESC
                """,
                (player_user_id,),
            ).fetchall()
        return [_row_to_session(r) for r in rows]

    def touch_session(self, session_id: str, *, increment_turns: int = 0) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE narrative_sessions
                SET last_active_at = ?, turn_count = turn_count + ?
                WHERE session_id = ?
                """,
                (_utc_now(), increment_turns, session_id),
            )
            conn.commit()

    def decrement_turn_budget(self, session_id: str, *, by: int = 1) -> int:
        """Reduce the session's turn_budget by `by` (used by advisor oracle
        to charge the player a turn). Floors at 1 to prevent killing the
        session immediately. Returns the new turn_budget."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE narrative_sessions
                SET turn_budget = MAX(1, turn_budget - ?), last_active_at = ?
                WHERE session_id = ?
                """,
                (by, _utc_now(), session_id),
            )
            row = conn.execute(
                "SELECT turn_budget FROM narrative_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            conn.commit()
        return int(row["turn_budget"]) if row else 0

    # ------------------------------------------------------------------
    # Story messages (per session)
    # ------------------------------------------------------------------

    def append_story_message(self, session_id: str, message: StoryMessage) -> None:
        delta_json: str | None = None
        if message.inventory_delta is not None:
            delta_json = json.dumps(message.inventory_delta.model_dump(), ensure_ascii=False)
        leverage_json: str | None = None
        if message.played_leverage is not None:
            leverage_json = json.dumps(message.played_leverage.model_dump(), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO narrative_story_messages
                (session_id, ord, role, content, options_json, chosen_option_index,
                 npc_pulse_json, inventory_delta_json, diary, played_leverage_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    message.ord,
                    message.role,
                    message.content,
                    json.dumps([o.model_dump() for o in message.options], ensure_ascii=False),
                    message.chosen_option_index,
                    json.dumps([p.model_dump() for p in message.npc_pulse], ensure_ascii=False),
                    delta_json,
                    message.diary,
                    leverage_json,
                ),
            )
            conn.commit()

    def list_story_messages(self, session_id: str) -> list[StoryMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ord, role, content, options_json, chosen_option_index,
                       npc_pulse_json, inventory_delta_json, diary, played_leverage_json
                FROM narrative_story_messages
                WHERE session_id = ?
                ORDER BY ord ASC
                """,
                (session_id,),
            ).fetchall()
        return [_row_to_story_message(r) for r in rows]

    def next_story_ord(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(ord), -1) AS max_ord FROM narrative_story_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row["max_ord"]) + 1

    def update_story_message_choice(
        self, session_id: str, ord_value: int, chosen_option_index: int
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE narrative_story_messages
                SET chosen_option_index = ?
                WHERE session_id = ? AND ord = ?
                """,
                (chosen_option_index, session_id, ord_value),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Advisor messages (per session)
    # ------------------------------------------------------------------

    def append_advisor_message(self, session_id: str, message: AdvisorMessage) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO narrative_advisor_messages
                (session_id, ord, role, content)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, message.ord, message.role, message.content),
            )
            conn.commit()

    def list_advisor_messages(self, session_id: str) -> list[AdvisorMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ord, role, content
                FROM narrative_advisor_messages
                WHERE session_id = ?
                ORDER BY ord ASC
                """,
                (session_id,),
            ).fetchall()
        return [
            AdvisorMessage(
                ord=int(row["ord"]),
                role=row["role"],
                content=row["content"],
            )
            for row in rows
        ]

    def next_advisor_ord(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(ord), -1) AS max_ord FROM narrative_advisor_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return int(row["max_ord"]) + 1

    # ------------------------------------------------------------------
    # Agent trace events (per session)
    # ------------------------------------------------------------------

    def append_agent_event(
        self,
        session_id: str,
        *,
        ord_value: int,
        event_type: AgentEventType,
        payload: AgentEventPayload,
    ) -> NarrativeAgentEvent:
        created_at = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(event_index), -1) AS max_idx
                FROM narrative_agent_events
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            event_index = int(row["max_idx"]) + 1
            conn.execute(
                """
                INSERT INTO narrative_agent_events
                (session_id, event_index, ord, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    event_index,
                    ord_value,
                    event_type,
                    json.dumps(payload.model_dump(mode="json"), ensure_ascii=False),
                    created_at,
                ),
            )
            conn.commit()
        return NarrativeAgentEvent(
            event_index=event_index,
            ord=ord_value,
            event_type=event_type,
            payload=payload,
            created_at=created_at,
        )

    def list_agent_events(self, session_id: str) -> list[NarrativeAgentEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_index, ord, event_type, payload_json, created_at
                FROM narrative_agent_events
                WHERE session_id = ?
                ORDER BY event_index ASC
                """,
                (session_id,),
            ).fetchall()
        events: list[NarrativeAgentEvent] = []
        for row in rows:
            event = _row_to_agent_event(row)
            if event is not None:
                events.append(event)
        return events

    # ------------------------------------------------------------------
    # Sanitized LLM call telemetry
    # ------------------------------------------------------------------

    def append_llm_call_event(
        self,
        *,
        operation: str,
        status: LLMCallStatus,
        source_label: LLMCallSourceLabel,
        latency_ms: int | None = None,
        operation_latency_ms: int | None = None,
        input_tokens: int | None = None,
        cached_input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        retry_count: int = 0,
        repair_count: int = 0,
        fallback_reason: str | None = None,
        response_id: str | None = None,
        user_id: str | None = None,
        template_id: str | None = None,
        session_id: str | None = None,
    ) -> LLMCallEvent:
        created_at = _utc_now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO narrative_llm_call_events
                (operation, status, source_label, latency_ms, operation_latency_ms,
                 input_tokens, cached_input_tokens, output_tokens, total_tokens,
                 retry_count, repair_count, fallback_reason, response_id,
                 user_id, template_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation,
                    status,
                    source_label,
                    latency_ms,
                    operation_latency_ms,
                    input_tokens,
                    cached_input_tokens,
                    output_tokens,
                    total_tokens,
                    int(retry_count),
                    int(repair_count),
                    fallback_reason,
                    response_id,
                    user_id,
                    template_id,
                    session_id,
                    created_at,
                ),
            )
            event_id = int(cur.lastrowid)
            conn.commit()
        return LLMCallEvent(
            event_id=event_id,
            operation=operation,
            status=status,
            source_label=source_label,
            latency_ms=latency_ms,
            operation_latency_ms=operation_latency_ms,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            retry_count=retry_count,
            repair_count=repair_count,
            fallback_reason=fallback_reason,
            response_id=response_id,
            user_id=user_id,
            template_id=template_id,
            session_id=session_id,
            created_at=created_at,
        )

    def list_llm_call_events_for_session(self, session_id: str) -> list[LLMCallEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM narrative_llm_call_events
                WHERE session_id = ?
                ORDER BY event_id ASC
                """,
                (session_id,),
            ).fetchall()
        return [_row_to_llm_call_event(r) for r in rows]

    def list_recent_llm_call_events_for_user(self, user_id: str, limit: int = 50) -> list[LLMCallEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM narrative_llm_call_events
                WHERE user_id = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (user_id, int(limit)),
            ).fetchall()
        return [_row_to_llm_call_event(r) for r in rows]


# --------------------------------------------------------------------------
# Row → model conversions
# --------------------------------------------------------------------------


def _row_to_agent_event(row: sqlite3.Row) -> NarrativeAgentEvent | None:
    try:
        event_type = row["event_type"]
        payload_raw = json.loads(row["payload_json"])
        if event_type == "agent_plan":
            payload = AgentPlan.model_validate(payload_raw)
        elif event_type == "step_judge":
            payload = StepJudgeResult.model_validate(payload_raw)
        elif event_type == "contract_judge":
            payload = ContractJudgeResult.model_validate(payload_raw)
        else:
            return None
        return NarrativeAgentEvent(
            event_index=int(row["event_index"]),
            ord=int(row["ord"]),
            event_type=event_type,
            payload=payload,
            created_at=row["created_at"],
        )
    except Exception:  # noqa: BLE001
        return None


def _row_to_llm_call_event(row: sqlite3.Row) -> LLMCallEvent:
    return LLMCallEvent(
        event_id=int(row["event_id"]),
        operation=row["operation"],
        status=row["status"],
        source_label=row["source_label"],
        latency_ms=int(row["latency_ms"]) if row["latency_ms"] is not None else None,
        operation_latency_ms=int(row["operation_latency_ms"]) if row["operation_latency_ms"] is not None else None,
        input_tokens=int(row["input_tokens"]) if row["input_tokens"] is not None else None,
        cached_input_tokens=int(row["cached_input_tokens"]) if row["cached_input_tokens"] is not None else None,
        output_tokens=int(row["output_tokens"]) if row["output_tokens"] is not None else None,
        total_tokens=int(row["total_tokens"]) if row["total_tokens"] is not None else None,
        retry_count=int(row["retry_count"] or 0),
        repair_count=int(row["repair_count"] or 0),
        fallback_reason=row["fallback_reason"],
        response_id=row["response_id"],
        user_id=row["user_id"],
        template_id=row["template_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
    )


def _row_to_template(row: sqlite3.Row) -> NarrativeTemplate:
    keys = row.keys()
    cast_raw = json.loads(row["cast_json"])
    cast: list[CastMember] = []
    for item in cast_raw:
        try:
            cast.append(CastMember.model_validate(item))
        except Exception:  # noqa: BLE001
            continue
    options_raw: Any = json.loads(row["opening_options_json"]) if row["opening_options_json"] else []
    options: list[StoryOption] = []
    if isinstance(options_raw, list):
        for item in options_raw:
            if isinstance(item, dict):
                try:
                    options.append(StoryOption.model_validate(item))
                except Exception:  # noqa: BLE001
                    continue
    goals: list[PlayerGoal] = []
    if "player_goals_json" in keys and row["player_goals_json"]:
        try:
            goals_raw = json.loads(row["player_goals_json"])
            for item in goals_raw if isinstance(goals_raw, list) else []:
                if isinstance(item, dict):
                    try:
                        goals.append(PlayerGoal.model_validate(item))
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            pass
    conds: list[FailureCondition] = []
    if "failure_conditions_json" in keys and row["failure_conditions_json"]:
        try:
            conds_raw = json.loads(row["failure_conditions_json"])
            for item in conds_raw if isinstance(conds_raw, list) else []:
                if isinstance(item, dict):
                    try:
                        conds.append(FailureCondition.model_validate(item))
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            pass
    roles: list[PlayerRole] = []
    if "player_role_options_json" in keys and row["player_role_options_json"]:
        try:
            roles_raw = json.loads(row["player_role_options_json"])
            for item in roles_raw if isinstance(roles_raw, list) else []:
                if isinstance(item, dict):
                    try:
                        roles.append(PlayerRole.model_validate(item))
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            pass
    raw_lang = row["language"] if "language" in keys else "zh"
    language: TemplateLanguage = "en" if raw_lang == "en" else "zh"
    return NarrativeTemplate(
        template_id=row["template_id"],
        owner_user_id=row["owner_user_id"],
        seed=row["seed"],
        title=row["title"],
        title_i18n=_load_localized_text(row["title_i18n_json"] if "title_i18n_json" in keys else None),
        summary_i18n=_load_localized_text(row["summary_i18n_json"] if "summary_i18n_json" in keys else None),
        cast=cast,
        advisor_persona=row["advisor_persona"],
        opening_passage=row["opening_passage"],
        opening_options=options,
        cover_image_url=row["cover_image_url"] if "cover_image_url" in keys else None,
        player_goals=goals,
        failure_conditions=conds,
        player_role_options=roles,
        visibility=row["visibility"],
        language=language,
        play_count=int(row["play_count"]),
        created_at=row["created_at"],
    )


def _row_to_session(row: sqlite3.Row) -> NarrativeSession:
    keys = row.keys()
    raw_difficulty = row["difficulty"] if "difficulty" in keys else "story"
    difficulty: Difficulty = "gauntlet" if raw_difficulty == "gauntlet" else "story"
    raw_tier = row["ending_tier"] if "ending_tier" in keys else None
    ending_tier: EndingTier | None
    if raw_tier in ("victory", "compromised", "collapsed"):
        ending_tier = raw_tier  # type: ignore[assignment]
    else:
        ending_tier = None
    return NarrativeSession(
        session_id=row["session_id"],
        template_id=row["template_id"],
        player_user_id=row["player_user_id"],
        turn_count=int(row["turn_count"]),
        turn_budget=int(row["turn_budget"]) if "turn_budget" in keys else 12,
        difficulty=difficulty,
        selected_player_role_id=row["selected_player_role_id"]
            if "selected_player_role_id" in keys else None,
        ending_label=row["ending_label"] if "ending_label" in keys else None,
        ending_subtitle=row["ending_subtitle"] if "ending_subtitle" in keys else None,
        ending_passage=row["ending_passage"] if "ending_passage" in keys else None,
        ending_tier=ending_tier,
        early_terminated=bool(row["early_terminated"]) if "early_terminated" in keys else False,
        failure_trigger=row["failure_trigger"] if "failure_trigger" in keys else None,
        created_at=row["created_at"],
        last_active_at=row["last_active_at"],
    )


def _row_to_story_message(row: sqlite3.Row) -> StoryMessage:
    keys = row.keys()
    options_raw: Any = json.loads(row["options_json"]) if row["options_json"] else []
    options: list[StoryOption] = []
    if isinstance(options_raw, list):
        for item in options_raw:
            if isinstance(item, dict):
                try:
                    options.append(StoryOption.model_validate(item))
                except Exception:  # noqa: BLE001
                    continue
    pulse: list[NPCPulse] = []
    if "npc_pulse_json" in keys and row["npc_pulse_json"]:
        try:
            pulse_raw = json.loads(row["npc_pulse_json"])
            for item in pulse_raw if isinstance(pulse_raw, list) else []:
                if isinstance(item, dict):
                    try:
                        pulse.append(NPCPulse.model_validate(item))
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            pass
    delta: InventoryDelta | None = None
    if "inventory_delta_json" in keys and row["inventory_delta_json"]:
        try:
            delta_raw = json.loads(row["inventory_delta_json"])
            if isinstance(delta_raw, dict):
                try:
                    delta = InventoryDelta.model_validate(delta_raw)
                except Exception:  # noqa: BLE001
                    delta = None
        except Exception:  # noqa: BLE001
            pass
    chosen = row["chosen_option_index"]
    diary_val: str | None = None
    if "diary" in keys and row["diary"]:
        diary_val = str(row["diary"])[:600]
    played_leverage: PlayedLeverageCard | None = None
    if "played_leverage_json" in keys and row["played_leverage_json"]:
        try:
            leverage_raw = json.loads(row["played_leverage_json"])
            if isinstance(leverage_raw, dict):
                try:
                    played_leverage = PlayedLeverageCard.model_validate(leverage_raw)
                except Exception:  # noqa: BLE001
                    played_leverage = None
        except Exception:  # noqa: BLE001
            pass
    return StoryMessage(
        ord=int(row["ord"]),
        role=row["role"],
        content=row["content"],
        options=options,
        chosen_option_index=int(chosen) if chosen is not None else None,
        npc_pulse=pulse,
        inventory_delta=delta,
        diary=diary_val,
        played_leverage=played_leverage,
    )

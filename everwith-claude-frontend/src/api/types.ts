import type {L10n, Lang} from '../lib/util'

export type DiscoverItem =
  | ({kind: 'character'} & CharacterJSON)
  | ({kind: 'story'} & StoryJSON)
  | ({kind: 'game'} & GameJSON)
export type CharacterJSON = {id: string; version: string; name: string; avatar: string | null; feed: string | null; description: L10n; tagline: L10n; traits: L10n[]; origin: 'official' | 'mine'; voice: string; live2d: Live2DKey | null}
export type Live2DKey = 'arthur' | 'lena' | 'marcus' | 'nora' | 'iris'
export type StoryRoleJSON = {id: string; title: L10n; description: L10n; replaceable: boolean; locked: boolean; default_character: CharacterJSON}
export type StoryJSON = {id: string; version: string; title: L10n; description: L10n; genre: L10n; content_note: L10n; image: string | null; image_wide: string | null; player_role: L10n; player_entry: 'script'; objectives: L10n[]; roles: StoryRoleJSON[]}
export type GameJSON = {id: 'vegas' | 'gems' | 'cabo'; slug: 'royale' | 'splendor' | 'cabo'; name: string; description: L10n; players: number[]; default_players: number; profile: string; profile_label: L10n; poster: string; preview: string; rule_notes: L10n[]}
export type DiscoverPage = {items: DiscoverItem[]; total: number; next_offset: number | null}

export type StoryCastJSON = {role_id: string; role_title: L10n; kind: 'npc' | 'friend'; character_id: string; character_name: string; friend_id: string | null; friend_epoch: number | null; name: string; avatar: string | null; live2d: Live2DKey | null; replaceable: boolean}
export type StorySegmentJSON = {segment_id: string; kind: 'narration' | 'dialogue' | 'action'; role_id: string | null; text: string}
export type StoryTurnJSON = {turn_id: string; kind: 'opening' | 'input' | 'continue'; input: string | null; input_availability: 'available' | 'withdrawn'; language: Lang; created_at: string; delta: {minutes: number; clue: L10n | null; objective: number | null}; segments: StorySegmentJSON[]}
export type StorySessionJSON = {
  schema_version: 'everwith-story-session-v1'; narration_mode: 'local_scripted_mock'; id: string; story_id: string; version: string; title: L10n; player_role: L10n
  status: 'active' | 'read_only'; archived: boolean; revision: number; head_turn_id: string | null; created_at: string; updated_at: string; language: Lang
  cast: StoryCastJSON[]; turns: StoryTurnJSON[]
  state: {objectives: {text: L10n; done: boolean; current: boolean}[]; clues: {id: string; label: L10n}[]; minutes: number; scene: string; scene_image: string | null; scene_position: string | null; scene_label: L10n | null; present: string[]; hint: L10n | null; open_mode: boolean}
  pending: {operation_id: string; kind: 'input' | 'continue'; text: string | null; status: string} | null
}

export type SeatJSON = {seat: number; kind: 'player' | 'friend' | 'temporary'; identity: string; friend_epoch: number | null; name: string; source_id: string | null; source_version: string | null; avatar: string | null; live2d: Live2DKey | null}
export type GameViewJSON = {
  schema_version: 'everwith-game-view-v1'; mode: 'rule_simulated_companions'; id: string; game_id: 'vegas' | 'gems' | 'cabo'; profile: string
  seats: SeatJSON[]; lifecycle: 'active' | 'paused' | 'ended' | 'abandoned'; revision: number; ai_hold: boolean; actor_seat: number | 'any'; phase: string
  player_view: unknown; settlement: null | {id: string; committed_revision: number; scores: number[]; winners: number[]; labels: L10n[]}
  origin: {kind: 'discover' | 'friend' | 'private'; friend_id?: string; conversation_id?: string; return_hash: string}
  created_at: string; updated_at: string; rematch_of: string | null; archived: boolean
  log: {revision: number; seat: number; summary: L10n; kind: string}[]; expressions: Record<number, 'neutral' | 'happy' | 'surprised'>; chat_count: number
}
export type TableMessageJSON = {id: string; seat: number; text: string; audience: 'table'; mode: 'player' | 'simulated_rule_reply'; kind?: 'dialogue' | 'narration'; language?: Lang}

export type RecordJSON = {
  kind: 'story' | 'game'; id: string; work_id: string; version: string; title: L10n; status: string; image: string | null
  lineup: {role: L10n | null; name: string; friend: boolean; temporary?: boolean}[]; created_at: string; updated_at: string; archived: boolean
  turns?: number; revision?: number; rematch_of?: string | null; result?: {scores: number[]; winners: number[]} | null
}
export type WorkJSON = {
  id: string; type: 'story' | 'character'; name: string; created_at: string; updated_at: string; draft: Record<string, unknown>; draft_revision: number
  versions: {version: number; saved_at: string}[]; latest_version: number | null; dirty: boolean; errors: {field: string; code: string}[]
  share: {enabled: boolean; version: number | null}; owner_kind: 'account' | 'guest'; saved_version?: number; unchanged?: boolean
}
export type PreviewJSON = {id: string; work_id: string; draft_revision: number; snapshot: Record<string, unknown>; turns: {id: string; role: 'player' | 'character'; text: string; language: Lang}[]; created_at: string}

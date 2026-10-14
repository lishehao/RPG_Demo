/** Deterministic, switchable mock scenarios (06_API_AND_MOCK.md / mock/SCENARIOS.json). */
import {readJSON, writeJSON} from '../lib/util'
import type {L10n} from '../lib/util'

export type ScenarioId =
  | 'chat.retryable_failure' | 'chat.commit_before_cancel' | 'chat.unknown_result' | 'chat.late_old_stream'
  | 'chat.stale_head' | 'chat.friend_reset_elsewhere' | 'auth.expired' | 'auth.forbidden'
  | 'net.slow' | 'discover.error' | 'discover.append_error' | 'live2d.model_missing' | 'assets.missing'
  | 'game.text_failed' | 'game.unknown_start' | 'story.retryable_failure'

export type ScenarioDef = {id: ScenarioId; kind: 'once' | 'toggle'; label: L10n; expect: L10n}
export const SCENARIOS: ScenarioDef[] = [
  {id: 'chat.retryable_failure', kind: 'once', label: {zh: '下一次私聊：生成中途可重试失败', en: 'Next chat: retryable failure mid-stream'}, expect: {zh: '保留原输入与明确“重试”；重试复用同一操作/输入/基线', en: 'Input kept with explicit Retry reusing the same operation'}},
  {id: 'chat.commit_before_cancel', kind: 'once', label: {zh: '下一次私聊：提交先于停止', en: 'Next chat: commit wins over Stop'}, expect: {zh: '按停止后提示“已完成”，保留结果，不谎称已停止', en: 'Stop reports “already completed” and keeps the result'}},
  {id: 'chat.unknown_result', kind: 'once', label: {zh: '下一次私聊：发送回执丢失（结果未知）', en: 'Next chat: send receipt lost (unknown result)'}, expect: {zh: '显示“尚未确认”，先查询原 key，不盲发第二轮', en: '“Not confirmed yet”; look up the original key before any resend'}},
  {id: 'chat.late_old_stream', kind: 'once', label: {zh: '下一次重试：旧 run 的流帧晚到', en: 'Next retry: stale frames from the old run arrive late'}, expect: {zh: '旧 run_epoch 帧被拒绝，不覆盖新状态', en: 'Old run_epoch frames are rejected'}},
  {id: 'chat.stale_head', kind: 'once', label: {zh: '下一次私聊：另一窗口已提交新回合', en: 'Next chat: another window already committed'}, expect: {zh: '409 后保留草稿、读最新版本，不自动重发', en: '409 → draft kept, latest version read, no auto replay'}},
  {id: 'chat.friend_reset_elsewhere', kind: 'once', label: {zh: '下一次私聊：好友在别处被重置（代次变化）', en: 'Next chat: friend reset elsewhere (epoch changed)'}, expect: {zh: '旧会话只读，停止旧展示并重新核验', en: 'Old conversation becomes read-only; identity re-verified'}},
  {id: 'auth.expired', kind: 'once', label: {zh: '下一次受保护请求：登录过期 401', en: 'Next protected request: 401 session expired'}, expect: {zh: '提示重新登录，草稿与位置保留', en: 'Sign-in prompt; draft and position kept'}},
  {id: 'auth.forbidden', kind: 'once', label: {zh: '下一次受保护请求：403 无权限', en: 'Next protected request: 403 forbidden'}, expect: {zh: '可读文案，不泄露私人数据', en: 'Readable copy, no private data'}},
  {id: 'net.slow', kind: 'toggle', label: {zh: '慢网络（+1.5 秒）', en: 'Slow network (+1.5 s)'}, expect: {zh: '加载与生成状态可见', en: 'Loading and generating states stay visible'}},
  {id: 'discover.error', kind: 'toggle', label: {zh: '发现页：加载失败', en: 'Discover: load fails'}, expect: {zh: '显示加载失败与重试，不说“没有内容”', en: 'Shows load failure with retry, not “nothing here”'}},
  {id: 'discover.append_error', kind: 'toggle', label: {zh: '发现页：追加失败', en: 'Discover: “load more” fails'}, expect: {zh: '已加载内容保留，追加处可重试', en: 'Loaded items stay; retry at the end'}},
  {id: 'live2d.model_missing', kind: 'toggle', label: {zh: 'Live2D 模型缺失', en: 'Live2D model missing'}, expect: {zh: '同一角色静态图 + 明确 unavailable，聊天照常', en: 'Same character’s static image + explicit unavailable'}},
  {id: 'assets.missing', kind: 'toggle', label: {zh: '图片素材缺失', en: 'Image assets missing'}, expect: {zh: '中性占位，不用别的角色顶替，阅读不阻塞', en: 'Neutral placeholders, never another character'}},
  {id: 'game.text_failed', kind: 'once', label: {zh: '下一次桌聊：台词生成失败', en: 'Next table chat: reply generation fails'}, expect: {zh: '已提交的牌局/revision 不变，不重掷不重抽', en: 'Committed board and revision unchanged'}},
  {id: 'game.unknown_start', kind: 'once', label: {zh: '下一次开局：回执丢失', en: 'Next game start: receipt lost'}, expect: {zh: '按原 key 查询，只有一局', en: 'Looks up the original key; only one game exists'}},
  {id: 'story.retryable_failure', kind: 'once', label: {zh: '下一次故事回合：校验失败可重试', en: 'Next story turn: validation fails (retryable)'}, expect: {zh: '半轮不提交，保留输入，可重试同一回合', en: 'No half turn; input kept; retry same turn'}},
]

const KEY = 'everwith.mock.scenarios'
type Active = Partial<Record<ScenarioId, true>>
let active: Active = readJSON<Active>(KEY, {}, 'session')
const listeners = new Set<() => void>()
const publish = () => { writeJSON(KEY, active, 'session'); listeners.forEach(fn => fn()) }

export const scenarios = {
  subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn) } },
  snapshot: () => active,
  isOn: (id: ScenarioId) => !!active[id],
  set(id: ScenarioId, on: boolean) { active = {...active}; if (on) active[id] = true; else delete active[id]; publish() },
  /** One-shot scenarios are consumed by the first request they apply to. */
  consume(id: ScenarioId): boolean {
    if (!active[id]) return false
    const def = SCENARIOS.find(s => s.id === id)
    if (def?.kind === 'once') { active = {...active}; delete active[id]; publish() }
    return true
  },
  clear() { active = {}; publish() },
}

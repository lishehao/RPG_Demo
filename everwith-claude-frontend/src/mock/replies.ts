/**
 * Deterministic SIMULATED replies for the local mock. No model, no provider, no
 * network. Every turn produced here is labelled reply_mode=simulated_fixed_reply and
 * the UI says “本地模拟回复”. Content is generic placeholder copy, not character canon.
 */
import {hash32} from '../lib/util'
import type {Lang} from '../lib/util'

type Expression = 'neutral' | 'happy' | 'surprised'
export type ReplyPlan = {segments: {kind: 'spoken' | 'action' | 'narration'; text: string}[]; expression: Expression}

const CATEGORIES: {id: string; test: RegExp; expression: Expression}[] = [
  {id: 'surprise', test: /真的吗|居然|不会吧|竟然|天哪|really\?|no way|seriously|wow/i, expression: 'surprised'},
  {id: 'play', test: /一起玩|玩一局|桌游|游戏|royale|splendor|cabo|play|game/i, expression: 'happy'},
  {id: 'thanks', test: /谢谢|感谢|厉害|喜欢你|真好|thank|thanks|great|love it|amazing/i, expression: 'happy'},
  {id: 'sorry', test: /对不起|抱歉|不好意思|sorry|apolog/i, expression: 'neutral'},
  {id: 'sad', test: /难过|累了|好累|伤心|烦|sad|tired|upset|exhausted/i, expression: 'neutral'},
  {id: 'story', test: /故事|剧院|名单|雨|末班车|手提箱|theat|guest list|rain|train|suitcase/i, expression: 'neutral'},
  {id: 'about', test: /你是谁|你喜欢|你平时|你觉得|who are you|do you like|what do you think|about you/i, expression: 'neutral'},
  {id: 'greet', test: /^(你好|嗨|在吗|早|晚上好|hi|hello|hey|good (morning|evening))/i, expression: 'happy'},
]

const ACTIONS: Record<string, {zh: string[]; en: string[]}> = {
  lena: {zh: ['轻轻点头。', '把笔记本合上，认真看着你。', '眯起眼睛想了想。'], en: ['Nods lightly.', 'Closes her notebook and looks at you properly.', 'Narrows her eyes, thinking.']},
  arthur: {zh: ['放下手里的笔。', '微微侧身，示意你继续。', '沉吟片刻。'], en: ['Sets down his pen.', 'Turns slightly, inviting you to go on.', 'Considers it for a moment.']},
  marcus: {zh: ['抱着手臂靠在墙边。', '点了一下头。', '把工具箱推到一边。'], en: ['Leans on the wall, arms folded.', 'Gives a single nod.', 'Pushes the toolbox aside.']},
  nora: {zh: ['眼睛一亮。', '往前凑了凑。', '歪着头笑了。'], en: ['Her eyes light up.', 'Leans in closer.', 'Tilts her head with a grin.']},
  iris: {zh: ['安静地听完，停顿了一下。', '指尖绕着杯沿转了一圈。', '低头想了想，又抬起眼。'], en: ['Listens quietly, then pauses.', 'Traces the rim of her cup.', 'Looks down to think, then back up.']},
  default: {zh: ['点点头。', '想了想。'], en: ['Nods.', 'Thinks for a moment.']},
}

const LINES: Record<string, {zh: string[]; en: string[]}> = {
  surprise: {zh: ['等等——真的？*睁大了眼睛*\n你再说一遍我听听。', '这倒是我没想到的。'], en: ['Wait — really? *eyes widening*\nSay that again.', 'I did not see that coming.']},
  play: {zh: ['好啊，我陪你。右边“一起玩”可以选桌游，开局前你还能改阵容。', '来一局？我先说好，我不会故意让着你。'], en: ['Sure, I\'ll join you. Use “Play together” to pick a game; you can still change seats before starting.', 'A game? Fair warning — I won\'t let you win on purpose.']},
  thanks: {zh: ['被你这么说，有点不好意思。*笑了一下*', '能帮上忙就好。'], en: ['Hearing that from you is a little embarrassing. *smiles*', 'Glad I could help.']},
  sorry: {zh: ['我听到了。谢谢你愿意说出来，我们慢慢把事情理清楚。', '没关系，不过我们还是把话说开。'], en: ['I hear you. Thank you for saying it; let\'s sort it out together.', 'It\'s alright — but let\'s talk it through.']},
  sad: {zh: ['那今天就先别勉强自己。想说的时候，我在这里。', '累了就歇一会儿。要不要讲讲发生了什么？'], en: ['Then don\'t push yourself today. I\'m here when you want to talk.', 'Rest a bit if you\'re tired. Want to tell me what happened?']},
  story: {zh: ['那件事我只知道自己亲眼看到的部分，别的我不乱猜。', '你提到的那段经历，我们可以从你记得的地方开始说。'], en: ['I only know the part I saw myself; I won\'t guess the rest.', 'We can start from what you remember of that.']},
  about: {zh: ['我嘛……比起说，我更习惯先看。你呢？', '这个问题我得想一想再回答你。'], en: ['Me? I tend to watch before I talk. And you?', 'Let me think before I answer that properly.']},
  greet: {zh: ['嗨。今天过得怎么样？', '你来了。坐吧。'], en: ['Hi. How has your day been?', 'You\'re here. Have a seat.']},
  fallback: {zh: ['嗯，我在听。你说的“{snippet}”，可以再多讲一点吗？', '我记下了“{snippet}”。接下来呢？'], en: ['Mm, I\'m listening. Tell me more about “{snippet}”?', 'Noted: “{snippet}”. What next?']},
}

export function classify(text: string): {id: string; expression: Expression} {
  for (const c of CATEGORIES) if (c.test.test(text.trim())) return {id: c.id, expression: c.expression}
  return {id: 'fallback', expression: 'neutral'}
}

export function planReply(character: string, text: string, language: Lang, turnIndex: number): ReplyPlan {
  const {id, expression} = classify(text)
  const seed = hash32(`${character}|${text}|${turnIndex}`)
  const acts = ACTIONS[character] ?? ACTIONS.default
  const lines = LINES[id] ?? LINES.fallback
  const action = acts[language][seed % acts[language].length]
  const snippet = [...text.replace(/\s+/g, ' ').trim()].slice(0, 18).join('') + ([...text.trim()].length > 18 ? '…' : '')
  const spoken = lines[language][(seed >>> 8) % lines[language].length].replace('{snippet}', snippet.replace(/\*/g, ''))
  const segments: ReplyPlan['segments'] = [{kind: 'action', text: action}, {kind: 'spoken', text: spoken}]
  if (id === 'play') segments.push({kind: 'narration', text: language === 'zh' ? '（本地模拟回复：不会替你创建牌局，需要你在准备页明确开始。）' : '(Local simulated reply: no game is created until you press Start.)'})
  return {segments, expression}
}

/** Preview (creation studio) replies: built only from the draft snapshot, isolated from friends. */
export function previewReply(draft: Record<string, unknown>, text: string, language: Lang, turnIndex: number): string {
  const name = typeof draft.name === 'string' && draft.name ? draft.name : (language === 'zh' ? '角色' : 'Character')
  const habit = typeof draft.habit === 'string' ? draft.habit : ''
  const {id} = classify(text)
  const seed = hash32(`${name}|${text}|${turnIndex}`)
  const lines = LINES[id] ?? LINES.fallback
  const base = lines[language][seed % lines[language].length].replace('{snippet}', [...text.trim()].slice(0, 16).join(''))
  return `${habit ? `*${habit.replace(/\*/g, '')}*\n` : ''}${base}`
}

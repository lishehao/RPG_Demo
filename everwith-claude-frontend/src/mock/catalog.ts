/**
 * Synthetic public catalogue for the LOCAL MOCK only.
 * Character one-line introductions follow the historical synthetic-QA discovery
 * cards (baseline/01_01-all-content.png); everything else here is new placeholder
 * copy written for this demo, not product canon. Character images are hash-verified
 * handoff files bound by source_id/version, never by display name. Story covers, story
 * scenes and game covers come from the user-provided GPT batch (/generated/; rights:
 * 用户经 GPT 生成并提供；商用/再分发权未核实 — see docs/GENERATED_ASSETS.json).
 */
import type {L10n} from '../lib/util'

const GEN = '/generated/batch-01'

export type Live2DKey = 'arthur' | 'lena' | 'marcus' | 'nora' | 'iris'
export type OfficialCharacter = {
  id: string; version: string; name: string; live2d: Live2DKey
  avatar: string; feed: string
  tagline: L10n; description: L10n; traits: L10n[]; voice: string
  greeting: L10n
  style: {warm: number; candor: number; reserve: number}
}

const P = '/handoff/assets/companions'
export const OFFICIAL_CHARACTERS: OfficialCharacter[] = [
  {
    id: 'official-lena', version: '1', name: 'Lena', live2d: 'lena',
    avatar: `${P}/portraits/lena-soft-anime-v2-neutral.png`, feed: `${P}/feed/lena.webp`,
    tagline: {zh: '剧院调查员', en: 'Theatre investigator'},
    description: {zh: '观察敏锐、说话直接的剧院调查员，重视承诺，也有自己的判断。', en: 'An observant, candid theater investigator who values promises and thinks for herself.'},
    traits: [{zh: '说话直接', en: 'Speaks plainly'}, {zh: '重视承诺', en: 'Keeps promises'}, {zh: '先观察再下结论', en: 'Observes before judging'}],
    voice: 'preset-lena-soft-alto',
    greeting: {zh: '*把伞收好，靠在门边。*\n你来了。今天想聊点什么？', en: '*Folds her umbrella and leans it by the door.*\nYou made it. What shall we talk about today?'},
    style: {warm: .6, candor: .9, reserve: .3},
  },
  {
    id: 'official-arthur', version: '1', name: 'Arthur', live2d: 'arthur',
    avatar: `${P}/portraits/arthur-r7-neutral.png`, feed: `${P}/feed/arthur.webp`,
    tagline: {zh: '剧院经理', en: 'Theatre manager'},
    description: {zh: '沉稳的剧院经理，会权衡各方利益，认真对待他在乎的人。', en: 'A composed theater manager who weighs competing interests and takes the people he cares about seriously.'},
    traits: [{zh: '沉稳', en: 'Composed'}, {zh: '权衡利弊', en: 'Weighs interests'}, {zh: '护短', en: 'Protective of his people'}],
    voice: 'preset-arthur-baritone',
    greeting: {zh: '*合上账本，抬头看你。*\n正好有空。坐吧，慢慢说。', en: '*Closes the ledger and looks up.*\nI have a moment. Sit down, take your time.'},
    style: {warm: .5, candor: .5, reserve: .7},
  },
  {
    id: 'official-marcus', version: '1', name: 'Marcus', live2d: 'marcus',
    avatar: `${P}/portraits/marcus-r3-neutral.png`, feed: `${P}/feed/marcus.webp`,
    tagline: {zh: '舞台监督', en: 'Stage manager'},
    description: {zh: '务实的舞台监督，观察细致，用行动表达信念。', en: 'A practical stage manager who watches carefully and expresses his convictions through action.'},
    traits: [{zh: '务实', en: 'Practical'}, {zh: '话少', en: 'Few words'}, {zh: '说到做到', en: 'Acts on his word'}],
    voice: 'preset-marcus-low',
    greeting: {zh: '*把手套塞进口袋。*\n嗯。有事就说，我听着。', en: '*Tucks his gloves into a pocket.*\nMm. Go ahead, I\'m listening.'},
    style: {warm: .4, candor: .7, reserve: .8},
  },
  {
    id: 'official-nora', version: '1', name: 'Nora', live2d: 'nora',
    avatar: `${P}/portraits/nora-r4-neutral.png`, feed: `${P}/feed/nora.webp`,
    tagline: {zh: '好奇的同伴', en: 'Curious companion'},
    description: {zh: '好奇又坦率，乐于尝试新想法，同时保留自己的看法。', en: 'Curious and candid, ready to explore new ideas while keeping her own views.'},
    traits: [{zh: '好奇', en: 'Curious'}, {zh: '坦率', en: 'Candid'}, {zh: '有主见', en: 'Has her own views'}],
    voice: 'preset-nora-bright',
    greeting: {zh: '*眼睛一亮，往前凑了凑。*\n你来得正好！我刚想到一个点子。', en: '*Her eyes light up as she leans in.*\nPerfect timing! I just had an idea.'},
    style: {warm: .8, candor: .8, reserve: .2},
  },
  {
    id: 'official-iris', version: '1', name: 'Iris', live2d: 'iris',
    avatar: `${P}/portraits/iris-local-neutral.png`, feed: `${P}/feed/iris.webp`,
    tagline: {zh: '细心的倾听者', en: 'Attentive listener'},
    description: {zh: '留意细节，需要一点时间去理解，再把感受说出口。', en: 'Attentive to details, taking time to understand and put her feelings into words.'},
    traits: [{zh: '细心', en: 'Attentive'}, {zh: '慢热', en: 'Slow to warm'}, {zh: '措辞谨慎', en: 'Careful with words'}],
    voice: 'preset-iris-calm',
    greeting: {zh: '*安静地点点头，把茶杯推到你面前。*\n……你好。慢慢来，我在听。', en: '*Nods quietly and slides a teacup toward you.*\n…Hello. Take your time, I\'m listening.'},
    style: {warm: .6, candor: .4, reserve: .8},
  },
]
export const characterById = (id: string) => OFFICIAL_CHARACTERS.find(c => c.id === id) ?? null

export type StoryRoleDef = {id: string; title: L10n; description: L10n; defaultCharacter: string; replaceable: boolean; locked?: boolean}
/** A place in a story. `position` is the vertical object-position of the reviewed 5:1 banner band. */
export type StoryScene = {image: string | null; position: string; label: L10n}
export type StoryBeat = {
  id: string; scene: string; narration: L10n
  lines: {role: string; text: L10n}[]
  clue?: {id: string; label: L10n}; objective?: number; minutes: number; hint: L10n
  keywords: string[]
}
export type StoryDef = {
  id: string; version: string; title: L10n; description: L10n; genre: L10n; contentNote: L10n
  cover: string | null; coverWide: string | null; playerRole: L10n; roles: StoryRoleDef[]; objectives: L10n[]; opening: L10n
  /** The opening shows the first beat's scene; each committed beat moves to its own scene. */
  beats: StoryBeat[]; scenes: Record<string, StoryScene>
  /** Shown for free turns once every beat has been played (open mode). */
  endingScene?: string
}

export const STORIES: StoryDef[] = [
  {
    id: 'story-promise-rain', version: '1',
    title: {zh: '雨中的约定', en: 'A Promise in the Rain'},
    description: {zh: '老剧院里，一份被改过的宾客名单把你和同伴挡在了雨中。', en: 'At an old theatre, an altered guest list keeps you and your companion out in the rain.'},
    genre: {zh: '悬疑 · 剧院', en: 'Mystery · Theatre'},
    contentNote: {zh: '轻度紧张情节，无暴力描写', en: 'Mild suspense, no graphic content'},
    cover: `${GEN}/story-promise-rain-cover-tall.webp`, coverWide: `${GEN}/story-promise-rain-cover-wide.webp`,
    playerRole: {zh: '受邀却被拒之门外的客人', en: 'An invited guest turned away at the door'},
    roles: [
      {id: 'investigator', title: {zh: '剧院调查员', en: 'Theatre investigator'}, description: {zh: '受托调查名单异常，知道剧院的旧规矩。', en: 'Hired to look into the guest list; knows the theatre\'s old rules.'}, defaultCharacter: 'official-lena', replaceable: true},
      {id: 'manager', title: {zh: '剧院经理', en: 'Theatre manager'}, description: {zh: '掌管名单与钥匙。作者锁定此位，不可替换。', en: 'Keeps the list and the keys. Locked by the author.'}, defaultCharacter: 'official-arthur', replaceable: false, locked: true},
      {id: 'stage', title: {zh: '舞台监督', en: 'Stage manager'}, description: {zh: '后台的每扇门都归他管。', en: 'Every backstage door is his responsibility.'}, defaultCharacter: 'official-marcus', replaceable: true},
    ],
    objectives: [
      {zh: '弄清名单为什么被改', en: 'Find out why the list was changed'},
      {zh: '找到改名单的人', en: 'Find who changed the list'},
      {zh: '决定要不要当面揭穿', en: 'Decide whether to confront them'},
    ],
    opening: {zh: '雨下得很大。剧院门口的灯牌忽明忽暗，门卫翻着名单，摇了摇头——你的名字被一道新鲜的墨迹划掉了。', en: 'The rain is heavy. The marquee flickers while the doorman scans his list and shakes his head — your name has been struck through in fresh ink.'},
    scenes: {
      'entrance-rain': {image: `${GEN}/story-promise-rain-scene-entrance-rain.webp`, position: '45%', label: {zh: '剧院正门 · 大雨', en: 'Theatre entrance · heavy rain'}},
      backstage: {image: `${GEN}/story-promise-rain-scene-backstage.webp`, position: '54%', label: {zh: '后台走廊', en: 'Backstage corridor'}},
      office: {image: `${GEN}/story-promise-rain-scene-office.webp`, position: '40%', label: {zh: '经理办公室', en: 'The manager\'s office'}},
      'entrance-after-rain': {image: `${GEN}/story-promise-rain-scene-entrance-after-rain.webp`, position: '52%', label: {zh: '剧院正门 · 雨小了', en: 'Theatre entrance · the rain eases'}},
    },
    beats: [
      {id: 'b1', scene: 'entrance-rain', minutes: 5, objective: 0, keywords: ['名单', 'list', '墨', 'ink', '门卫', 'doorman'],
        narration: {zh: '你凑近名单。划线的墨迹还没干透，边缘晕开了一点——有人在开场前不久才动过它。', en: 'You lean closer. The ink is still damp at the edges — someone changed it shortly before curtain.'},
        lines: [{role: 'investigator', text: {zh: '*用指尖轻碰纸面。*\n墨还是湿的。改名单的人离这里不会太远。', en: '*Touches the paper lightly.*\nStill wet. Whoever did this isn\'t far.'}}],
        clue: {id: 'wet-ink', label: {zh: '未干的划线墨迹', en: 'Still-wet strike-through'}}, hint: {zh: '*看向后台入口。*\n后台签到簿也许有记录。', en: '*Looks toward the stage door.*\nThe backstage sign-in book might show something.'}},
      {id: 'b2', scene: 'backstage', minutes: 10, objective: 1, keywords: ['后台', 'backstage', '签到', 'sign', '簿', 'book'],
        narration: {zh: '后台走廊比外面安静。签到簿摊在桌上，今晚最后一行的笔迹和名单上的划线一模一样。', en: 'The backstage corridor is quieter. The sign-in book lies open; tonight\'s last entry matches the strike-through exactly.'},
        lines: [{role: 'stage', text: {zh: '*把灯拧亮。*\n这一页是我七点锁的柜子。之后进来的人，只有拿着钥匙的。', en: '*Turns up the lamp.*\nI locked that cabinet at seven. Anyone after that had a key.'}}],
        clue: {id: 'sign-in', label: {zh: '签到簿上相同的笔迹', en: 'Matching handwriting in the sign-in book'}}, hint: {zh: '*压低声音。*\n钥匙一共只有两把。', en: '*Lowers voice.*\nThere are only two keys.'}},
      {id: 'b3', scene: 'office', minutes: 10, objective: 2, keywords: ['钥匙', 'key', '经理', 'manager', 'arthur'],
        narration: {zh: '经理办公室的门半掩着。桌上放着一把钥匙，钥匙牌上沾着同样的墨。', en: 'The manager\'s office door is ajar. A key lies on the desk, its tag smudged with the same ink.'},
        lines: [{role: 'manager', text: {zh: '*没有立刻否认，只是叹了口气。*\n名单是我改的。今晚有人要来闹事，我不能让他们借你的名字进门。', en: '*Doesn\'t deny it, only sighs.*\nI changed the list. Someone planned to use your name to get in tonight.'}}],
        clue: {id: 'ink-key', label: {zh: '沾墨的钥匙牌', en: 'Ink-smudged key tag'}}, hint: {zh: '*看着你。*\n你想怎么处理？', en: '*Looks at you.*\nHow do you want to handle this?'}},
      {id: 'b4', scene: 'entrance-after-rain', minutes: 15, keywords: ['揭穿', 'confront', '原谅', 'forgive', '一起', 'together'],
        narration: {zh: '雨势小了一些。剧院的灯重新亮起，开场铃声从门内传来。这一晚还没有结束，但名单的事已经说清。', en: 'The rain eases. The lights come back on and the first bell rings inside. The night isn\'t over, but the list is explained.'},
        lines: [{role: 'investigator', text: {zh: '*把伞递给你。*\n约好的事，我们还是一起去看完吧。', en: '*Hands you the umbrella.*\nWe promised. Let\'s still see the show together.'}}],
        hint: {zh: '*侧过头。*\n要进去吗？', en: '*Tilts her head.*\nShall we go in?'}},
    ],
  },
  {
    id: 'story-last-train', version: '1',
    title: {zh: '末班车之后', en: 'After the Last Train'},
    description: {zh: '末班车已经开走，候车室里却留下一只无人认领的手提箱。', en: 'The last train has left, but an unclaimed suitcase remains in the waiting room.'},
    genre: {zh: '日常 · 小悬疑', en: 'Slice of life · Light mystery'},
    contentNote: {zh: '无惊吓内容', en: 'No jump scares'},
    cover: `${GEN}/story-last-train-cover-tall.webp`, coverWide: `${GEN}/story-last-train-cover-wide.webp`,
    playerRole: {zh: '错过末班车的旅客', en: 'A traveller who missed the last train'},
    roles: [
      {id: 'clerk', title: {zh: '夜班站务员', en: 'Night station clerk'}, description: {zh: '要在天亮前处理好失物。', en: 'Must log the lost item before dawn.'}, defaultCharacter: 'official-nora', replaceable: true},
      {id: 'traveller', title: {zh: '同样滞留的旅人', en: 'Another stranded traveller'}, description: {zh: '坐在角落，似乎认得那只箱子。', en: 'Sits in the corner and seems to recognise the case.'}, defaultCharacter: 'official-iris', replaceable: true},
      {id: 'guard', title: {zh: '车站保安', en: 'Station guard'}, description: {zh: '负责锁门，按规矩办事。', en: 'Locks up and goes by the book.'}, defaultCharacter: 'official-marcus', replaceable: true},
    ],
    objectives: [
      {zh: '弄清手提箱属于谁', en: 'Find out who owns the suitcase'},
      {zh: '把它交到对的人手里', en: 'Get it to the right person'},
    ],
    opening: {zh: '站台的广播停了。候车室只剩下几盏灯，长椅边立着一只旧手提箱，标签被雨水泡得模糊。', en: 'The platform announcements have stopped. Only a few lamps remain on in the waiting room; beside a bench stands an old suitcase, its tag blurred by rain.'},
    scenes: {
      'waiting-room': {image: `${GEN}/story-last-train-scene-waiting-room.webp`, position: '52%', label: {zh: '候车室 · 深夜', en: 'Waiting room · late at night'}},
      corner: {image: `${GEN}/story-last-train-scene-corner.webp`, position: '55%', label: {zh: '候车室的角落', en: 'A corner of the waiting room'}},
      'duty-room': {image: `${GEN}/story-last-train-scene-duty-room.webp`, position: '45%', label: {zh: '值班室 · 天快亮了', en: 'Duty room · nearly dawn'}},
      'platform-dawn': {image: `${GEN}/story-last-train-scene-platform-dawn.webp`, position: '57%', label: {zh: '站台 · 天亮', en: 'Platform · daybreak'}},
    },
    endingScene: 'platform-dawn',
    beats: [
      {id: 'b1', scene: 'waiting-room', minutes: 5, objective: 0, keywords: ['箱', 'suitcase', '标签', 'tag'],
        narration: {zh: '你蹲下看标签。字迹被泡开了，只能认出一个城市名和半个电话号码。', en: 'You crouch to read the tag. Only a city name and half a phone number survive.'},
        lines: [{role: 'clerk', text: {zh: '*递来一支手电。*\n照着看看？失物登记要写清楚。', en: '*Hands you a flashlight.*\nTry this? The lost-item log needs details.'}}],
        clue: {id: 'tag', label: {zh: '半个电话号码', en: 'Half a phone number'}}, hint: {zh: '*看向角落的旅人。*\n她刚才好像一直盯着这只箱子。', en: '*Glances at the corner.*\nShe\'s been watching this case.'}},
      {id: 'b2', scene: 'corner', minutes: 10, objective: 1, keywords: ['旅人', 'traveller', '她', 'her', '认识', 'recognise'],
        narration: {zh: '角落里的旅人犹豫了一下，走了过来。她说出了号码的后半段。', en: 'The traveller in the corner hesitates, then comes over and recites the rest of the number.'},
        lines: [{role: 'traveller', text: {zh: '*声音很轻。*\n……那是我姐姐的箱子。她坐的是更早一班车。', en: '*Quietly.*\n…That\'s my sister\'s case. She took an earlier train.'}}],
        clue: {id: 'owner', label: {zh: '箱子主人的身份', en: 'The owner\'s identity'}}, hint: {zh: '*看向保安。*\n能先替她保管吗？', en: '*Looks at the guard.*\nCan it be held for her?'}},
      {id: 'b3', scene: 'duty-room', minutes: 10, keywords: ['保管', 'hold', '登记', 'log', '交给', 'give'],
        narration: {zh: '保安按规矩做了登记，把箱子锁进值班室。天边开始发白，第一班车的时刻表亮了起来。', en: 'The guard logs it and locks the case in the duty room. The sky pales; the first-train timetable lights up.'},
        lines: [{role: 'guard', text: {zh: '*在登记簿上签字。*\n明早她来，凭证件取。规矩不能破。', en: '*Signs the log.*\nShe can collect it with ID in the morning. Rules are rules.'}}],
        hint: {zh: '*伸了个懒腰。*\n还有一个小时才发车。', en: '*Stretches.*\nAn hour until the first train.'}},
    ],
  },
]
export const storyById = (id: string, version?: string) => STORIES.find(s => s.id === id && (!version || s.version === version)) ?? null

export type GameDef = {
  id: 'vegas' | 'gems' | 'cabo'; slug: 'royale' | 'splendor' | 'cabo'; name: string; title: L10n
  description: L10n; players: number[]; defaultPlayers: number; profile: string; profileLabel: L10n
  poster: string; preview: string; ruleNotes: L10n[]
}
/** Hover clips stay the package's. Posters are the generated covers; the package's own
 * 480×480 posters remain synced and can be restored by pointing `poster` back to
 * `${V}/royale-poster.webp` / `${V}/splendor-poster.webp` / `${V}/cabo-poster.webp`. */
const V = '/handoff/assets/companions/game-previews/v1'
export const GAMES: GameDef[] = [
  {id: 'vegas', slug: 'royale', name: 'Royale', title: {zh: 'Royale', en: 'Royale'},
    description: {zh: '掷骰并整组放入赌场，争夺各家钞票。', en: 'Roll and place dice to compete for casino banknotes.'},
    players: [2, 3, 4, 5], defaultPlayers: 4, profile: 'las-vegas-royale-broadway-zh-intro-v1',
    profileLabel: {zh: '入门局 · 三轮', en: 'Introductory · 3 rounds'}, poster: `${GEN}/game-royale-cover.webp`, preview: `${V}/royale.mp4`,
    ruleNotes: [
      {zh: '每人 7 个小骰 + 1 个 Biggy（影响力 2）；每轮 +2 筹码，可结余。', en: '7 small dice + 1 Biggy (weight 2) each; +2 chips per round, chips carry over.'},
      {zh: '掷剩余骰子，选一个点数，把该点数的骰子整组放进对应赌场；付 1 筹码可跳过本次放置。', en: 'Roll remaining dice, pick one face, place all dice of that face in that casino; pay 1 chip to skip.'},
      {zh: '影响力相同的玩家都被排除；三轮共 18 次派彩后结算，剩余筹码每枚折 10,000。', en: 'Tied influence is excluded; after 18 payouts over 3 rounds, chips are worth 10,000 each.'},
      {zh: '16 面效果板、额外骰与中文行动牌未实现（不是完整豪华版）。', en: 'Effect board, extra dice and Chinese action cards are not implemented (not the full deluxe game).'},
    ]},
  {id: 'gems', slug: 'splendor', name: 'Splendor', title: {zh: 'Splendor', en: 'Splendor'},
    description: {zh: '收集宝石，购买发展卡，赢得贵族青睐。', en: 'Collect gems and buy development cards.'},
    players: [2, 3, 4], defaultPlayers: 4, profile: 'splendor-base-2024-v2',
    profileLabel: {zh: '基础规则 v2（新局）', en: 'Base rules v2 (new games)'}, poster: `${GEN}/game-splendor-cover.webp`, preview: `${V}/splendor.mp4`,
    ruleNotes: [
      {zh: '拿三种不同颜色各一枚；该色池中至少 4 枚时可同色拿两枚；黄金只能通过预留获得。', en: 'Take 3 different colors, or 2 of one color if 4+ remain; gold only by reserving.'},
      {zh: '按成本与永久折扣购买；最多预留 3 张；持有宝石上限 10（含黄金）。', en: 'Buy with cost minus permanent bonuses; reserve up to 3; hold at most 10 tokens.'},
      {zh: '满足贵族条件必须访问，每回合至多一位；有人达到 15 分后补齐当前轮。', en: 'Nobles visit when eligible (one per turn); at 15 points the round is completed.'},
      {zh: '供应与卡牌数值来自冻结数据文件；未宣称已核实实体版全部数值。', en: 'Card/supply numbers come from the frozen data file; physical edition not verified.'},
    ]},
  {id: 'cabo', slug: 'cabo', name: 'CABO', title: {zh: 'CABO', en: 'CABO'},
    description: {zh: '记住你的牌，通过交换降低分数。', en: 'Remember your cards and exchange to lower your score.'},
    players: [2, 3, 4, 5], defaultPlayers: 4, profile: 'cabo-shareful-2025-en-slice-provisional',
    profileLabel: {zh: 'Shareful 流程 · 临时组件假设', en: 'Shareful procedures · provisional components'}, poster: `${GEN}/game-cabo-cover.webp`, preview: `${V}/cabo.mp4`,
    ruleNotes: [
      {zh: '52 张，值 0–13（0/13 各 2 张，其余各 4 张）——组件分布为假设，未核实。', en: '52 cards valued 0–13 (two each of 0/13, four of others) — provisional, unverified.'},
      {zh: '7/8 偷看自己、9/10 窥探他人、11/12 盲换——能力编号为假设，未核实。', en: '7/8 peek own, 9/10 spy, 11/12 blind swap — ability numbers are provisional.'},
      {zh: '叫 CABO 代替抽牌，其余各走一次；叫错 +5；12/12/13/13 射月他人 +50。', en: 'Calling CABO replaces a draw; others play once more; wrong call +5; 12/12/13/13 shoots the moon (+50 to others).'},
      {zh: '累计恰为 100 可一次回到 50；有人超过 100 即终局，最低累计分胜。', en: 'Exactly 100 resets once to 50; above 100 ends the game; lowest total wins.'},
    ]},
]
export const gameById = (id: string) => GAMES.find(g => g.id === id || g.slug === id) ?? null

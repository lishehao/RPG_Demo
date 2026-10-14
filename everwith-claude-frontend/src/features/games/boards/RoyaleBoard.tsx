import {useMemo} from 'react'
import type {CSSProperties, ReactNode} from 'react'
import {Check, Dices, SkipForward, X, Coins, Flag} from 'lucide-react'
import * as royale from '../../../games/engines/royale/engine'
import {useI18n} from '../../../app/i18n'
import {classNames} from '../../../lib/util'
import type {Lang} from '../../../lib/util'
import {ActionBar, GAME_ASSETS, cropStyle, formatMoney, seatColor, useBoardAsset, useBoardText, useRevisionState} from './shared'
import type {BoardProps} from './shared'

/**
 * Royale (Las Vegas Royale introductory profile). Everything numeric — dice pips, Biggy
 * weight, money values, chips, influence — is drawn by code from the seat-0 projection.
 * Animation only replays faces the engine already committed; it never draws new numbers.
 */
type PlayerView = {id: number; chips: number; roundGain: number; passes: number; earnings: ({id: string; value: number} | null)[]; cash: number | null; wealth: number | null}
type RoyaleView = Omit<royale.State, 'rng' | 'deck' | 'players'> & {bankCount: number; players: PlayerView[]}
type Selection = null | {kind: 'place'; face: number} | {kind: 'pass'}

const CASINOS: {zh: string; en: string; color: string}[] = [
  {zh: '奇迹', en: 'Miracle', color: '#77c6ac'}, {zh: '帝王', en: 'Kings', color: '#dabe76'}, {zh: '海滨', en: 'Marina', color: '#6abdd9'},
  {zh: '广场', en: 'Plaza', color: '#da839d'}, {zh: '埃及艳后', en: 'Cleopatra', color: '#ac9bd9'}, {zh: '日落', en: 'Sunset', color: '#ebaa76'},
]
const NEUTRAL = '#9aa1ab'
const PIPS: Record<number, number[]> = {1: [4], 2: [2, 6], 3: [2, 4, 6], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8]}

const TEXT = {
  zh: {
    round: '第 {n}/3 轮', paid: '已派彩 {n}/6', bank: '钱堆 {n} 张', pool: '筹码池 {n}', neutral: '中立', biggy: 'Biggy（影响力 2）',
    die: '{owner} 的骰子 {face} 点', dieBlank: '{owner} 的骰子（未掷）', influence: '影响力 {n}', tieOut: '并列出局', lead: '暂列第 {n}', paidOut: '已派彩',
    noWinner: '无人获奖，钞票回到钱堆', nextPayout: '下一个派彩', notes: '钱卡', casino: '{n} 号赌场 · {name}', you: '你',
    chips: '筹码 {n}', diceLeft: '剩 {n} 骰', biggyLeft: '含 Biggy', hidden: '{n} 张钞票（金额不公开）', cash: '现金 {money}', wealth: '总值 {money}',
    arenaYou: '你掷出的骰子', arenaOther: '{name} 掷出的骰子', arenaEmpty: '牌桌中央', waitRoll: '等待 {name} 掷骰', yourSupply: '你还有 {n} 颗骰子未放置',
    roll: '掷 {n} 颗骰子', rollPrompt: '轮到你：掷出剩下的 {n} 颗骰子。', choosePrompt: '选择一个点数：同点数的骰子会整组放进对应赌场。',
    faceBtn: '{face} 点 ×{count}', faceInf: '影响力 {n}', pass: '付 1 筹码跳过', passPrompt: '付 1 筹码跳过本次放置：骰子收回，下次轮到你时再掷。',
    placePrompt: '把 {count} 颗 {face} 点放进 {casino}（影响力 +{inf}）', confirmPlace: '确认放置', confirmPass: '确认跳过', cancel: '取消选择',
    preview: '放入后：', previewWin: '你将暂列第 {rank}，可得 {money}', previewTie: '你会与他人并列而出局', previewOut: '你暂时拿不到这里的钱卡',
    payoutPrompt: '轮到你推进派彩：{casino}', payout: '派彩', nextRound: '开始第 {n} 轮', roundEndPrompt: '第 {n} 轮的六个赌场都已派彩。',
    endedPrompt: '三轮结束，结果已锁定。', otherTurn: '{name}：{phase}', phase_roll: '掷骰', phase_choose: '选择放置', phase_payout: '派彩中', phase_roundEnd: '本轮结束', phase_ended: '已结束',
    abandoned: '本局已放弃（只读）', paused: '暂停中：可以先聊聊，再点“继续”。', place: '放到这里', placeHint: '{count} 颗 {face} 点',
    recent: '最新：', lastPayout: '{casino} 派彩', tieRule: '正影响力相同的玩家都出局，其余按影响力领钱。', biggyRule: 'Biggy 计 2 点影响力。',
    yourNotes: '你的钱卡', none: '暂无',
  },
  en: {
    round: 'Round {n}/3', paid: 'Paid {n}/6', bank: 'Bank {n} notes', pool: 'Chip pool {n}', neutral: 'Neutral', biggy: 'Biggy (influence 2)',
    die: '{owner}\'s die showing {face}', dieBlank: '{owner}\'s die (not rolled)', influence: 'Influence {n}', tieOut: 'tied – out', lead: 'now #{n}', paidOut: 'Paid',
    noWinner: 'No winner; notes return to the bank', nextPayout: 'Next payout', notes: 'Notes', casino: 'Casino {n} · {name}', you: 'You',
    chips: 'Chips {n}', diceLeft: '{n} dice left', biggyLeft: 'incl. Biggy', hidden: '{n} notes (amount hidden)', cash: 'Cash {money}', wealth: 'Total {money}',
    arenaYou: 'Your roll', arenaOther: '{name}\'s roll', arenaEmpty: 'Table centre', waitRoll: 'Waiting for {name} to roll', yourSupply: 'You still have {n} dice to place',
    roll: 'Roll {n} dice', rollPrompt: 'Your turn: roll your remaining {n} dice.', choosePrompt: 'Pick a number: all dice showing it go to that casino together.',
    faceBtn: '{face}s ×{count}', faceInf: 'influence {n}', pass: 'Pay 1 chip to skip', passPrompt: 'Pay 1 chip to skip this placement: dice return and you roll again next turn.',
    placePrompt: 'Place {count} × {face} in {casino} (influence +{inf})', confirmPlace: 'Confirm placement', confirmPass: 'Confirm skip', cancel: 'Cancel selection',
    preview: 'After placing:', previewWin: 'you would be #{rank} and take {money}', previewTie: 'you would tie and be excluded', previewOut: 'you would not reach a note here yet',
    payoutPrompt: 'Your turn to run the payout: {casino}', payout: 'Pay out', nextRound: 'Start round {n}', roundEndPrompt: 'All six casinos of round {n} have paid out.',
    endedPrompt: 'Three rounds done; the result is locked.', otherTurn: '{name}: {phase}', phase_roll: 'rolling', phase_choose: 'choosing', phase_payout: 'payouts', phase_roundEnd: 'round over', phase_ended: 'finished',
    abandoned: 'Game abandoned (read-only)', paused: 'Paused: chat first, then press Continue.', place: 'Place here', placeHint: '{count} × {face}',
    recent: 'Latest: ', lastPayout: '{casino} pays out', tieRule: 'Players tied on positive influence are all excluded; the rest are paid by influence.', biggyRule: 'Biggy counts as 2 influence.',
    yourNotes: 'Your notes', none: 'none',
  },
}

const ownerColor = (o: royale.Owner) => o === 'neutral' ? NEUTRAL : seatColor(o)
function pipColor(hex: string) {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255
  return (r * 299 + g * 587 + b * 114) / 1000 > 150 ? '#1b1410' : '#fff8ea'
}

export function Die({face, color, big = false, size = 'md', className, label, style}: {face: number | null; color: string; big?: boolean; size?: 'sm' | 'md' | 'lg'; className?: string; label: string; style?: CSSProperties}) {
  const pips = face ? PIPS[face] : []
  return (
    <span className={classNames('rb-die', big && 'is-big', `size-${size}`, face === null && 'is-blank', className)} style={{'--die': color, '--pip': pipColor(color), ...style} as CSSProperties} role="img" aria-label={label}>
      {Array.from({length: 9}, (_, i) => <i key={i} className={pips.includes(i) ? 'pip' : undefined} />)}
      {big && <b className="rb-biggy" aria-hidden="true">×2</b>}
    </span>
  )
}

const NOTE_TINTS: Record<number, string> = {30000: '#a9b7a0', 40000: '#9fb3c4', 50000: '#c8b48c', 60000: '#c9a2a0', 70000: '#b5a6c6', 80000: '#c2b26e', 90000: '#9cc0b6', 100000: '#d9b06a'}
function Note({value, lang, ornament, size = 'md', highlight}: {value: number; lang: Lang; ornament: string; size?: 'sm' | 'md'; highlight?: boolean}) {
  return (
    <span className={classNames('rb-note', `size-${size}`, highlight && 'is-highlight')} style={{'--note-tint': NOTE_TINTS[value] ?? '#c8b48c'} as CSSProperties} aria-label={`$${formatMoney(value, lang)}`}>
      <span className="rb-note-art" style={cropStyle(ornament, 1536, 1024, [0, 0, 1, 1], 2.1)} aria-hidden="true" />
      <b aria-hidden="true">{formatMoney(value, lang)}</b>
    </span>
  )
}

function Chips({n, label}: {n: number; label: string}) {
  return <span className="rb-chips" role="img" aria-label={label}>{Array.from({length: Math.min(n, 8)}, (_, i) => <i key={i} />)}{n > 8 && <small>+{n - 8}</small>}<b aria-hidden="true">{n}</b></span>
}

export function RoyaleBoard({view, pending, act, seatName, readOnly}: BoardProps) {
  const {lang} = useI18n()
  const bt = useBoardText(TEXT)
  const asset = useBoardAsset()
  const v = view.player_view as RoyaleView
  const [sel, setSel] = useRevisionState<Selection>(null, view.revision)
  const active = view.lifecycle === 'active'
  const myTurn = active && !readOnly && v.current === 0
  const ownerName = (o: royale.Owner) => o === 'neutral' ? bt('neutral') : seatName(o)
  const casinoLabel = (i: number) => bt('casino', {n: i + 1, name: CASINOS[i][lang]})
  const atlas = asset(`${GAME_ASSETS}/royale/generated/casino-scene-atlas-r7.png`)
  const ornament = asset(`${GAME_ASSETS}/royale/generated/fictional-game-token-ornament-20261004.png`)

  const last = v.history[v.history.length - 1]
  const lastEvent = last?.events[0]
  const rolledNow = new Set(last?.action.type === 'roll' ? (lastEvent?.dice ?? []).map(d => d.id) : [])
  const landedNow = new Set(last?.action.type === 'place' ? (lastEvent?.dice ?? []).map(d => d.id) : [])
  const paidNow = last?.action.type === 'payout' ? lastEvent?.result?.casino ?? null : null

  const arena = v.dice.filter(d => d.location === 'arena')
  const groups = useMemo(() => {
    const mine = v.dice.filter(d => d.owner === 0 && d.location === 'arena')
    const by = new Map<number, royale.Die[]>()
    for (const d of mine) by.set(d.face!, [...(by.get(d.face!) ?? []), d])
    return [...by.entries()].sort((a, b) => a[0] - b[0]).map(([face, dice]) => ({face, dice, influence: dice.reduce((n, d) => n + royale.weight(d), 0)}))
  }, [v.dice])
  const remainingMine = royale.remaining(v, 0)
  const preview = useMemo(() => {
    if (sel?.kind !== 'place') return null
    const next = structuredClone(v)
    for (const d of next.dice) if (d.owner === 0 && d.location === 'arena' && d.face === sel.face) { d.location = 'casino'; d.casino = sel.face - 1 }
    return royale.casinoResult(next as unknown as royale.State, sel.face - 1)
  }, [sel, v])

  const submit = async () => {
    if (!sel || pending) return
    await act(sel.kind === 'place' ? {type: 'place', face: sel.face} : {type: 'pass'})
  }

  // ----- action strip -----
  let bar: ReactNode
  if (view.lifecycle === 'abandoned') bar = <ActionBar prompt={bt('abandoned')} />
  else if (v.phase === 'ended' || view.lifecycle === 'ended') bar = <ActionBar prompt={bt('endedPrompt')} tone="turn" />
  else if (!myTurn) bar = <ActionBar prompt={view.ai_hold ? bt('paused') : bt('otherTurn', {name: seatName(v.current), phase: bt(`phase_${v.phase}`)})} />
  else if (v.phase === 'roll') bar = (
    <ActionBar prompt={bt('rollPrompt', {n: remainingMine.length})} tone="turn" testId="royale-actions">
      <button type="button" className="ew-btn primary" data-testid="royale-roll" disabled={pending} onClick={() => void act({type: 'roll'})}><Dices aria-hidden="true" />{bt('roll', {n: remainingMine.length})}</button>
    </ActionBar>
  )
  else if (v.phase === 'choose' && sel?.kind === 'place') {
    const g = groups.find(x => x.face === sel.face)!
    const rankIndex = preview ? preview.awards.findIndex(a => a.owner === 0) : -1
    const excluded = preview?.excluded.includes(0)
    bar = (
      <ActionBar tone="select" testId="royale-actions" prompt={bt('placePrompt', {count: g.dice.length, face: sel.face, casino: casinoLabel(sel.face - 1), inf: g.influence})}
        detail={<span>{bt('preview')} {excluded ? bt('previewTie') : rankIndex >= 0 ? bt('previewWin', {rank: rankIndex + 1, money: formatMoney(preview!.awards[rankIndex].value, lang)}) : bt('previewOut')}</span>}>
        <button type="button" className="ew-btn ghost" data-testid="royale-cancel" onClick={() => setSel(null)}><X aria-hidden="true" />{bt('cancel')}</button>
        <button type="button" className="ew-btn primary" data-testid="royale-confirm" disabled={pending} onClick={() => void submit()}><Check aria-hidden="true" />{bt('confirmPlace')}</button>
      </ActionBar>
    )
  } else if (v.phase === 'choose' && sel?.kind === 'pass') bar = (
    <ActionBar tone="select" prompt={bt('passPrompt')} testId="royale-actions">
      <button type="button" className="ew-btn ghost" data-testid="royale-cancel" onClick={() => setSel(null)}><X aria-hidden="true" />{bt('cancel')}</button>
      <button type="button" className="ew-btn primary" data-testid="royale-confirm" disabled={pending} onClick={() => void submit()}><Check aria-hidden="true" />{bt('confirmPass')}</button>
    </ActionBar>
  )
  else if (v.phase === 'choose') bar = (
    <ActionBar prompt={bt('choosePrompt')} tone="turn" testId="royale-actions" detail={<span className="ew-faint">{bt('biggyRule')} {bt('tieRule')}</span>}>
      {groups.map(g => (
        <button key={g.face} type="button" className="ew-btn rb-face-btn" data-testid={`royale-face-${g.face}`} onClick={() => setSel({kind: 'place', face: g.face})}
          aria-label={`${bt('faceBtn', {face: g.face, count: g.dice.length})} · ${bt('faceInf', {n: g.influence})} → ${casinoLabel(g.face - 1)}`}>
          <Die face={g.face} color={seatColor(0)} size="sm" label="" />
          <span>{bt('faceBtn', {face: g.face, count: g.dice.length})}<small>{bt('faceInf', {n: g.influence})} · {CASINOS[g.face - 1][lang]}</small></span>
        </button>
      ))}
      {v.players[0].chips > 0 && <button type="button" className="ew-btn ghost" data-testid="royale-pass" onClick={() => setSel({kind: 'pass'})}><SkipForward aria-hidden="true" />{bt('pass')}</button>}
    </ActionBar>
  )
  else if (v.phase === 'payout') bar = (
    <ActionBar tone="turn" prompt={bt('payoutPrompt', {casino: casinoLabel(v.payoutIndex)})} testId="royale-actions">
      <button type="button" className="ew-btn primary" data-testid="royale-payout" disabled={pending} onClick={() => void act({type: 'payout'})}><Coins aria-hidden="true" />{bt('payout')}</button>
    </ActionBar>
  )
  else if (v.phase === 'roundEnd') bar = (
    <ActionBar tone="turn" prompt={bt('roundEndPrompt', {n: v.round})} testId="royale-actions">
      <button type="button" className="ew-btn primary" data-testid="royale-next" disabled={pending} onClick={() => void act({type: 'nextRound'})}><Flag aria-hidden="true" />{bt('nextRound', {n: v.round + 1})}</button>
    </ActionBar>
  )

  const arenaOwner = arena[0]?.owner
  return (
    <div className="gb-board rb-board" data-phase={v.phase} data-current={v.current} data-round={v.round}>
      <div className="rb-top">
        <span className="rb-round"><strong>{bt('round', {n: v.round})}</strong></span>
        <span className="ew-chip">{bt('paid', {n: v.payoutIndex})}</span>
        <span className="ew-chip">{bt('bank', {n: v.bankCount})}</span>
        <span className="ew-chip">{bt('pool', {n: v.chipPool})}</span>
        {view.log.length > 0 && <span className="gb-recent" aria-live="off"><span className="ew-faint">{bt('recent')}</span>{view.log[view.log.length - 1].summary[lang]}</span>}
      </div>

      <div className="rb-casinos">
        {v.casinos.map((c, i) => {
          const dice = v.dice.filter(d => d.location === 'casino' && d.casino === i)
          const owners = [...new Set(dice.map(d => d.owner))]
          const done = i < v.payoutIndex && ['payout', 'roundEnd', 'ended'].includes(v.phase)
          const result = done ? v.results[i] : null
          const standing = !done && c.notes.length ? royale.casinoResult(v as unknown as royale.State, i) : null
          const selectable = myTurn && v.phase === 'choose' && groups.some(g => g.face === i + 1)
          const selected = sel?.kind === 'place' && sel.face === i + 1
          const counts = (result ?? standing)?.counts ?? owners.map(o => ({owner: o, count: dice.filter(d => d.owner === o).reduce((n, d) => n + royale.weight(d), 0)}))
          const excluded = (result ?? standing)?.excluded ?? []
          const awards = (result ?? standing)?.awards ?? []
          return (
            <section key={i} className={classNames('rb-casino', selected && 'is-selected', selectable && 'is-selectable', done && 'is-done', paidNow === i && 'is-paying', v.phase === 'payout' && v.payoutIndex === i && 'is-next')}
              style={{'--casino': CASINOS[i].color} as CSSProperties} aria-label={casinoLabel(i)} data-casino={i}>
              <div className="rb-casino-art" style={cropStyle(atlas, 1024, 1536, [(i % 2) / 2, Math.floor(i / 2) / 3, 1 / 2, 1 / 3], 1.25)} aria-hidden="true" />
              <header className="rb-casino-head">
                <Die face={i + 1} color={CASINOS[i].color} size="sm" label={`${i + 1}`} />
                <strong>{CASINOS[i][lang]}</strong>
                {v.phase === 'payout' && v.payoutIndex === i && <span className="ew-chip warn">{bt('nextPayout')}</span>}
                {done && <span className="ew-chip ok">{bt('paidOut')}</span>}
              </header>
              <div className="rb-casino-notes" aria-label={bt('notes')}>
                {done
                  ? (result!.awards.length ? result!.awards.map(a => <span key={a.note} className="rb-award"><span className="ew-seat-dot" style={{background: ownerColor(a.owner)}} aria-hidden="true" />{ownerName(a.owner)} <Note value={a.value} lang={lang} ornament={ornament} size="sm" highlight={paidNow === i} /></span>) : <span className="ew-faint ew-small">{bt('noWinner')}</span>)
                  : c.notes.map(id => <Note key={id} value={royale.note(id).value} lang={lang} ornament={ornament} />)}
              </div>
              <ul className="rb-influence">
                {counts.filter(x => x.count > 0).sort((a, b) => b.count - a.count).map(x => {
                  const rank = awards.findIndex(a => a.owner === x.owner)
                  const own = dice.filter(d => d.owner === x.owner)
                  return (
                    <li key={String(x.owner)} className={classNames(excluded.includes(x.owner) && 'is-excluded')}>
                      <span className="rb-own-dice">{own.map(d => <Die key={landedNow.has(d.id) ? `${d.id}-${view.revision}` : d.id} face={d.face} color={ownerColor(d.owner)} big={d.kind === 'big'} size="sm" className={landedNow.has(d.id) ? 'is-landing' : undefined} label={`${bt('die', {owner: ownerName(d.owner), face: d.face ?? ''})}${d.kind === 'big' ? ` · ${bt('biggy')}` : ''}`} />)}</span>
                      <span className="rb-own-name">{ownerName(x.owner)}</span>
                      <b>{bt('influence', {n: x.count})}</b>
                      {excluded.includes(x.owner) ? <span className="ew-chip danger">{bt('tieOut')}</span> : rank >= 0 && !done ? <span className="ew-chip">{bt('lead', {n: rank + 1})}</span> : null}
                    </li>
                  )
                })}
              </ul>
              {selectable && !selected && (() => {
                const g = groups.find(x => x.face === i + 1)!
                return <button type="button" className="rb-casino-pick" data-testid={`royale-casino-${i}`} onClick={() => setSel({kind: 'place', face: i + 1})}>{bt('place')} · {bt('placeHint', {count: g.dice.length, face: i + 1})}</button>
              })()}
            </section>
          )
        })}
      </div>

      <div className={classNames('rb-arena', arena.length > 0 && 'has-dice')} aria-label={arenaOwner === undefined ? bt('arenaEmpty') : arenaOwner === 0 ? bt('arenaYou') : bt('arenaOther', {name: ownerName(arenaOwner)})}>
        <span className="rb-arena-label">{arenaOwner === undefined ? (active && v.phase === 'roll' ? bt('waitRoll', {name: seatName(v.current)}) : bt('arenaEmpty')) : arenaOwner === 0 ? bt('arenaYou') : bt('arenaOther', {name: ownerName(arenaOwner)})}</span>
        <div className="rb-arena-dice">
          {arena.slice().sort((a, b) => (a.face ?? 0) - (b.face ?? 0)).map((d, k) => (
            <Die key={rolledNow.has(d.id) ? `${d.id}-${view.revision}` : d.id} face={d.face} color={ownerColor(d.owner)} big={d.kind === 'big'} size="lg"
              className={classNames(rolledNow.has(d.id) && 'is-rolling', sel?.kind === 'place' && d.owner === 0 && d.face === sel.face && 'is-chosen')}
              style={{'--roll-delay': `${(k % 4) * 45}ms`} as CSSProperties}
              label={`${bt('die', {owner: ownerName(d.owner), face: d.face ?? ''})}${d.kind === 'big' ? ` · ${bt('biggy')}` : ''}`} />
          ))}
          {arena.length === 0 && myTurn && v.phase === 'roll' && remainingMine.map(d => <Die key={d.id} face={null} color={seatColor(0)} big={d.kind === 'big'} size="lg" label={bt('dieBlank', {owner: seatName(0)})} />)}
        </div>
      </div>

      <ol className="rb-players" aria-label="players">
        {v.players.map(p => {
          const left = royale.remaining(v, p.id)
          return (
            <li key={p.id} className={classNames('rb-player', p.id === v.current && active && 'is-current', p.id === 0 && 'is-me')} data-seat={p.id}>
              <span className="ew-seat-dot" style={{background: seatColor(p.id)}} aria-hidden="true" />
              <strong className="rb-player-name">{seatName(p.id)}</strong>
              <Chips n={p.chips} label={bt('chips', {n: p.chips})} />
              <span className="rb-left">{bt('diceLeft', {n: left.length})}{left.some(d => d.kind === 'big') ? ` · ${bt('biggyLeft')}` : ''}</span>
              <span className="rb-money">{p.cash !== null ? <>{bt('cash', {money: formatMoney(p.cash, lang)})}{p.wealth !== null && v.phase === 'ended' ? ` · ${bt('wealth', {money: formatMoney(p.wealth, lang)})}` : ''}</> : bt('hidden', {n: p.earnings.length})}</span>
              {p.id === 0 && <span className="rb-my-notes" aria-label={bt('yourNotes')}>{p.earnings.length ? p.earnings.map((e, k) => e && <Note key={`${e.id}-${k}`} value={e.value} lang={lang} ornament={ornament} size="sm" />) : <small className="ew-faint">{bt('yourNotes')}：{bt('none')}</small>}</span>}
            </li>
          )
        })}
      </ol>
      {bar}
    </div>
  )
}

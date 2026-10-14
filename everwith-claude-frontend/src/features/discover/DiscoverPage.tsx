import {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react'
import {Search, X, RotateCcw, Users, BookOpen, Dice5} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import type {DiscoverTab} from '../../app/router'
import {api} from '../../api/adapter'
import type {DiscoverItem, RecordJSON} from '../../api/types'
import {Portrait, useAssetUrl} from '../../components/Portrait'
import {SpotArt, StageBackdrop} from '../../components/Art'
import {backdropFor} from '../../art/generated'
import {LiveStage} from '../../live2d/LiveStage'
import {characterFor} from '../../live2d/characters'
import {useApp} from '../../app/store'
import {pick, readJSON, writeJSON} from '../../lib/util'

const TABS: DiscoverTab[] = ['all', 'characters', 'stories', 'games']
type Load = {status: 'loading' | 'ready' | 'error'; items: DiscoverItem[]; total: number; next: number | null; appendError: boolean; appending: boolean}
const scrollKey = (tab: string, q: string) => `everwith.discover.scroll:${tab}:${q}`

export default function DiscoverPage({tab, q}: {tab: DiscoverTab; q: string}) {
  const {t, lang} = useI18n()
  const [query, setQuery] = useState(q)
  const [load, setLoad] = useState<Load>({status: 'loading', items: [], total: 0, next: null, appendError: false, appending: false})
  const [recent, setRecent] = useState<RecordJSON[]>([])
  const flight = useRef(0)
  const restored = useRef(false)
  const reducedMotion = useApp(s => s.reducedMotion)

  const fetchPage = useCallback(async (offset: number) => {
    const id = ++flight.current
    if (offset === 0) setLoad(l => ({...l, status: 'loading', appendError: false}))
    else setLoad(l => ({...l, appending: true, appendError: false}))
    try {
      const page = await api.catalog.discover({type: tab, q, offset})
      if (id !== flight.current) return
      setLoad(l => ({status: 'ready', items: offset === 0 ? page.items : [...l.items, ...page.items], total: page.total, next: page.next_offset, appendError: false, appending: false}))
    } catch {
      if (id !== flight.current) return
      if (offset === 0) setLoad({status: 'error', items: [], total: 0, next: null, appendError: false, appending: false})
      else setLoad(l => ({...l, appending: false, appendError: true}))
    }
  }, [tab, q])

  useEffect(() => { restored.current = false; void fetchPage(0) }, [fetchPage])
  useEffect(() => { setQuery(q) }, [q])
  useEffect(() => { api.records.list(false).then(r => setRecent(r.items.filter(x => x.status === 'active' || x.status === 'paused').slice(0, 3))).catch(() => setRecent([])) }, [])
  // Debounced search keeps the URL (and therefore Back/refresh) as the source of truth.
  useEffect(() => {
    if (query === q) return
    const timer = setTimeout(() => navigate(href.discover(tab, query.trim()), {replace: true}), 280)
    return () => clearTimeout(timer)
  }, [query, q, tab])

  // Scroll position per tab+query survives detail → Back.
  useLayoutEffect(() => {
    const main = document.getElementById('main')
    if (!main || load.status !== 'ready' || restored.current) return
    restored.current = true
    const saved = readJSON<{top: number; count: number} | null>(scrollKey(tab, q), null, 'session')
    if (saved && saved.count > load.items.length && load.next !== null) { void fetchPage(load.items.length); restored.current = false; return }
    main.scrollTop = saved?.top ?? 0
  }, [load.status, load.items.length, load.next, tab, q, fetchPage])
  useEffect(() => {
    const main = document.getElementById('main')
    if (!main) return
    let raf = 0
    const onScroll = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => writeJSON(scrollKey(tab, q), {top: main.scrollTop, count: load.items.length}, 'session')) }
    main.addEventListener('scroll', onScroll, {passive: true})
    return () => { main.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf) }
  }, [tab, q, load.items.length])

  return (
    <div className="ew-page ew-discover">
      <header className="ew-page-head">
        <div>
          <h1>{t('discover.title')}</h1>
          <p className="ew-muted">{t('discover.subtitle')}</p>
        </div>
        <form className="ew-search" role="search" onSubmit={e => { e.preventDefault(); navigate(href.discover(tab, query.trim()), {replace: true}) }}>
          <Search aria-hidden="true" />
          <input className="ew-input" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={t('discover.search')} aria-label={t('discover.search')} />
          {query && <button type="button" className="ew-icon-btn" aria-label={t('common.clear')} onClick={() => setQuery('')}><X aria-hidden="true" /></button>}
        </form>
      </header>
      <nav className="ew-tabs" aria-label={t('discover.title')}>
        {TABS.map(x => <a key={x} href={href.discover(x, q)} className="ew-tab" aria-current={x === tab ? 'page' : undefined}>{t(`discover.tab.${x}`)}</a>)}
      </nav>
      {recent.length > 0 && tab === 'all' && !q && (
        <section className="ew-continue" aria-label={t('discover.continue')}>
          <h2 className="ew-section-title">{t('discover.continue')}</h2>
          <div className="ew-continue-row">
            {recent.map(r => <a key={r.id} className="ew-continue-card" href={r.kind === 'story' ? href.storyPlay(r.id) : href.gamePlay(r.id)}>
              {r.image ? <span className="ew-continue-thumb" aria-hidden="true"><Portrait src={r.image} name={pick(r.title, lang)} alt="" /></span> : r.kind === 'story' ? <BookOpen aria-hidden="true" /> : <Dice5 aria-hidden="true" />}
              <span><strong>{pick(r.title, lang)}</strong><small>{r.lineup.map(l => l.name).join(' · ')}</small></span>
            </a>)}
          </div>
        </section>
      )}
      {load.status === 'loading' && <div className="ew-grid" aria-busy="true">{Array.from({length: 8}, (_, i) => <div key={i} className="ew-card skeleton"><div className="ew-skeleton ew-card-media" /><div className="ew-skeleton" style={{height: 18, margin: 14}} /></div>)}</div>}
      {load.status === 'error' && (
        <div className="ew-load-failed">
          <SpotArt kind="load-error" />
          <div className="ew-notice danger" role="alert">
            <RotateCcw aria-hidden="true" />
            <div><strong>{t('discover.error')}</strong><div className="ew-notice-actions"><button type="button" className="ew-btn small" onClick={() => void fetchPage(0)}>{t('common.retry')}</button></div></div>
          </div>
        </div>
      )}
      {load.status === 'ready' && load.items.length === 0 && (
        q ? <div className="ew-empty"><h2>{t('discover.empty.search', {q})}</h2><button type="button" className="ew-btn" onClick={() => { setQuery(''); navigate(href.discover(tab), {replace: true}) }}>{t('discover.empty.clear')}</button></div>
          : <div className="ew-empty"><h2>{t('discover.empty.catalog')}</h2></div>
      )}
      {load.status === 'ready' && load.items.length > 0 && (
        <>
          <ul className="ew-grid" aria-label={t(`discover.tab.${tab}`)}>
            {load.items.map(item => <li key={`${item.kind}:${item.id}`}><DiscoverCard item={item} reducedMotion={reducedMotion} /></li>)}
          </ul>
          <div className="ew-grid-foot">
            {load.appendError && <div className="ew-notice warn" role="alert"><span>{t('discover.appendError')}</span><button type="button" className="ew-btn small" onClick={() => void fetchPage(load.items.length)}>{t('common.retry')}</button></div>}
            {load.next !== null && !load.appendError && <button type="button" className="ew-btn" disabled={load.appending} onClick={() => void fetchPage(load.next!)}>{load.appending && <span className="ew-spinner" />}{t('discover.loadMore')}</button>}
          </div>
        </>
      )}
    </div>
  )
}

let hoverOwner: (() => void) | null = null
function DiscoverCard({item, reducedMotion}: {item: DiscoverItem; reducedMotion: boolean}) {
  const {t, lang} = useI18n()
  const [live, setLive] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const preview = useAssetUrl(item.kind === 'game' ? item.preview : null)
  const begin = () => {
    if (item.kind !== 'character' || reducedMotion) return
    clearTimeout(timer.current)
    timer.current = setTimeout(() => { hoverOwner?.(); hoverOwner = () => setLive(false); setLive(true) }, 450)
  }
  const end = () => { clearTimeout(timer.current); setLive(false) }
  useEffect(() => () => clearTimeout(timer.current), [])
  if (item.kind === 'character') {
    const cfg = characterFor(item.id, item.version)
    return (
      <a className="ew-card is-character" href={href.character(item.id, item.version)} onMouseEnter={begin} onMouseLeave={end} onFocus={begin} onBlur={end}>
        <div className="ew-card-media">
          <StageBackdrop src={backdropFor(cfg?.key)} />
          {live && cfg ? <LiveStage character={cfg} name={item.name} preset="card" showStatus={false} backdrop={null} /> : <Portrait src={item.feed} name={item.name} position="50% 10%" />}
          <span className="ew-card-kind">{t('discover.kind.character')}</span>
        </div>
        <div className="ew-card-body">
          <h3 className="ew-card-title">{item.name}</h3>
          <p className="ew-card-tag">{pick(item.tagline, lang)}</p>
          <p className="ew-card-desc">{pick(item.description, lang)}</p>
        </div>
      </a>
    )
  }
  if (item.kind === 'story') {
    return (
      <a className="ew-card is-story" href={href.story(item.id, item.version)}>
        <div className="ew-card-media">
          {item.image ? <Portrait src={item.image} name={pick(item.title, lang)} /> : <div className="ew-card-placeholder" aria-hidden="true"><BookOpen /></div>}
          <span className="ew-card-kind">{t('discover.kind.story')}</span>
        </div>
        <div className="ew-card-body">
          <h3 className="ew-card-title">{pick(item.title, lang)}</h3>
          <p className="ew-card-tag">{pick(item.genre, lang)} · {pick(item.content_note, lang)}</p>
          <p className="ew-card-desc">{pick(item.description, lang)}</p>
        </div>
      </a>
    )
  }
  return (
    <a className="ew-card is-game" href={href.gamePrepare(item.id, null, href.discover('games'))}
      onMouseEnter={e => { const v = e.currentTarget.querySelector('video'); if (v && !reducedMotion) void v.play().catch(() => {}) }}
      onMouseLeave={e => { const v = e.currentTarget.querySelector('video'); if (v) { v.pause(); v.currentTime = 0 } }}>
      <div className="ew-card-media">
        <Portrait src={item.poster} name={item.name} />
        {preview && <video className="ew-card-video" src={preview} muted loop playsInline preload="none" aria-hidden="true" />}
        <span className="ew-card-kind">{t('discover.kind.game')}</span>
      </div>
      <div className="ew-card-body">
        <h3 className="ew-card-title">{item.name}</h3>
        <p className="ew-card-tag"><Users aria-hidden="true" className="ew-inline-icon" /> {item.players.join(' / ')} {t('common.players')} · {t('discover.companionGame')}</p>
        <p className="ew-card-desc">{pick(item.description, lang)}</p>
      </div>
    </a>
  )
}

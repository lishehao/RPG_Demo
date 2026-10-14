import {useSyncExternalStore, lazy, Suspense, useEffect, useMemo, useState} from 'react'
import {Compass, History, PenLine, Users, UserCircle2, PanelLeftClose, PanelLeftOpen, Languages, FlaskConical} from 'lucide-react'
import {LangContext, makeT} from './i18n'
import {appStore, loadAccount, setLang, setNavCollapsed, useApp} from './store'
import {href, navigate, useRoute} from './router'
import type {Route} from './router'
import {AuthDialog} from '../features/account/AuthDialog'
import {MockPanel, OPEN_MOCK_PANEL} from '../features/mock/MockPanel'
import {scenarios} from '../mock/scenarios'
import {Toasts} from '../components/Toasts'
import {ADAPTER_MODE} from '../api/adapter'
import {Portrait, useAssetUrl} from '../components/Portrait'
import {BRAND_EMBLEM, personaAvatarUrl} from '../art/generated'
import {classNames} from '../lib/util'

const DiscoverPage = lazy(() => import('../features/discover/DiscoverPage'))
const FriendsPage = lazy(() => import('../features/friends/FriendsPage'))
const ChatPage = lazy(() => import('../features/chat/ChatPage'))
const CharacterPage = lazy(() => import('../features/character/CharacterPage'))
const StoryDetailPage = lazy(() => import('../features/story/StoryDetailPage'))
const StoryPreparePage = lazy(() => import('../features/story/StoryPreparePage'))
const StoryPlayPage = lazy(() => import('../features/story/StoryPlayPage'))
const GamePreparePage = lazy(() => import('../features/games/GamePreparePage'))
const GamePlayPage = lazy(() => import('../features/games/GamePlayPage'))
const RecentPage = lazy(() => import('../features/recent/RecentPage'))
const CreatePage = lazy(() => import('../features/create/CreatePage'))
const WorkEditorPage = lazy(() => import('../features/create/WorkEditorPage'))
const AccountPage = lazy(() => import('../features/account/AccountPage'))
const NotFoundPage = lazy(() => import('../features/misc/NotFoundPage'))

const NAV = [
  {key: 'friends', icon: Users, label: 'nav.friends', href: href.friends(), match: ['friends', 'chat']},
  {key: 'discover', icon: Compass, label: 'nav.discover', href: href.discover(), match: ['discover', 'character', 'story', 'storyPrepare', 'gamePrepare']},
  {key: 'recent', icon: History, label: 'nav.recent', href: href.recent(), match: ['recent', 'storyPlay']},
  {key: 'create', icon: PenLine, label: 'nav.create', href: href.create(), match: ['create', 'work']},
] as const

function page(route: Route) {
  switch (route.name) {
    case 'discover': return <DiscoverPage tab={route.tab} q={route.q} />
    case 'friends': return <FriendsPage />
    case 'chat': return <ChatPage key={route.friendId} friendId={route.friendId} />
    case 'character': return <CharacterPage key={`${route.id}@${route.version}`} sourceId={route.id} version={route.version} />
    case 'story': return <StoryDetailPage key={route.id} storyId={route.id} version={route.version} />
    case 'storyPrepare': return <StoryPreparePage key={`${route.id}|${route.withFriend}`} storyId={route.id} version={route.version} withFriend={route.withFriend} from={route.from} />
    case 'storyPlay': return <StoryPlayPage key={route.sessionId} sessionId={route.sessionId} />
    case 'gamePrepare': return <GamePreparePage key={`${route.gameId}|${route.withFriend}`} gameId={route.gameId} withFriend={route.withFriend} from={route.from} />
    case 'gamePlay': return <GamePlayPage key={route.sessionId} sessionId={route.sessionId} />
    case 'recent': return <RecentPage archived={route.archived} />
    case 'create': return <CreatePage />
    case 'work': return <WorkEditorPage key={route.workId} workId={route.workId} />
    case 'account': return <AccountPage />
    case 'notFound': return <NotFoundPage />
    default: return null
  }
}

export function App() {
  const lang = useApp(s => s.lang)
  const collapsed = useApp(s => s.navCollapsed)
  const reducedMotion = useApp(s => s.reducedMotion)
  const account = useApp(s => s.account)
  const friends = useApp(s => s.friends)
  const route = useRoute()
  const scenarioCount = Object.keys(useSyncExternalStore(scenarios.subscribe, scenarios.snapshot, scenarios.snapshot)).length
  const i18n = useMemo(() => ({lang, t: makeT(lang)}), [lang])
  const {t} = i18n
  useEffect(() => { void loadAccount(); document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en' }, []) // eslint-disable-line react-hooks/exhaustive-deps
  // Empty hash: returning users with friends land on Friends; new visitors on Discover.
  // Explicit deep links, Back and sign-in returns always win over this default.
  useEffect(() => {
    if (route.name !== 'root' || !account) return
    if (account.authenticated && friends === null) return
    navigate(account.authenticated && friends && friends.length ? href.friends() : href.discover(), {replace: true})
  }, [route.name, account, friends])
  useEffect(() => {
    const titles: Partial<Record<Route['name'], string>> = {discover: t('discover.title'), friends: t('friends.title'), recent: t('recent.title'), create: t('create.title'), account: t('account.title')}
    document.title = `${titles[route.name] ?? 'Everwith'} · ${t('mock.badge')}`
  }, [route.name, t])
  const task = route.name === 'gamePlay'
  const active = NAV.find(n => (n.match as readonly string[]).includes(route.name))?.key
  return (
    <LangContext.Provider value={i18n}>
      <div className={classNames('ew-app', collapsed && 'nav-collapsed', task && 'is-task', reducedMotion && 'reduce-motion')}>
        <a className="ew-skip" href="#main" onClick={e => { e.preventDefault(); document.getElementById('main')?.focus() }}>{t('shell.skip')}</a>
        {!task && <nav className="ew-nav" aria-label={t('nav.main')}>
          <div className="ew-brand">
            <BrandMark />
            <span className="ew-brand-name">{t('brand')}</span>
          </div>
          <ul className="ew-nav-list">
            {NAV.map(item => {
              const Icon = item.icon
              return <li key={item.key}><a href={item.href} className="ew-nav-item" aria-current={active === item.key ? 'page' : undefined} title={collapsed ? t(item.label) : undefined}>
                <Icon aria-hidden="true" /><span className="ew-nav-label">{t(item.label)}</span></a></li>
            })}
          </ul>
          <div className="ew-nav-foot">
            <span className="ew-chip mock ew-nav-mock" title={t('mock.badge.long')}>{ADAPTER_MODE === 'mock' ? t('mock.badge') : 'REAL (not connected)'}</span>
            {ADAPTER_MODE === 'mock' && <button type="button" className="ew-nav-item as-button" onClick={() => window.dispatchEvent(new Event(OPEN_MOCK_PANEL))} title={t('mock.panel.title')} aria-haspopup="dialog" data-testid="mock-panel-open">
              <FlaskConical aria-hidden="true" /><span className="ew-nav-label">{t('mock.panel')}</span>{scenarioCount > 0 && <span className="ew-mock-count" aria-label={`${scenarioCount}`}>{scenarioCount}</span>}
            </button>}
            <button type="button" className="ew-nav-item as-button" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')} aria-label={lang === 'zh' ? 'Switch to English' : '切换到中文'} title={lang === 'zh' ? 'English' : '中文'}>
              <Languages aria-hidden="true" /><span className="ew-nav-label">{lang === 'zh' ? '中文 · EN' : 'EN · 中文'}</span>
            </button>
            <a href={href.account()} className="ew-nav-item" aria-current={route.name === 'account' ? 'page' : undefined} title={collapsed ? t('nav.account') : undefined}>
              {account?.persona?.avatar
                ? <span className="ew-nav-avatar" aria-hidden="true"><Portrait src={personaAvatarUrl(account.persona.avatar)} name={account.persona.name || '·'} alt="" /></span>
                : <UserCircle2 aria-hidden="true" />}
              <span className="ew-nav-label ew-nav-account">{account?.authenticated ? account.persona?.name || account.account?.email : t('account.guest')}</span>
            </a>
            <button type="button" className="ew-nav-item as-button" onClick={() => setNavCollapsed(!collapsed)} aria-label={collapsed ? t('nav.expand') : t('nav.collapse')} aria-expanded={!collapsed}>
              {collapsed ? <PanelLeftOpen aria-hidden="true" /> : <PanelLeftClose aria-hidden="true" />}<span className="ew-nav-label">{t('nav.collapse')}</span>
            </button>
          </div>
        </nav>}
        <main id="main" className="ew-main" tabIndex={-1}>
          {ADAPTER_MODE === 'real' && <div className="ew-notice danger" role="alert">Real adapter selected but not connected. See README “Real adapter gaps”. No mock fallback is used.</div>}
          <Suspense fallback={<div className="ew-page-loading is-first" role="status"><BrandMark /><span className="ew-spinner" />{t('common.loading')}</div>}>
            {page(route)}
          </Suspense>
        </main>
        <MockPanel />
        <AuthDialog />
        <Toasts />
      </div>
    </LangContext.Provider>
  )
}
/** Generated brand emblem; the lettermark stays as the fallback if the file is missing. */
function BrandMark() {
  const url = useAssetUrl(BRAND_EMBLEM)
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  return url && !failed
    ? <img className="ew-brand-mark is-emblem" src={url} alt="" aria-hidden="true" width={30} height={30} draggable={false} onError={() => setFailed(true)} />
    : <span className="ew-brand-mark" aria-hidden="true">e</span>
}
export {appStore}

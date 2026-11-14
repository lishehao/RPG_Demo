import {useCallback, useEffect, useState} from 'react'
import {Archive, ArchiveRestore, BookOpen, Dices, Eye, Play, Trash2} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import type {I18nKey} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {toast} from '../../app/store'
import {api} from '../../api/adapter'
import type {RecordJSON} from '../../api/types'
import {ConfirmDialog} from '../../components/Dialog'
import {Portrait} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {classNames, formatTime, pick} from '../../lib/util'

const STATUS: Record<string, I18nKey> = {active: 'recent.status.active', in_progress: 'recent.status.active', ended: 'recent.status.ended', abandoned: 'recent.status.abandoned', paused: 'recent.status.paused', read_only: 'story.readOnlyShort'}

/** One row per concrete run — never merged by work title. Continue opens that exact run. */
export default function RecentPage({archived}: {archived: boolean}) {
  const {t, lang} = useI18n()
  const [items, setItems] = useState<RecordJSON[] | null>(null)
  const [error, setError] = useState(false)
  const [confirm, setConfirm] = useState<RecordJSON | null>(null)
  const load = useCallback(() => { setError(false); api.records.list(archived).then(r => setItems(r.items)).catch(() => setError(true)) }, [archived])
  useEffect(() => { setItems(null); load() }, [load])
  const mutate = async (r: RecordJSON, action: 'archive' | 'restore' | 'delete') => {
    try { await api.records.mutate(r.kind, r.id, action); load() } catch { toast(t('error.generic'), 'error') }
  }
  const open = (r: RecordJSON) => navigate(r.kind === 'story' ? href.storyPlay(r.id) : href.gamePlay(r.id))
  return (
    <div className="ew-page ew-recent">
      <header className="ew-page-head"><div><h1>{t('recent.title')}</h1><p className="ew-muted">{t('recent.subtitle')}</p></div></header>
      <nav className="ew-tabs" aria-label={t('recent.title')}>
        <a className="ew-tab" aria-current={!archived ? 'page' : undefined} href={href.recent(false)}>{t('recent.active')}</a>
        <a className="ew-tab" aria-current={archived ? 'page' : undefined} href={href.recent(true)}>{t('recent.archived')}</a>
      </nav>
      {error && <div className="ew-notice danger" role="alert"><span>{t('error.network')}<span className="ew-notice-actions"><button type="button" className="ew-btn small" onClick={load}>{t('common.retry')}</button></span></span></div>}
      {!items && !error && <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>}
      {items && items.length === 0 && <div className="ew-empty"><SpotArt kind="recent" /><h2>{archived ? t('recent.emptyArchived') : t('recent.empty')}</h2>{!archived && <a className="ew-btn primary" href={href.discover()}>{t('recent.goDiscover')}</a>}</div>}
      {items && items.length > 0 && (
        <ul className="ew-records">
          {items.map(r => {
            const live = r.status === 'active' || r.status === 'in_progress' || r.status === 'paused'
            const winners = r.result?.winners.map(w => r.lineup[w]?.name ?? `#${w}`)
            return (
              <li key={`${r.kind}-${r.id}`} className="ew-record" data-kind={r.kind} data-testid="record">
                <span className="ew-record-icon" aria-hidden="true">{r.image ? <Portrait src={r.image} name={pick(r.title, lang)} alt="" /> : r.kind === 'story' ? <BookOpen /> : <Dices />}</span>
                <span className="ew-record-main">
                  <span className="ew-record-title"><strong>{pick(r.title, lang)}</strong>
                    <span className="ew-chip">{r.kind === 'story' ? t('recent.story') : t('recent.game')}</span>
                    <span className={classNames('ew-chip', live ? 'ok' : r.status === 'abandoned' ? 'warn' : '')}>{t(STATUS[r.status] ?? 'recent.status.active')}</span>
                    {r.rematch_of && <span className="ew-chip">{t('recent.rematch')}</span>}</span>
                  <span className="ew-record-lineup">{t('recent.lineup')}：{r.lineup.map(l => `${l.role ? `${pick(l.role, lang)}·` : ''}${l.name}${l.friend ? `（${t('common.friend')}）` : l.temporary ? `（${t('common.temporary')}）` : ''}`).join(lang === 'zh' ? '、' : ', ')}</span>
                  <span className="ew-record-meta">{r.kind === 'story' ? t('story.runMeta', {turns: r.turns ?? 0, time: formatTime(r.updated_at, lang)}) : t('recent.gameMeta', {rev: r.revision ?? 0, time: formatTime(r.updated_at, lang)})}
                    {winners && winners.length > 0 ? ` · ${t('game.winner')}：${winners.join('、')}` : ''}</span>
                </span>
                <span className="ew-record-actions">
                  {!archived && <button type="button" className={classNames('ew-btn small', live && 'primary')} onClick={() => open(r)} data-testid="record-open">{live ? <><Play aria-hidden="true" />{t('recent.continue')}</> : <><Eye aria-hidden="true" />{t('recent.review')}</>}</button>}
                  {archived
                    ? <button type="button" className="ew-btn small" onClick={() => void mutate(r, 'restore')}><ArchiveRestore aria-hidden="true" />{t('common.restore')}</button>
                    : <button type="button" className="ew-btn small ghost" onClick={() => void mutate(r, 'archive')}><Archive aria-hidden="true" />{t('common.archive')}</button>}
                  <button type="button" className="ew-btn small ghost danger-text" onClick={() => setConfirm(r)} aria-label={`${t('common.delete')} · ${pick(r.title, lang)}`}><Trash2 aria-hidden="true" />{t('common.delete')}</button>
                </span>
              </li>
            )
          })}
        </ul>
      )}
      {confirm && <ConfirmDialog title={`${t('common.delete')} · ${pick(confirm.title, lang)}`} body={<p>{t('recent.deleteConfirm')}</p>} confirmLabel={t('common.delete')} danger
        onCancel={() => setConfirm(null)} onConfirm={() => { const r = confirm; setConfirm(null); void mutate(r, 'delete') }} />}
    </div>
  )
}

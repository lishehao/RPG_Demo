import {useEffect, useRef, useState} from 'react'
import type {FormEvent} from 'react'
import {BookOpen, Plus, UserRound} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {toast} from '../../app/store'
import {api} from '../../api/adapter'
import type {WorkJSON} from '../../api/types'
import {Dialog} from '../../components/Dialog'
import {Portrait, useAssetUrl} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {CREATE_TYPE_ART, workCoverUrl} from '../../art/generated'
import {formatTime, randomId} from '../../lib/util'

/**
 * Creation list. A new work starts from an explicit type choice and a name — there is
 * no default blank editor. The type is fixed once created.
 */
export default function CreatePage() {
  const {t, lang} = useI18n()
  const [works, setWorks] = useState<WorkJSON[] | null>(null)
  const [error, setError] = useState(false)
  const [creating, setCreating] = useState(false)
  const load = () => { setError(false); api.works.list().then(r => setWorks(r.items)).catch(() => setError(true)) }
  useEffect(load, [])
  return (
    <div className="ew-page ew-create">
      <header className="ew-page-head">
        <div><h1>{t('create.title')}</h1><p className="ew-muted">{t('create.subtitle')}</p></div>
        <button type="button" className="ew-btn primary" onClick={() => setCreating(true)} data-testid="create-new"><Plus aria-hidden="true" />{t('create.new')}</button>
      </header>
      {error && <div className="ew-notice danger" role="alert"><span>{t('error.network')}<span className="ew-notice-actions"><button type="button" className="ew-btn small" onClick={load}>{t('common.retry')}</button></span></span></div>}
      {!works && !error && <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>}
      {works && works.length === 0 && <div className="ew-empty"><SpotArt kind="create" /><h2>{t('create.empty')}</h2><p>{t('create.emptyNote')}</p><button type="button" className="ew-btn primary" onClick={() => setCreating(true)}><Plus aria-hidden="true" />{t('create.new')}</button></div>}
      {works && works.length > 0 && (
        <ul className="ew-works">
          {works.map(w => (
            <li key={w.id}>
              <a className="ew-work-card" href={href.work(w.id)} data-testid="work-card">
                <span className="ew-work-cover" aria-hidden="true"><Portrait src={workCoverUrl(w.draft.cover)} name={w.name} alt="" /></span>
                <span className="ew-work-text">
                  <span className="ew-row"><span className="ew-chip">{w.type === 'story' ? <BookOpen aria-hidden="true" /> : <UserRound aria-hidden="true" />}{w.type === 'story' ? t('create.story') : t('create.character')}</span>
                    {w.share.enabled && <span className="ew-chip ok">{t('create.shareOn', {n: w.share.version ?? ''})}</span>}</span>
                  <strong>{w.name}</strong>
                  <small className="ew-faint">{w.latest_version ? t('create.saved', {n: w.latest_version}) : t('create.neverSaved')}{w.dirty ? ` · ${t('create.unsaved')}` : ''} · {formatTime(w.updated_at, lang)}</small>
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
      {creating && <NewWorkDialog onClose={() => setCreating(false)} onCreated={w => { setCreating(false); navigate(href.work(w.id)) }} onError={() => toast(t('error.generic'), 'error')} />}
    </div>
  )
}

function NewWorkDialog({onClose, onCreated, onError}: {onClose: () => void; onCreated: (w: WorkJSON) => void; onError: () => void}) {
  const {t} = useI18n()
  const [type, setType] = useState<'story' | 'character' | null>(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const key = useRef(randomId('work', 10))
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!type || !name.trim() || busy) return
    setBusy(true)
    try { onCreated(await api.works.create(key.current, type, name.trim())) } catch { onError(); setBusy(false) }
  }
  return (
    <Dialog title={t('create.chooseType')} onClose={onClose}>
      <form className="ew-form" onSubmit={submit}>
        <div className="ew-type-choice" role="group" aria-label={t('create.chooseType')}>
          <button type="button" aria-pressed={type === 'story'} onClick={() => setType('story')} data-testid="type-story"><TypeArt kind="story" /><strong>{t('create.story')}</strong><small>{t('create.storyNote')}</small></button>
          <button type="button" aria-pressed={type === 'character'} onClick={() => setType('character')} data-testid="type-character"><TypeArt kind="character" /><strong>{t('create.character')}</strong><small>{t('create.characterNote')}</small></button>
        </div>
        <p className="ew-faint ew-small">{t('create.typeFixed')}</p>
        {type && <label className="ew-field"><span>{t('create.nameLabel')}</span><input className="ew-input" value={name} maxLength={60} autoFocus onChange={e => setName(e.target.value)} required data-testid="work-name" /></label>}
        <div className="ew-form-actions">
          <button type="button" className="ew-btn ghost" onClick={onClose}>{t('common.cancel')}</button>
          <button type="submit" className="ew-btn primary" disabled={!type || !name.trim() || busy} data-testid="work-create">{t('create.create')}</button>
        </div>
      </form>
    </Dialog>
  )
}

/** Generated type illustration; falls back to the plain icon if the file is missing. */
function TypeArt({kind}: {kind: 'story' | 'character'}) {
  const url = useAssetUrl(CREATE_TYPE_ART[kind])
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  if (!url || failed) return kind === 'story' ? <BookOpen aria-hidden="true" /> : <UserRound aria-hidden="true" />
  return <img className="ew-type-art" src={url} alt="" aria-hidden="true" width={72} height={72} draggable={false} onError={() => setFailed(true)} />
}

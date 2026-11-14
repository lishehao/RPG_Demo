import {useCallback, useEffect, useRef, useState} from 'react'
import {ArrowLeft, Maximize2, Minimize2, Play, Plus, RotateCcw, Save, Share2, Sparkles, Trash2, Undo2, UserPlus, X} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import type {I18nKey} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {requireSignIn, toast, useApp} from '../../app/store'
import {api} from '../../api/adapter'
import type {PreviewJSON, WorkJSON} from '../../api/types'
import {CompanionRequestError} from '../../contracts/companion'
import {OFFICIAL_CHARACTERS} from '../../mock/catalog'
import {Composer} from '../../chat/Composer'
import {CharacterLine, PlayerLine, RichText} from '../../chat/RichText'
import {Portrait, useAssetUrl} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {errorArt, WORK_COVERS, workCoverUrl} from '../../art/generated'
import type {WorkCoverId} from '../../art/generated'
import {useAddFriend} from '../friends/AddFriendFlow'
import {classNames, randomId} from '../../lib/util'

type Draft = Record<string, unknown>
type Role = {id: string; title: string; description: string; character: string; replaceable: boolean; locked: boolean}
type Sync = 'synced' | 'pending' | 'saving' | 'conflict' | 'error'
const VOICES = ['preset-neutral', 'preset-warm', 'preset-bright', 'preset-low', 'preset-calm']
const CHARACTER_FIELDS: {key: string; label: I18nKey; long?: boolean; required?: boolean}[] = [
  {key: 'name', label: 'create.f.name', required: true}, {key: 'tagline', label: 'create.f.tagline'},
  {key: 'intro', label: 'create.f.intro', long: true, required: true}, {key: 'persona', label: 'create.f.persona', long: true, required: true},
  {key: 'habit', label: 'create.f.habit', long: true}, {key: 'background', label: 'create.f.background', long: true}, {key: 'opening', label: 'create.f.opening', long: true},
]
const STORY_FIELDS: {key: string; label: I18nKey; long?: boolean; required?: boolean}[] = [
  {key: 'title', label: 'create.f.title', required: true}, {key: 'genre', label: 'create.f.genre'}, {key: 'content_note', label: 'create.f.contentNote'},
  {key: 'intro', label: 'create.f.intro', long: true}, {key: 'setting', label: 'create.f.setting', long: true}, {key: 'player_entry', label: 'create.f.playerEntry', long: true},
  {key: 'opening', label: 'create.f.opening', long: true, required: true},
]

/**
 * Editor + always-on isolated Preview. Drafts sync with a base revision (no silent
 * overwrite); versions are immutable; sharing is explicit and off by default. Preview
 * runs on a frozen draft snapshot and never touches friends, chats or memories.
 */
const strings = (v: unknown) => Array.isArray(v) ? v.map(x => typeof x === 'string' ? x : String((x as {text?: string})?.text ?? '')) : []
function ListEditor({label, items, onChange}: {label: string; items: string[]; onChange: (next: string[]) => void}) {
  const {t} = useI18n()
  return (
    <div className="ew-field">
      <span>{label}</span>
      {items.map((x, i) => (
        <span key={i} className="ew-row">
          <input className="ew-input" value={x} maxLength={120} aria-label={`${label} ${i + 1}`} onChange={e => onChange(items.map((y, j) => j === i ? e.target.value : y))} />
          <button type="button" className="ew-icon-btn" onClick={() => onChange(items.filter((_, j) => j !== i))} aria-label={`${t('create.remove')} · ${label} ${i + 1}`} title={t('create.remove')}><Trash2 aria-hidden="true" /></button>
        </span>
      ))}
      <span><button type="button" className="ew-btn small ghost" disabled={items.length >= 12} onClick={() => onChange([...items, ''])}><Plus aria-hidden="true" />{t('create.addEntry')}</button></span>
    </div>
  )
}

export default function WorkEditorPage({workId}: {workId: string}) {
  const {t, lang} = useI18n()
  const authenticated = useApp(s => !!s.account?.authenticated)
  const [work, setWork] = useState<WorkJSON | null>(null)
  const [draft, setDraftState] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sync, setSync] = useState<Sync>('synced')
  const [saving, setSaving] = useState(false)
  const [assistSummary, setAssistSummary] = useState<string[] | null>(null)
  const [preview, setPreview] = useState<PreviewJSON | null>(null)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewDraft, setPreviewDraft] = useState('')
  const [zoom, setZoom] = useState(false)
  const base = useRef(0)
  const dirty = useRef(false)
  const flight = useRef(false)
  const undo = useRef<Draft[]>([])
  const draftRef = useRef<Draft | null>(null)
  draftRef.current = draft
  const {open: openAddFriend, dialog: addFriendDialog} = useAddFriend(friend => navigate(href.chat(friend.id)))

  const adopt = useCallback((w: WorkJSON) => { setWork(w); setDraftState(w.draft); base.current = w.draft_revision; dirty.current = false; setSync('synced') }, [])
  useEffect(() => { api.works.get(workId).then(adopt).catch(e => setError(e instanceof CompanionRequestError ? e.code : 'network_error')) }, [workId, adopt])

  // Debounced sync of the local draft against the base revision it was edited from.
  const flush = useCallback(async () => {
    if (flight.current || !dirty.current || !draftRef.current) return
    flight.current = true; setSync('saving')
    const sent = draftRef.current
    dirty.current = false
    try {
      const w = await api.works.putDraft(workId, sent, base.current)
      base.current = w.draft_revision; setWork(w)
      setSync(dirty.current ? 'pending' : 'synced')
    } catch (e) {
      dirty.current = true
      setSync(e instanceof CompanionRequestError && e.code === 'draft_revision_changed' ? 'conflict' : 'error')
    } finally { flight.current = false }
  }, [workId])
  useEffect(() => {
    if (sync !== 'pending') return
    const timer = setTimeout(() => { void flush() }, 700)
    return () => clearTimeout(timer)
  }, [draft, sync, flush])
  useEffect(() => { if (sync === 'synced' && dirty.current) setSync('pending') }, [sync])

  const edit = (next: Draft, record = false) => {
    if (record && draftRef.current) undo.current = [...undo.current.slice(-19), draftRef.current]
    setDraftState(next); dirty.current = true; if (sync !== 'conflict') setSync('pending')
  }
  const setField = (key: string, value: unknown) => draft && edit({...draft, [key]: value})

  if (error) return <div className="ew-page"><a className="ew-back ew-btn ghost" href={href.create()}><ArrowLeft aria-hidden="true" />{t('common.back')}</a><div className="ew-empty"><SpotArt kind={errorArt(error)} /><h2>{error === 'not_found' ? t('error.notFound') : t('error.generic')}</h2></div></div>
  if (!work || !draft) return <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>

  const errors = new Map(work.errors.map(e => [e.field, e.code]))
  const blocked = work.errors.length > 0
  const errorText = (field: string) => { const code = errors.get(field); return code ? t(`create.err.${code}` as I18nKey) : null }
  const str = (key: string) => typeof draft[key] === 'string' ? draft[key] as string : ''
  const roles = (Array.isArray(draft.roles) ? draft.roles : []) as Role[]
  const setRole = (i: number, patch: Partial<Role>) => setField('roles', roles.map((r, j) => j === i ? {...r, ...patch} : r))
  const stale = !!preview && preview.draft_revision !== work.draft_revision

  const save = async () => {
    if (saving) return
    if (!(await requireSignIn('auth.action.save'))) return
    await flush()
    setSaving(true)
    try {
      const w = await api.works.save(work.id, base.current)
      setWork(w); toast(w.unchanged ? t('create.unchangedSave', {n: w.saved_version ?? ''}) : t('create.saved', {n: w.saved_version ?? ''}), 'success')
    } catch (e) { toast(e instanceof CompanionRequestError && e.code === 'draft_revision_changed' ? t('error.conflict') : t('create.saveFailed'), 'error') }
    finally { setSaving(false) }
  }
  const share = async (enabled: boolean) => {
    if (!(await requireSignIn('auth.action.share'))) return
    try { setWork(await api.works.share(work.id, enabled, enabled ? work.latest_version : null)) }
    catch (e) { toast(e instanceof CompanionRequestError && e.code === 'share_check_failed' ? t('create.previewBlocked') : t('error.generic'), 'error') }
  }
  const assist = async (instruction: string) => {
    try {
      const r = await api.works.assist(work.id, instruction, draft, lang)
      edit(r.draft, true); setAssistSummary(r.summary)
    } catch { toast(t('error.generic'), 'error') }
  }
  const startPreview = async () => {
    if (previewBusy) return
    await flush()
    setPreviewBusy(true)
    try { setPreview(await api.works.preview(work.id, base.current, lang)) }
    catch (e) { toast(e instanceof CompanionRequestError && e.code === 'preview_check_failed' ? t('create.previewBlocked') : t('error.generic'), 'error') }
    finally { setPreviewBusy(false) }
  }
  const field = (f: {key: string; label: I18nKey; long?: boolean; required?: boolean}) => {
    const err = errorText(f.key), id = `wf-${f.key}`
    return (
      <label key={f.key} className={classNames('ew-field', f.long && 'is-wide')} htmlFor={id}>
        <span>{t(f.label)}{f.required && <small> · {t('common.required')}</small>}</span>
        {f.long
          ? <textarea id={id} className="ew-textarea" value={str(f.key)} maxLength={2000} aria-invalid={!!err} onChange={e => setField(f.key, e.target.value)} data-testid={`field-${f.key}`} />
          : <input id={id} className="ew-input" value={str(f.key)} maxLength={f.key === 'name' ? 40 : 80} aria-invalid={!!err} onChange={e => setField(f.key, e.target.value)} data-testid={`field-${f.key}`} />}
        {err && <span className="ew-field-error">{err}</span>}
      </label>
    )
  }
  const syncLabel = sync === 'saving' ? t('create.draftSaving') : sync === 'pending' ? t('create.unsavedDraft') : sync === 'conflict' ? t('create.conflict') : sync === 'error' ? t('create.syncError') : t('create.draftSaved')

  return (
    <div className={classNames('ew-editor', zoom && 'is-preview-zoom')} data-testid="work-editor" data-draft-revision={work.draft_revision}>
      <div className="ew-editor-form">
        <a className="ew-back ew-btn ghost" href={href.create()}><ArrowLeft aria-hidden="true" />{t('create.title')}</a>
        <div className="ew-editor-head">
          <span className="ew-work-cover small" aria-hidden="true"><Portrait src={workCoverUrl(draft.cover)} name={work.name} alt="" /></span>
          <span className="ew-chip">{work.type === 'story' ? t('create.story') : t('create.character')}</span>
          <h1>{work.name}</h1>
          <div className="ew-editor-status">
            <span className={classNames('ew-chip', sync === 'conflict' || sync === 'error' ? 'danger' : sync === 'synced' ? 'ok' : '')} role="status" data-testid="sync-status">{syncLabel}</span>
            <span className="ew-chip">{work.latest_version ? t('create.saved', {n: work.latest_version}) : t('create.neverSaved')}{work.dirty && work.latest_version ? ` · ${t('create.unsaved')}` : ''}</span>
            <button type="button" className="ew-btn primary small" onClick={() => void save()} disabled={saving} data-testid="work-save"><Save aria-hidden="true" />{saving ? t('create.saving') : t('create.save')}</button>
          </div>
        </div>
        {!authenticated && <div className="ew-notice"><span>{t('create.guestNote')}</span></div>}
        {sync === 'conflict' && <div className="ew-notice warn" role="alert"><span>{t('create.conflictNote')}<span className="ew-notice-actions">
          <button type="button" className="ew-btn small" onClick={() => api.works.get(work.id).then(adopt)}>{t('create.loadLatest')}</button>
          <button type="button" className="ew-btn small ghost" onClick={async () => { const w = await api.works.get(work.id); base.current = w.draft_revision; dirty.current = true; setSync('pending') }}>{t('create.keepMine')}</button></span></span></div>}
        {sync === 'error' && <div className="ew-notice danger" role="alert"><span>{t('create.syncError')}<span className="ew-notice-actions"><button type="button" className="ew-btn small" onClick={() => { dirty.current = true; setSync('pending') }}>{t('common.retry')}</button></span></span></div>}
        {blocked && <div className="ew-notice warn" role="status">{t('create.previewBlocked')}</div>}

        <section className="ew-editor-section" aria-labelledby="assist-title">
          <h2 id="assist-title"><Sparkles aria-hidden="true" className="ew-inline-icon" /> {t('create.assist')}</h2>
          <p className="ew-faint ew-small">{t('create.assistNote')}</p>
          <div className="ew-assist">
            <button type="button" className="ew-btn small" onClick={() => void assist('fill')} data-testid="assist-fill">{t('create.assist.fill')}</button>
            <button type="button" className="ew-btn small" onClick={() => void assist('shorter')}>{t('create.assist.shorter')}</button>
            {work.type === 'character' && <button type="button" className="ew-btn small" onClick={() => void assist('warmer')}>{t('create.assist.warmer')}</button>}
            {work.type === 'story' && <button type="button" className="ew-btn small" onClick={() => void assist('add_role')}>{t('create.assist.addRole')}</button>}
            <button type="button" className="ew-btn small ghost" disabled={!undo.current.length} onClick={() => { const prev = undo.current.pop(); if (prev) { edit(prev); setAssistSummary(null) } }} data-testid="assist-undo"><Undo2 aria-hidden="true" />{t('create.undo')}</button>
          </div>
          {assistSummary && <ul className="ew-assist-summary" aria-live="polite">{assistSummary.map((s, i) => <li key={i}>{s}</li>)}</ul>}
        </section>

        <section className="ew-editor-section" aria-labelledby="fields-title">
          <h2 id="fields-title">{t('create.fields')}</h2>
          <div className="ew-editor-grid">
            {(work.type === 'character' ? CHARACTER_FIELDS : STORY_FIELDS).map(field)}
            <div className="ew-field is-wide">
              <span id="wf-cover">{t('create.f.cover')}</span>
              <div className="ew-cover-picker" role="group" aria-labelledby="wf-cover" data-testid="cover-picker">
                {WORK_COVERS.map((id, i) => <CoverChoice key={id} id={id} label={t('create.coverN', {n: i + 1})} selected={draft.cover === id} onSelect={() => setField('cover', id)} />)}
              </div>
              {errorText('cover') && <span className="ew-field-error">{errorText('cover')}</span>}
              <small>{t('create.coverNote')}</small>
            </div>
            {work.type === 'character' && <>
              <label className="ew-field"><span>{t('create.f.voice')}</span>
                <select className="ew-select" value={str('voice')} onChange={e => setField('voice', e.target.value)}>{VOICES.map(v => <option key={v} value={v}>{t(`create.voice.${v}` as I18nKey)}</option>)}</select></label>
              <div className="ew-field"><span>{t('create.f.portrait')}</span><span className="ew-row"><span className="ew-avatar large"><Portrait src={null} name={str('name') || '?'} /></span><small className="ew-faint">{t('create.f.portraitNote')}</small></span></div>
            </>}
            {work.type === 'story' && <>
              <label className="ew-field"><span>{t('create.f.narrative')}</span>
                <select className="ew-select" value={str('narrative')} onChange={e => setField('narrative', e.target.value)}>{['balanced', 'dialogue', 'atmosphere'].map(v => <option key={v} value={v}>{t(`create.narr.${v}` as I18nKey)}</option>)}</select></label>
              <label className="ew-field"><span>{t('create.f.mode')}</span>
                <select className="ew-select" value={str('mode')} onChange={e => setField('mode', e.target.value)} aria-invalid={!!errors.get('mode')}>{['open', 'ending'].map(v => <option key={v} value={v}>{t(`create.mode.${v}` as I18nKey)}</option>)}</select></label>
            </>}
          </div>
        </section>

        {work.type === 'story' && (
          <section className="ew-editor-section" aria-labelledby="roles-edit-title">
            <h2 id="roles-edit-title">{t('create.f.roles')} <span className="ew-chip">{roles.length} / 10</span></h2>
            {errorText('roles') && <span className="ew-field-error">{errorText('roles')}</span>}
            {roles.map((r, i) => (
              <div key={r.id} className="ew-role-edit" data-role={r.id}>
                <header><strong>{t('create.roleN', {n: i + 1})}</strong>
                  <button type="button" className="ew-icon-btn" disabled={roles.length <= 1} onClick={() => setField('roles', roles.filter((_, j) => j !== i))} aria-label={`${t('common.delete')} · ${t('create.roleN', {n: i + 1})}`} title={t('common.delete')}><Trash2 aria-hidden="true" /></button></header>
                <div className="ew-editor-grid">
                  <label className="ew-field"><span>{t('create.f.roleTitle')}</span><input className="ew-input" value={r.title} maxLength={40} aria-invalid={!!errors.get(`roles.${i}.title`)} onChange={e => setRole(i, {title: e.target.value})} />
                    {errorText(`roles.${i}.title`) && <span className="ew-field-error">{errorText(`roles.${i}.title`)}</span>}</label>
                  <label className="ew-field"><span>{t('create.f.roleCharacter')}</span>
                    <select className="ew-select" value={r.character} onChange={e => setRole(i, {character: e.target.value})}>{OFFICIAL_CHARACTERS.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
                  <label className="ew-field is-wide"><span>{t('create.f.roleDesc')}</span><textarea className="ew-textarea" value={r.description} maxLength={400} onChange={e => setRole(i, {description: e.target.value})} /></label>
                  <span className="ew-row wrap is-wide">
                    <label className="ew-check"><input type="checkbox" checked={r.replaceable && !r.locked} disabled={r.locked} onChange={e => setRole(i, {replaceable: e.target.checked})} />{t('create.f.replaceable')}</label>
                    <label className="ew-check"><input type="checkbox" checked={r.locked} onChange={e => setRole(i, {locked: e.target.checked, replaceable: e.target.checked ? false : true})} />{t('create.f.locked')}</label>
                  </span>
                </div>
              </div>
            ))}
            <div><button type="button" className="ew-btn small" disabled={roles.length >= 10} onClick={() => setField('roles', [...roles, {id: `role-${Date.now().toString(36)}`, title: '', description: '', character: 'official-nora', replaceable: true, locked: false}])}><Plus aria-hidden="true" />{t('create.addRole')}</button></div>
            <ListEditor label={t('create.f.items')} items={strings(draft.items)} onChange={v => setField('items', v)} />
            <ListEditor label={t('create.f.stages')} items={strings(draft.stages)} onChange={v => setField('stages', v)} />
            <p className="ew-faint ew-small">{t('create.worldbookGap')}</p>
          </section>
        )}

        <section className="ew-editor-section" aria-labelledby="share-title">
          <h2 id="share-title"><Share2 aria-hidden="true" className="ew-inline-icon" /> {t('create.share')}</h2>
          <p className="ew-small">{work.share.enabled ? t('create.shareOn', {n: work.share.version ?? ''}) : t('create.shareOff')}</p>
          <p className="ew-faint ew-small">{t('create.shareNote')}</p>
          <div className="ew-row wrap">
            {work.share.enabled
              ? <button type="button" className="ew-btn small" onClick={() => void share(false)} data-testid="share-off">{t('create.shareDisable')}</button>
              : <button type="button" className="ew-btn small" disabled={!work.latest_version} onClick={() => void share(true)} data-testid="share-on">{t('create.shareEnable', {n: work.latest_version ?? '—'})}</button>}
            {work.type === 'character' && work.latest_version && <button type="button" className="ew-btn small" onClick={() => openAddFriend({sourceId: `work-${work.id}`, version: String(work.latest_version), sourceName: work.name})} data-testid="work-befriend"><UserPlus aria-hidden="true" />{t('create.addFriend', {n: work.latest_version})}</button>}
          </div>
        </section>
      </div>

      <aside className="ew-preview" aria-label={t('create.preview')} data-testid="preview">
        <div className="ew-preview-head">
          <strong>{t('create.preview')}</strong>
          {preview && <span className="ew-chip">{t('create.previewSnapshot', {n: preview.draft_revision})}</span>}
          <button type="button" className="ew-btn small" disabled={blocked || previewBusy} onClick={() => void startPreview()} data-testid="preview-start">{preview ? <><RotateCcw aria-hidden="true" />{t('create.previewRestart')}</> : <><Play aria-hidden="true" />{t('create.previewStart')}</>}</button>
          <button type="button" className="ew-icon-btn" aria-pressed={zoom} onClick={() => setZoom(z => !z)} aria-label={zoom ? t('create.collapse') : t('create.expand')} title={zoom ? t('create.collapse') : t('create.expand')}>{zoom ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}</button>
        </div>
        <div className="ew-notice mock"><span>{t('create.previewNote')}</span></div>
        {stale && <div className="ew-notice warn" role="status" data-testid="preview-stale"><span>{t('create.previewStale', {n: preview!.draft_revision})}</span></div>}
        <div className="ew-preview-body" role="log" aria-live="polite">
          {!preview && <p className="ew-faint ew-small">{blocked ? t('create.previewBlocked') : t('create.previewIdle')}</p>}
          {preview?.turns.map(turn => turn.role === 'player'
            ? <PlayerLine key={turn.id}><RichText text={turn.text} /></PlayerLine>
            : <CharacterLine key={turn.id} name={String(preview.snapshot.name ?? preview.snapshot.title ?? work.name)} avatar={<span className="ew-avatar small"><Portrait src={null} name={String(preview.snapshot.name ?? preview.snapshot.title ?? '?')} /></span>}><p><RichText text={turn.text} /></p></CharacterLine>)}
        </div>
        <div className="ew-preview-composer">
          <Composer value={previewDraft} onChange={setPreviewDraft} busy={previewBusy} disabled={!preview} label={t('create.preview')} placeholder={preview ? t('create.previewSay') : t('create.previewIdle')}
            onSubmit={async text => {
              if (!preview) return
              setPreviewBusy(true)
              try { setPreview(await api.works.previewTurn(preview.id, randomId('pv', 8), text.trim(), lang)); setPreviewDraft('') } catch { toast(t('error.generic'), 'error') } finally { setPreviewBusy(false) }
            }} />
          {preview && <button type="button" className="ew-btn ghost small" onClick={() => setPreview(null)}><X aria-hidden="true" />{t('create.previewClose')}</button>}
        </div>
      </aside>
      {addFriendDialog}
    </div>
  )
}

function CoverChoice({id, label, selected, onSelect}: {id: WorkCoverId; label: string; selected: boolean; onSelect: () => void}) {
  const url = useAssetUrl(workCoverUrl(id))
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [url])
  return (
    <button type="button" className="ew-cover-choice" aria-pressed={selected} aria-label={label} title={label} onClick={onSelect} data-cover={id}>
      {url && !failed ? <img src={url} alt="" decoding="async" draggable={false} onError={() => setFailed(true)} /> : <span aria-hidden="true">{label}</span>}
    </button>
  )
}

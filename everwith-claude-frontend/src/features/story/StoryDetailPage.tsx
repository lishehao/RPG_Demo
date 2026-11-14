import {useEffect, useState} from 'react'
import {ArrowLeft, BookOpen, Lock, Play, Users} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {api} from '../../api/adapter'
import type {RecordJSON, StoryJSON} from '../../api/types'
import {CompanionRequestError} from '../../contracts/companion'
import {Portrait} from '../../components/Portrait'
import {SpotArt} from '../../components/Art'
import {errorArt} from '../../art/generated'
import {formatTime, pick} from '../../lib/util'

/**
 * Public story page: introduction, people, version; continue one of MY existing runs
 * (each run listed separately, never merged by title) or explicitly start another.
 */
export default function StoryDetailPage({storyId, version}: {storyId: string; version: string}) {
  const {t, lang} = useI18n()
  const [story, setStory] = useState<StoryJSON | null>(null)
  const [runs, setRuns] = useState<RecordJSON[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api.catalog.story(storyId, version).then(setStory).catch(e => setError(e instanceof CompanionRequestError ? e.code : 'network_error'))
    api.records.list(false).then(r => setRuns(r.items.filter(x => x.kind === 'story' && x.work_id === storyId && x.version === version))).catch(() => setRuns([]))
  }, [storyId, version])
  const back = href.discover('stories')
  if (error) return <div className="ew-page"><a className="ew-back ew-btn ghost" href={back}><ArrowLeft aria-hidden="true" />{t('common.back')}</a><div className="ew-empty"><SpotArt kind={errorArt(error)} /><h2>{error === 'not_found' ? t('error.notFound') : t('error.generic')}</h2>{error !== 'not_found' && <button type="button" className="ew-btn" onClick={() => { setError(null); api.catalog.story(storyId, version).then(setStory).catch(() => setError('network_error')) }}>{t('common.retry')}</button>}</div></div>
  if (!story) return <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>
  const here = href.story(storyId, version)
  return (
    <div className="ew-page ew-story-detail">
      <a className="ew-back ew-btn ghost" href={back} onClick={e => { if (history.length > 1) { e.preventDefault(); history.back() } }}><ArrowLeft aria-hidden="true" />{t('common.back')}</a>
      <div className="ew-story-hero">
        <div className="ew-story-cover">{(story.image_wide ?? story.image) ? <Portrait src={story.image_wide ?? story.image} name={pick(story.title, lang)} /> : <span className="ew-story-cover-fallback" aria-hidden="true"><BookOpen /></span>}</div>
        <section className="ew-story-intro" aria-labelledby="story-title">
          <p className="ew-eyebrow">{pick(story.genre, lang)} · v{story.version}</p>
          <h1 id="story-title" className="ew-title-xl">{pick(story.title, lang)}</h1>
          <p className="ew-lead">{pick(story.description, lang)}</p>
          <p className="ew-faint ew-small">{pick(story.content_note, lang)}</p>
          <dl className="ew-facts">
            <div><dt>{t('story.playerRole')}</dt><dd>{pick(story.player_role, lang)}</dd></div>
            <div><dt>{t('story.objectives')}</dt><dd><ol>{story.objectives.map((o, i) => <li key={i}>{pick(o, lang)}</li>)}</ol></dd></div>
          </dl>
          <div className="ew-row wrap">
            <a className="ew-btn primary" href={href.storyPrepare(storyId, version, null, here)} data-testid="story-prepare"><Play aria-hidden="true" />{runs && runs.length ? t('story.newRun') : t('story.start')}</a>
          </div>
          <p className="ew-faint ew-small">{t('story.noRecord')}</p>
        </section>
      </div>

      {runs && runs.length > 0 && (
        <section className="ew-story-runs" aria-labelledby="runs-title">
          <h2 id="runs-title" className="ew-section-title">{t('story.continueExisting')}</h2>
          <ul className="ew-list">
            {runs.map(r => (
              <li key={r.id}>
                <button type="button" className="ew-list-row" onClick={() => navigate(href.storyPlay(r.id))} data-testid="story-continue">
                  <Play aria-hidden="true" />
                  <span className="ew-list-main">
                    <strong>{r.lineup.map(l => `${l.role ? pick(l.role, lang) + '：' : ''}${l.name}${l.friend ? `（${t('common.friend')}）` : ''}`).join(' · ')}</strong>
                    <small>{t('story.runMeta', {turns: r.turns ?? 0, time: formatTime(r.updated_at, lang)})}{r.status === 'read_only' ? ` · ${t('story.readOnlyShort')}` : ''}</small>
                  </span>
                  <span className="ew-chip">{t('recent.continue')}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="roles-title">
        <h2 id="roles-title" className="ew-section-title"><Users aria-hidden="true" className="ew-inline-icon" /> {t('story.roles')}</h2>
        <ul className="ew-role-grid">
          {story.roles.map(r => (
            <li key={r.id} className="ew-role-card">
              <span className="ew-avatar large"><Portrait src={r.default_character.avatar} name={r.default_character.name} position="50% 14%" /></span>
              <span className="ew-role-text">
                <strong>{pick(r.title, lang)}</strong>
                <small>{r.default_character.name} · {pick(r.default_character.tagline, lang)}</small>
                <span className="ew-faint ew-small">{pick(r.description, lang)}</span>
                {r.locked || !r.replaceable ? <span className="ew-chip"><Lock aria-hidden="true" />{t('story.locked')}</span> : <span className="ew-chip friend">{t('story.friendCanPlay')}</span>}
              </span>
            </li>
          ))}
        </ul>
        <p className="ew-faint ew-small">{t('story.publicNote')}</p>
      </section>
    </div>
  )
}

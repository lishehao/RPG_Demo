import {useEffect, useState} from 'react'
import {ArrowLeft, MessageCircle, UserPlus, Maximize2, Minimize2, Volume2} from 'lucide-react'
import {useI18n} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {api} from '../../api/adapter'
import {useApp} from '../../app/store'
import type {CharacterWork} from '../../contracts/companion'
import {CompanionRequestError} from '../../contracts/companion'
import {LiveStage} from '../../live2d/LiveStage'
import {SpotArt} from '../../components/Art'
import {errorArt} from '../../art/generated'
import {characterFor} from '../../live2d/characters'
import {useAddFriend} from '../friends/AddFriendFlow'
import {formatTime, pick} from '../../lib/util'

export default function CharacterPage({sourceId, version}: {sourceId: string; version: string}) {
  const {t, lang} = useI18n()
  const [character, setCharacter] = useState<CharacterWork | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [zoom, setZoom] = useState(false)
  const friends = useApp(s => s.friends)
  const authenticated = useApp(s => !!s.account?.authenticated)
  const {open, dialog} = useAddFriend(friend => navigate(href.chat(friend.id)))
  useEffect(() => {
    api.catalog.character(sourceId, version).then(setCharacter).catch(e => setError(e instanceof CompanionRequestError ? e.code : 'network_error'))
  }, [sourceId, version])
  if (error) return <div className="ew-page"><a className="ew-back ew-btn ghost" href={href.discover('characters')}><ArrowLeft aria-hidden="true" />{t('common.back')}</a><div className="ew-empty"><SpotArt kind={errorArt(error)} /><h2>{error === 'not_found' ? t('error.notFound') : t('error.generic')}</h2></div></div>
  if (!character) return <div className="ew-page-loading" role="status"><span className="ew-spinner" />{t('common.loading')}</div>
  const cfg = characterFor(character.id, character.version)
  // Same-source friends are separate people: listed with their own names and dates.
  const same = (friends ?? []).filter(f => f.source_id === character.id)
  return (
    <div className="ew-page ew-character">
      <a className="ew-back ew-btn ghost" href={href.discover('characters')} onClick={e => { if (history.length > 1) { e.preventDefault(); history.back() } }}><ArrowLeft aria-hidden="true" />{t('common.back')}</a>
      <div className={`ew-character-layout ${zoom ? 'is-zoom' : ''}`}>
        <div className="ew-character-stage">
          <LiveStage character={cfg} name={character.name} fallbackImage={character.avatar} preset={zoom ? 'zoom' : 'stage'} />
          <button type="button" className="ew-icon-btn ew-stage-zoom" aria-pressed={zoom} onClick={() => setZoom(z => !z)} aria-label={zoom ? t('live2d.unzoom') : t('live2d.zoom')} title={zoom ? t('live2d.unzoom') : t('live2d.zoom')}>{zoom ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}</button>
        </div>
        <section className="ew-character-info" aria-labelledby="char-name">
          <p className="ew-eyebrow">{character.origin === 'official' ? 'Everwith' : t('create.character')} · {pick(character.tagline, lang)}</p>
          <h1 id="char-name">{character.name}</h1>
          <h2 className="ew-section-title">{t('character.public')}</h2>
          <p className="ew-lead">{pick(character.description, lang)}</p>
          {character.traits.length > 0 && <>
            <h2 className="ew-section-title">{t('character.traits')}</h2>
            <ul className="ew-traits">{character.traits.map((tr, i) => <li key={i} className="ew-chip">{pick(tr, lang)}</li>)}</ul>
          </>}
          <p className="ew-faint ew-small"><Volume2 aria-hidden="true" className="ew-inline-icon" /> {t('character.voice')}: {character.voice}</p>
          <p className="ew-faint ew-small">{t('character.noPrivate')}</p>
          <div className="ew-row wrap ew-character-actions">
            {same.length > 0 && <a className="ew-btn primary" href={href.chat(same[0].id)}><MessageCircle aria-hidden="true" />{t('character.chatWith', {name: same[0].name})}</a>}
            <button type="button" className={`ew-btn ${same.length ? '' : 'primary'}`} onClick={() => open({sourceId: character.id, version: character.version, sourceName: character.name})}>
              <UserPlus aria-hidden="true" />{same.length ? t('character.addAnother') : t('character.add')}</button>
          </div>
          {authenticated && same.length > 0 && (
            <section className="ew-same-source" aria-labelledby="same-source">
              <h2 id="same-source" className="ew-section-title">{t('character.existing')}</h2>
              <p className="ew-faint ew-small">{t('character.existingHint')}</p>
              <ul className="ew-list">
                {same.map(f => <li key={f.id}><a className="ew-list-row" href={href.chat(f.id)}>
                  <span className="ew-list-main"><strong>{f.name}</strong><small>{t('friends.number', {n: f.display_number})} · {t('friends.since', {date: formatTime(f.created_at, lang)})} · {pick(f.origin.label, lang)}</small></span>
                  <MessageCircle aria-hidden="true" /></a></li>)}
              </ul>
            </section>
          )}
        </section>
      </div>
      {dialog}
    </div>
  )
}

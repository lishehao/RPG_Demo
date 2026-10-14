import {useEffect, useState} from 'react'
import {BookOpen, Dice5} from 'lucide-react'
import {Dialog} from '../../components/Dialog'
import {Portrait} from '../../components/Portrait'
import {useI18n} from '../../app/i18n'
import {href, navigate} from '../../app/router'
import {api} from '../../api/adapter'
import type {GameJSON, StoryJSON} from '../../api/types'
import type {CompanionFriend} from '../../contracts/companion'
import {pick} from '../../lib/util'

/** P20 “一起玩”: choosing only prepares — nothing is created or sent until Start. */
export function PlayTogetherDialog({friend, from, onClose}: {friend: CompanionFriend; from: string; onClose: () => void}) {
  const {t, lang} = useI18n()
  const [stories, setStories] = useState<StoryJSON[] | null>(null)
  const [games, setGames] = useState<GameJSON[] | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    Promise.all([api.catalog.stories(), api.catalog.games()]).then(([s, g]) => { setStories(s.items); setGames(g.items) }).catch(() => setFailed(true))
  }, [])
  return (
    <Dialog title={`${t('friends.play')} · ${friend.name}`} onClose={onClose} wide>
      {failed && <div className="ew-notice danger" role="alert">{t('error.generic')}</div>}
      {!failed && (!stories || !games) && <div className="ew-page-loading"><span className="ew-spinner" />{t('common.loading')}</div>}
      {stories && games && (
        <div className="ew-play-grid">
          <section aria-labelledby="pt-stories">
            <h3 id="pt-stories" className="ew-section-title"><BookOpen aria-hidden="true" className="ew-inline-icon" /> {t('discover.tab.stories')}</h3>
            <ul className="ew-list">
              {stories.map(s => <li key={s.id}><button type="button" className="ew-list-row" onClick={() => { onClose(); navigate(href.storyPrepare(s.id, s.version, friend.id, from)) }}>
                <span className="ew-list-thumb" aria-hidden="true"><Portrait src={s.image} name={pick(s.title, lang)} alt="" /></span>
                <span className="ew-list-main"><strong>{pick(s.title, lang)}</strong><small>{pick(s.description, lang)}</small></span></button></li>)}
            </ul>
          </section>
          <section aria-labelledby="pt-games">
            <h3 id="pt-games" className="ew-section-title"><Dice5 aria-hidden="true" className="ew-inline-icon" /> {t('discover.tab.games')}</h3>
            <ul className="ew-list">
              {games.map(g => <li key={g.id}><button type="button" className="ew-list-row" onClick={() => { onClose(); navigate(href.gamePrepare(g.id, friend.id, from)) }}>
                <span className="ew-list-thumb" aria-hidden="true"><Portrait src={g.poster} name={g.name} alt="" /></span>
                <span className="ew-list-main"><strong>{g.name}</strong><small>{pick(g.description, lang)} · {g.players.join('/')} {t('common.players')}</small></span></button></li>)}
            </ul>
          </section>
        </div>
      )}
    </Dialog>
  )
}

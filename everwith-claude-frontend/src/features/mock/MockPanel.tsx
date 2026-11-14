import {useEffect, useState, useSyncExternalStore} from 'react'
import {Dialog} from '../../components/Dialog'
import {useI18n} from '../../app/i18n'
import {SCENARIOS, scenarios} from '../../mock/scenarios'
import {resetDB} from '../../mock/db'
import {api} from '../../api/adapter'
import {href, navigate} from '../../app/router'
import {loadAccount, toast} from '../../app/store'
import {randomId} from '../../lib/util'
import {ADAPTER_MODE} from '../../api/adapter'

export const OPEN_MOCK_PANEL = 'everwith:open-mock-panel'

export function MockPanel() {
  const {t, lang} = useI18n()
  const [open, setOpen] = useState(false)
  const active = useSyncExternalStore(scenarios.subscribe, scenarios.snapshot, scenarios.snapshot)
  // Task pages (the game table) hide the floating button and open the panel from their own toolbar.
  useEffect(() => {
    const onOpen = () => setOpen(true)
    window.addEventListener(OPEN_MOCK_PANEL, onOpen)
    return () => window.removeEventListener(OPEN_MOCK_PANEL, onOpen)
  }, [])
  if (ADAPTER_MODE !== 'mock') return null
  const importLegacy = async () => {
    try {
      const view = await api.games.start({key: randomId('legacy'), game_id: 'gems', players: 3, profile: 'splendor-legacy-v1', legacy_fixture: true,
        seats: [{seat: 1, kind: 'temporary', character_id: 'official-nora'}, {seat: 2, kind: 'temporary', character_id: 'official-marcus'}],
        origin: {kind: 'discover', return_hash: href.recent()}})
      setOpen(false); navigate(href.gamePlay(view.id))
    } catch { toast(t('error.generic'), 'error') }
  }
  return (
    <>
      {open && (
        <Dialog title={t('mock.panel.title')} onClose={() => setOpen(false)} wide>
          <p className="ew-muted">{t('mock.panel.desc')}</p>
          <ul className="ew-scenarios">
            {SCENARIOS.map(s => (
              <li key={s.id}>
                <label className="ew-check">
                  <input type="checkbox" checked={!!active[s.id]} onChange={e => scenarios.set(s.id, e.target.checked)} />
                  <span><strong>{s.label[lang]}</strong> <span className="ew-chip">{s.kind === 'once' ? t('mock.panel.once') : t('mock.panel.toggle')}</span><br /><small className="ew-faint">{s.expect[lang]}</small></span>
                </label>
              </li>
            ))}
          </ul>
          <div className="ew-row wrap">
            <button type="button" className="ew-btn" onClick={() => void importLegacy()}>{t('mock.panel.legacy')}</button>
            <button type="button" className="ew-btn danger" onClick={() => { if (confirm(t('mock.panel.resetConfirm'))) { resetDB(); scenarios.clear(); void loadAccount(); setOpen(false); navigate(href.discover()) } }}>{t('mock.panel.reset')}</button>
          </div>
        </Dialog>
      )}
    </>
  )
}

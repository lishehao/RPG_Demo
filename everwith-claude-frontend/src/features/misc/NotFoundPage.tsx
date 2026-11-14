import {useI18n} from '../../app/i18n'
import {href} from '../../app/router'
import {SpotArt} from '../../components/Art'

export default function NotFoundPage() {
  const {t} = useI18n()
  return (
    <div className="ew-page">
      <div className="ew-empty">
        <SpotArt kind="not-found" />
        <h2>{t('error.notFound')}</h2>
        <a className="ew-btn primary" href={href.discover()}>{t('nav.discover')}</a>
      </div>
    </div>
  )
}

/**
 * Safe rich text: plain React text nodes only (no HTML, no Markdown). `*action*` spans
 * render as muted italics. Escape rule kept from the frozen 677b1b4b scanner: an odd
 * run of backslashes before `*` escapes that star (one backslash consumed), an even
 * run keeps every backslash and the star still delimits; same rule inside and outside.
 */
import type {ReactNode} from 'react'

export type Span = {text: string; action: boolean}
export function parseRichText(text: string, action = false): Span[] {
  const spans: Span[] = []
  let plain = '', i = 0
  const flush = () => { if (plain) { spans.push({text: plain, action}); plain = '' } }
  while (i < text.length) {
    if (text[i] === '\\') {
      const start = i
      while (text[i] === '\\') i++
      const escaped = text[i] === '*' && (i - start) % 2 === 1
      plain += text.slice(start, escaped ? i - 1 : i)
      if (escaped) { plain += '*'; i++ }
      continue
    }
    if (text[i] === '*') {
      let end = i + 1, content = ''
      while (end < text.length) {
        if (text[end] === '\\') {
          const start = end
          while (text[end] === '\\') end++
          const escaped = text[end] === '*' && (end - start) % 2 === 1
          content += text.slice(start, escaped ? end - 1 : end)
          if (escaped) { content += '*'; end++ }
          continue
        }
        if (text[end] === '*') break
        content += text[end++]
      }
      if (end < text.length && end > i + 1) { flush(); spans.push({text: content, action: true}); i = end + 1; continue }
    }
    plain += text[i++]
  }
  flush()
  return spans
}
export function RichText({text, action = false}: {text: string; action?: boolean}) {
  return <>{parseRichText(text, action).map((s, n) => s.action ? <em key={n} className="ew-act">{s.text}</em> : <span key={n}>{s.text}</span>)}</>
}

export function CharacterLine({name, avatar, children, meta, tone, provisional = false, actorKey}: {name: string; avatar: ReactNode; children: ReactNode; meta?: ReactNode; tone?: string; provisional?: boolean; actorKey?: string}) {
  return (
    <div className={`ew-msg is-character ${provisional ? 'is-provisional' : ''} ${tone ?? ''}`} data-actor={actorKey}>
      <span className="ew-msg-avatar">{avatar}</span>
      <div className="ew-msg-content">
        <span className="ew-msg-name">{name}{meta}</span>
        <div className="ew-msg-bubble">{children}</div>
      </div>
    </div>
  )
}
export function PlayerLine({children, meta, provisional = false}: {children: ReactNode; meta?: ReactNode; provisional?: boolean}) {
  return (
    <div className={`ew-msg is-player ${provisional ? 'is-provisional' : ''}`}>
      <div className="ew-msg-bubble">{children}</div>
      {meta && <div className="ew-msg-meta">{meta}</div>}
    </div>
  )
}
export function NarrationLine({children}: {children: ReactNode}) {
  return <div className="ew-msg is-narration"><p><RichTextChildren>{children}</RichTextChildren></p></div>
}
function RichTextChildren({children}: {children: ReactNode}) { return <>{children}</> }

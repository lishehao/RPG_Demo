/**
 * Minimal motion3.json curve evaluator (linear / restricted bezier / stepped /
 * inverse-stepped), used as a read-only sampler for authored idle loops. The single
 * frame writer decides what is actually applied (and clamps it to frozen caps).
 */
type Point = {t: number; v: number}
type Segment = {kind: 0 | 1 | 2 | 3; points: Point[]}
export type Curve = {id: string; segments: Segment[]}
export type Motion = {duration: number; loop: boolean; curves: Map<string, Curve>}

export function parseMotion(json: unknown): Motion {
  const data = json as {Meta?: {Duration?: number; Loop?: boolean}; Curves?: {Target?: string; Id?: string; Segments?: number[]}[]}
  if (!data?.Meta || !Array.isArray(data.Curves)) throw Error('motion_invalid')
  const curves = new Map<string, Curve>()
  for (const c of data.Curves) {
    if (c.Target !== 'Parameter' || typeof c.Id !== 'string' || !Array.isArray(c.Segments) || c.Segments.length < 2) continue
    const s = c.Segments
    const segments: Segment[] = []
    let last: Point = {t: s[0], v: s[1]}
    let i = 2
    while (i < s.length) {
      const kind = s[i] as 0 | 1 | 2 | 3
      if (kind === 1) {
        const p1 = {t: s[i + 1], v: s[i + 2]}, p2 = {t: s[i + 3], v: s[i + 4]}, p3 = {t: s[i + 5], v: s[i + 6]}
        segments.push({kind, points: [last, p1, p2, p3]}); last = p3; i += 7
      } else {
        const p = {t: s[i + 1], v: s[i + 2]}
        segments.push({kind, points: [last, p]}); last = p; i += 3
      }
    }
    curves.set(c.Id, {id: c.Id, segments})
  }
  return {duration: Number(data.Meta.Duration ?? 0), loop: !!data.Meta.Loop, curves}
}

function evalSegment(seg: Segment, t: number): number {
  const [a, b] = seg.points
  if (seg.kind === 0) {
    const end = seg.points[1], span = end.t - a.t
    const k = span <= 0 ? 0 : (t - a.t) / span
    return a.v + (end.v - a.v) * k
  }
  if (seg.kind === 2) return a.v
  if (seg.kind === 3) return b.v
  // Restricted bezier: time maps linearly (AreBeziersRestricted = true in every frozen file).
  const [p0, p1, p2, p3] = seg.points
  const span = p3.t - p0.t
  const k = span <= 0 ? 0 : Math.max(0, Math.min(1, (t - p0.t) / span))
  const lerp = (x: number, y: number) => x + (y - x) * k
  const q0 = lerp(p0.v, p1.v), q1 = lerp(p1.v, p2.v), q2 = lerp(p2.v, p3.v)
  const r0 = lerp(q0, q1), r1 = lerp(q1, q2)
  return lerp(r0, r1)
}

export function sampleCurve(curve: Curve, t: number): number {
  const segs = curve.segments
  if (!segs.length) return 0
  if (t <= segs[0].points[0].t) return segs[0].points[0].v
  for (const seg of segs) {
    const end = seg.points[seg.points.length - 1]
    if (t <= end.t) return evalSegment(seg, t)
  }
  const last = segs[segs.length - 1]
  return last.points[last.points.length - 1].v
}

export function sampleMotion(motion: Motion, seconds: number, ids: string[]): Record<string, number> {
  const t = motion.loop && motion.duration > 0 ? ((seconds % motion.duration) + motion.duration) % motion.duration : Math.min(seconds, motion.duration)
  const out: Record<string, number> = {}
  for (const id of ids) { const c = motion.curves.get(id); if (c) out[id] = sampleCurve(c, t) }
  return out
}

/** Loop-boundary continuity check used by tests and the stats overlay. */
export function loopSeam(motion: Motion, id: string): number {
  const c = motion.curves.get(id)
  if (!c) return 0
  return Math.abs(sampleCurve(c, 0) - sampleCurve(c, motion.duration))
}

import { useMemo, useRef, useState, type ChangeEvent } from "react"
import { useLanguage } from "../../shared/lib/i18n"
import {
  evaluateRpgBundle,
  isRpgEvaluationBundle,
  type EvaluationStatus,
  type RpgEvaluationBundle,
  type RpgEvaluationReport,
} from "./rpg-evaluation-contract"
import { RPG_EVALUATION_SAMPLES } from "./rpg-evaluation-samples"

type LabView = "overview" | "run" | "memory" | "adapter"

const CRITERION_LABELS = {
  memory_continuity: ["记忆连续性", "Memory continuity"],
  memory_boundedness: ["记忆有界性", "Memory boundedness"],
  consequence_visibility: ["后果可见性", "Consequence visibility"],
  player_agency: ["玩家能动性", "Player agency"],
  trajectory_progress: ["轨迹推进", "Trajectory progress"],
  entity_coherence: ["实体一致性", "Entity coherence"],
  choice_diversity: ["选择多样性", "Choice diversity"],
  boundary_hygiene: ["边界与界面卫生", "Boundary hygiene"],
} as const

const UI = {
  zh: {
    kicker: "研究型运行时 · 公开评测前端",
    title: "RPG Runtime Evaluation Lab",
    lede: "把不同 RPG Agent 的回合轨迹转成同一个可比较合同：记忆、选择、后果、人物、目标推进与边界。",
    boundary: "这是确定性产品诊断，不是已校准的学术质量分。叙事吸引力仍需要有界的人类评审。",
    back: "返回作品页",
    overview: "总览",
    run: "回合轨迹",
    memory: "记忆",
    adapter: "接入规范",
    benchmark: "基准运行",
    score: "综合诊断",
    turns: "回合",
    facts: "有效事实",
    corrections: "已覆盖事实",
    status: "状态",
    objective: "本局目标",
    compare: "对照结果",
    criteria: "逐项评测",
    action: "玩家行动",
    reaction: "世界响应",
    changes: "明确变化",
    next: "下一动作",
    active: "当前事实",
    superseded: "被覆盖但可审计",
    threads: "开放问题",
    entities: "人物状态",
    recent: "最近事件",
    import: "导入 JSON 运行包",
    exportBundle: "下载运行包",
    exportReport: "下载评测报告",
    reset: "恢复内置样例",
    invalid: "文件不是 rpg_evaluation_bundle.v1，或缺少回合数据。",
    adapterTitle: "让其他 RPG 接入",
    adapterCopy: "适配器只需输出场景、逐回合行动/响应、选项、结构化变化和记忆快照。评测前端不要求接入 Tiny Stories 后端。",
    noValue: "无",
  },
  en: {
    kicker: "Research runtime · public evaluation frontend",
    title: "RPG Runtime Evaluation Lab",
    lede: "Normalize RPG-agent runs into one comparable contract: memory, choices, consequences, people, objective progress, and boundaries.",
    boundary: "This is a deterministic product diagnostic, not a calibrated academic quality score. Narrative appeal still needs bounded human review.",
    back: "Back to portfolio",
    overview: "Overview",
    run: "Run trace",
    memory: "Memory",
    adapter: "Adapter",
    benchmark: "Benchmark run",
    score: "Diagnostic score",
    turns: "Turns",
    facts: "Active facts",
    corrections: "Superseded facts",
    status: "Status",
    objective: "Episode objective",
    compare: "Comparison",
    criteria: "Criterion review",
    action: "Player action",
    reaction: "World response",
    changes: "Visible changes",
    next: "Next actions",
    active: "Current facts",
    superseded: "Superseded, still auditable",
    threads: "Open threads",
    entities: "Person state",
    recent: "Recent events",
    import: "Import JSON run bundle",
    exportBundle: "Download run bundle",
    exportReport: "Download evaluation report",
    reset: "Restore built-in sample",
    invalid: "The file is not an rpg_evaluation_bundle.v1 bundle, or has no turns.",
    adapterTitle: "Connect another RPG",
    adapterCopy: "An adapter only needs to emit the scenario, per-turn action/response, options, typed changes, and memory snapshots. The lab does not require the Tiny Stories backend.",
    noValue: "None",
  },
} as const

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function scoreTone(status: EvaluationStatus) {
  return `rpg-lab-status rpg-lab-status--${status}`
}

export function RpgEvaluationPage({ onBack }: { onBack: () => void }) {
  const { lang, setLang } = useLanguage()
  const copy = UI[lang]
  const [bundle, setBundle] = useState<RpgEvaluationBundle>(RPG_EVALUATION_SAMPLES[0])
  const [view, setView] = useState<LabView>("overview")
  const [selectedTurn, setSelectedTurn] = useState(RPG_EVALUATION_SAMPLES[0].turns.length - 1)
  const [importError, setImportError] = useState("")
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const report = useMemo(() => evaluateRpgBundle(bundle), [bundle])
  const comparison = useMemo(
    () => RPG_EVALUATION_SAMPLES.map((sample) => ({ sample, report: evaluateRpgBundle(sample) })),
    [],
  )
  const latestMemory = bundle.turns[Math.min(selectedTurn, bundle.turns.length - 1)]?.memory

  const chooseBundle = (next: RpgEvaluationBundle) => {
    setBundle(next)
    setSelectedTurn(Math.max(0, next.turns.length - 1))
    setImportError("")
  }

  const handleImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      const value: unknown = JSON.parse(await file.text())
      if (!isRpgEvaluationBundle(value)) throw new Error("invalid bundle")
      chooseBundle(value)
    } catch {
      setImportError(copy.invalid)
    } finally {
      event.target.value = ""
    }
  }

  return (
    <div className="rpg-lab-page" data-rpg-evaluation-lab="true" data-rpg-evaluation-locale={lang}>
      <header className="rpg-lab-topbar">
        <button type="button" className="rpg-lab-back" onClick={onBack} aria-label={copy.back}>←</button>
        <div className="rpg-lab-brand">
          <strong>Tiny Stories</strong>
          <span>Runtime Lab / v1</span>
        </div>
        <div className="rpg-lab-language" aria-label="Language">
          <button type="button" className={lang === "zh" ? "is-active" : ""} onClick={() => setLang("zh")}>中</button>
          <button type="button" className={lang === "en" ? "is-active" : ""} onClick={() => setLang("en")}>EN</button>
        </div>
      </header>

      <main className="rpg-lab-main">
        <section className="rpg-lab-hero">
          <span>{copy.kicker}</span>
          <h1>{copy.title}</h1>
          <p>{copy.lede}</p>
          <div className="rpg-lab-boundary" data-rpg-evaluation-boundary="true">{copy.boundary}</div>
        </section>

        <section className="rpg-lab-controls" aria-label={copy.benchmark}>
          <div className="rpg-lab-sample-switcher" data-rpg-evaluation-sample-switcher="true">
            {RPG_EVALUATION_SAMPLES.map((sample) => (
              <button
                key={sample.run_id}
                type="button"
                className={sample.run_id === bundle.run_id ? "is-active" : ""}
                onClick={() => chooseBundle(sample)}
              >
                <span>{sample.system_label}</span>
                <small>{sample.scenario.title} · {sample.turns.length} {copy.turns.toLowerCase()}</small>
              </button>
            ))}
          </div>
          <div className="rpg-lab-import">
            <input ref={fileInputRef} type="file" accept="application/json,.json" onChange={(event) => void handleImport(event)} />
            <button type="button" onClick={() => fileInputRef.current?.click()}>{copy.import}</button>
          </div>
          {importError ? <p className="rpg-lab-import-error" role="alert">{importError}</p> : null}
        </section>

        <section className="rpg-lab-scoreboard" data-rpg-evaluation-summary="true">
          <div className="rpg-lab-score">
            <span>{copy.score}</span>
            <strong>{report.score}</strong>
            <em className={scoreTone(report.status)}>{report.status}</em>
          </div>
          <dl>
            <div><dt>{copy.turns}</dt><dd>{bundle.turns.length}/{bundle.scenario.turn_budget}</dd></div>
            <div><dt>{copy.facts}</dt><dd>{latestMemory?.active_facts.length ?? 0}</dd></div>
            <div><dt>{copy.corrections}</dt><dd>{latestMemory?.superseded_facts.length ?? 0}</dd></div>
            <div><dt>{copy.status}</dt><dd>{bundle.system_label}</dd></div>
          </dl>
        </section>

        <nav className="rpg-lab-tabs" aria-label="Evaluation views">
          {(["overview", "run", "memory", "adapter"] as const).map((item) => (
            <button key={item} type="button" className={view === item ? "is-active" : ""} onClick={() => setView(item)}>
              {copy[item]}
            </button>
          ))}
        </nav>

        {view === "overview" ? (
          <Overview report={report} bundle={bundle} comparison={comparison} lang={lang} copy={copy} />
        ) : null}
        {view === "run" ? <RunTrace bundle={bundle} copy={copy} /> : null}
        {view === "memory" && latestMemory ? (
          <MemoryView bundle={bundle} selectedTurn={selectedTurn} setSelectedTurn={setSelectedTurn} copy={copy} />
        ) : null}
        {view === "adapter" ? (
          <AdapterView
            copy={copy}
            onDownloadBundle={() => downloadJson(`${bundle.run_id}.json`, bundle)}
            onDownloadReport={() => downloadJson(`${bundle.run_id}-report.json`, report)}
            onReset={() => chooseBundle(RPG_EVALUATION_SAMPLES[0])}
          />
        ) : null}
      </main>
    </div>
  )
}

function Overview({
  report,
  bundle,
  comparison,
  lang,
  copy,
}: {
  report: RpgEvaluationReport
  bundle: RpgEvaluationBundle
  comparison: Array<{ sample: RpgEvaluationBundle; report: RpgEvaluationReport }>
  lang: "zh" | "en"
  copy: typeof UI.zh | typeof UI.en
}) {
  const labelIndex = lang === "zh" ? 0 : 1
  return (
    <section className="rpg-lab-view" data-rpg-evaluation-view="overview">
      <div className="rpg-lab-objective">
        <div>
          <span>{copy.objective}</span>
          <strong>{bundle.scenario.objective}</strong>
          <p>{bundle.scenario.genre} · {bundle.scenario.boundaries.join(" · ")}</p>
        </div>
        {bundle.scenario.scenario_id === "awards-livestream" ? (
          <figure>
            <img src="/webtoons/shells/entertainment_scandal.jpg" alt="Backstage awards livestream reference scene" />
            <figcaption>Reference scene / Awards Livestream</figcaption>
          </figure>
        ) : null}
      </div>
      <div className="rpg-lab-overview-grid">
        <section className="rpg-lab-criteria" aria-label={copy.criteria}>
          <div className="rpg-lab-section-head"><span>01</span><h2>{copy.criteria}</h2></div>
          {report.criteria.map((item) => (
            <article key={item.criterion} data-rpg-evaluation-criterion={item.criterion}>
              <div>
                <span className={scoreTone(item.status)}>{item.status}</span>
                <strong>{CRITERION_LABELS[item.criterion][labelIndex]}</strong>
              </div>
              <b>{item.score}</b>
              <p>{item.summary}</p>
              <details><summary>{item.evidence.length} evidence</summary>{item.evidence.map((entry) => <span key={entry}>{entry}</span>)}</details>
            </article>
          ))}
        </section>
        <aside className="rpg-lab-comparison" data-rpg-evaluation-comparison="true">
          <div className="rpg-lab-section-head"><span>02</span><h2>{copy.compare}</h2></div>
          {comparison.map(({ sample, report: sampleReport }) => (
            <div key={sample.run_id} className={sample.run_id === bundle.run_id ? "is-active" : ""}>
              <strong>{sample.system_label}</strong>
              <span>{sampleReport.score}</span>
              <i><b style={{ width: `${sampleReport.score}%` }} /></i>
              <small>{sampleReport.status} · {sample.turns.length} {copy.turns.toLowerCase()}</small>
            </div>
          ))}
          <p>{report.limitations[0]}</p>
        </aside>
      </div>
    </section>
  )
}

function RunTrace({ bundle, copy }: { bundle: RpgEvaluationBundle; copy: typeof UI.zh | typeof UI.en }) {
  return (
    <section className="rpg-lab-view rpg-lab-trace" data-rpg-evaluation-view="run">
      {bundle.turns.map((turn) => (
        <article key={turn.turn_index} data-rpg-evaluation-turn={turn.turn_index}>
          <header><span>{String(turn.turn_index).padStart(2, "0")}</span><strong>{Math.round(turn.objective_progress * 100)}%</strong></header>
          <div className="rpg-lab-trace-copy"><span>{copy.action}</span><p>{turn.player_action}</p></div>
          <div className="rpg-lab-trace-copy"><span>{copy.reaction}</span><p>{turn.world_response}</p></div>
          <div className="rpg-lab-deltas" aria-label={copy.changes}>
            {[...turn.state_deltas.map((delta) => delta.label), ...turn.clue_unlocks, ...turn.opportunity_unlocks].map((item) => <span key={item}>{item}</span>)}
          </div>
          <ol aria-label={copy.next}>{turn.options.map((option) => <li key={option}>{option}</li>)}</ol>
        </article>
      ))}
    </section>
  )
}

function MemoryView({
  bundle,
  selectedTurn,
  setSelectedTurn,
  copy,
}: {
  bundle: RpgEvaluationBundle
  selectedTurn: number
  setSelectedTurn: (turn: number) => void
  copy: typeof UI.zh | typeof UI.en
}) {
  const memory = bundle.turns[selectedTurn]?.memory
  if (!memory) return null
  return (
    <section className="rpg-lab-view" data-rpg-evaluation-view="memory">
      <div className="rpg-lab-turn-selector">
        {bundle.turns.map((turn, index) => (
          <button key={turn.turn_index} type="button" className={index === selectedTurn ? "is-active" : ""} onClick={() => setSelectedTurn(index)}>
            T{turn.turn_index}
          </button>
        ))}
      </div>
      <div className="rpg-lab-memory-grid" data-rpg-evaluation-memory="true">
        <section><div className="rpg-lab-section-head"><span>A</span><h2>{copy.active}</h2></div>{memory.active_facts.map((fact) => <p key={fact.fact_id}><b>{fact.key}</b><span>{fact.value}</span></p>)}</section>
        <section><div className="rpg-lab-section-head"><span>B</span><h2>{copy.superseded}</h2></div>{memory.superseded_facts.length ? memory.superseded_facts.map((fact) => <p key={fact.fact_id}><b>{fact.key}</b><span>{fact.value}</span></p>) : <em>{copy.noValue}</em>}</section>
        <section><div className="rpg-lab-section-head"><span>C</span><h2>{copy.entities}</h2></div>{memory.entities.map((entity) => <p key={entity.entity_id}><b>{entity.name}</b><span>{Object.entries(entity.state).map(([key, value]) => `${key}: ${value}`).join(" · ")}</span></p>)}</section>
        <section><div className="rpg-lab-section-head"><span>D</span><h2>{copy.threads}</h2></div>{memory.open_threads.length ? memory.open_threads.map((thread) => <p key={thread}>{thread}</p>) : <em>{copy.noValue}</em>}<h3>{copy.recent}</h3>{memory.recent_events.map((event) => <small key={event}>{event}</small>)}</section>
      </div>
    </section>
  )
}

function AdapterView({
  copy,
  onDownloadBundle,
  onDownloadReport,
  onReset,
}: {
  copy: typeof UI.zh | typeof UI.en
  onDownloadBundle: () => void
  onDownloadReport: () => void
  onReset: () => void
}) {
  return (
    <section className="rpg-lab-view rpg-lab-adapter" data-rpg-evaluation-view="adapter">
      <div className="rpg-lab-section-head"><span>API</span><h2>{copy.adapterTitle}</h2></div>
      <p>{copy.adapterCopy}</p>
      <div className="rpg-lab-adapter-flow">
        <span>Scenario</span><i>→</i><span>Turns</span><i>→</i><span>Memory</span><i>→</i><span>Report</span>
      </div>
      <pre aria-label="Adapter contract">{`{
  "schema_version": "rpg_evaluation_bundle.v1",
  "scenario": { "objective": "...", "entity_ids": [] },
  "turns": [{
    "player_action": "...",
    "world_response": "...",
    "options": ["..."],
    "state_deltas": [],
    "memory": { "schema_version": "rpg_memory.v1" }
  }]
}`}</pre>
      <div className="rpg-lab-adapter-actions">
        <button type="button" onClick={onDownloadBundle}>{copy.exportBundle}</button>
        <button type="button" onClick={onDownloadReport}>{copy.exportReport}</button>
        <button type="button" onClick={onReset}>{copy.reset}</button>
      </div>
    </section>
  )
}

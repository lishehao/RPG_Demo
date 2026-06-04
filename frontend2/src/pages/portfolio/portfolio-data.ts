export const REVIEWER_DEMO_TITLE = "The Merger Betrayal"

export const YOUTUBE_DEMO_URL = "https://youtu.be/RRJ7uyjW_nA"

export const YOUTUBE_DEMO_EMBED_URL =
  "https://www.youtube.com/embed/RRJ7uyjW_nA?autoplay=1&mute=1&playsinline=1&controls=1&rel=0"

export const LOCAL_DEMO_MP4_URL =
  "https://lishehao.github.io/RPG_Demo/demo-video/tiny-stories-admissions-demo-readme.mp4"

export const REVIEWER_DEMO_SEED =
  "Minutes before the awards livestream, my cofounder announces our secret merger onstage. My ex steps into the control room holding the recording that proves I buried the deal."

export const REVIEWER_DEMO_ACTIONS = [
  "Start from a locked English seed",
  "Inspect the generated cast and player role",
  "Play two or three turns to watch consequences accumulate",
  "Open the advisor sidechat for out-of-band reasoning",
  "Finish on a labeled ending with highlights and alternate branches",
] as const

export const PORTFOLIO_METRICS = [
  { value: "1 seed", label: "from prompt to playable runtime" },
  { value: "12 turns", label: "bounded episode arc for demo reliability" },
  { value: "5 layers", label: "seed, role, state, advisor, ending" },
  { value: "EN first", label: "portfolio-facing path and UI copy" },
] as const

export const PIPELINE_STEPS = [
  {
    eyebrow: "01",
    title: "Seed Router",
    summary: "Classifies setting, conflict, language and story shell before generation starts.",
    proof: "The reviewer seed is deliberately office + entertainment + betrayal, which routes into the current hand-drawn case-file demo surface.",
  },
  {
    eyebrow: "02",
    title: "Playable Role Model",
    summary: "Turns the protagonist into an operational player identity with public persona, private objective, leverage and starting assets.",
    proof: "This is the piece that makes the project more than story completion: the player has a position to defend, not just text to read.",
  },
  {
    eyebrow: "03",
    title: "Stateful Consequences",
    summary: "Every chosen option or free-form action appends a narrator beat, updates turn state, and preserves inventory / pulse signals.",
    proof: "The runtime inspector exposes the current stage, option count, inventory count and ending state while the run is being played.",
  },
  {
    eyebrow: "04",
    title: "Advisor Channel",
    summary: "A parallel sidechat gives the player an outside reader without taking control away from them.",
    proof: "For portfolio review, this shows a second story-aware companion surface that stays role-separated from the narrator.",
  },
  {
    eyebrow: "05",
    title: "Ending Compiler",
    summary: "The run resolves into a labeled ending, a subtitle, highlights, and hypothetical branches.",
    proof: "The final screen converts a free-form playthrough into a shareable artifact and a replay loop.",
  },
] as const

export const CASE_STUDY_POINTS = [
  {
    title: "Problem",
    body: "Most AI story demos feel either like a chatbot or a random text generator. They do not make the player position, system state, or ending logic visible enough to feel designed.",
  },
  {
    title: "Product Thesis",
    body: "Tiny Stories treats generation as a bounded interactive runtime: one strong seed becomes a cast, a role, staged turns, advisor context, and a replayable ending.",
  },
  {
    title: "Engineering Angle",
    body: "The useful portfolio signal is not prompt novelty. It is the product layer around generation: deterministic routing, typed contracts, state recovery, English localization, and verifiable demo flow.",
  },
] as const

export const INTERACTION_LOOP = [
  {
    eyebrow: "Seed",
    title: "A dense conflict starts the run",
    body: "The reviewer does not browse a gallery first; they enter through a single high-pressure premise with public stakes and private evidence.",
    artifact: "secret merger · awards livestream · ex with proof",
  },
  {
    eyebrow: "Role",
    title: "The player gets a position to defend",
    body: "The generated role gives the player a public persona, private objective, trump cards, and items before the first turn.",
    artifact: "identity · objective · leverage · assets",
  },
  {
    eyebrow: "Turn",
    title: "Choices create visible consequences",
    body: "Each move updates the story, relationship pulse, inventory and reviewer inspector without turning the play surface into a dashboard.",
    artifact: "option / free text · pulse · inventory · advisor",
  },
  {
    eyebrow: "Ending",
    title: "The run becomes a replayable artifact",
    body: "The ending compiler turns a live playthrough into a labeled result with highlights and alternate branches.",
    artifact: "label · subtitle · highlights · branches",
  },
] as const

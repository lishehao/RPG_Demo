export const REVIEWER_DEMO_TITLE = "The Merger Betrayal"

export const YOUTUBE_DEMO_URL = "https://youtu.be/RRJ7uyjW_nA"

export const YOUTUBE_DEMO_EMBED_URL =
  "https://www.youtube.com/embed/RRJ7uyjW_nA?autoplay=1&mute=1&playsinline=1&controls=1&rel=0"

export const LOCAL_DEMO_MP4_URL =
  "https://lishehao.github.io/RPG_Demo/demo-video/tiny-stories-admissions-demo-readme.mp4"

export const REVIEWER_DEMO_SEED =
  "Minutes before the awards livestream, Mira the anxious publicist, Producer Han, Rina the backup dancer witness, Eun Sol the fan-channel reporter, and Choi the sponsor director gather in the control room after singer Seo Mina disappears. Mira must decide what to reveal before sponsors and fans panic, with no violence and no blackmail."

export const REVIEWER_DEMO_ACTIONS = [
  "Start from a locked English seed",
  "Inspect the generated cast and player role",
  "Play two or three turns to watch consequences accumulate",
  "Open the advisor sidechat for out-of-band reasoning",
  "Finish on a labeled ending with highlights and alternate branches",
] as const

export const PORTFOLIO_METRICS = [
  { value: "Locked seed", label: "same premise for every reviewer run" },
  { value: "12-turn cap", label: "bounded episode budget visible in Play" },
  { value: "3 proofs", label: "playable state, state change, archived checks" },
  { value: "Replay loop", label: "ending can be shared or restarted" },
] as const

export const PIPELINE_STEPS = [
  {
    eyebrow: "01",
    title: "Seed becomes setup",
    summary: "A concrete premise turns into cast, pressure, language, and a bounded episode plan before play starts.",
    proof: "Reviewers can start from the same locked seed and compare the generated role, opening scene, and choices against that premise.",
  },
  {
    eyebrow: "02",
    title: "Role creates stakes",
    summary: "The protagonist becomes a playable identity with public persona, private objective, leverage, and starting assets.",
    proof: "This is the piece that makes the project more than story completion: the player has a position to defend, not just text to read.",
  },
  {
    eyebrow: "03",
    title: "Choices change state",
    summary: "Every chosen option or free-form action appends a narrator beat and updates visible pulse, inventory, and next-move signals.",
    proof: "The reviewer evidence summary exposes playable state, state change, and archived checks while the run is being played.",
  },
  {
    eyebrow: "04",
    title: "Advisor stays separate",
    summary: "A parallel sidechat gives the player an outside reader without taking control away from the narrator or the player.",
    proof: "For portfolio review, this shows a second context-aware surface that helps the player think without submitting moves for them.",
  },
  {
    eyebrow: "05",
    title: "Ending becomes replay",
    summary: "The run resolves into a labeled ending, subtitle, highlights, and alternate-branch recap.",
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
    body: "The reviewer starts from one locked premise, so the generated setup can be checked against the same source every time.",
    artifact: "visible evidence: locked seed and generated opening",
  },
  {
    eyebrow: "Role",
    title: "The player gets a position to defend",
    body: "The generated role gives the player a public persona, private objective, leverage, and starting assets before the first turn.",
    artifact: "visible evidence: role panel, objective, assets",
  },
  {
    eyebrow: "Turn",
    title: "Choices create visible consequences",
    body: "Each move updates the story, relationship pulse, inventory, and reviewer evidence without turning the play surface into a dashboard.",
    artifact: "visible evidence: next moves, pulse, inventory",
  },
  {
    eyebrow: "Ending",
    title: "The run becomes a replayable artifact",
    body: "The ending screen turns the playthrough into a labeled result with highlights, alternate branches, share, and replay.",
    artifact: "visible evidence: ending, highlights, replay link",
  },
] as const

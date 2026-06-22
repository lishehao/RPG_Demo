export const REVIEWER_DEMO_TITLE = "The Missing Singer Broadcast"

export const YOUTUBE_DEMO_URL = "https://youtu.be/RRJ7uyjW_nA"

export const YOUTUBE_DEMO_EMBED_URL =
  "https://www.youtube.com/embed/RRJ7uyjW_nA?autoplay=1&mute=1&playsinline=1&controls=1&rel=0"

export const LOCAL_DEMO_MP4_URL =
  "https://lishehao.github.io/RPG_Demo/demo-video/tiny-stories-admissions-demo-readme.mp4"

export const PUBLIC_REPO_URL = "https://github.com/lishehao/RPG_Demo"

export const SYSTEM_MAP_URL = "https://github.com/lishehao/RPG_Demo/blob/main/docs/CURRENT_SYSTEM_MAP.md"

export const EVIDENCE_PACKET_URL =
  "https://github.com/lishehao/RPG_Demo/blob/main/docs/tiny-stories-engineering-evidence-packet.md"

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
  { value: "3 proofs", label: "playable state, visible change, proof limits" },
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
    summary: "Every chosen option or free-form action appends a narrator beat and updates visible character reactions, story items, and next-move signals.",
    proof: "The reviewer evidence summary shows playable state, visible change after a move, and the proof limits for that run while it is being played.",
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
    body: "Many AI story demos hide player role, state changes, and ending proof, so a reviewer cannot tell whether the result is a designed product system or just generated text.",
  },
  {
    title: "Product Loop",
    body: "Tiny Stories makes one seed travel through locked setup, playable role, visible state changes, advisor boundary, and replayable ending, so the player can follow what changed.",
  },
  {
    title: "Evidence Standard",
    body: "The application signal is product-system evidence: typed state, persistent sessions, reviewer evidence hooks, recovery paths, and mobile-checked surfaces without claiming broad adoption.",
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
    body: "Each move updates the story, character reactions, story items, and reviewer evidence without turning the play surface into a dashboard.",
    artifact: "visible evidence: next moves, character reactions, story items",
  },
  {
    eyebrow: "Ending",
    title: "The run becomes a replayable artifact",
    body: "The ending screen turns the playthrough into a labeled result with highlights, alternate branches, share, and replay.",
    artifact: "visible evidence: ending, highlights, replay link",
  },
] as const

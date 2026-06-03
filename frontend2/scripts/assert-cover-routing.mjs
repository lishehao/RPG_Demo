#!/usr/bin/env node

import {
  GENERATED_ASSETS,
  resolveGeneratedCoverForText,
} from "../src/shared/lib/webtoon-assets.ts"

const cases = [
  {
    name: "Mars comedy setting overrides cozy tone",
    explicitProfile: "comedy",
    corpus: [
      "Mars colony talent show",
      "Theatre Club",
      "oxygen accusation",
      "Hydroponics faction",
      "Earth Media",
      "low-stakes comedy",
    ].join(" "),
    expected: GENERATED_ASSETS.coverSciFiMars,
  },
  {
    name: "Plain cozy comedy stays cozy",
    explicitProfile: "comedy",
    corpus: "Neighborhood bake sale comedy with cupcakes and a playful misunderstanding",
    expected: GENERATED_ASSETS.coverCozy,
  },
]

for (const testCase of cases) {
  const actual = resolveGeneratedCoverForText(testCase.corpus, testCase.explicitProfile)
  if (actual !== testCase.expected) {
    throw new Error(`${testCase.name}: expected ${testCase.expected}, got ${actual}`)
  }
}

console.log(`cover routing assertions passed (${cases.length})`)

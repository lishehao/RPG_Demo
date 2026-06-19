import type { NarrativeTensionProfile } from "../../api/contracts"
import type { StoryGuideConversationState, StoryGuideInlineLedger, StoryGuideNodeName } from "../../shared/lib/story-guide-loop"

export type TensionProfileChoice = "auto" | NarrativeTensionProfile

export type GuideMessage = {
  id: string
  speaker: "guide" | "user"
  text: string
  node?: StoryGuideNodeName
  state?: StoryGuideConversationState
  ledger?: StoryGuideInlineLedger
}

export type StoryShapeRead = {
  runLength: string
  runLengthDetail: string
  pressureMode: string
  pressureModeDetail: string
  storyLanguage: string
  storyLanguageDetail: string
  tone: string
  toneDetail: string
}

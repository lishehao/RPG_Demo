export function stageDisplayName(stage: string): string {
  if (stage === "hook") return "Prelude"
  if (stage === "pressure") return "Build"
  if (stage === "reversal") return "Turn"
  if (stage === "climax") return "Climax"
  if (stage === "pre_finale" || stage === "pre_finale_open") return "Coda"
  return stage.replace(/_/g, " ")
}

export type ReviewSeverity = 'blocking' | 'warning' | 'info';
export type ReviewTargetType = 'beat' | 'scene' | 'move' | 'pack';

export type ReviewIssue = {
  severity: ReviewSeverity;
  title: string;
  message: string;
  target_type: ReviewTargetType;
  target_id: string;
};

export type StoryPackOverview = {
  storyId: string;
  title: string;
  description: string;
  styleGuard: string;
  inputHint: string;
};

export type StoryPackCastMember = {
  name: string;
  redLine: string;
  conflictTags: string[];
};

export type StoryPackBeat = {
  id: string;
  title: string;
  stepBudget: number | null;
  requiredEvents: string[];
  npcQuota: number | null;
  entrySceneId: string;
};

export type StoryPackExitCondition = {
  id: string;
  conditionKind: string;
  key: string;
  value: string;
  nextSceneId: string;
  endStory: boolean;
};

export type StoryPackScene = {
  id: string;
  beatId: string;
  sceneSeed: string;
  presentNpcs: string[];
  enabledMoves: string[];
  alwaysAvailableMoves: string[];
  exitConditions: StoryPackExitCondition[];
  isTerminal: boolean;
};

export type StoryPackMove = {
  id: string;
  label: string;
  strategyStyle: string;
  intents: string[];
  outcomes: { id: string; result: string }[];
};

export type StoryPackReviewModel = {
  overview: StoryPackOverview;
  cast: StoryPackCastMember[];
  beats: StoryPackBeat[];
  scenes: StoryPackScene[];
  moves: StoryPackMove[];
  issues: ReviewIssue[];
  counts: {
    cast: number;
    beats: number;
    scenes: number;
    moves: number;
  };
};

function asObject(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asObjectArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(asObject) : [];
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function buildStoryPackReviewModel(draftPack: Record<string, unknown>): StoryPackReviewModel {
  const pack = asObject(draftPack);
  const overview: StoryPackOverview = {
    storyId: asString(pack.story_id),
    title: asString(pack.title),
    description: asString(pack.description),
    styleGuard: asString(pack.style_guard),
    inputHint: asString(pack.input_hint),
  };

  const cast = asObjectArray(pack.npc_profiles).map((profile) => ({
    name: asString(profile.name),
    redLine: asString(profile.red_line),
    conflictTags: asStringArray(profile.conflict_tags),
  }));

  const beats = asObjectArray(pack.beats).map((beat) => ({
    id: asString(beat.id),
    title: asString(beat.title),
    stepBudget: asNumber(beat.step_budget),
    requiredEvents: asStringArray(beat.required_events),
    npcQuota: asNumber(beat.npc_quota),
    entrySceneId: asString(beat.entry_scene_id),
  }));

  const scenes = asObjectArray(pack.scenes).map((scene) => ({
    id: asString(scene.id),
    beatId: asString(scene.beat_id),
    sceneSeed: asString(scene.scene_seed),
    presentNpcs: asStringArray(scene.present_npcs),
    enabledMoves: asStringArray(scene.enabled_moves),
    alwaysAvailableMoves: asStringArray(scene.always_available_moves),
    exitConditions: asObjectArray(scene.exit_conditions).map((condition) => ({
      id: asString(condition.id),
      conditionKind: asString(condition.condition_kind),
      key: asString(condition.key),
      value: asString(condition.value),
      nextSceneId: asString(condition.next_scene_id),
      endStory: Boolean(condition.end_story),
    })),
    isTerminal: Boolean(scene.is_terminal),
  }));

  const moves = asObjectArray(pack.moves).map((move) => ({
    id: asString(move.id),
    label: asString(move.label),
    strategyStyle: asString(move.strategy_style),
    intents: asStringArray(move.intents),
    outcomes: asObjectArray(move.outcomes).map((outcome) => ({
      id: asString(outcome.id),
      result: asString(outcome.result),
    })),
  }));

  const issues: ReviewIssue[] = [];
  const sceneIds = new Set(scenes.map((scene) => scene.id).filter(Boolean));
  const beatIds = new Set(beats.map((beat) => beat.id).filter(Boolean));
  const moveIds = new Set(moves.map((move) => move.id).filter(Boolean));

  if (!overview.storyId) {
    issues.push({
      severity: 'blocking',
      title: 'Missing story_id',
      message: 'The pack is missing a top-level story identifier.',
      target_type: 'pack',
      target_id: 'story_id',
    });
  }
  if (beats.length === 0) {
    issues.push({
      severity: 'blocking',
      title: 'No beats defined',
      message: 'The pack should define at least one beat before publish review.',
      target_type: 'pack',
      target_id: 'beats',
    });
  }
  if (scenes.length === 0) {
    issues.push({
      severity: 'blocking',
      title: 'No scenes defined',
      message: 'The pack should define at least one scene before publish review.',
      target_type: 'pack',
      target_id: 'scenes',
    });
  }
  if (moves.length === 0) {
    issues.push({
      severity: 'blocking',
      title: 'No moves defined',
      message: 'The pack should define at least one move before publish review.',
      target_type: 'pack',
      target_id: 'moves',
    });
  }

  for (const beat of beats) {
    if (!beat.entrySceneId || !sceneIds.has(beat.entrySceneId)) {
      issues.push({
        severity: 'blocking',
        title: 'Beat entry scene missing',
        message: `Beat ${beat.id || '(unknown)'} points at a missing entry scene '${beat.entrySceneId || 'none'}'.`,
        target_type: 'beat',
        target_id: beat.id || 'unknown-beat',
      });
    }
  }

  for (const scene of scenes) {
    if (!scene.beatId || !beatIds.has(scene.beatId)) {
      issues.push({
        severity: 'blocking',
        title: 'Scene beat reference missing',
        message: `Scene ${scene.id || '(unknown)'} references beat '${scene.beatId || 'none'}', which does not exist.`,
        target_type: 'scene',
        target_id: scene.id || 'unknown-scene',
      });
    }
    if (scene.enabledMoves.length === 0) {
      issues.push({
        severity: 'warning',
        title: 'Scene has no enabled moves',
        message: `Scene ${scene.id || '(unknown)'} has no authored moves surfaced in enabled_moves.`,
        target_type: 'scene',
        target_id: scene.id || 'unknown-scene',
      });
    }

    const availableMoveIds = new Set([...scene.enabledMoves, ...scene.alwaysAvailableMoves]);
    for (const condition of scene.exitConditions) {
      if (!condition.endStory && !condition.nextSceneId) {
        issues.push({
          severity: 'blocking',
          title: 'Exit condition has no destination',
          message: `Scene ${scene.id || '(unknown)'} has condition '${condition.id || 'unknown'}' without next_scene_id or end_story=true.`,
          target_type: 'scene',
          target_id: scene.id || 'unknown-scene',
        });
      }
      if (condition.nextSceneId && !sceneIds.has(condition.nextSceneId)) {
        issues.push({
          severity: 'blocking',
          title: 'Exit condition points to missing scene',
          message: `Scene ${scene.id || '(unknown)'} points to next_scene_id '${condition.nextSceneId}', which is not defined.`,
          target_type: 'scene',
          target_id: scene.id || 'unknown-scene',
        });
      }
      if (condition.conditionKind === 'state_equals' && condition.key === 'last_move' && condition.value && !availableMoveIds.has(condition.value)) {
        issues.push({
          severity: 'blocking',
          title: 'Exit condition references an unavailable move',
          message: `Scene ${scene.id || '(unknown)'} requires last_move='${condition.value}', but that move is not available in this scene.`,
          target_type: 'scene',
          target_id: scene.id || 'unknown-scene',
        });
      }
    }
  }

  for (const move of moves) {
    if (move.outcomes.length === 0) {
      issues.push({
        severity: 'blocking',
        title: 'Move has no outcomes',
        message: `Move ${move.id || '(unknown)'} has no authored outcomes.`,
        target_type: 'move',
        target_id: move.id || 'unknown-move',
      });
    }
    if (!move.label) {
      issues.push({
        severity: 'warning',
        title: 'Move label missing',
        message: `Move ${move.id || '(unknown)'} has an empty label, which makes review and play harder to read.`,
        target_type: 'move',
        target_id: move.id || 'unknown-move',
      });
    }
    if (!moveIds.has(move.id)) {
      issues.push({
        severity: 'warning',
        title: 'Move identifier missing',
        message: 'A move entry is missing its id.',
        target_type: 'move',
        target_id: 'unknown-move',
      });
    }
  }

  if (issues.length === 0) {
    issues.push({
      severity: 'info',
      title: 'No structural issues detected',
      message: 'The draft looks internally consistent enough for human review and publish evaluation.',
      target_type: 'pack',
      target_id: overview.storyId || 'pack',
    });
  }

  return {
    overview,
    cast,
    beats,
    scenes,
    moves,
    issues,
    counts: {
      cast: cast.length,
      beats: beats.length,
      scenes: scenes.length,
      moves: moves.length,
    },
  };
}

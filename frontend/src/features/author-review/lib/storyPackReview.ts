export type ReviewSeverity = 'blocking' | 'warning' | 'info';
export type ReviewTargetType = 'beat' | 'scene' | 'move' | 'pack';

export type ReviewIssue = {
  severity: ReviewSeverity;
  title: string;
  message: string;
  target_type: ReviewTargetType;
  target_id: string;
};

export type StoryPackOpeningGuidance = {
  introText: string;
  goalHint: string;
  starterPrompts: [string, string, string] | string[];
};

export type StoryPackOverview = {
  storyId: string;
  title: string;
  description: string;
  styleGuard: string;
  inputHint: string;
  openingGuidance: StoryPackOpeningGuidance;
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

function buildFallbackOpeningGuidance(pack: Record<string, unknown>) {
  const title = asString(pack.title) || 'This story';
  const description = asString(pack.description);
  const beat = asObjectArray(pack.beats)[0] ?? {};
  const intro = [title, description].filter(Boolean).join(' — ');
  return {
    introText: intro || 'You are entering the opening pressure point of this story.',
    goalHint: `Start by understanding ${asString(beat.title) || 'the first beat'} and what will get worse if you wait.`,
    starterPrompts: [
      'I inspect the immediate scene and look for the first reliable clue.',
      'I ask the most relevant ally what changed just before this began.',
      'I move carefully and test the safest next action.',
    ],
  };
}

export function buildStoryPackReviewModel(draftPack: Record<string, unknown>): StoryPackReviewModel {
  const pack = asObject(draftPack);
  const openingGuidanceObject = asObject(pack.opening_guidance);
  const overview: StoryPackOverview = {
    storyId: asString(pack.story_id),
    title: asString(pack.title),
    description: asString(pack.description),
    styleGuard: asString(pack.style_guard),
    inputHint: asString(pack.input_hint),
    openingGuidance:
      Object.keys(openingGuidanceObject).length > 0
        ? {
            introText: asString(openingGuidanceObject.intro_text),
            goalHint: asString(openingGuidanceObject.goal_hint),
            starterPrompts: asStringArray(openingGuidanceObject.starter_prompts).slice(0, 3),
          }
        : buildFallbackOpeningGuidance(pack),
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
  if (!overview.openingGuidance.introText.trim()) {
    issues.push({
      severity: 'warning',
      title: 'Opening intro is empty',
      message: 'Play first-turn guidance works better when the story has a clear opening setup.',
      target_type: 'pack',
      target_id: 'opening_guidance.intro_text',
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

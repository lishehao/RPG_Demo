import { buildStoryPackReviewModel, type StoryPackReviewModel } from '@/shared/lib/storyPackReview';
import type { StoryDraftPatchChange } from '@/shared/api/types';

export type EditableStoryDraftState = {
  story: {
    title: string;
    description: string;
    style_guard: string;
    input_hint: string;
  };
  beats: Record<string, { title: string }>;
  scenes: Record<string, { scene_seed: string }>;
  npcs: Record<string, { red_line: string }>;
};

function cloneDraftPack(draftPack: Record<string, unknown>) {
  return JSON.parse(JSON.stringify(draftPack)) as Record<string, unknown>;
}

export function buildEditableStoryDraftState(reviewModel: StoryPackReviewModel): EditableStoryDraftState {
  return {
    story: {
      title: reviewModel.overview.title,
      description: reviewModel.overview.description,
      style_guard: reviewModel.overview.styleGuard,
      input_hint: reviewModel.overview.inputHint,
    },
    beats: Object.fromEntries(reviewModel.beats.map((beat) => [beat.id, { title: beat.title }])),
    scenes: Object.fromEntries(reviewModel.scenes.map((scene) => [scene.id, { scene_seed: scene.sceneSeed }])),
    npcs: Object.fromEntries(reviewModel.cast.map((member) => [member.name, { red_line: member.redLine }])),
  };
}

export function applyEditableStoryDraft(
  draftPack: Record<string, unknown>,
  editableDraft: EditableStoryDraftState,
): Record<string, unknown> {
  const nextPack = cloneDraftPack(draftPack);

  nextPack.title = editableDraft.story.title;
  nextPack.description = editableDraft.story.description;
  nextPack.style_guard = editableDraft.story.style_guard;
  nextPack.input_hint = editableDraft.story.input_hint;

  const beats = Array.isArray(nextPack.beats) ? nextPack.beats : [];
  for (const beat of beats) {
    if (beat && typeof beat === 'object') {
      const beatId = typeof beat.id === 'string' ? beat.id : '';
      if (beatId && editableDraft.beats[beatId]) {
        beat.title = editableDraft.beats[beatId].title;
      }
    }
  }

  const scenes = Array.isArray(nextPack.scenes) ? nextPack.scenes : [];
  for (const scene of scenes) {
    if (scene && typeof scene === 'object') {
      const sceneId = typeof scene.id === 'string' ? scene.id : '';
      if (sceneId && editableDraft.scenes[sceneId]) {
        scene.scene_seed = editableDraft.scenes[sceneId].scene_seed;
      }
    }
  }

  const profiles = Array.isArray(nextPack.npc_profiles) ? nextPack.npc_profiles : [];
  for (const profile of profiles) {
    if (profile && typeof profile === 'object') {
      const name = typeof profile.name === 'string' ? profile.name : '';
      if (name && editableDraft.npcs[name]) {
        profile.red_line = editableDraft.npcs[name].red_line;
      }
    }
  }

  return nextPack;
}

export function buildStoryDraftPatchChanges(
  originalReviewModel: StoryPackReviewModel,
  editableDraft: EditableStoryDraftState,
): StoryDraftPatchChange[] {
  const changes: StoryDraftPatchChange[] = [];

  if (editableDraft.story.title !== originalReviewModel.overview.title) {
    changes.push({ target_type: 'story', field: 'title', value: editableDraft.story.title });
  }
  if (editableDraft.story.description !== originalReviewModel.overview.description) {
    changes.push({ target_type: 'story', field: 'description', value: editableDraft.story.description });
  }
  if (editableDraft.story.style_guard !== originalReviewModel.overview.styleGuard) {
    changes.push({ target_type: 'story', field: 'style_guard', value: editableDraft.story.style_guard });
  }
  if (editableDraft.story.input_hint !== originalReviewModel.overview.inputHint) {
    changes.push({ target_type: 'story', field: 'input_hint', value: editableDraft.story.input_hint });
  }

  for (const beat of originalReviewModel.beats) {
    const nextValue = editableDraft.beats[beat.id]?.title;
    if (nextValue !== undefined && nextValue !== beat.title) {
      changes.push({ target_type: 'beat', target_id: beat.id, field: 'title', value: nextValue });
    }
  }

  for (const scene of originalReviewModel.scenes) {
    const nextValue = editableDraft.scenes[scene.id]?.scene_seed;
    if (nextValue !== undefined && nextValue !== scene.sceneSeed) {
      changes.push({ target_type: 'scene', target_id: scene.id, field: 'scene_seed', value: nextValue });
    }
  }

  for (const member of originalReviewModel.cast) {
    const nextValue = editableDraft.npcs[member.name]?.red_line;
    if (nextValue !== undefined && nextValue !== member.redLine) {
      changes.push({ target_type: 'npc', target_id: member.name, field: 'red_line', value: nextValue });
    }
  }

  return changes;
}

export function hasEditableStoryDraftChanges(
  originalReviewModel: StoryPackReviewModel,
  editableDraft: EditableStoryDraftState,
): boolean {
  return buildStoryDraftPatchChanges(originalReviewModel, editableDraft).length > 0;
}

export function buildReviewModelFromEditableDraft(
  draftPack: Record<string, unknown>,
  editableDraft: EditableStoryDraftState,
): StoryPackReviewModel {
  return buildStoryPackReviewModel(applyEditableStoryDraft(draftPack, editableDraft));
}

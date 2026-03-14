from __future__ import annotations

from rpg_backend.application.author_runs.workflow_vocabulary import AuthorWorkflowNode


WORKFLOW_CONDITIONAL_ROUTES: dict[str, set[str]] = {
    AuthorWorkflowNode.GENERATE_STORY_OVERVIEW: {
        AuthorWorkflowNode.GENERATE_STORY_OVERVIEW,
        AuthorWorkflowNode.PLAN_BEATS,
        AuthorWorkflowNode.WORKFLOW_FAILED,
    },
    AuthorWorkflowNode.PLAN_BEATS: {
        AuthorWorkflowNode.PLAN_BEATS,
        AuthorWorkflowNode.PLAN_BEAT_SCENES,
        AuthorWorkflowNode.WORKFLOW_FAILED,
    },
    AuthorWorkflowNode.PLAN_BEAT_SCENES: {
        AuthorWorkflowNode.PLAN_BEAT_SCENES,
        AuthorWorkflowNode.GENERATE_SCENE,
        AuthorWorkflowNode.WORKFLOW_FAILED,
    },
    AuthorWorkflowNode.GENERATE_SCENE: {
        AuthorWorkflowNode.GENERATE_SCENE,
        AuthorWorkflowNode.ASSEMBLE_BEAT,
        AuthorWorkflowNode.WORKFLOW_FAILED,
    },
    AuthorWorkflowNode.ASSEMBLE_BEAT: {
        AuthorWorkflowNode.PLAN_BEAT_SCENES,
        AuthorWorkflowNode.BEAT_LINT,
        AuthorWorkflowNode.WORKFLOW_FAILED,
    },
    AuthorWorkflowNode.BEAT_LINT: {
        AuthorWorkflowNode.PLAN_BEAT_SCENES,
        AuthorWorkflowNode.ASSEMBLE_STORY_PACK,
        AuthorWorkflowNode.WORKFLOW_FAILED,
    },
    AuthorWorkflowNode.FINAL_LINT: {
        AuthorWorkflowNode.REVIEW_READY,
        AuthorWorkflowNode.WORKFLOW_FAILED,
    },
}


WORKFLOW_LINEAR_EDGES: tuple[tuple[str, str], ...] = (
    (AuthorWorkflowNode.ASSEMBLE_STORY_PACK, AuthorWorkflowNode.NORMALIZE_STORY_PACK),
    (AuthorWorkflowNode.NORMALIZE_STORY_PACK, AuthorWorkflowNode.FINAL_LINT),
)

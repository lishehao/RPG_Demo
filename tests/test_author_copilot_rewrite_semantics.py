from __future__ import annotations

from datetime import datetime, timezone

from rpg_backend.author.compiler.bundle import build_design_bundle
from rpg_backend.author.contracts import (
    AffordanceEffectProfile,
    AuthorCopilotBeatRewrite,
    AuthorCopilotCastRewrite,
    AuthorCopilotProposalResponse,
    AuthorCopilotRewritePlan,
    AuthorCopilotRulePackRewrite,
    AuthorCopilotStoryFrameRewrite,
    AuthorCopilotStateAxisRewrite,
    AuthorCopilotWorkspaceSnapshot,
    EndingRule,
    EndingRulesDraft,
    OverviewFlagDraft,
    OverviewTruthDraft,
    RouteAffordancePackDraft,
    RouteUnlockRule,
)
from rpg_backend.author.copilot import (
    _classify_rewrite_intent_heuristically,
    apply_copilot_operations,
    build_copilot_proposal,
    build_copilot_locked_boundaries,
    repair_copilot_candidate,
    validate_copilot_candidate,
)
from rpg_backend.play.compiler import compile_play_plan
from rpg_backend.roster.admin import build_runtime_catalog
from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from rpg_backend.roster.service import CharacterRosterService
from tests.author_fixtures import author_fixture_bundle
from tests.author_fixtures import FakeGateway
from tests.author_fixtures import gateway_with_overrides
from tests.author_fixtures import repeated_gateway_error
from rpg_backend.author.jobs import AuthorJobService
from rpg_backend.author.storage import SQLiteAuthorJobStorage


class _StubEmbeddingProvider:
    def embed_text(self, text: str) -> list[float] | None:
        del text
        return None


def _roster_source_entry(**overrides) -> CharacterRosterSourceEntry:
    payload = {
        "character_id": "roster_archive_vote_certifier",
        "slug": "archive-vote-certifier",
        "name_en": "Lin Verrow",
        "name_zh": "林维若",
        "portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/neutral/current.png",
        "default_portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/neutral/current.png",
        "portrait_variants": {
            "negative": "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/negative/current.png",
            "neutral": "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/neutral/current.png",
            "positive": "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/positive/current.png",
        },
        "public_summary_en": "A formal certifier who keeps the public archive vote legible.",
        "public_summary_zh": "一名维持档案投票可读性的正式认证官。",
        "role_hint_en": "Archive vote certifier",
        "role_hint_zh": "档案投票认证官",
        "agenda_seed_en": "Keep the certification chain intact.",
        "agenda_seed_zh": "守住认证链条。",
        "red_line_seed_en": "Will not certify altered records.",
        "red_line_seed_zh": "不会认证被改写的记录。",
        "pressure_signature_seed_en": "Turns every missing seal into a public credibility problem.",
        "pressure_signature_seed_zh": "把每一个缺失印章都变成公共可信度问题。",
        "gender_lock": "unspecified",
        "personality_core_en": "Calm in public, exacting under pressure, and difficult to stampede once procedure matters.",
        "personality_core_zh": "公开场合冷静，压力上来时会更苛刻，一旦程序变重要就很难被裹挟。",
        "experience_anchor_en": "A records certifier known for staying with the chain of custody after others want a quicker story.",
        "experience_anchor_zh": "一名长期守着交接链的记录认证官，别人想更快翻页时仍会把链条盯到底。",
        "identity_lock_notes_en": "Keep the same person, the same face, and the same public identity. Do not rename or rewrite them into a different person.",
        "identity_lock_notes_zh": "必须保持同一个人、同一张脸和同一公共身份。不得改名，也不得改写成另一个人。",
        "theme_tags": ["truth_record_crisis"],
        "setting_tags": ["archive"],
        "tone_tags": ["procedural"],
        "conflict_tags": ["public_record"],
        "slot_tags": ["guardian"],
        "retrieval_terms": ["archive", "vote", "certifier"],
        "rarity_weight": 1.0,
    }
    payload.update(overrides)
    return CharacterRosterSourceEntry.from_payload(payload)


def _archive_vote_roster_service() -> CharacterRosterService:
    return CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=build_runtime_catalog((_roster_source_entry(),)).entries,
        embedding_provider=_StubEmbeddingProvider(),
        max_supporting_cast_selections=4,
    )


def _workspace_snapshot() -> AuthorCopilotWorkspaceSnapshot:
    fixture = author_fixture_bundle()
    plan = compile_play_plan(story_id="copilot-semantics", bundle=fixture.design_bundle)
    return AuthorCopilotWorkspaceSnapshot(
        focused_brief=fixture.focused_brief,
        story_frame_draft=fixture.story_frame,
        cast_overview_draft=fixture.cast_overview,
        cast_member_drafts=list(fixture.cast_draft.cast),
        cast_draft=fixture.cast_draft,
        beat_plan_draft=fixture.beat_plan,
        route_opportunity_plan_draft=fixture.route_opportunity_plan,
        route_affordance_pack_draft=None,
        ending_intent_draft=None,
        ending_rules_draft=None,
        primary_theme="logistics_quarantine_crisis",
        theme_modifiers=[],
        cast_topology="three_slot",
        runtime_profile=plan.runtime_policy_profile,
        closeout_profile=plan.closeout_profile,
        max_turns=plan.max_turns,
    )


def _proposal(plan: AuthorCopilotRewritePlan) -> AuthorCopilotProposalResponse:
    now = datetime.now(timezone.utc)
    return AuthorCopilotProposalResponse(
        proposal_id="proposal-1",
        proposal_group_id="group-1",
        session_id="session-1",
        job_id="job-1",
        status="draft",
        source="llm",
        mode="bundle_rewrite",
        instruction="Rewrite the whole bundle more aggressively.",
        base_revision=now.isoformat(),
        variant_index=1,
        variant_label="Semantic rewrite",
        supersedes_proposal_id=None,
        created_at=now,
        updated_at=now,
        request_summary="Broaden story and rule semantics while preserving runtime lane.",
        rewrite_scope="global_story_rewrite",
        rewrite_brief="Broaden story and rule semantics while preserving runtime lane.",
        affected_sections=["story_frame", "cast", "beats", "rule_pack"],
        stability_guards=[],
        rewrite_plan=plan,
        patch_targets=["story_frame", "cast", "beats", "rule_pack"],
        operations=[],
        impact_summary=[],
        warnings=[],
    )


def _editor_state(snapshot: AuthorCopilotWorkspaceSnapshot):
    fixture = author_fixture_bundle()
    service = AuthorJobService(storage=SQLiteAuthorJobStorage(":memory:"))
    bundle = build_design_bundle(
        snapshot.story_frame_draft,
        snapshot.cast_draft,
        snapshot.beat_plan_draft,
        snapshot.focused_brief,
    )
    from rpg_backend.author.jobs import _AuthorJobRecord
    from rpg_backend.author.preview import build_author_story_summary
    from rpg_backend.author.contracts import AuthorJobProgress
    from tests.test_author_product_api import _preview_response

    record = _AuthorJobRecord(
        job_id="intent-job",
        owner_user_id="local-dev",
        prompt_seed="seed",
        preview=_preview_response("seed"),
        status="completed",
        progress=AuthorJobProgress(stage="completed", stage_index=10, stage_total=10),
        summary=build_author_story_summary(bundle, primary_theme=snapshot.primary_theme),
        bundle=bundle,
        copilot_workspace_snapshot=snapshot,
    )
    service._save_record(record)
    return service.get_job_editor_state("intent-job")


def test_classify_rewrite_intent_heuristically_supports_broad_en_and_zh_briefs() -> None:
    snapshot = _workspace_snapshot()
    editor_state = _editor_state(snapshot)

    en_intent = _classify_rewrite_intent_heuristically(
        instruction="Broaden the story rules and political texture, push the draft toward public record exposure, and keep the same runtime lane.",
        rewrite_brief="Keep the same premise family and runtime lane while preparing a global rewrite.",
        editor_state=editor_state,
    )
    zh_intent = _classify_rewrite_intent_heuristically(
        instruction="在不改变当前玩法轮廓的前提下，强化公开记录曝光与政治拉扯，让世界规则、角色关系和节拍反馈更鲜明。",
        rewrite_brief="保留当前故事的核心题材与玩法轮廓，但允许做更宽泛的全局重写。",
        editor_state=editor_state.model_copy(update={"language": "zh"}),
    )

    assert en_intent is not None
    assert en_intent.story_frame_emphasis is not None
    assert en_intent.political_texture is not None
    assert en_intent.truth_exposure_emphasis is not None
    assert zh_intent is not None
    assert zh_intent.story_frame_emphasis is not None
    assert zh_intent.political_texture is not None
    assert zh_intent.truth_exposure_emphasis is not None


def test_build_copilot_proposal_synthesizes_broad_brief_without_exact_keyword_match() -> None:
    snapshot = _workspace_snapshot()
    editor_state = _editor_state(snapshot)

    proposal, _fingerprint = build_copilot_proposal(
        gateway=None,
        session=None,
        job_id="broad-job",
        base_revision="2026-03-24T00:00:00+00:00",
        editor_state=editor_state,
        workspace_snapshot=snapshot,
        instruction="Broaden the story rules and political texture, push the draft toward public record exposure, and keep the same runtime lane.",
        proposal_group_id="group-1",
        variant_index=1,
    )

    assert proposal.source == "heuristic"
    assert "story_frame" in proposal.affected_sections
    assert any(section in proposal.affected_sections for section in ("beats", "rule_pack", "cast"))
    assert proposal.request_summary
    assert proposal.variant_label


def test_apply_copilot_operations_supports_richer_bundle_rewrite(monkeypatch) -> None:
    snapshot = _workspace_snapshot()
    import rpg_backend.author.copilot as copilot_module

    monkeypatch.setattr(copilot_module, "get_character_roster_service", _archive_vote_roster_service)
    base_bundle = build_design_bundle(
        snapshot.story_frame_draft,
        snapshot.cast_draft,
        snapshot.beat_plan_draft,
        snapshot.focused_brief,
    )
    supporting_npc_id = base_bundle.story_bible.cast[1].npc_id
    plan = AuthorCopilotRewritePlan(
        story_frame=AuthorCopilotStoryFrameRewrite(
            world_rules=[
                "Emergency shipping law only works if every exception is visible.",
                "A sealed record is as dangerous as a sealed berth.",
            ],
            truths=[
                OverviewTruthDraft(text="The quarantine ledger was falsified before the first inspection.", importance="core"),
                OverviewTruthDraft(text="Every faction needs the harbor to reopen but wants the blame pinned elsewhere.", importance="core"),
            ],
            flags=[OverviewFlagDraft(label="Ledger leak", starting_value=True)],
            state_axis_choices=[
                AuthorCopilotStateAxisRewrite(
                    template_id="external_pressure",
                    story_label="Harbor Heat",
                    starting_value=2,
                )
            ],
        ),
        cast=[
            AuthorCopilotCastRewrite(
                npc_id=supporting_npc_id,
                name="Certifier Jun",
                roster_character_id="roster_archive_vote_certifier",
                agenda="Turn the forged ledger into the one document nobody in the harbor coalition can outrun.",
            )
        ],
        beats=[
            AuthorCopilotBeatRewrite(
                beat_id="b1",
                focus_names=["Envoy Iri", "Broker Tal"],
                conflict_pair=["Envoy Iri", "Broker Tal"],
                required_truth_texts=["The quarantine ledger was falsified before the first inspection."],
                detour_budget=2,
                return_hooks=["A missing seal becomes the one detail everyone has to explain in public."],
                affordance_tags=["reveal_truth", "shift_public_narrative"],
                blocked_affordances=["build_trust"],
            ),
                AuthorCopilotBeatRewrite(
                    beat_id="b2",
                    focus_names=["Lin Verrow", "Broker Tal"],
                    conflict_pair=["Lin Verrow", "Broker Tal"],
                    required_truth_texts=["Every faction needs the harbor to reopen but wants the blame pinned elsewhere."],
                ),
        ],
        rule_pack=AuthorCopilotRulePackRewrite(
            route_unlock_rules=[
                RouteUnlockRule(
                    rule_id="b1_public_archive_route",
                    beat_id="b1",
                    conditions={"required_truths": ["truth_1"]},
                    unlock_route_id="b1_public_archive_route",
                    unlock_affordance_tag="reveal_truth",
                )
            ],
            affordance_effect_profiles=[
                AffordanceEffectProfile(
                    affordance_tag="reveal_truth",
                    default_story_function="reveal",
                    axis_deltas={"external_pressure": 1},
                    stance_deltas={},
                    can_add_truth=True,
                    can_add_event=False,
                ),
                AffordanceEffectProfile(
                    affordance_tag="shift_public_narrative",
                    default_story_function="advance",
                    axis_deltas={"political_leverage": 1},
                    stance_deltas={},
                    can_add_truth=False,
                    can_add_event=True,
                ),
            ],
            ending_rules=[
                EndingRule(ending_id="collapse", priority=1, conditions={"min_axes": {"external_pressure": 5}}),
                EndingRule(
                    ending_id="pyrrhic",
                    priority=2,
                    conditions={"min_axes": {"political_leverage": 5, "external_pressure": 3}, "required_truths": ["truth_1"]},
                ),
                EndingRule(ending_id="mixed", priority=10, conditions={}),
            ],
        ),
    )

    candidate_snapshot, candidate_bundle = apply_copilot_operations(
        workspace_snapshot=snapshot,
        proposal=_proposal(plan),
        gateway=FakeGateway(),
    )

    assert candidate_snapshot.story_frame_draft.world_rules[0] == "Emergency shipping law only works if every exception is visible."
    assert candidate_snapshot.story_frame_draft.truths[0].text == "The quarantine ledger was falsified before the first inspection."
    assert candidate_snapshot.story_frame_draft.flags[0].label == "Ledger leak"
    assert candidate_snapshot.story_frame_draft.state_axis_choices[0].story_label == "Harbor Heat"
    assert candidate_snapshot.cast_draft.cast[1].name == "Lin Verrow"
    assert candidate_snapshot.cast_draft.cast[1].roster_character_id == "roster_archive_vote_certifier"
    assert candidate_snapshot.cast_draft.cast[1].roster_public_summary
    assert candidate_snapshot.cast_draft.cast[1].template_version
    assert candidate_snapshot.cast_draft.cast[1].portrait_url == "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/neutral/current.png"
    assert candidate_snapshot.cast_draft.cast[1].role == "Archive certifier"
    assert candidate_snapshot.cast_draft.cast[1].agenda == "Turn the forged ledger into the one document nobody in the harbor coalition can outrun."
    assert "missing seal" in candidate_snapshot.cast_draft.cast[1].pressure_signature
    assert candidate_snapshot.beat_plan_draft.beats[0].focus_names == ["Envoy Iri", "Broker Tal"]
    assert candidate_snapshot.beat_plan_draft.beats[0].affordance_tags == ["reveal_truth", "shift_public_narrative"]
    assert candidate_snapshot.route_affordance_pack_draft is not None
    assert candidate_snapshot.ending_rules_draft is not None
    assert any(rule.rule_id == "b1_public_archive_route" for rule in candidate_snapshot.route_affordance_pack_draft.route_unlock_rules)
    assert {"collapse", "pyrrhic", "mixed"} == {rule.ending_id for rule in candidate_bundle.rule_pack.ending_rules}
    assert validate_copilot_candidate(
        workspace_snapshot=snapshot,
        candidate_snapshot=candidate_snapshot,
        bundle=candidate_bundle,
    ) == []


def test_validate_copilot_candidate_rejects_invalid_references_and_missing_endings() -> None:
    snapshot = _workspace_snapshot()
    broken_cast = list(snapshot.cast_draft.cast)
    broken_cast[1] = broken_cast[1].model_copy(update={"roster_character_id": "roster_missing_character"})
    broken_snapshot = snapshot.model_copy(
        update={
            "cast_draft": snapshot.cast_draft.model_copy(update={"cast": broken_cast}),
            "cast_member_drafts": broken_cast,
            "beat_plan_draft": snapshot.beat_plan_draft.model_copy(
                update={
                    "beats": [
                        snapshot.beat_plan_draft.beats[0].model_copy(
                            update={
                                "focus_names": ["Missing Witness"],
                                "conflict_pair": ["Missing Witness", "Broker Tal"],
                                "pressure_axis_id": "resource_strain",
                                "required_truth_texts": ["A truth that is not in the catalog."],
                            }
                        ),
                        *snapshot.beat_plan_draft.beats[1:],
                    ]
                }
            ),
            "route_affordance_pack_draft": RouteAffordancePackDraft(
                route_unlock_rules=[],
                affordance_effect_profiles=[
                    AffordanceEffectProfile(
                        affordance_tag="reveal_truth",
                        default_story_function="reveal",
                        axis_deltas={"missing_axis": 1},
                        stance_deltas={},
                        can_add_truth=True,
                        can_add_event=False,
                    ),
                    AffordanceEffectProfile(
                        affordance_tag="build_trust",
                        default_story_function="advance",
                        axis_deltas={},
                        stance_deltas={"missing_stance": 1},
                        can_add_truth=False,
                        can_add_event=True,
                    ),
                ],
            ),
            "ending_rules_draft": EndingRulesDraft(
                ending_rules=[
                    EndingRule(
                        ending_id="mixed",
                        priority=10,
                        conditions={"min_axes": {"missing_axis": 1}},
                    )
                ]
            ),
        }
    )
    bundle = build_design_bundle(
        broken_snapshot.story_frame_draft,
        broken_snapshot.cast_draft,
        broken_snapshot.beat_plan_draft,
        broken_snapshot.focused_brief,
    )

    reasons = validate_copilot_candidate(
        workspace_snapshot=snapshot,
        candidate_snapshot=broken_snapshot,
        bundle=bundle,
    )

    assert "roster_character_missing" in reasons
    assert "beat_focus_reference_missing" in reasons
    assert "beat_conflict_reference_missing" in reasons
    assert "beat_axis_reference_missing" in reasons
    assert "beat_required_truth_missing" in reasons
    assert "route_unlock_rules_empty" in reasons
    assert "affordance_profile_reference_invalid" in reasons
    assert "required_endings_missing" in reasons
    assert "ending_rule_reference_invalid" in reasons


def test_apply_copilot_operations_falls_back_to_deterministic_roster_projection_when_instance_generation_fails(monkeypatch) -> None:
    snapshot = _workspace_snapshot()
    import rpg_backend.author.copilot as copilot_module

    monkeypatch.setattr(copilot_module, "get_character_roster_service", _archive_vote_roster_service)
    base_bundle = build_design_bundle(
        snapshot.story_frame_draft,
        snapshot.cast_draft,
        snapshot.beat_plan_draft,
        snapshot.focused_brief,
    )
    supporting_npc_id = base_bundle.story_bible.cast[1].npc_id
    plan = AuthorCopilotRewritePlan(
        cast=[
                AuthorCopilotCastRewrite(
                    npc_id=supporting_npc_id,
                    roster_character_id="roster_archive_vote_certifier",
                )
            ]
        )

    candidate_snapshot, _candidate_bundle = apply_copilot_operations(
        workspace_snapshot=snapshot,
        proposal=_proposal(plan),
        gateway=gateway_with_overrides(character_instance_variation=repeated_gateway_error("llm_invalid_json")),
    )

    member = candidate_snapshot.cast_draft.cast[1]
    assert member.name == "Lin Verrow"
    assert member.roster_character_id == "roster_archive_vote_certifier"
    assert member.template_version
    assert member.role == snapshot.cast_overview_draft.cast_slots[1].public_role
    assert member.portrait_url == "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/neutral/current.png"


def test_apply_copilot_operations_falls_back_to_deterministic_roster_projection_when_instance_provider_fails(monkeypatch) -> None:
    snapshot = _workspace_snapshot()
    import rpg_backend.author.copilot as copilot_module

    monkeypatch.setattr(copilot_module, "get_character_roster_service", _archive_vote_roster_service)
    base_bundle = build_design_bundle(
        snapshot.story_frame_draft,
        snapshot.cast_draft,
        snapshot.beat_plan_draft,
        snapshot.focused_brief,
    )
    supporting_npc_id = base_bundle.story_bible.cast[1].npc_id
    plan = AuthorCopilotRewritePlan(
        cast=[
                AuthorCopilotCastRewrite(
                    npc_id=supporting_npc_id,
                    roster_character_id="roster_archive_vote_certifier",
                )
            ]
        )

    candidate_snapshot, _candidate_bundle = apply_copilot_operations(
        workspace_snapshot=snapshot,
        proposal=_proposal(plan),
        gateway=gateway_with_overrides(character_instance_variation=repeated_gateway_error("llm_provider_failed")),
    )

    member = candidate_snapshot.cast_draft.cast[1]
    assert member.name == "Lin Verrow"
    assert member.roster_character_id == "roster_archive_vote_certifier"
    assert member.template_version
    assert member.role == snapshot.cast_overview_draft.cast_slots[1].public_role
    assert member.portrait_url == "http://127.0.0.1:8000/portraits/roster/roster_archive_vote_certifier/neutral/current.png"


def test_apply_copilot_operations_sanitizes_gender_locked_member_updates(monkeypatch) -> None:
    snapshot = _workspace_snapshot()
    import rpg_backend.author.copilot as copilot_module

    monkeypatch.setattr(copilot_module, "get_character_roster_service", _archive_vote_roster_service)
    base_bundle = build_design_bundle(
        snapshot.story_frame_draft,
        snapshot.cast_draft,
        snapshot.beat_plan_draft,
        snapshot.focused_brief,
    )
    supporting_npc_id = base_bundle.story_bible.cast[1].npc_id
    plan = AuthorCopilotRewritePlan(
        cast=[
            AuthorCopilotCastRewrite(
                npc_id=supporting_npc_id,
                roster_character_id="roster_archive_vote_certifier",
                role="Archive certifier under emergency review",
                agenda="She means to keep the certification chain public before the chamber locks a false result into law.",
            )
        ]
    )

    candidate_snapshot, _candidate_bundle = apply_copilot_operations(
        workspace_snapshot=snapshot,
        proposal=_proposal(plan),
        gateway=FakeGateway(),
    )

    member = candidate_snapshot.cast_draft.cast[1]
    assert member.role == "Archive certifier under emergency review"
    assert "she " not in member.agenda.casefold()


def test_repair_copilot_candidate_reverts_rule_semantics_but_preserves_safe_tilt() -> None:
    snapshot = _workspace_snapshot()
    plan = AuthorCopilotRewritePlan(
        rule_pack=AuthorCopilotRulePackRewrite(
            toward="collapse",
            intensity="strong",
            route_unlock_rules=[
                RouteUnlockRule(
                    rule_id="bad-route",
                    beat_id="missing-beat",
                    conditions={},
                    unlock_route_id="missing-route",
                    unlock_affordance_tag="reveal_truth",
                )
            ],
            ending_rules=[EndingRule(ending_id="mixed", priority=10, conditions={})],
        )
    )
    proposal = _proposal(plan)

    candidate_snapshot, candidate_bundle = apply_copilot_operations(
        workspace_snapshot=snapshot,
        proposal=proposal,
    )
    initial_reasons = validate_copilot_candidate(
        workspace_snapshot=snapshot,
        candidate_snapshot=candidate_snapshot,
        bundle=candidate_bundle,
    )
    assert "route_unlock_rules_empty" in initial_reasons
    assert "required_endings_missing" in initial_reasons

    repaired_snapshot, repaired_bundle = repair_copilot_candidate(
        workspace_snapshot=snapshot,
        candidate_snapshot=candidate_snapshot,
        proposal=proposal,
    )

    assert validate_copilot_candidate(
        workspace_snapshot=snapshot,
        candidate_snapshot=repaired_snapshot,
        bundle=repaired_bundle,
    ) == []
    mixed_rule = next(rule for rule in repaired_bundle.rule_pack.ending_rules if rule.ending_id == "mixed")
    assert mixed_rule.conditions.max_axes
    assert repaired_snapshot.route_affordance_pack_draft is not None
    assert repaired_snapshot.route_affordance_pack_draft.route_unlock_rules

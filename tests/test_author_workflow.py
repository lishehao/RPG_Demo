from __future__ import annotations

import time

from langgraph.checkpoint.memory import InMemorySaver
from rpg_backend.story_profiles import AuthorThemeDecision

from rpg_backend.author.checkpointer import graph_config
from rpg_backend.author.jobs import AuthorJobService
from rpg_backend.author.progress import AUTHOR_LOADING_NODE_FLOW
from rpg_backend.author.contracts import AuthorBundleRequest
from rpg_backend.play.compiler import compile_play_plan
from rpg_backend.author.workflow import build_author_graph, run_author_bundle
from rpg_backend.roster.admin import build_runtime_catalog
from rpg_backend.roster.contracts import CharacterRosterSourceEntry
from rpg_backend.roster.service import CharacterRosterService
from tests.author_fixtures import (
    FakeGateway,
    RecoveringStoryFrameGateway,
    LowQualityStoryFrameGateway,
    fallback_beat_plan_gateway,
    fallback_ending_rules_gateway,
    fallback_overview_gateway,
    fallback_rulepack_gateway,
    generic_cast_gateway,
    gateway_with_overrides,
    narrow_route_diversity_gateway,
    noncanonical_ending_priority_gateway,
    low_quality_route_opportunities_gateway,
    placeholder_cast_gateway,
    repeated_gateway_error,
)


class _StubEmbeddingProvider:
    def embed_text(self, text: str) -> list[float] | None:
        del text
        return None


def _roster_source_entry(**overrides) -> CharacterRosterSourceEntry:
    payload = {
        "character_id": "roster_default",
        "slug": "default",
        "name_en": "Default",
        "name_zh": "默认",
        "portrait_url": None,
        "public_summary_en": "Default roster entry.",
        "public_summary_zh": "默认角色。",
        "role_hint_en": "Default role",
        "role_hint_zh": "默认角色",
        "agenda_seed_en": "Keeps the record visible.",
        "agenda_seed_zh": "让记录保持可见。",
        "red_line_seed_en": "Will not let the room erase the record.",
        "red_line_seed_zh": "不会让这间屋子抹掉记录。",
        "pressure_signature_seed_en": "Turns every missing stamp into a public question.",
        "pressure_signature_seed_zh": "会把每一个缺失印记都变成公开问题。",
        "gender_lock": "unspecified",
        "personality_core_en": "Calm in public, exacting under pressure, and difficult to stampede once procedure matters.",
        "personality_core_zh": "公开场合冷静，压力上来时会更苛刻，一旦程序变重要就很难被裹挟。",
        "experience_anchor_en": "A records-facing civic worker known for staying with the file after everyone else wants a quicker story.",
        "experience_anchor_zh": "一名长期面向记录工作的公共人员，别人想更快翻页时，仍会留下来把档案看完。",
        "identity_lock_notes_en": "Keep the same person, the same face, and the same public identity. Do not rename or rewrite them into a different person.",
        "identity_lock_notes_zh": "必须保持同一个人、同一张脸和同一公共身份。不得改名，也不得改写成另一个人。",
        "theme_tags": ["legitimacy_crisis"],
        "setting_tags": ["archive", "blackout"],
        "tone_tags": ["tense"],
        "conflict_tags": ["public_record", "legitimacy"],
        "slot_tags": ["guardian"],
        "retrieval_terms": ["archive", "record", "hearing"],
        "rarity_weight": 1.0,
    }
    payload.update(overrides)
    return CharacterRosterSourceEntry.from_payload(payload)


def test_author_graph_can_checkpoint_state_snapshot() -> None:
    graph = build_author_graph(gateway=FakeGateway(), checkpointer=InMemorySaver())
    config = graph_config(run_id="run-1")
    result = graph.invoke(
        {
            "run_id": "run-1",
            "raw_brief": "A hopeful political fantasy about keeping a city together during a crisis.",
        },
        config=config,
    )
    snapshot = graph.get_state(config)

    assert "design_bundle" in result
    assert snapshot.values["story_frame_draft"].title
    assert snapshot.values["cast_overview_draft"].cast_slots
    assert snapshot.values["cast_member_drafts"]
    assert snapshot.values["cast_draft"].cast
    assert snapshot.values["beat_plan_draft"].beats
    assert snapshot.values["primary_theme"]
    assert snapshot.values["beat_plan_strategy"]
    assert snapshot.values["story_frame_source"] == "generated"
    assert snapshot.values["beat_plan_source"] == "generated"
    assert snapshot.values["route_opportunity_plan_draft"].opportunities
    assert snapshot.values["route_opportunity_plan_source"] == "generated"
    assert snapshot.values["route_affordance_pack_draft"].affordance_effect_profiles
    assert snapshot.values["route_affordance_source"] == "compiled"
    assert snapshot.values["ending_intent_draft"].ending_intents
    assert snapshot.values["ending_rules_draft"].ending_rules
    assert snapshot.values["ending_source"] == "generated"
    assert snapshot.values["quality_trace"]
    assert {item["stage"] for item in snapshot.values["quality_trace"]} >= {"story_frame", "beat_plan", "route_affordance", "ending"}
    assert snapshot.values["design_bundle"].story_bible.title
    assert snapshot.values["design_bundle"].rule_pack.ending_rules
    assert snapshot.values["bundle_snapshot"].snapshot_id
    assert len(snapshot.values["beat_snapshots"]) == len(snapshot.values["design_bundle"].beat_spine)
    assert len(snapshot.values["design_bundle"].beat_runtime_shards) == len(snapshot.values["design_bundle"].beat_spine)
    assert [item.beat_id for item in snapshot.values["design_bundle"].beat_runtime_shards] == [
        beat.beat_id for beat in snapshot.values["design_bundle"].beat_spine
    ]
    assert "rule_pack" not in snapshot.values
    assert snapshot.values["author_session_response_id"]


def test_author_loading_progress_starts_from_zero_of_ten() -> None:
    progress = AuthorJobService._initial_author_loading_progress()

    assert AUTHOR_LOADING_NODE_FLOW[0] == "resume_from_preview_checkpoint"
    assert len(AUTHOR_LOADING_NODE_FLOW) == 10
    assert progress.stage == "resume_from_preview_checkpoint"
    assert progress.stage_index == 0
    assert progress.stage_total == 10


def test_author_graph_generates_dynamic_number_of_cast_members_from_cast_overview() -> None:
    gateway = FakeGateway()
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=gateway,
    )

    assert len(result.state["cast_overview_draft"].cast_slots) == 4
    assert len(result.state["cast_member_drafts"]) == 4
    assert len(result.bundle.story_bible.cast) == 4
    assert result.state["cast_strategy"] == "legitimacy_cast"
    assert result.bundle.story_bible.cast[0].name == "Envoy Iri"
    assert result.bundle.story_bible.cast[0].roster_character_id is None
    roster_character_ids = [item.roster_character_id for item in result.bundle.story_bible.cast if item.roster_character_id]
    assert set(roster_character_ids) == {
        "roster_legitimacy_charter_envoy",
        "roster_legitimacy_compact_broker",
        "roster_legitimacy_oath_witness",
    }
    generated_cast_calls = [item for item in gateway.call_trace if item["operation"] == "cast_member_semantics"]
    assert len(generated_cast_calls) == 1


def test_author_bundle_uses_batch_cast_generation_when_roster_disabled(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    monkeypatch.setattr(
        workflow_module,
        "get_character_roster_service",
        lambda: CharacterRosterService(
            enabled=False,
            catalog_version=None,
            catalog=(),
            embedding_provider=_StubEmbeddingProvider(),
            max_supporting_cast_selections=0,
        ),
    )

    gateway = FakeGateway()
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=gateway,
    )

    assert len(result.bundle.story_bible.cast) == 4
    assert any(item["operation"] == "cast_generate_full" for item in gateway.call_trace)
    assert not any(item["operation"] == "cast_member_semantics" for item in gateway.call_trace)


def test_author_graph_progress_observer_reports_cast_substage_details(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    monkeypatch.setattr(
        workflow_module,
        "get_character_roster_service",
        lambda: CharacterRosterService(
            enabled=False,
            catalog_version=None,
            catalog=(),
            embedding_provider=_StubEmbeddingProvider(),
            max_supporting_cast_selections=0,
        ),
    )

    seen: list[dict[str, object]] = []
    graph = build_author_graph(
        gateway=FakeGateway(),
        checkpointer=InMemorySaver(),
        progress_observer=lambda **payload: seen.append(payload),
    )
    graph.invoke(
        {
            "run_id": "run-progress-observer",
            "raw_brief": "A civic fantasy about preserving trust during a blackout election.",
        },
        config=graph_config(run_id="run-progress-observer"),
    )

    assert any(item.get("running_substage") == "roster_retrieval" for item in seen)
    assert any(item.get("running_substage") == "theme_route_lock" for item in seen)
    assert any(item.get("running_substage") == "cast_topology_plan" for item in seen)
    assert any(item.get("running_substage") == "cast_overview_compile" for item in seen)
    assert any(item.get("running_substage") == "batch_generate_remaining_cast" for item in seen)
    assert any(item.get("running_capability") == "author.cast_member_generate" for item in seen)


def test_author_graph_progress_observer_reports_story_frame_repair_details() -> None:
    seen: list[dict[str, object]] = []
    graph = build_author_graph(
        gateway=RecoveringStoryFrameGateway(),
        checkpointer=InMemorySaver(),
        progress_observer=lambda **payload: seen.append(payload),
    )
    graph.invoke(
        {
            "run_id": "run-story-frame-progress",
            "raw_brief": "A harbor inspector must keep the dock coalition alive after missing manifests threaten emergency rule during quarantine.",
        },
        config=graph_config(run_id="run-story-frame-progress"),
    )

    assert any(item.get("running_substage") == "story_frame_generate" for item in seen)
    assert any(item.get("running_substage") == "story_frame_repair" for item in seen)
    assert any(item.get("running_capability") == "author.story_frame_scaffold" for item in seen)
    assert any(item.get("running_capability") == "author.story_frame_finalize" for item in seen)


def test_author_graph_progress_observer_reports_beat_plan_fallback_details(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    monkeypatch.setattr(
        workflow_module,
        "get_character_roster_service",
        lambda: CharacterRosterService(
            enabled=False,
            catalog_version=None,
            catalog=(),
            embedding_provider=_StubEmbeddingProvider(),
            max_supporting_cast_selections=0,
        ),
    )
    seen: list[dict[str, object]] = []
    graph = build_author_graph(
        gateway=fallback_beat_plan_gateway(),
        checkpointer=InMemorySaver(),
        progress_observer=lambda **payload: seen.append(payload),
    )
    graph.invoke(
        {
            "run_id": "run-beat-progress",
            "raw_brief": "A civic fantasy about preserving trust during a blackout election.",
        },
        config=graph_config(run_id="run-beat-progress"),
    )

    assert any(item.get("running_substage") == "beat_plan_generate" for item in seen)
    assert any(item.get("running_substage") == "beat_plan_default_fallback" for item in seen)
    assert any(item.get("running_capability") == "author.beat_skeleton_generate" for item in seen)


def test_author_graph_progress_observer_reports_route_compile_details(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    monkeypatch.setattr(
        workflow_module,
        "get_character_roster_service",
        lambda: CharacterRosterService(
            enabled=False,
            catalog_version=None,
            catalog=(),
            embedding_provider=_StubEmbeddingProvider(),
            max_supporting_cast_selections=0,
        ),
    )
    seen: list[dict[str, object]] = []
    graph = build_author_graph(
        gateway=low_quality_route_opportunities_gateway(),
        checkpointer=InMemorySaver(),
        progress_observer=lambda **payload: seen.append(payload),
    )
    graph.invoke(
        {
            "run_id": "run-route-progress",
            "raw_brief": "A civic fantasy about preserving trust during a blackout election.",
        },
        config=graph_config(run_id="run-route-progress"),
    )

    assert any(item.get("running_substage") == "route_generate" for item in seen)
    assert any(item.get("running_substage") == "route_compile" for item in seen)
    assert any(item.get("running_capability") == "author.rulepack_generate" for item in seen)


def test_author_bundle_generates_beat_runtime_shards_in_deterministic_order_with_fallback_trace(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module
    from rpg_backend.author.beat_shards import deterministic_beat_runtime_shard

    original_worker = workflow_module.build_beat_runtime_shard_from_snapshot

    def _fake_worker(snapshot):
        if snapshot.beat_id == "b1":
            time.sleep(0.03)
        elif snapshot.beat_id == "b2":
            time.sleep(0.02)
        else:
            time.sleep(0.01)
        shard = deterministic_beat_runtime_shard(snapshot)
        if snapshot.beat_id == "b2":
            shard = shard.model_copy(update={"fallback_reason": "binding_scaffold_drift"})
            return shard, 7, ["binding_scaffold_drift"]
        return shard, 5, []

    monkeypatch.setattr(workflow_module, "build_beat_runtime_shard_from_snapshot", _fake_worker)

    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A harbor inspector must keep quarantine from turning into private rule."
        ),
        gateway=FakeGateway(),
    )

    assert result.state["bundle_snapshot"].snapshot_id
    assert len(result.state["beat_snapshots"]) == len(result.bundle.beat_spine)
    assert [item.beat_id for item in result.bundle.beat_runtime_shards] == [beat.beat_id for beat in result.bundle.beat_spine]
    fallback_shard = next(item for item in result.bundle.beat_runtime_shards if item.beat_id == "b2")
    assert fallback_shard.fallback_reason == "binding_scaffold_drift"
    assert result.state["beat_runtime_shard_fallback_count"] == 1
    assert result.state["beat_runtime_shard_drift_distribution"]["binding_scaffold_drift"] == 1
    assert any(
        item["stage"] == "beat_runtime_shard"
        and item["subject"] == "b2"
        and "beat_runtime_shard_fallback" in item["reasons"]
        and "binding_scaffold_drift" in item["reasons"]
        for item in result.state["quality_trace"]
    )


def test_author_graph_progress_observer_reports_route_fallback_details(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    monkeypatch.setattr(
        workflow_module,
        "get_character_roster_service",
        lambda: CharacterRosterService(
            enabled=False,
            catalog_version=None,
            catalog=(),
            embedding_provider=_StubEmbeddingProvider(),
            max_supporting_cast_selections=0,
        ),
    )
    seen: list[dict[str, object]] = []
    graph = build_author_graph(
        gateway=fallback_rulepack_gateway(),
        checkpointer=InMemorySaver(),
        progress_observer=lambda **payload: seen.append(payload),
    )
    graph.invoke(
        {
            "run_id": "run-route-fallback-progress",
            "raw_brief": "A civic fantasy about preserving trust during a blackout election.",
        },
        config=graph_config(run_id="run-route-fallback-progress"),
    )

    assert any(item.get("running_substage") == "route_generate" for item in seen)
    assert any(item.get("running_substage") == "route_default_fallback" for item in seen)


def test_author_graph_progress_observer_reports_ending_fallback_details(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    monkeypatch.setattr(
        workflow_module,
        "get_character_roster_service",
        lambda: CharacterRosterService(
            enabled=False,
            catalog_version=None,
            catalog=(),
            embedding_provider=_StubEmbeddingProvider(),
            max_supporting_cast_selections=0,
        ),
    )
    seen: list[dict[str, object]] = []
    graph = build_author_graph(
        gateway=fallback_ending_rules_gateway(),
        checkpointer=InMemorySaver(),
        progress_observer=lambda **payload: seen.append(payload),
    )
    graph.invoke(
        {
            "run_id": "run-ending-progress",
            "raw_brief": "A civic fantasy about preserving trust during a blackout election.",
        },
        config=graph_config(run_id="run-ending-progress"),
    )

    assert any(item.get("running_substage") == "ending_generate" for item in seen)
    assert any(item.get("running_substage") == "ending_default_fallback" for item in seen)
    assert any(item.get("running_capability") == "author.rulepack_generate" for item in seen)


def test_author_bundle_falls_back_when_cast_stage_budget_is_exhausted(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    monkeypatch.setattr(
        workflow_module,
        "get_character_roster_service",
        lambda: CharacterRosterService(
            enabled=False,
            catalog_version=None,
            catalog=(),
            embedding_provider=_StubEmbeddingProvider(),
            max_supporting_cast_selections=0,
        ),
    )
    monkeypatch.setattr(workflow_module, "_cast_stage_budget_seconds", lambda _state: 0.0)

    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=FakeGateway(),
    )

    assert len(result.bundle.story_bible.cast) == 4
    assert any(
        item["stage"] == "cast_member"
        and item["source"] == "default"
        and "cast_stage_budget_exhausted" in item["reasons"]
        for item in result.state["quality_trace"]
    )


def test_author_bundle_can_bind_three_supporting_roster_casts_when_limit_is_three(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    roster_service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=build_runtime_catalog(
            (
                _roster_source_entry(
                    character_id="roster_archive_certifier",
                    slug="archive-certifier",
                    name_en="Lin Verrow",
                    name_zh="林维若",
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier.png",
                    role_hint_en="Records certifier",
                    role_hint_zh="记录认证官",
                    slot_tags=["guardian", "anchor"],
                    setting_tags=["archive", "record", "hearing"],
                    conflict_tags=["public_record", "witness"],
                    retrieval_terms=["archive", "record", "certify", "witness", "hearing"],
                ),
                _roster_source_entry(
                    character_id="roster_courtyard_witness",
                    slug="courtyard-witness",
                    name_en="Pei Sorn",
                    name_zh="裴松",
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_courtyard_witness.png",
                    role_hint_en="Public witness",
                    role_hint_zh="公共见证人",
                    slot_tags=["witness", "civic"],
                    setting_tags=["archive", "council", "public_gallery"],
                    conflict_tags=["witness", "legitimacy"],
                    retrieval_terms=["witness", "public", "record", "council", "hearing"],
                ),
                _roster_source_entry(
                    character_id="roster_blackout_grid_broker",
                    slug="grid-broker",
                    name_en="Tarin Dusk",
                    name_zh="塔林·暮岚",
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_blackout_grid_broker.png",
                    role_hint_en="Grid broker",
                    role_hint_zh="电网掮客",
                    slot_tags=["broker", "civic"],
                    setting_tags=["blackout", "grid", "district"],
                    conflict_tags=["public_order", "resource", "legitimacy"],
                    retrieval_terms=["blackout", "grid", "district", "broker", "power"],
                ),
            )
        ).entries,
        embedding_provider=_StubEmbeddingProvider(),
        max_supporting_cast_selections=3,
    )
    monkeypatch.setattr(workflow_module, "get_character_roster_service", lambda: roster_service)

    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="During a blackout legitimacy hearing, a city archivist must restore one binding public record before rival factions weaponize sealed testimony."
        ),
        gateway=FakeGateway(),
    )

    roster_casts = [item for item in result.bundle.story_bible.cast if item.roster_character_id]
    assert len(roster_casts) == 3
    assert {item.roster_character_id for item in roster_casts} == {
        "roster_archive_certifier",
        "roster_courtyard_witness",
        "roster_blackout_grid_broker",
    }
    assert all(item.portrait_url for item in roster_casts)
    assert result.state["roster_retrieval_trace"]
    assert "query_language" in result.state["roster_retrieval_trace"][0]
    assert "story_query_text" in result.state["roster_retrieval_trace"][0]
    assert "slot_query_text" in result.state["roster_retrieval_trace"][0]
    assert "candidate_pool_size" in result.state["roster_retrieval_trace"][0]
    assert result.state["roster_retrieval_trace"][0]["selected_template_version"]


def test_author_bundle_materializes_story_instance_without_changing_name_or_portrait(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    roster_service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=build_runtime_catalog(
            (
                _roster_source_entry(
                    character_id="roster_archive_certifier",
                    slug="archive-certifier",
                    name_en="Lin Verrow",
                    name_zh="林维若",
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                    portrait_variants={
                        "negative": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/negative/current.png",
                        "neutral": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                        "positive": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/positive/current.png",
                    },
                    role_hint_en="Archive certifier",
                    role_hint_zh="档案认证官",
                    slot_tags=["guardian", "anchor"],
                    setting_tags=["archive", "record", "hearing"],
                    conflict_tags=["public_record", "witness"],
                    retrieval_terms=["archive", "record", "certify", "witness", "hearing"],
                ),
            )
        ).entries,
        embedding_provider=_StubEmbeddingProvider(),
        max_supporting_cast_selections=3,
    )
    monkeypatch.setattr(workflow_module, "get_character_roster_service", lambda: roster_service)

    gateway = gateway_with_overrides()

    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="An archive vote is drifting toward a false mandate unless the certification chain holds in public."
        ),
        gateway=gateway,
    )

    roster_cast = next(item for item in result.bundle.story_bible.cast if item.roster_character_id == "roster_archive_certifier")
    assert roster_cast.name == "Lin Verrow"
    assert roster_cast.portrait_url == "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png"
    assert roster_cast.template_version
    assert roster_cast.role
    assert roster_cast.agenda
    assert roster_cast.pressure_signature
    assert roster_cast.story_instance is not None
    assert roster_cast.story_instance.materialization_source == "default"
    assert not any(item["operation"] == "character_instance_variation" for item in gateway.call_trace)
    play_plan = compile_play_plan(story_id="story-instance-propagation", bundle=result.bundle)
    play_roster_cast = next(item for item in play_plan.cast if item.roster_character_id == "roster_archive_certifier")
    assert play_roster_cast.template_version == roster_cast.template_version
    assert play_roster_cast.story_instance == roster_cast.story_instance


def test_author_bundle_sanitizes_story_instance_gender_drift(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    roster_service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=build_runtime_catalog(
            (
                _roster_source_entry(
                    character_id="roster_archive_certifier",
                    slug="archive-certifier",
                    name_en="Lin Verrow",
                    name_zh="林维若",
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                    portrait_variants={
                        "negative": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/negative/current.png",
                        "neutral": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                        "positive": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/positive/current.png",
                    },
                    role_hint_en="Archive certifier",
                    role_hint_zh="档案认证官",
                    slot_tags=["guardian", "anchor"],
                    setting_tags=["archive", "record", "hearing"],
                    conflict_tags=["public_record", "witness"],
                    retrieval_terms=["archive", "record", "certify", "witness", "hearing"],
                ),
            )
        ).entries,
        embedding_provider=_StubEmbeddingProvider(),
        max_supporting_cast_selections=3,
    )
    monkeypatch.setattr(workflow_module, "get_character_roster_service", lambda: roster_service)

    gateway = gateway_with_overrides(
        character_instance_variation=repeated_gateway_error("llm_provider_failed"),
    )

    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="An archive vote is drifting toward a false mandate unless the certification chain holds in public."
        ),
        gateway=gateway,
    )

    roster_cast = next(item for item in result.bundle.story_bible.cast if item.roster_character_id == "roster_archive_certifier")
    assert roster_cast.role
    assert "she " not in roster_cast.agenda.casefold()
    assert "she " not in roster_cast.red_line.casefold()
    assert "she " not in roster_cast.pressure_signature.casefold()
    assert roster_cast.story_instance is not None
    assert roster_cast.story_instance.materialization_source == "default"
    assert not any(item["operation"] == "character_instance_variation" for item in gateway.call_trace)


def test_author_bundle_falls_back_when_story_instance_generation_provider_fails(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    roster_service = CharacterRosterService(
        enabled=True,
        catalog_version="v1",
        catalog=build_runtime_catalog(
            (
                _roster_source_entry(
                    character_id="roster_archive_certifier",
                    slug="archive-certifier",
                    name_en="Lin Verrow",
                    name_zh="林维若",
                    portrait_url="http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                    portrait_variants={
                        "negative": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/negative/current.png",
                        "neutral": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                        "positive": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/positive/current.png",
                    },
                    role_hint_en="Archive certifier",
                    role_hint_zh="档案认证官",
                    slot_tags=["guardian", "anchor"],
                    setting_tags=["archive", "record", "hearing"],
                    conflict_tags=["public_record", "witness"],
                    retrieval_terms=["archive", "record", "certify", "witness", "hearing"],
                ),
            )
        ).entries,
        embedding_provider=_StubEmbeddingProvider(),
        max_supporting_cast_selections=3,
    )
    monkeypatch.setattr(workflow_module, "get_character_roster_service", lambda: roster_service)

    gateway = gateway_with_overrides(
        character_instance_variation=repeated_gateway_error("llm_provider_failed"),
    )
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="An archive vote is drifting toward a false mandate unless the certification chain holds in public."
        ),
        gateway=gateway,
    )

    roster_cast = next(item for item in result.bundle.story_bible.cast if item.roster_character_id == "roster_archive_certifier")
    assert roster_cast.name == "Lin Verrow"
    assert roster_cast.portrait_url == "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png"
    assert roster_cast.story_instance is not None
    assert roster_cast.story_instance.materialization_source == "default"
    assert not any(item["operation"] == "character_instance_variation" for item in gateway.call_trace)
    assert "her " not in roster_cast.story_instance.instance_experience_summary.casefold()


def test_author_preview_can_be_built_from_cast_overview_partial_state() -> None:
    from rpg_backend.author.preview import build_author_preview_from_state
    from tests.author_fixtures import author_fixture_bundle

    fixture = author_fixture_bundle()
    preview = build_author_preview_from_state(
        preview_id="preview-partial",
        prompt_seed="A royal archivist must prove a buried warning is real before the city locks itself into denial.",
        state={
            "focused_brief": fixture.focused_brief,
            "primary_theme": "truth_record_crisis",
            "theme_modifiers": ["archive"],
            "theme_router_reason": "test",
            "story_frame_strategy": "warning_record_story",
            "cast_strategy": "warning_record_cast",
            "beat_plan_strategy": "warning_record_compile",
            "story_frame_draft": fixture.story_frame,
            "cast_overview_draft": fixture.cast_overview,
            "cast_topology": "four_slot",
        },
    )

    assert preview.stage == "cast_planned"
    assert preview.cast_slots
    assert all(slot.portrait_url is None for slot in preview.cast_slots)
    assert preview.structure.expected_npc_count >= 3
    assert preview.beats


def test_author_preview_enriches_cast_slots_once_concrete_cast_exists() -> None:
    from rpg_backend.author.preview import build_author_preview_from_state
    from tests.author_fixtures import author_fixture_bundle

    fixture = author_fixture_bundle()
    concrete_cast = list(fixture.design_bundle.story_bible.cast)
    concrete_cast[1] = concrete_cast[1].model_copy(
        update={
            "roster_character_id": "roster_archive_certifier",
            "roster_public_summary": "A records certifier trusted by no faction precisely because they have blocked all of them before.",
            "portrait_url": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
            "portrait_variants": {
                "negative": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/negative/current.png",
                "neutral": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/neutral/current.png",
                "positive": "http://127.0.0.1:8000/portraits/roster/roster_archive_certifier/positive/current.png",
            },
            "template_version": "tpl-archive-certifier-v1",
        }
    )
    preview = build_author_preview_from_state(
        preview_id="preview-concrete",
        prompt_seed="A royal archivist must prove a buried warning is real before the city locks itself into denial.",
        state={
            "focused_brief": fixture.focused_brief,
            "primary_theme": "truth_record_crisis",
            "theme_modifiers": ["archive"],
            "theme_router_reason": "test",
            "story_frame_strategy": "warning_record_story",
            "cast_strategy": "warning_record_cast",
            "beat_plan_strategy": "warning_record_compile",
            "story_frame_draft": fixture.story_frame,
            "cast_overview_draft": fixture.cast_overview,
            "cast_draft": fixture.cast_draft.model_copy(update={"cast": concrete_cast}),
            "cast_topology": "four_slot",
        },
    )

    assert preview.stage == "cast_ready"
    assert preview.cast_slots
    assert preview.cast_slots[1].npc_id == concrete_cast[1].npc_id
    assert preview.cast_slots[1].name == concrete_cast[1].name
    assert preview.cast_slots[1].portrait_url == concrete_cast[1].portrait_url
    assert preview.cast_slots[1].portrait_variants is not None
    assert preview.cast_slots[1].portrait_variants.model_dump(mode="json") == concrete_cast[1].portrait_variants
    assert preview.cast_slots[1].template_version == "tpl-archive-certifier-v1"


def test_author_bundle_falls_back_to_default_rulepack_when_rulepack_payload_is_malformed() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=fallback_rulepack_gateway(),
    )

    assert result.bundle.rule_pack.ending_rules


def test_author_bundle_duration_controls_change_story_flow_shape() -> None:
    short = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A harbor inspector must keep quarantine from turning into private rule.",
            target_duration_minutes=10,
        ),
        gateway=FakeGateway(),
    )
    long = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A harbor inspector must keep quarantine from turning into private rule.",
            target_duration_minutes=25,
        ),
        gateway=FakeGateway(),
    )

    short_plan = compile_play_plan(story_id="story-short", bundle=short.bundle)
    long_plan = compile_play_plan(story_id="story-long", bundle=long.bundle)

    assert short.bundle.story_flow_plan.target_duration_minutes == 10
    assert short.bundle.story_flow_plan.branch_budget == "low"
    assert len(short.bundle.beat_spine) == 2
    assert [beat.progress_required for beat in short.bundle.beat_spine] == [2, 2]
    assert short_plan.max_turns == 4

    assert long.bundle.story_flow_plan.target_duration_minutes == 25
    assert long.bundle.story_flow_plan.branch_budget == "high"
    assert len(long.bundle.beat_spine) == 5
    assert [beat.progress_required for beat in long.bundle.beat_spine] == [2, 2, 2, 2, 2]
    assert len(long.bundle.story_bible.cast) == 5
    assert long.state["cast_topology"] == "five_slot"
    assert len(long.bundle.rule_pack.route_unlock_rules) >= len(short.bundle.rule_pack.route_unlock_rules)
    assert long_plan.max_turns == 10
    assert long_plan.minimum_resolution_turn == 7


def test_author_bundle_preserves_specific_story_frame_strategy_family_when_story_theme_drifts(monkeypatch) -> None:
    import rpg_backend.author.workflow as workflow_module

    bridge_decision = AuthorThemeDecision(
        primary_theme="logistics_quarantine_crisis",
        modifiers=("harbor", "infrastructure"),
        router_reason="matched_story_bridge_ration_keywords",
        story_frame_strategy="bridge_ration_story",
        cast_strategy="bridge_ration_cast",
        beat_plan_strategy="bridge_ration_compile",
    )
    monkeypatch.setattr(workflow_module, "plan_story_theme", lambda *_args, **_kwargs: bridge_decision)

    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A harbor inspector must keep quarantine from turning into private rule.",
            target_duration_minutes=10,
        ),
        gateway=FakeGateway(),
    )

    assert result.state["story_frame_strategy"] == "harbor_quarantine_story"
    assert result.state["cast_strategy"] == "harbor_quarantine_cast"
    assert result.state["beat_plan_strategy"] == "harbor_quarantine_compile"


def test_author_bundle_warning_record_short_lane_does_not_raise_on_beat_plan_repair() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="When a river warning is buried to protect a council vote, a records magistrate must prove the threat is real before courtiers rewrite the public story.",
            target_duration_minutes=10,
        ),
        gateway=FakeGateway(),
    )

    assert result.bundle.beat_spine
    assert result.state["story_frame_strategy"] == "warning_record_story"
    assert result.state["cast_strategy"] == "warning_record_cast"
    assert result.state["beat_plan_strategy"] == "warning_record_compile"


def test_author_bundle_tone_controls_reshape_style_without_changing_runtime_lane() -> None:
    base = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A records examiner must restore one public record before the vote hardens."
        ),
        gateway=FakeGateway(),
    )
    guided = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A records examiner must restore one public record before the vote hardens.",
            tone_direction="Measured institutional melancholy with visible public cost.",
            tone_focus="public_ethics",
            prose_style="restrained",
        ),
        gateway=FakeGateway(),
    )

    base_plan = compile_play_plan(story_id="story-base-tone", bundle=base.bundle)
    guided_plan = compile_play_plan(story_id="story-guided-tone", bundle=guided.bundle)

    assert guided.bundle.story_bible.tone == "Measured institutional melancholy with visible public cost."
    assert guided.bundle.story_bible.style_guard != base.bundle.story_bible.style_guard
    assert guided.bundle.story_bible.cast[0].pressure_signature != base.bundle.story_bible.cast[0].pressure_signature
    assert guided.bundle.beat_spine[0].goal != base.bundle.beat_spine[0].goal
    assert guided_plan.runtime_policy_profile == base_plan.runtime_policy_profile
    assert guided_plan.closeout_profile == base_plan.closeout_profile


def test_author_bundle_falls_back_to_default_endings_when_ending_payload_is_malformed() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=fallback_ending_rules_gateway(),
    )

    assert result.bundle.rule_pack.ending_rules
    assert {item.ending_id for item in result.bundle.rule_pack.ending_rules} == {"collapse", "pyrrhic", "mixed"}
    assert result.state["ending_source"] == "default"
    assert any(
        item["stage"] == "ending"
        and item["source"] == "default"
        and item["outcome"] == "fallback"
        and "llm_invalid_json" in item["reasons"]
        for item in result.state["quality_trace"]
    )


def test_author_bundle_canonicalizes_noncanonical_ending_priorities() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=noncanonical_ending_priority_gateway(),
    )

    assert [(item.ending_id, item.priority) for item in result.bundle.rule_pack.ending_rules] == [
        ("collapse", 1),
        ("pyrrhic", 2),
        ("mixed", 10),
    ]


def test_author_bundle_replaces_low_quality_route_opportunities_with_default_routes() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=low_quality_route_opportunities_gateway(),
    )

    assert len(result.bundle.rule_pack.route_unlock_rules) >= 2
    assert len({item.beat_id for item in result.bundle.rule_pack.route_unlock_rules}) >= 2


def test_author_bundle_supplements_narrow_route_diversity() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=narrow_route_diversity_gateway(),
    )

    assert len({item.beat_id for item in result.bundle.rule_pack.route_unlock_rules}) >= 2
    assert len({item.unlock_affordance_tag for item in result.bundle.rule_pack.route_unlock_rules}) >= 2


def test_author_bundle_replaces_low_quality_story_frame_with_default_story_frame() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=LowQualityStoryFrameGateway(),
    )

    assert result.bundle.story_bible.premise.startswith("In ")
    assert "player fails" not in result.bundle.story_bible.stakes.casefold()
    assert result.state["story_frame_source"] == "default"
    assert any(
        item["stage"] == "story_frame"
        and item["source"] == "default"
        and item["outcome"] == "fallback"
        and item["reasons"]
        for item in result.state["quality_trace"]
    )


def test_author_bundle_recovers_low_quality_story_frame_via_glean() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=RecoveringStoryFrameGateway(),
    )

    assert result.bundle.story_bible.title == "The Archive Blackout"
    assert result.state["story_frame_source"] == "gleaned"
    assert any(
        item["stage"] == "story_frame"
        and item["source"] == "gleaned"
        and item["outcome"] == "repaired"
        and item["reasons"]
        for item in result.state["quality_trace"]
    )


def test_author_bundle_falls_back_to_default_beats_when_payload_is_malformed() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=fallback_beat_plan_gateway(),
    )

    assert result.state["beat_plan_source"] == "default"
    assert len(result.bundle.beat_spine) >= 2
    assert any(
        item["stage"] == "beat_plan"
        and item["source"] == "default"
        and item["outcome"] == "fallback"
        and "llm_invalid_json" in item["reasons"]
        for item in result.state["quality_trace"]
    )


def test_author_bundle_falls_back_to_default_beats_when_provider_fails() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=gateway_with_overrides(beat_plan_generate=repeated_gateway_error("llm_provider_failed")),
    )

    assert result.state["beat_plan_source"] == "default"
    assert len(result.bundle.beat_spine) >= 2
    assert any(
        item["stage"] == "beat_plan"
        and item["source"] == "default"
        and item["outcome"] == "fallback"
        and "llm_provider_failed" in item["reasons"]
        for item in result.state["quality_trace"]
    )


def test_author_bundle_repairs_generic_cast_fields_without_dropping_named_characters() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=generic_cast_gateway(),
    )

    cast = result.bundle.story_bible.cast
    assert result.state["cast_strategy"] == "legitimacy_cast"
    assert [item.name for item in cast] == ["Mira Vale", "Teren Vale", "Soren Pike", "Lena Sorn"]
    assert [item.roster_character_id for item in cast] == [
        None,
        "roster_legitimacy_charter_envoy",
        "roster_legitimacy_compact_broker",
        "roster_legitimacy_oath_witness",
    ]
    assert all("preserve their role in the crisis" not in item.agenda.casefold() for item in cast)
    assert all("pressure threatens public order" not in item.pressure_signature.casefold() for item in cast)


def test_author_bundle_replaces_placeholder_cast_with_default_cast() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=placeholder_cast_gateway(),
    )

    cast_names = [item.name for item in result.bundle.story_bible.cast]
    assert cast_names != ["Mediator Anchor", "Archive Guardian", "Coalition Rival"]
    assert all(not name.startswith("Civic Figure ") for name in cast_names)
    assert all(" " in name for name in cast_names)


def test_author_bundle_falls_back_to_default_overview_when_overview_payload_is_malformed() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A civic fantasy about preserving trust during a blackout election."
        ),
        gateway=fallback_overview_gateway(),
    )

    assert result.bundle.story_bible.title
    assert result.bundle.beat_spine


def test_author_graph_records_gameplay_semantics_stage_in_quality_trace() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A harbor inspector must keep the dock coalition alive after missing manifests threaten emergency rule during quarantine."
        ),
        gateway=FakeGateway(),
    )

    assert result.state["gameplay_semantics_source"] in {"accepted", "repaired"}
    assert any(item["stage"] == "gameplay_semantics" for item in result.state["quality_trace"])


def test_author_bundle_repairs_overcollapsed_gameplay_semantics_profiles() -> None:
    result = run_author_bundle(
        AuthorBundleRequest(
            raw_brief="A royal archivist must prove a buried storm warning is real before the capital locks itself into denial."
        ),
        gateway=FakeGateway(),
    )

    pressure_axes = {
        axis_id
        for profile in result.bundle.rule_pack.affordance_effect_profiles
        for axis_id, delta in profile.axis_deltas.items()
        if delta > 0
    }

    assert len(pressure_axes) >= 2

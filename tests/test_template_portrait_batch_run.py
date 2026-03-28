from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tools.template_portrait_batch_run import run_batch
from tools.template_portrait_review_sheet import build_review_sheet


def test_template_batch_runner_can_build_single_template_trial(monkeypatch, tmp_path) -> None:
    plan_calls: list[dict[str, object]] = []

    def fake_build_job_matrix(**kwargs):  # noqa: ANN003
        plan_calls.append(kwargs)
        return SimpleNamespace(
            batch_id="portrait_batch_test",
            prompt_version="v1_editorial_dossier",
            image_model="gemini-3.1-flash-image-preview",
            image_api_base_url="https://vip.123everything.com",
            output_dir=str(Path(kwargs["output_dir"]).resolve()),
            jobs=(
                SimpleNamespace(
                    asset_id="asset_a",
                    character_id=kwargs["character_ids"][0],
                    variant_key="negative",
                    candidate_index=1,
                    prompt_text="prompt",
                    prompt_hash="hash",
                    relative_output_path=f"{kwargs['character_ids'][0]}/negative/asset_a.png",
                ),
            ),
            to_payload=lambda: {
                "batch_id": "portrait_batch_test",
                "prompt_version": "v1_editorial_dossier",
                "image_model": "gemini-3.1-flash-image-preview",
                "image_api_base_url": "https://vip.123everything.com",
                "output_dir": str(Path(kwargs["output_dir"]).resolve()),
                "jobs": [
                    {
                        "asset_id": "asset_a",
                        "character_id": kwargs["character_ids"][0],
                        "variant_key": "negative",
                        "candidate_index": 1,
                        "prompt_text": "prompt",
                        "prompt_hash": "hash",
                        "relative_output_path": f"{kwargs['character_ids'][0]}/negative/asset_a.png",
                    }
                ],
            },
        )

    monkeypatch.setattr("tools.template_portrait_batch_run._load_env_value", lambda name: "test-key" if name == "PORTRAIT_IMAGE_API_KEY" else None)
    monkeypatch.setattr("tools.template_portrait_batch_run.build_job_matrix", fake_build_job_matrix)
    monkeypatch.setattr(
        "tools.template_portrait_batch_run.run_generation",
        lambda args: {
            "generated_count": 1,
            "generated_files": [str(Path(args.plan_path).with_suffix(".png"))],
        },
    )

    payload = run_batch(
        SimpleNamespace(
            cast_pack_path="artifacts/portraits/cast_content/template_aligned_cast_pack_30_v2.json",
            trials_root=str(tmp_path / "trials"),
            templates=["blackout_referendum_story"],
            skip_templates=[],
            candidates_per_variant=1,
            request_timeout_seconds=30.0,
            api_key=None,
        )
    )

    assert payload["template_count"] == 1
    assert payload["generated_count"] == 1
    assert payload["template_results"][0]["template_name"] == "blackout_referendum_story"
    assert Path(payload["template_results"][0]["plan_path"]).name == "portrait_plan.json"
    assert plan_calls[0]["character_ids"] == (
        "roster_blackout_tally_registrar",
        "roster_blackout_ward_delegate",
        "roster_blackout_grid_compact_broker",
    )


def test_review_sheet_lists_assets_and_screening_fields(tmp_path) -> None:
    trials_root = tmp_path / "trials"
    template_dir = trials_root / "archive_vote_story"
    template_dir.mkdir(parents=True, exist_ok=True)
    plan_payload = {
        "batch_id": "portrait_batch_test",
        "prompt_version": "v1_editorial_dossier",
        "image_model": "gemini-3.1-flash-image-preview",
        "image_api_base_url": "https://vip.123everything.com",
        "output_dir": str(template_dir.resolve()),
        "jobs": [
            {
                "asset_id": "asset_a",
                "character_id": "roster_archive_vote_certifier",
                "variant_key": "negative",
                "candidate_index": 1,
                "prompt_text": "prompt",
                "prompt_hash": "hash",
                "relative_output_path": "roster_archive_vote_certifier/negative/asset_a.png",
            }
        ],
    }
    (template_dir / "portrait_plan.json").write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    screening_path = tmp_path / "screening.json"
    screening_path.write_text(
        json.dumps(
            {
                "archive_vote_story": {
                    "trio_summary": "The trio is readable overall; the certifier is strongest while the petitioner needs expression review.",
                    "asset_a": {
                        "template_fit": "pass",
                        "role_distinctness": "watch",
                        "silhouette_readability": "pass",
                        "face_crop_safety": "pass",
                        "style_lock_match": "pass",
                        "expression_match": "watch",
                        "overall_recommendation": "keep",
                        "initial_screening_note": "Readable role and crop, but expression shift is modest.",
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    content = build_review_sheet(
        SimpleNamespace(
            cast_pack_path="artifacts/portraits/cast_content/template_aligned_cast_pack_30_v2.json",
            trials_root=str(trials_root),
            output_path=str(tmp_path / "review_sheet.md"),
            screening_json=str(screening_path),
        )
    )

    assert "## `archive_vote_story`" in content
    assert "`asset_id`" not in content
    assert "asset_a" in content
    assert "`template_fit`: `pass`" in content
    assert "`overall_recommendation`: `keep`" in content
    assert "Readable role and crop" in content
    assert "The trio is readable overall" in content
    assert "ui_agent_notes" in content

from __future__ import annotations

import pytest

import rpg_backend.narrative.service as narrative_service_module
from rpg_backend.narrative.contracts import CreateTemplateRequest
from rpg_backend.narrative.repository import NarrativeRepository
from rpg_backend.narrative.service import NarrativeService, NarrativeServiceError


def test_create_template_surfaces_small_cast_prompt_shape_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_generate_opening(**_: object) -> object:
        raise ValueError("cast too small after sanitization: 1")

    monkeypatch.setattr(narrative_service_module, "generate_opening", fake_generate_opening)
    repo = NarrativeRepository(str(tmp_path / "runtime.sqlite3"))
    service = NarrativeService(repository=repo, gateway=object())  # type: ignore[arg-type]

    with pytest.raises(NarrativeServiceError) as exc_info:
        service.create_template(
            CreateTemplateRequest(seed="A quiet laundromat ring goes missing."),
            owner_user_id="usr_test",
        )

    assert exc_info.value.code == "opening_prompt_shape_mismatch"
    assert exc_info.value.status_code == 422
    assert "3+ people" in exc_info.value.message

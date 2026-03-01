from app.llm.fake_provider import FakeProvider


def test_fake_provider_matches_keywords() -> None:
    provider = FakeProvider()
    result = provider.route_intent(
        {
            "moves": [
                {"id": "scan_signal", "label": "Scan", "intents": ["scan"], "synonyms": ["signal"]},
                {"id": "global.clarify", "label": "Clarify", "intents": ["global.clarify"], "synonyms": ["ask"]},
            ],
            "fallback_move": "global.help_me_progress",
        },
        "I want to scan the signal",
    )
    assert result.move_id == "scan_signal"
    assert result.confidence >= 0.55


def test_fake_provider_falls_back_on_gibberish() -> None:
    provider = FakeProvider()
    result = provider.route_intent(
        {
            "moves": [
                {"id": "scan_signal", "label": "Scan", "intents": ["scan"], "synonyms": ["signal"]},
            ],
            "fallback_move": "global.help_me_progress",
        },
        "@@@### ???",
    )
    assert result.move_id == "global.help_me_progress"
    assert result.confidence < 0.55

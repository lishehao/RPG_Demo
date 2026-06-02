from __future__ import annotations

from tools.rpg_eval.contracts import EvalCase, EvalOracleConfig, EvalPlayerPolicy


def default_player_policies() -> list[EvalPlayerPolicy]:
    return [
        EvalPlayerPolicy(
            policy_id="power_optimizer",
            label="Power Optimizer",
            objective="Maximize visible control, status, and leverage.",
            risk_bias="medium",
        ),
        EvalPlayerPolicy(
            policy_id="truth_revealer",
            label="Truth Revealer",
            objective="Push secrets into public view as early as possible.",
            risk_bias="high",
        ),
        EvalPlayerPolicy(
            policy_id="relationship_loyalist",
            label="Relationship Loyalist",
            objective="Protect one important NPC relationship even at material cost.",
            risk_bias="medium",
        ),
        EvalPlayerPolicy(
            policy_id="chaos_escalator",
            label="Chaos Escalator",
            objective="Choose public, irreversible, high-pressure actions.",
            risk_bias="high",
        ),
        EvalPlayerPolicy(
            policy_id="cautious_survivor",
            label="Cautious Survivor",
            objective="Avoid irreversible exposure until forced by the story state.",
            risk_bias="low",
        ),
    ]


def default_case_catalog() -> list[EvalCase]:
    return [
        EvalCase(
            case_id="wealth_public_heir_short",
            seed="豪门家宴开席前，私生证据、旧爱和继承协议一起被推到主桌上。做成短局，必须有公开站队和不可逆代价。",
            expected_shells=["wealth_families"],
            play_length="short",
            required_affordances=["public_reveal", "relationship_tradeoff", "irreversible_cost"],
            oracle=EvalOracleConfig(
                min_turns=6,
                min_distinct_endings=2,
                min_state_divergence=0.35,
                required_state_keys=["public_pressure", "protagonist_control", "relationship_stance"],
            ),
        ),
        EvalCase(
            case_id="entertainment_live_scandal_short",
            seed="颁奖礼直播前，偷拍视频、假情侣营销和旧绯闻对象同时逼女主表态。做成短局，选择必须影响热搜和关系结局。",
            expected_shells=["entertainment_scandal"],
            play_length="short",
            required_affordances=["camera_pressure", "public_reveal", "reputation_cost"],
            oracle=EvalOracleConfig(
                min_turns=6,
                min_distinct_endings=2,
                min_state_divergence=0.35,
                required_state_keys=["public_pressure", "reputation", "relationship_stance"],
            ),
        ),
        EvalCase(
            case_id="office_merger_blackmail_short",
            seed="并购发布会前夜，上司、法务和竞争对手把黑账录音交到女主手里。做成短局，必须能选择保职位、保真相或保关系。",
            expected_shells=["office_power"],
            play_length="short",
            required_affordances=["career_tradeoff", "public_reveal", "relationship_tradeoff"],
            oracle=EvalOracleConfig(
                min_turns=6,
                min_distinct_endings=2,
                min_state_divergence=0.35,
                required_state_keys=["career_security", "public_pressure", "relationship_stance"],
            ),
        ),
    ]

from __future__ import annotations


PUBLIC_STAGE_FLOW = [
    ("focus_brief", "brief_parsed"),
    ("plan_brief_theme", "brief_classified"),
    ("generate_story_frame", "story_frame_ready"),
    ("plan_story_theme", "theme_confirmed"),
    ("derive_cast_overview", "cast_planned"),
    ("generate_cast_members", "cast_ready"),
    ("generate_beat_plan", "beat_plan_ready"),
    ("compile_route_affordance_pack", "route_ready"),
    ("generate_ending_rules", "ending_ready"),
    ("merge_rule_pack", "completed"),
]

STAGE_INDEX_BY_NODE = {
    node_name: index + 1
    for index, (node_name, _public_stage) in enumerate(PUBLIC_STAGE_FLOW)
}

PUBLIC_STAGE_BY_NODE = {
    node_name: public_stage
    for node_name, public_stage in PUBLIC_STAGE_FLOW
}

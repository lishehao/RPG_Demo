from __future__ import annotations

from dataclasses import dataclass

from rpg_backend.content_language import is_chinese_language, localized_text
from rpg_backend.author.contracts import (
    CastDraft,
    CastMemberSemanticsDraft,
    CastOverviewDraft,
    CastOverviewSlotDraft,
    FocusedBrief,
    OverviewCastDraft,
    StoryFrameDraft,
)
from rpg_backend.author.normalize import normalize_whitespace, slugify, trim_ellipsis


CAST_ARCHETYPE_LIBRARY: dict[str, dict[str, str]] = {
    "civic_mediator": {
        "slot_label": "Mediator Anchor",
        "public_role": "Mediator",
        "agenda_anchor": "Keep the emergency process legitimate long enough to stop the city from splintering.",
        "red_line_anchor": "Will not let emergency pressure erase public consent.",
        "pressure_vector": "Starts bridging hostile sides before every guarantee is secured.",
        "counter_trait": "idealistic in public, quietly controlling in execution",
        "pressure_tell": "Speaks faster, narrows the options, and starts counting who is still willing to stay in the room.",
        "name_bucket": "protagonist",
    },
    "harbor_inspector": {
        "slot_label": "Mediator Anchor",
        "public_role": "Harbor inspector",
        "agenda_anchor": "Keep the quarantine process enforceable without letting trade politics tear the harbor apart.",
        "red_line_anchor": "Will not let emergency decrees turn into unaccountable seizure.",
        "pressure_vector": "Treats every procedural gap as a point where panic and smuggling can rush in together.",
        "counter_trait": "methodical in public, personally restless under delay",
        "pressure_tell": "Starts inspecting details out loud and turning vague claims into hard checkpoints.",
        "name_bucket": "protagonist",
    },
    "bridge_engineer": {
        "slot_label": "Mediator Anchor",
        "public_role": "Bridge engineer",
        "agenda_anchor": "Keep the crossings operable without letting ration panic break the city into hostile districts.",
        "red_line_anchor": "Will not let emergency engineering authority become a pretext for political seizure.",
        "pressure_vector": "Treats every damaged crossing and forged count as a pressure point that can split the wards apart.",
        "counter_trait": "publicly measured, privately obsessed with weak links and countdowns",
        "pressure_tell": "Starts naming load limits, breakpoints, and closure windows until the room has to confront material constraints.",
        "name_bucket": "protagonist",
    },
    "record_examiner": {
        "slot_label": "Mediator Anchor",
        "public_role": "Records examiner",
        "agenda_anchor": "Keep the official record credible long enough to stop a false result from hardening into law.",
        "red_line_anchor": "Will not let certification move forward on evidence they know has been altered.",
        "pressure_vector": "Turns every procedural shortcut into a question of who benefits once the record becomes irreversible.",
        "counter_trait": "publicly restrained, privately relentless once chain-of-custody starts to wobble",
        "pressure_tell": "Starts reducing grand claims to timestamps, signatures, and who touched the record last.",
        "name_bucket": "protagonist",
    },
    "ward_coordinator": {
        "slot_label": "Mediator Anchor",
        "public_role": "Ward coordinator",
        "agenda_anchor": "Keep the neighborhoods inside one shared emergency process before outage panic turns into mutual blame.",
        "red_line_anchor": "Will not let blackout improvisation replace public accountability.",
        "pressure_vector": "Treats rumor spikes and local panic as signs that civic procedure is already starting to break apart.",
        "counter_trait": "publicly conciliatory, privately ruthless about stopping spiral dynamics early",
        "pressure_tell": "Starts narrowing the room toward concrete commitments before panic can multiply into factional stories.",
        "name_bucket": "protagonist",
    },
    "archive_guardian": {
        "slot_label": "Institutional Guardian",
        "public_role": "Archive authority",
        "agenda_anchor": "Preserve the institutions and procedures that still make the city governable.",
        "red_line_anchor": "Will not surrender formal authority without a visible procedural reason.",
        "pressure_vector": "Tightens procedure whenever panic, blame, or uncertainty starts to spread.",
        "counter_trait": "severe in public, privately protective of what would be lost",
        "pressure_tell": "Repeats the rules more precisely as the room gets louder and closes off informal exits.",
        "name_bucket": "guardian",
    },
    "port_guardian": {
        "slot_label": "Institutional Guardian",
        "public_role": "Port authority",
        "agenda_anchor": "Keep the harbor operating under rules that still look legitimate to frightened citizens and traders.",
        "red_line_anchor": "Will not let emergency traffic control become private leverage for one faction.",
        "pressure_vector": "Locks movement, paperwork, and access down tighter every time panic jumps a level.",
        "counter_trait": "rigid in public, quietly terrified of systemic collapse",
        "pressure_tell": "Starts reciting manifests, quotas, and access thresholds like a shield against chaos.",
        "name_bucket": "guardian",
    },
    "leverage_broker": {
        "slot_label": "Leverage Broker",
        "public_role": "Political rival",
        "agenda_anchor": "Turn the crisis into leverage over who controls the settlement that comes after it.",
        "red_line_anchor": "Will not accept exclusion from the final settlement.",
        "pressure_vector": "Treats every emergency as proof that someone else should lose authority.",
        "counter_trait": "calculating in public, needy about irrelevance underneath",
        "pressure_tell": "Reframes every setback as evidence that the balance of power must change immediately.",
        "name_bucket": "rival",
    },
    "trade_bloc_rival": {
        "slot_label": "Leverage Broker",
        "public_role": "Trade bloc rival",
        "agenda_anchor": "Convert quarantine chaos into bargaining power over who controls shipping, credit, and recovery.",
        "red_line_anchor": "Will not let the harbor reopen on terms that leave their bloc weakened.",
        "pressure_vector": "Turns every supply shock into a negotiation over power rather than relief.",
        "counter_trait": "polished in public, vengeful about being sidelined",
        "pressure_tell": "Starts offering practical help that always arrives tied to a new concession.",
        "name_bucket": "rival",
    },
    "public_witness": {
        "slot_label": "Civic Witness",
        "public_role": "Public advocate",
        "agenda_anchor": "Force the crisis response to remain publicly accountable while pressure keeps rising.",
        "red_line_anchor": "Will not let elite procedure erase the public record of what happened.",
        "pressure_vector": "Turns ambiguity, secrecy, or procedural drift into public scrutiny.",
        "counter_trait": "morally direct in public, emotionally stubborn in private",
        "pressure_tell": "Stops accepting closed-room assurances and demands that someone say the cost aloud.",
        "name_bucket": "witness",
    },
    "dock_delegate": {
        "slot_label": "Civic Witness",
        "public_role": "Dock delegate",
        "agenda_anchor": "Keep working crews and neighborhood residents from paying for elite quarantine bargains they never approved.",
        "red_line_anchor": "Will not let emergency port rules bury who benefited and who got stranded.",
        "pressure_vector": "Turns private deals into dockside rumors and then into organized pressure.",
        "counter_trait": "plainspoken in public, deeply strategic about crowd mood",
        "pressure_tell": "Starts naming names, losses, and delays until the room can no longer hide behind abstractions.",
        "name_bucket": "witness",
    },
    "resource_steward": {
        "slot_label": "Material Steward",
        "public_role": "Relief steward",
        "agenda_anchor": "Keep relief channels materially workable after the speeches end and the real costs come due.",
        "red_line_anchor": "Will not let a public settlement stand if no one has said how the city will actually carry it.",
        "pressure_vector": "Turns every civic promise into a question of supply, labor, upkeep, and who is really paying.",
        "counter_trait": "practical in public, quietly relentless about hidden cost transfer",
        "pressure_tell": "Starts itemizing shortages, staffing gaps, and deferred repairs until the room has to price its own promises.",
        "name_bucket": "witness",
    },
}

CAST_RELATIONSHIP_DYNAMIC_LIBRARY: dict[str, str] = {
    "protagonist_bears_public_weight": "The protagonist stands inside the crisis rather than above it, so every compromise lands as a public burden they personally own.",
    "improvisation_vs_procedure": "This figure needs the protagonist's flexibility but distrusts improvisation once legitimacy is already under strain.",
    "settlement_vs_leverage": "This figure tests whether the protagonist can stabilize the crisis without conceding who gets power after it.",
    "public_record_vs_private_bargain": "This figure turns private bargains into public accountability whenever the room starts deciding too much in secret.",
    "material_cost_vs_public_order": "This figure forces the protagonist to translate every public promise into material delivery, maintenance, and who will actually bear the cost.",
}

CAST_RELATIONSHIP_DYNAMIC_LIBRARY_ZH: dict[str, str] = {
    "protagonist_bears_public_weight": "主角并不站在危机之外，而是身处其内，所以每一次妥协都会变成他们必须亲自承担的公共负担。",
    "improvisation_vs_procedure": "这个角色需要主角的灵活性，却不相信在公信力已经承压时还能继续靠临场应变撑过去。",
    "settlement_vs_leverage": "这个角色会不断试探主角：究竟能不能在不让出权力分配的前提下稳住局势。",
    "public_record_vs_private_bargain": "一旦房间里开始想在私下决定太多事情，这个角色就会把私下交易重新拽回公共问责之中。",
    "material_cost_vs_public_order": "这个角色会逼主角把每一项公共承诺翻译成真正的供给、维护与买单对象。",
}

_CAST_ARCHETYPE_TRANSLATIONS_ZH: dict[str, dict[str, str]] = {
    "civic_mediator": {
        "slot_label": "调停锚点",
        "public_role": "调停者",
        "agenda_anchor": "维持紧急程序的正当性，直到城市不再继续裂开。",
        "red_line_anchor": "不会让紧急压力抹去公众同意。",
        "pressure_vector": "会在每一项保障都还没到位前，就先试着把敌对双方重新拉回同一张桌子。",
        "counter_trait": "公开场合偏理想主义，执行时却带着安静的控制欲",
        "pressure_tell": "一旦压力升高，说话会更快，选项会更少，也会开始盘点还有谁愿意留在房间里。",
    },
    "harbor_inspector": {
        "slot_label": "调停锚点",
        "public_role": "港务检察官",
        "agenda_anchor": "在不让贸易政治撕裂港口的前提下，让检疫程序继续可执行。",
        "red_line_anchor": "不会让紧急法令变成无人负责的夺取行为。",
        "pressure_vector": "会把每一个程序缺口都看成恐慌与走私一起灌进来的入口。",
        "counter_trait": "公开场合一丝不苟，私下里却被拖延折磨得焦躁不安",
        "pressure_tell": "会开始把细节逐条念出来，把模糊说法压成一个个硬检查点。",
    },
    "bridge_engineer": {
        "slot_label": "调停锚点",
        "public_role": "桥务工程官",
        "agenda_anchor": "在不让配给恐慌撕裂街区的前提下，让桥线与调度程序继续运转。",
        "red_line_anchor": "不会让紧急工程权变成政治夺取的借口。",
        "pressure_vector": "会把每一处受损桥线和异常台账都看成足以把上下游街区彻底扯开的断点。",
        "counter_trait": "公开场合克制冷静，私下里却对结构弱点和倒计时近乎偏执",
        "pressure_tell": "会开始不断报出承载上限、失稳节点和封桥窗口，逼着所有人正视物理约束。",
    },
    "record_examiner": {
        "slot_label": "调停锚点",
        "public_role": "档案核验官",
        "agenda_anchor": "在虚假结果被写成定局前，守住官方记录的可信度。",
        "red_line_anchor": "不会让认证程序在明知证据被改写的情况下继续推进。",
        "pressure_vector": "会把每一次程序抄近路都改写成“谁会从不可逆记录里获利”的问题。",
        "counter_trait": "公开场合克制寡言，一旦链条开始摇晃就会变得异常执拗",
        "pressure_tell": "会把宏大说辞一条条压回时间戳、签名和最后接触记录的人。",
    },
    "ward_coordinator": {
        "slot_label": "调停锚点",
        "public_role": "社区协调员",
        "agenda_anchor": "在停电恐慌变成互相甩锅前，把几个街区继续拴在同一套紧急程序里。",
        "red_line_anchor": "不会让停电时的临时应对取代公共问责。",
        "pressure_vector": "会把流言上升和街区恐慌都当成程序已经开始解体的征兆。",
        "counter_trait": "公开场合愿意协调让步，私下里却对阻断失控连锁反应非常强硬",
        "pressure_tell": "会在恐慌扩散前把房间迅速压缩到少数几个必须立刻兑现的承诺上。",
    },
    "archive_guardian": {
        "slot_label": "制度守门人",
        "public_role": "档案机构负责人",
        "agenda_anchor": "守住仍然让这座城市可以被治理的制度与程序。",
        "red_line_anchor": "没有公开可见的程序理由，就不会让出正式权威。",
        "pressure_vector": "一旦恐慌、甩锅或不确定蔓延，就会把程序再收紧一层。",
        "counter_trait": "公开场合严厉冷硬，私下里却极度在意那些正在流失的东西",
        "pressure_tell": "随着房间越来越嘈杂，会把规则念得更细，也会把非正式出口一个个堵死。",
    },
    "port_guardian": {
        "slot_label": "制度守门人",
        "public_role": "港务机构负责人",
        "agenda_anchor": "在让市民与商人都还能相信的规则下，维持港口继续运转。",
        "red_line_anchor": "不会让紧急交通管制变成某一派的私人筹码。",
        "pressure_vector": "每当恐慌再升一级，就会把流动、手续与准入条件再锁紧一层。",
        "counter_trait": "公开场合僵硬强硬，私下里却对系统性崩塌怀着真实恐惧",
        "pressure_tell": "会把舱单、配额和准入阈值一条条背出来，仿佛那是对抗混乱的盾牌。",
    },
    "leverage_broker": {
        "slot_label": "筹码经纪人",
        "public_role": "政治对手",
        "agenda_anchor": "把危机变成筹码，改写危机之后谁来主导结算。",
        "red_line_anchor": "绝不接受自己被排除在最终结算之外。",
        "pressure_vector": "会把每一次紧急状况都说成“某些人该失去权力”的证据。",
        "counter_trait": "公开场合极度算计，骨子里却非常害怕自己失去意义",
        "pressure_tell": "会把每一次挫折都改写成“权力必须立刻重新分配”的证明。",
    },
    "trade_bloc_rival": {
        "slot_label": "筹码经纪人",
        "public_role": "贸易集团对手",
        "agenda_anchor": "把检疫混乱转成对航运、信贷与重建分配权的谈判筹码。",
        "red_line_anchor": "不会接受港口在削弱自己集团的条件下重开。",
        "pressure_vector": "会把每一次供给震荡都改造成围绕权力分配的谈判，而不是围绕救济本身。",
        "counter_trait": "公开场合礼貌精致，私下里却对被边缘化耿耿于怀",
        "pressure_tell": "会开始提供看似务实的帮助，但每一份帮助都绑着新的让步条件。",
    },
    "public_witness": {
        "slot_label": "公共见证者",
        "public_role": "公众倡议者",
        "agenda_anchor": "在压力不断升高时，强迫危机应对继续对公众负责。",
        "red_line_anchor": "不会让精英程序抹去事情究竟如何发生的公共记录。",
        "pressure_vector": "会把模糊、保密或程序漂移直接变成公共审视。",
        "counter_trait": "公开场合有强烈的道德直觉，私下里则异常固执",
        "pressure_tell": "会停止接受闭门保证，转而要求有人把真实代价当场说出来。",
    },
    "dock_delegate": {
        "slot_label": "公共见证者",
        "public_role": "码头代表",
        "agenda_anchor": "不让工人和街区居民替他们从未同意过的检疫交易买单。",
        "red_line_anchor": "不会让紧急港务规则掩埋“谁获利、谁被困住”的事实。",
        "pressure_vector": "会把私下交易先变成码头流言，再把流言推成组织化压力。",
        "counter_trait": "公开场合说话直白，私下里却对人群情绪的走向极度敏锐",
        "pressure_tell": "会不断点名、点损失、点拖延，直到房间再也不能躲在抽象话术后面。",
    },
    "resource_steward": {
        "slot_label": "物资守门人",
        "public_role": "救济统筹员",
        "agenda_anchor": "让救济渠道在口号之后仍然真的能运转下去，不让代价偷偷转移给最脆弱的人。",
        "red_line_anchor": "如果没人说明这座城市究竟怎么承担成本，就不会承认这份公共结算已经成立。",
        "pressure_vector": "会把每一项公共承诺都翻译成供给、维护、人手与最终由谁买单的问题。",
        "counter_trait": "公开场合务实克制，私下里却对隐性成本转移异常执拗",
        "pressure_tell": "会开始逐项报出短缺、人手缺口和被延期的修复工作，逼房间给自己的承诺标价。",
    },
}


def _localized_cast_archetype_value(archetype_id: str, field: str, fallback: str, *, language: str) -> str:
    translated = (_CAST_ARCHETYPE_TRANSLATIONS_ZH.get(archetype_id) or {}).get(field)
    if translated and is_chinese_language(language):
        return translated
    return fallback


def _localized_relationship_dynamic(relationship_dynamic_id: str, *, language: str) -> str:
    if is_chinese_language(language):
        return CAST_RELATIONSHIP_DYNAMIC_LIBRARY_ZH.get(
            relationship_dynamic_id,
            CAST_RELATIONSHIP_DYNAMIC_LIBRARY[relationship_dynamic_id],
        )
    return CAST_RELATIONSHIP_DYNAMIC_LIBRARY[relationship_dynamic_id]

FOUR_SLOT_KEYWORDS: tuple[str, ...] = (
    "blackout",
    "succession",
    "election",
    "harbor",
    "port",
    "trade",
    "quarantine",
    "public",
    "civic",
    "coalition",
    "停电",
    "继承",
    "选举",
    "投票",
    "港口",
    "码头",
    "贸易",
    "检疫",
    "公众",
    "城市",
    "联盟",
)

HARBOR_FOURTH_SLOT_KEYWORDS: tuple[str, ...] = (
    "harbor",
    "port",
    "trade",
    "quarantine",
    "港口",
    "码头",
    "贸易",
    "检疫",
    "舱单",
)


@dataclass(frozen=True)
class CastTopologyPlan:
    topology: str
    slot_archetypes: tuple[str, ...]
    planner_reason: str


def _build_cast_slot_from_archetype(
    archetype_id: str,
    relationship_dynamic_id: str,
    *,
    language: str = "en",
) -> CastOverviewSlotDraft:
    archetype = CAST_ARCHETYPE_LIBRARY[archetype_id]
    return CastOverviewSlotDraft(
        slot_label=_localized_cast_archetype_value(archetype_id, "slot_label", archetype["slot_label"], language=language),
        public_role=_localized_cast_archetype_value(archetype_id, "public_role", archetype["public_role"], language=language),
        relationship_to_protagonist=_localized_relationship_dynamic(relationship_dynamic_id, language=language),
        agenda_anchor=_localized_cast_archetype_value(archetype_id, "agenda_anchor", archetype["agenda_anchor"], language=language),
        red_line_anchor=_localized_cast_archetype_value(archetype_id, "red_line_anchor", archetype["red_line_anchor"], language=language),
        pressure_vector=_localized_cast_archetype_value(archetype_id, "pressure_vector", archetype["pressure_vector"], language=language),
        archetype_id=archetype_id,
        relationship_dynamic_id=relationship_dynamic_id,
        counter_trait=_localized_cast_archetype_value(archetype_id, "counter_trait", archetype["counter_trait"], language=language),
        pressure_tell=_localized_cast_archetype_value(archetype_id, "pressure_tell", archetype["pressure_tell"], language=language),
    )


def build_default_cast_overview_draft(focused_brief: FocusedBrief) -> CastOverviewDraft:
    return CastOverviewDraft(
        cast_slots=[
            _build_cast_slot_from_archetype("civic_mediator", "protagonist_bears_public_weight", language=focused_brief.language),
            _build_cast_slot_from_archetype("archive_guardian", "improvisation_vs_procedure", language=focused_brief.language),
            _build_cast_slot_from_archetype("leverage_broker", "settlement_vs_leverage", language=focused_brief.language),
        ],
        relationship_summary=[
            _localized_relationship_dynamic("improvisation_vs_procedure", language=focused_brief.language),
            _localized_relationship_dynamic("settlement_vs_leverage", language=focused_brief.language),
        ],
    )


def plan_cast_topology(
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    *,
    preferred_count: int | None = None,
) -> CastTopologyPlan:
    haystack = " ".join(
        [
            focused_brief.setting_signal,
            focused_brief.core_conflict,
            story_frame.title,
            story_frame.premise,
        ]
    ).casefold()
    use_four_slot = any(keyword in haystack for keyword in FOUR_SLOT_KEYWORDS)
    use_five_slot = bool(preferred_count is not None and preferred_count >= 5)
    if preferred_count is not None and preferred_count <= 3:
        use_four_slot = False
    elif preferred_count is not None and preferred_count >= 4:
        use_four_slot = True
    protagonist_archetype_id = "civic_mediator"
    if any(keyword in haystack for keyword in ("inspector", "harbor inspector", "港口", "检疫", "舱单", "码头")):
        protagonist_archetype_id = "harbor_inspector"
    elif any(keyword in haystack for keyword in ("bridge", "flood", "ration", "checkpoint", "allotment", "桥", "洪水", "配给", "台账", "工程")):
        protagonist_archetype_id = "bridge_engineer"
    elif any(keyword in haystack for keyword in ("archive", "ledger", "record", "witness", "vote", "certify", "档案", "账本", "记录", "核验", "投票", "表决", "委员会")):
        protagonist_archetype_id = "record_examiner"
    elif any(keyword in haystack for keyword in ("blackout", "curfew", "neighborhood", "delegate", "停电", "社区", "协调员", "供给通报", "宵禁")):
        protagonist_archetype_id = "ward_coordinator"

    guardian_archetype_id = "archive_guardian"
    if any(keyword in haystack for keyword in ("harbor", "port", "trade", "港口", "码头", "贸易", "舱单")):
        guardian_archetype_id = "port_guardian"

    rival_archetype_id = "leverage_broker"
    if any(keyword in haystack for keyword in ("quarantine", "accord", "trade", "检疫", "贸易", "舱单")):
        rival_archetype_id = "trade_bloc_rival"

    slot_archetypes = [
        protagonist_archetype_id,
        guardian_archetype_id,
        rival_archetype_id,
    ]
    planner_reason = "default_three_slot"
    if use_four_slot:
        planner_reason = "keyword_triggered_four_slot"
        fourth_slot = (
            "dock_delegate"
            if any(keyword in haystack for keyword in HARBOR_FOURTH_SLOT_KEYWORDS)
            else "public_witness"
        )
        slot_archetypes.append(fourth_slot)
    if use_five_slot:
        planner_reason = "preferred_five_slot"
        fifth_slot = (
            "public_witness"
            if "dock_delegate" in slot_archetypes
            else "resource_steward"
        )
        slot_archetypes.append(fifth_slot)
    return CastTopologyPlan(
        topology="five_slot" if use_five_slot else "four_slot" if use_four_slot else "three_slot",
        slot_archetypes=tuple(slot_archetypes),
        planner_reason=planner_reason,
    )


def _coerce_topology_plan(
    topology_plan: CastTopologyPlan,
    *,
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    topology_override: str | None,
) -> CastTopologyPlan:
    if topology_override not in {"three_slot", "four_slot", "five_slot"}:
        return topology_plan
    if topology_override == topology_plan.topology:
        return topology_plan
    slot_archetypes = list(topology_plan.slot_archetypes[:3])
    if len(slot_archetypes) < 3:
        slot_archetypes.extend(["civic_mediator", "archive_guardian", "leverage_broker"][len(slot_archetypes):3])
    if topology_override in {"four_slot", "five_slot"}:
        haystack = " ".join(
            [
                focused_brief.setting_signal,
                focused_brief.core_conflict,
                story_frame.title,
                story_frame.premise,
            ]
        ).casefold()
        fourth_slot = (
            "dock_delegate"
            if any(keyword in haystack for keyword in HARBOR_FOURTH_SLOT_KEYWORDS)
            else "public_witness"
        )
        slot_archetypes.append(fourth_slot)
    if topology_override == "five_slot":
        fifth_slot = "public_witness" if "dock_delegate" in slot_archetypes else "resource_steward"
        slot_archetypes.append(fifth_slot)
    return CastTopologyPlan(
        topology=topology_override,
        slot_archetypes=tuple(
            slot_archetypes[:5]
            if topology_override == "five_slot"
            else slot_archetypes[:4]
            if topology_override == "four_slot"
            else slot_archetypes[:3]
        ),
        planner_reason="forced_topology_override",
    )


def derive_cast_overview_draft(
    focused_brief: FocusedBrief,
    story_frame: StoryFrameDraft,
    *,
    topology_override: str | None = None,
) -> CastOverviewDraft:
    topology_plan = plan_cast_topology(focused_brief, story_frame)
    topology_plan = _coerce_topology_plan(
        topology_plan,
        focused_brief=focused_brief,
        story_frame=story_frame,
        topology_override=topology_override,
    )
    cast_slots = [
        _build_cast_slot_from_archetype(topology_plan.slot_archetypes[0], "protagonist_bears_public_weight", language=focused_brief.language),
        _build_cast_slot_from_archetype(topology_plan.slot_archetypes[1], "improvisation_vs_procedure", language=focused_brief.language),
        _build_cast_slot_from_archetype(topology_plan.slot_archetypes[2], "settlement_vs_leverage", language=focused_brief.language),
    ]
    relationship_summary = [
        _localized_relationship_dynamic("improvisation_vs_procedure", language=focused_brief.language),
        _localized_relationship_dynamic("settlement_vs_leverage", language=focused_brief.language),
    ]
    if topology_plan.topology == "four_slot":
        cast_slots.append(
            _build_cast_slot_from_archetype(
                topology_plan.slot_archetypes[3],
                "public_record_vs_private_bargain",
                language=focused_brief.language,
            )
        )
        relationship_summary.append(
            _localized_relationship_dynamic("public_record_vs_private_bargain", language=focused_brief.language)
        )
    if topology_plan.topology == "five_slot":
        if len(cast_slots) < 4:
            cast_slots.append(
                _build_cast_slot_from_archetype(
                    topology_plan.slot_archetypes[3],
                    "public_record_vs_private_bargain",
                    language=focused_brief.language,
                )
            )
            relationship_summary.append(
                _localized_relationship_dynamic("public_record_vs_private_bargain", language=focused_brief.language)
            )
        cast_slots.append(
            _build_cast_slot_from_archetype(
                topology_plan.slot_archetypes[4],
                "material_cost_vs_public_order",
                language=focused_brief.language,
            )
        )
        relationship_summary.append(
            _localized_relationship_dynamic("material_cost_vs_public_order", language=focused_brief.language)
        )
    return CastOverviewDraft(
        cast_slots=cast_slots[:5],
        relationship_summary=relationship_summary[:6],
    )


def _name_palette_for_brief(focused_brief: FocusedBrief) -> dict[str, list[str]]:
    if is_chinese_language(focused_brief.language):
        setting = focused_brief.setting_signal.casefold()
        if any(keyword in setting for keyword in ("archive", "archives", "ledger", "record", "script", "library", "档案", "记录", "账本", "证词")):
            return {
                "protagonist": ["岑港", "闻砚", "林栈", "顾潮"],
                "guardian": ["沈册", "韩汀", "许衡", "周砚"],
                "rival": ["邵津", "杜阙", "裴竞", "乔策"],
                "civic": ["苏苇", "唐屿", "陆岚", "程堤"],
                "witness": ["叶舟", "沈苇", "何栈", "白岚"],
            }
        if any(keyword in setting for keyword in ("harbor", "port", "trade", "quarantine", "republic", "dock", "港口", "码头", "贸易", "检疫", "舱单")):
            return {
                "protagonist": ["岑港", "顾潮", "林栈", "闻砚"],
                "guardian": ["韩汀", "周衡", "沈策", "许阔"],
                "rival": ["邵津", "杜阙", "裴渡", "乔竞"],
                "civic": ["苏岚", "唐屿", "陆槐", "程渡"],
                "witness": ["叶舟", "白汐", "何堤", "沈棠"],
            }
        return {
            "protagonist": ["顾潮", "林栈", "闻砚", "岑港"],
            "guardian": ["韩汀", "周衡", "许策", "沈册"],
            "rival": ["邵津", "杜阙", "裴竞", "乔渡"],
            "civic": ["苏岚", "唐屿", "陆槐", "程堤"],
            "witness": ["叶舟", "白汐", "何栈", "沈棠"],
        }
    setting = focused_brief.setting_signal.casefold()
    if any(keyword in setting for keyword in ("archive", "archives", "ledger", "record", "script", "library")):
        return {
            "protagonist": ["Elara Vance", "Iri Vale", "Nera Quill", "Tarin Sloane"],
            "guardian": ["Kaelen Thorne", "Sen Ardin", "Pell Ivar", "Sera Nhal"],
            "rival": ["Mira Solis", "Tal Reth", "Dain Voss", "Cass Vey"],
            "civic": ["Lio Maren", "Risa Vale", "Joren Pell", "Tavi Sern"],
            "witness": ["Ona Pell", "Lio Maren", "Risa Vale", "Tavi Sern"],
        }
    if any(keyword in setting for keyword in ("harbor", "port", "trade", "quarantine", "republic", "dock")):
        return {
            "protagonist": ["Corin Hale", "Mara Vey", "Tessa Vale", "Ilan Dorr"],
            "guardian": ["Jun Pell", "Soren Vale", "Neris Dane", "Hadrin Voss"],
            "rival": ["Tal Reth", "Cass Voren", "Mira Solis", "Dain Vey"],
            "civic": ["Edda Marr", "Korin Pell", "Rhea Doss", "Sel Varan"],
            "witness": ["Edda Marr", "Sel Varan", "Brin Vale", "Rhea Doss"],
        }
    return {
        "protagonist": ["Elara Vance", "Corin Hale", "Mira Vale", "Iri Vale"],
        "guardian": ["Kaelen Thorne", "Sera Pell", "Jun Ardin", "Pell Ivar"],
        "rival": ["Tal Reth", "Mira Solis", "Dain Voss", "Cass Vey"],
        "civic": ["Risa Vale", "Lio Maren", "Tavi Sern", "Neris Dane"],
        "witness": ["Lio Maren", "Ona Pell", "Risa Vale", "Tavi Sern"],
    }


def _cast_slot_bucket(slot: CastOverviewSlotDraft) -> str:
    if slot.archetype_id in {"public_witness", "dock_delegate"}:
        return "witness"
    text = f"{slot.slot_label} {slot.public_role}".casefold()
    if any(keyword in text for keyword in ("mediator", "anchor", "player", "envoy", "inspector", "protagonist", "调停", "检察官", "工程官", "核验官", "协调员")):
        return "protagonist"
    if any(keyword in text for keyword in ("institution", "guardian", "authority", "curator", "scribe", "warden")):
        return "guardian"
    if any(keyword in text for keyword in ("broker", "rival", "opposition", "leverage", "faction", "merchant")):
        return "rival"
    return "civic"


def is_legitimacy_broker_slot(cast_strategy: str, slot: CastOverviewSlotDraft) -> bool:
    if cast_strategy != "legitimacy_cast":
        return False
    slot_text = f"{slot.slot_label} {slot.public_role} {slot.archetype_id or ''}".casefold()
    return any(
        token in slot_text
        for token in (
            "leverage broker",
            "political rival",
            "trade bloc rival",
            "leverage_broker",
            "trade_bloc_rival",
        )
    )


def _generated_name_for_slot(
    slot: CastOverviewSlotDraft,
    focused_brief: FocusedBrief,
    slot_index: int,
    used_names: set[str],
) -> str:
    palette = _name_palette_for_brief(focused_brief)
    bucket = _cast_slot_bucket(slot)
    options = palette[bucket]
    seed = f"{focused_brief.story_kernel}|{focused_brief.setting_signal}|{slot.slot_label}|{slot_index}"
    start = sum(ord(ch) for ch in seed) % len(options)
    for offset in range(len(options)):
        candidate = options[(start + offset) % len(options)]
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
    fallback = f"{options[start]} {slot_index + 1}"
    used_names.add(fallback)
    return fallback


def _looks_like_role_label_name_locally(
    member_name: str,
    slot: CastOverviewSlotDraft,
) -> bool:
    normalized_name = normalize_whitespace(member_name).casefold()
    if normalized_name in {
        normalize_whitespace(slot.slot_label).casefold(),
        normalize_whitespace(slot.public_role).casefold(),
    }:
        return True
    generic_tokens = {
        "mediator",
        "anchor",
        "guardian",
        "broker",
        "leverage",
        "witness",
        "rival",
        "authority",
        "advocate",
        "public",
        "civic",
        "institutional",
        "archive",
        "coalition",
        "trade",
        "bloc",
        "player",
        "power",
        "figure",
        "delegate",
        "stakeholder",
    }
    tokens = [token for token in normalized_name.replace("-", " ").split() if token]
    if len(tokens) < 2:
        return True
    nongeneric_tokens = [token for token in tokens if token not in generic_tokens]
    return len(nongeneric_tokens) < 1


def _clean_member_detail(detail: str, fallback: str, *, limit: int = 180) -> str:
    text = trim_ellipsis(detail or fallback, limit)
    if not text:
        return trim_ellipsis(fallback, limit)
    return text


def _merge_anchor_with_detail(anchor: str, detail: str, *, limit: int = 220) -> str:
    anchor_text = trim_ellipsis(anchor, limit)
    detail_text = trim_ellipsis(detail, limit)
    if not detail_text:
        return anchor_text
    if detail_text.casefold() in anchor_text.casefold() or anchor_text.casefold() in detail_text.casefold():
        return anchor_text
    return trim_ellipsis(f"{anchor_text} {detail_text}", limit)


def build_cast_draft_from_overview(
    cast_overview: CastOverviewDraft,
    focused_brief: FocusedBrief,
) -> CastDraft:
    used_names: set[str] = set()
    return CastDraft(
        cast=[
            OverviewCastDraft(
                name=_generated_name_for_slot(slot, focused_brief, index, used_names),
                role=trim_ellipsis(slot.public_role, 120),
                agenda=trim_ellipsis(slot.agenda_anchor, 220),
                red_line=trim_ellipsis(slot.red_line_anchor, 220),
                pressure_signature=trim_ellipsis(slot.pressure_vector, 220),
            )
            for index, slot in enumerate(cast_overview.cast_slots)
        ]
    )


def build_cast_member_from_slot(
    slot: CastOverviewSlotDraft,
    focused_brief: FocusedBrief,
    slot_index: int,
    existing_names: set[str],
) -> OverviewCastDraft:
    return OverviewCastDraft(
        name=_generated_name_for_slot(slot, focused_brief, slot_index, existing_names),
        role=trim_ellipsis(slot.public_role, 120),
        agenda=trim_ellipsis(slot.agenda_anchor, 220),
        red_line=trim_ellipsis(slot.red_line_anchor, 220),
        pressure_signature=trim_ellipsis(slot.pressure_vector, 220),
    )


def compile_cast_member_semantics(
    semantics: CastMemberSemanticsDraft,
    slot: CastOverviewSlotDraft,
    focused_brief: FocusedBrief,
    slot_index: int,
    existing_names: set[str],
) -> OverviewCastDraft:
    fallback_member = build_cast_member_from_slot(
        slot,
        focused_brief,
        slot_index,
        set(existing_names),
    )
    generated_name = trim_ellipsis(semantics.name, 80)
    if (
        not generated_name
        or generated_name in existing_names
        or generated_name.startswith("Civic Figure ")
        or _looks_like_role_label_name_locally(generated_name, slot)
    ):
        name = fallback_member.name
    else:
        name = generated_name
    agenda_detail = _clean_member_detail(
        semantics.agenda_detail,
        "Uses their position to turn private hesitation into a concrete bargaining advantage.",
    )
    red_line_detail = _clean_member_detail(
        semantics.red_line_detail,
        "The line hardens whenever they think the settlement will erase their public standing.",
    )
    pressure_detail = _clean_member_detail(
        semantics.pressure_detail,
        slot.pressure_tell or "Their instincts sharpen as the room turns brittle.",
    )
    return OverviewCastDraft(
        name=name,
        role=trim_ellipsis(slot.public_role, 120),
        agenda=_merge_anchor_with_detail(slot.agenda_anchor, agenda_detail, limit=220),
        red_line=_merge_anchor_with_detail(slot.red_line_anchor, red_line_detail, limit=220),
        pressure_signature=_merge_anchor_with_detail(slot.pressure_vector, pressure_detail, limit=220),
    )


def build_default_cast_draft(_: FocusedBrief) -> CastDraft:
    focused_brief = _
    return CastDraft(
        cast=[
            OverviewCastDraft(
                name=localized_text(focused_brief.language, en="The Mediator", zh="调停者"),
                role=localized_text(focused_brief.language, en="Player anchor", zh="局中调停者"),
                agenda=localized_text(focused_brief.language, en="Hold the city together long enough to expose the truth.", zh="先稳住整座城市，再把真相揭出来。"),
                red_line=localized_text(focused_brief.language, en="Will not deliberately sacrifice civilians for speed.", zh="不会为了追求速度而故意牺牲平民。"),
                pressure_signature=localized_text(focused_brief.language, en="Feels every compromise as a public burden.", zh="会把每一次让步都当成必须向公众承担的负担。"),
            ),
            OverviewCastDraft(
                name=localized_text(focused_brief.language, en="Civic Authority", zh="公共机构代表"),
                role=localized_text(focused_brief.language, en="Institutional power", zh="机构掌权者"),
                agenda=localized_text(focused_brief.language, en="Preserve order and legitimacy.", zh="维护秩序与正当性。"),
                red_line=localized_text(focused_brief.language, en="Will not publicly yield without visible cause.", zh="没有公开可见的理由时绝不会退让。"),
                pressure_signature=localized_text(focused_brief.language, en="Turns every crisis into a test of control.", zh="会把每一次危机都变成控制力测试。"),
            ),
            OverviewCastDraft(
                name=localized_text(focused_brief.language, en="Opposition Broker", zh="反对派经纪人"),
                role=localized_text(focused_brief.language, en="Political rival", zh="政治对手"),
                agenda=localized_text(focused_brief.language, en="Exploit the crisis to reshape power.", zh="利用危机重塑权力分配。"),
                red_line=localized_text(focused_brief.language, en="Will not accept irrelevance.", zh="绝不接受自己被边缘化。"),
                pressure_signature=localized_text(focused_brief.language, en="Smiles while pressure spreads through the room.", zh="会在压力蔓延全场时仍保持微笑。"),
            ),
        ]
    )


def _is_generic_cast_text(value: str) -> bool:
    lowered = normalize_whitespace(value).casefold()
    generic_fragments = (
        "tries to preserve their role in the crisis",
        "will not lose public legitimacy without resistance",
        "reacts sharply when pressure threatens public order",
        "protect their corner of the city during the crisis",
        "will not accept total collapse without resistance",
        "pushes for quick action whenever the public mood worsens",
        "placeholder agenda",
        "placeholder red line",
        "placeholder pressure signature",
    )
    return any(fragment in lowered for fragment in generic_fragments)


def repair_cast_draft(
    cast_draft: CastDraft,
    focused_brief: FocusedBrief,
    cast_overview: CastOverviewDraft | None = None,
) -> CastDraft:
    role_templates = (
        (
            ("mediator", "envoy", "inspector", "player", "anchor", "negotiator"),
            {
                "agenda": trim_ellipsis(f"Keep the civic process intact long enough to resolve {focused_brief.core_conflict}.", 220),
                "red_line": "Will not let emergency pressure erase public consent.",
                "pressure_signature": "Reads every compromise in terms of what the public will have to live with next.",
            },
        ),
        (
            ("authority", "curator", "official", "institution", "guardian"),
            {
                "agenda": trim_ellipsis(f"Preserve institutional continuity inside {focused_brief.setting_signal}.", 220),
                "red_line": "Will not yield formal authority without a visible procedural reason.",
                "pressure_signature": "Tightens procedure whenever panic, blame, or uncertainty starts to spread.",
            },
        ),
        (
            ("broker", "rival", "faction", "opposition", "merchant", "leader"),
            {
                "agenda": trim_ellipsis(f"Exploit {focused_brief.core_conflict} to reshape who holds leverage after the crisis.", 220),
                "red_line": "Will not accept exclusion from the final settlement.",
                "pressure_signature": "Treats every emergency as proof that someone else should lose authority.",
            },
        ),
    )
    slot_templates = list(cast_overview.cast_slots) if cast_overview else []
    repaired = []
    for index, member in enumerate(cast_draft.cast):
        matching_slot = None
        if slot_templates:
            member_role = member.role.casefold()
            member_name = member.name.casefold()
            for slot in slot_templates:
                if slot.slot_label.casefold() in member_name or slot.public_role.casefold() in member_role or any(
                    keyword in member_role
                    for keyword in slot.public_role.casefold().split()
                    if len(keyword) > 3
                ):
                    matching_slot = slot
                    break
            if matching_slot is None and index < len(slot_templates):
                matching_slot = slot_templates[index]
        role_text = member.role.casefold()
        template = None
        for keywords, candidate in role_templates:
            if any(keyword in role_text for keyword in keywords):
                template = candidate
                break
        if matching_slot is not None:
            template = {
                "agenda": trim_ellipsis(matching_slot.agenda_anchor, 220),
                "red_line": trim_ellipsis(matching_slot.red_line_anchor, 220),
                "pressure_signature": trim_ellipsis(matching_slot.pressure_vector, 220),
            }
        elif template is None:
            template = (
                role_templates[min(index, len(role_templates) - 1)][1]
                if index < len(role_templates)
                else {
                    "agenda": trim_ellipsis(f"Protect their stake in {focused_brief.setting_signal} while the crisis unfolds.", 220),
                    "red_line": "Will not accept being made irrelevant by emergency decree.",
                    "pressure_signature": "Pushes harder for advantage whenever the public mood turns brittle.",
                }
            )
        repaired.append(
            OverviewCastDraft(
                name=member.name,
                role=member.role,
                agenda=template["agenda"] if _is_generic_cast_text(member.agenda) else member.agenda,
                red_line=template["red_line"] if _is_generic_cast_text(member.red_line) else member.red_line,
                pressure_signature=template["pressure_signature"] if _is_generic_cast_text(member.pressure_signature) else member.pressure_signature,
            )
        )
    return CastDraft(cast=repaired)


def repair_cast_member(
    member: OverviewCastDraft,
    focused_brief: FocusedBrief,
    slot: CastOverviewSlotDraft,
) -> OverviewCastDraft:
    role_text = (member.role or slot.public_role).casefold()
    agenda = member.agenda
    red_line = member.red_line
    pressure_signature = member.pressure_signature
    if _is_generic_cast_text(agenda):
        agenda = slot.agenda_anchor
    if _is_generic_cast_text(red_line):
        red_line = slot.red_line_anchor
    if _is_generic_cast_text(pressure_signature):
        pressure_signature = slot.pressure_vector
    if "mediator" in role_text or "inspector" in role_text or "anchor" in role_text:
        agenda = slot.agenda_anchor if _is_generic_cast_text(member.agenda) else agenda
    elif any(keyword in role_text for keyword in ("guardian", "authority", "institution", "curator", "scribe")):
        agenda = slot.agenda_anchor if _is_generic_cast_text(member.agenda) else agenda
    elif any(keyword in role_text for keyword in ("broker", "rival", "opposition", "merchant", "trade bloc")):
        agenda = slot.agenda_anchor if _is_generic_cast_text(member.agenda) else agenda
    return OverviewCastDraft(
        name=member.name,
        role=trim_ellipsis(member.role or slot.public_role, 120),
        agenda=trim_ellipsis(agenda, 220),
        red_line=trim_ellipsis(red_line, 220),
        pressure_signature=trim_ellipsis(pressure_signature, 220),
    )

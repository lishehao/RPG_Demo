from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random
from typing import Literal


StorySeedLanguage = Literal["en", "zh"]
_BUCKET_IDS: tuple[str, ...] = (
    "legitimacy_warning",
    "ration_infrastructure",
    "blackout_panic",
    "harbor_quarantine",
    "archive_vote_record",
    "charter_oath_breach",
    "checkpoint_corridor_access",
    "customs_clearance_standoff",
    "shelter_capacity_surge",
    "testimony_release_timing",
)
STORY_SEED_BUCKET_IDS: tuple[str, ...] = _BUCKET_IDS


@dataclass(frozen=True)
class GeneratedStorySeed:
    bucket_id: str
    slug: str
    seed: str
    generated_at: str
    language: StorySeedLanguage = "en"


def _timestamp(now: datetime | None = None) -> str:
    resolved = now or datetime.now(timezone.utc)
    return resolved.isoformat()


def _slug_for_bucket(bucket_id: str, language: StorySeedLanguage) -> str:
    return bucket_id if language == "en" else f"{bucket_id}_{language}"


def _english_seed(bucket_id: str, rng: Random) -> str:
    if bucket_id == "legitimacy_warning":
        return (
            f"When a {rng.choice(['lunar', 'storm', 'river', 'watchtower'])} warning is buried to protect "
            f"a {rng.choice(['council vote', 'succession bargain', 'emergency mandate'])}, "
            f"a {rng.choice(['royal archivist', 'civic envoy', 'records magistrate'])} must prove the threat is real "
            f"before {rng.choice(['courtiers rewrite the public story', 'the capital locks itself into denial', 'the city accepts a false calm as law'])}."
        )
    if bucket_id == "ration_infrastructure":
        return (
            f"After {rng.choice(['forged ration counts', 'tampered bridge ledgers', 'hidden reserve tallies'])} split "
            f"{rng.choice(['the upper wards and the river docks', 'the bridge crews and the market districts', 'the flood board and the grain stewards'])}, "
            f"a {rng.choice(['bridge engineer', 'public works marshal', 'levee comptroller'])} must keep the "
            f"{rng.choice(['flood defense coalition', 'cross-river relief pact', 'emergency works charter'])} intact before "
            f"{rng.choice(['the crossing fails under panic', 'scarcity turns maintenance into factional leverage', 'the city blames the wrong ward for the collapse'])}."
        )
    if bucket_id == "blackout_panic":
        return (
            f"During a {rng.choice(['blackout referendum', 'rolling power crisis', 'night-curfew recall vote'])}, "
            f"a {rng.choice(['city ombudsman', 'ward mediator', 'public audit officer'])} must stop "
            f"{rng.choice(['forged supply reports', 'staged shortage bulletins', 'panic-rich rumor ledgers'])} from "
            f"breaking apart {rng.choice(['the neighborhood councils', 'the ward coalition', 'the emergency compact'])} before "
            f"{rng.choice(['street patrols turn rumor into authority', 'the districts seize the grid room by force', 'panic becomes the only public language left'])}."
        )
    if bucket_id == "harbor_quarantine":
        return (
            f"In a port city under quarantine, a {rng.choice(['harbor inspector', 'dock auditor', 'quarantine liaison'])} must keep "
            f"{rng.choice(['the harbor compact', 'the dock coalition', 'the relief corridor'])} alive after "
            f"{rng.choice(['missing manifests', 'staged scarcity reports', 'quietly redirected medical crates'])} threaten to hand "
            f"{rng.choice(['private trade brokers', 'emergency wardens', 'supply syndicates'])} the right to rule by exception."
        )
    if bucket_id == "archive_vote_record":
        return (
            f"When {rng.choice(['vote ledgers', 'emergency transcripts', 'sealed chain-of-custody records'])} are altered during "
            f"{rng.choice(['an emergency council vote', 'a succession settlement', 'a public legitimacy hearing'])}, "
            f"a {rng.choice(['city archivist', 'records advocate', 'civic witness clerk'])} must restore one binding public record before "
            f"{rng.choice(['rumor hardens into law', 'the council governs from a forged mandate', 'every faction claims a different city truth'])}."
        )
    if bucket_id == "charter_oath_breach":
        return (
            f"After a {rng.choice(['charter oath', 'mandate pledge', 'emergency office vow'])} is broken in public, "
            f"a {rng.choice(['charter envoy', 'oath registrar', 'mandate witness'])} must prove who voided the city's binding promise before "
            f"{rng.choice(['a rival faction recasts betrayal as lawful necessity', 'the council treats perjury as an acceptable emergency tool', 'public consent collapses into competing oath stories'])}."
        )
    if bucket_id == "checkpoint_corridor_access":
        return (
            f"When a {rng.choice(['relief corridor', 'river checkpoint lane', 'district passage charter'])} is quietly narrowed, "
            f"a {rng.choice(['corridor marshal', 'checkpoint auditor', 'passage liaison'])} must reopen lawful access before "
            f"{rng.choice(['favored wards turn movement rights into political leverage', 'the checkpoint regime hardens into a private toll order', 'the city accepts selective passage as a new normal'])}."
        )
    if bucket_id == "customs_clearance_standoff":
        return (
            f"With customs clearance frozen by {rng.choice(['conflicting manifests', 'seized inspection seals', 'withheld release orders'])}, "
            f"a {rng.choice(['customs examiner', 'clearance magistrate', 'harbor release clerk'])} must keep trade oversight legitimate before "
            f"{rng.choice(['dock brokers rewrite the queue by private favor', 'inspection exceptions become the only route to survive the harbor', 'cargo control slips from public ledger into private bargaining'])}."
        )
    if bucket_id == "shelter_capacity_surge":
        return (
            f"After {rng.choice(['shelter rosters', 'bed-capacity ledgers', 'evacuation allotments'])} fail under a sudden surge, "
            f"a {rng.choice(['shelter comptroller', 'relief allocator', 'district intake steward'])} must keep the city's placement order intact before "
            f"{rng.choice(['queue-jumping turns triage into factional privilege', 'families start treating rumors as the only admission system', 'capacity panic breaks the relief pact between districts'])}."
        )
    if bucket_id == "testimony_release_timing":
        return (
            f"When sworn testimony about a {rng.choice(['quarantine bargain', 'vote certification dispute', 'blackout command order'])} is held back, "
            f"a {rng.choice(['hearing clerk', 'testimony custodian', 'release advocate'])} must decide what to publish, and when, before "
            f"{rng.choice(['the delay lets rumor outrun the public record', 'selective leaks turn witness protection into narrative control', 'the hearing closes under a version of events no longer anchored to evidence'])}."
        )
    raise ValueError(f"unsupported bucket_id: {bucket_id}")


def _chinese_seed(bucket_id: str, rng: Random) -> str:
    if bucket_id == "legitimacy_warning":
        return (
            f"当一份关于{rng.choice(['月潮', '风暴', '河堤', '天文台'])}的预警被压下，只为了保住"
            f"{rng.choice(['议会表决', '继承交易', '紧急授权'])}时，"
            f"一名{rng.choice(['王室档案官', '市政使节', '记录裁定官'])}必须在"
            f"{rng.choice(['权臣重写公众叙事之前', '首都把自我欺骗当成秩序之前', '整座城市接受虚假的平静为法律之前'])}"
            f"证明这场威胁是真的。"
        )
    if bucket_id == "ration_infrastructure":
        return (
            f"在{rng.choice(['配给数字被篡改', '桥梁账本被动过手脚', '储备清单被偷偷改写'])}之后，"
            f"{rng.choice(['上城区与河港码头', '桥梁工段与市场街区', '防洪委员会与粮仓保管人'])}迅速分裂，"
            f"一名{rng.choice(['桥梁工程官', '公共工程巡查官', '堤岸总会计'])}必须在"
            f"{rng.choice(['跨河防御联盟崩掉之前', '紧急维修契约被派系当成筹码之前', '全城把坍塌责任推给错误街区之前'])}"
            f"稳住这份{rng.choice(['防洪联盟', '跨河救济协议', '紧急工程宪章'])}。"
        )
    if bucket_id == "blackout_panic":
        return (
            f"在一场{rng.choice(['停电公投', '滚动断电危机', '夜间宵禁罢免投票'])}中，"
            f"一名{rng.choice(['市政申诉官', '街区调停人', '公共审计官'])}必须阻止"
            f"{rng.choice(['伪造的物资报告', '被故意放大的短缺通告', '煽动恐慌的流言账簿'])}"
            f"在{rng.choice(['街区委员会', '片区联盟', '紧急协定'])}之间制造彻底破裂，"
            f"否则{rng.choice(['街头巡逻会把流言变成权威', '各区会直接冲进电网控制室', '恐慌会成为唯一剩下的公共语言'])}。"
        )
    if bucket_id == "harbor_quarantine":
        return (
            f"在一座处于检疫中的港城里，一名{rng.choice(['港务检查官', '码头审计官', '检疫联络官'])}必须保住"
            f"{rng.choice(['港务协定', '码头联盟', '救济走廊'])}，因为"
            f"{rng.choice(['消失的舱单', '被操纵的短缺报告', '悄悄改道的医药箱'])}"
            f"正准备把按例外统治的权力交给{rng.choice(['私人贸易掮客', '紧急管制官', '供应黑市集团'])}。"
        )
    if bucket_id == "archive_vote_record":
        return (
            f"当{rng.choice(['投票账本', '紧急会议记录', '封存的证据链文件'])}在"
            f"{rng.choice(['紧急委员会表决', '继承和解', '公共合法性听证'])}期间被人篡改时，"
            f"一名{rng.choice(['市政档案官', '记录辩护人', '公民证词书记官'])}必须在"
            f"{rng.choice(['流言凝固成法律之前', '议会凭一份伪造授权治理全城之前', '每个派系都宣称自己掌握唯一城市真相之前'])}"
            f"恢复一份具约束力的公开记录。"
        )
    if bucket_id == "charter_oath_breach":
        return (
            f"当一份{rng.choice(['宪章誓言', '授权承诺', '紧急职位誓约'])}在公众面前被撕毁时，"
            f"一名{rng.choice(['宪章使节', '誓约登记官', '授权见证人'])}必须在"
            f"{rng.choice(['对手把背誓包装成合法必要之前', '议会把伪誓当成紧急治理手段之前', '公众同意瓦解成彼此冲突的誓言叙事之前'])}"
            f"证明究竟是谁先让这座城市失去了仍然有效的绑定承诺。"
        )
    if bucket_id == "checkpoint_corridor_access":
        return (
            f"当一条{rng.choice(['救济通道', '河岸检查通路', '街区通行走廊'])}被人悄悄收紧时，"
            f"一名{rng.choice(['通道巡查官', '检查点审计官', '通行协调员'])}必须在"
            f"{rng.choice(['特权街区把通行权变成筹码之前', '检查制度硬化成私人收费秩序之前', '全城把选择性放行当成新常态之前'])}"
            f"恢复合法而公开的通行边界。"
        )
    if bucket_id == "customs_clearance_standoff":
        return (
            f"当{rng.choice(['彼此冲突的舱单', '被扣下的验印', '迟迟不发的放行令'])}让港口清关陷入僵局时，"
            f"一名{rng.choice(['关务检查官', '清关裁定官', '放行书记员'])}必须在"
            f"{rng.choice(['码头掮客靠私下关系重排队列之前', '例外放行成为唯一还能活下去的路径之前', '货物流向从公共账本滑入私人交易之前'])}"
            f"守住清关程序的合法性。"
        )
    if bucket_id == "shelter_capacity_surge":
        return (
            f"当一波突发潮涌击穿了{rng.choice(['避难所名册', '床位容量账本', '撤离安置配额'])}时，"
            f"一名{rng.choice(['避难所总会计', '救济配额官', '街区接纳主管'])}必须在"
            f"{rng.choice(['插队把分流变成派系特权之前', '家家户户只能依赖流言抢位置之前', '街区之间的安置协定彻底断裂之前'])}"
            f"守住这座城市的安置秩序。"
        )
    if bucket_id == "testimony_release_timing":
        return (
            f"当一份关于{rng.choice(['检疫交易', '认证争议', '停电指令'])}的宣誓证词被压着不放时，"
            f"一名{rng.choice(['听证书记官', '证词保管人', '公开申请代理人'])}必须在"
            f"{rng.choice(['流言先一步取代公共记录之前', '选择性泄露把见证保护变成叙事操控之前', '听证会在不再锚定证据的版本里草草收束之前'])}"
            f"决定什么该公开、什么时候公开。"
        )
    raise ValueError(f"unsupported bucket_id: {bucket_id}")


def all_story_seed_bucket_ids() -> tuple[str, ...]:
    return STORY_SEED_BUCKET_IDS


def build_story_seed_for_bucket(
    bucket_id: str,
    *,
    language: StorySeedLanguage = "en",
    rng: Random | None = None,
    generated_at: str | None = None,
) -> GeneratedStorySeed:
    resolved_rng = rng or Random()
    if bucket_id not in _BUCKET_IDS:
        raise ValueError(f"unsupported bucket_id: {bucket_id}")
    seed_text = _english_seed(bucket_id, resolved_rng) if language == "en" else _chinese_seed(bucket_id, resolved_rng)
    return GeneratedStorySeed(
        bucket_id=bucket_id,
        slug=_slug_for_bucket(bucket_id, language),
        seed=seed_text,
        generated_at=generated_at or _timestamp(),
        language=language,
    )


def build_story_seed_batch(
    *,
    rng: Random | None = None,
    now: datetime | None = None,
    story_count: int = 5,
    language: StorySeedLanguage = "en",
    bucket_ids: list[str] | tuple[str, ...] | None = None,
) -> list[GeneratedStorySeed]:
    resolved_rng = rng or Random()
    generated_at = _timestamp(now)
    available_bucket_ids = list(bucket_ids or _BUCKET_IDS)
    normalized_count = max(1, min(int(story_count), len(available_bucket_ids)))
    if normalized_count >= len(available_bucket_ids):
        selected_bucket_ids = list(available_bucket_ids)
    else:
        selected_bucket_ids = resolved_rng.sample(available_bucket_ids, k=normalized_count)
    generated = [
        build_story_seed_for_bucket(
            bucket_id,
            language=language,
            rng=resolved_rng,
            generated_at=generated_at,
        )
        for bucket_id in selected_bucket_ids
    ]
    return sorted(generated, key=lambda item: item.bucket_id)

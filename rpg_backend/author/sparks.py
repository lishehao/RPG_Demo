from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from random import Random
import re
from threading import Lock
from time import sleep
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from rpg_backend.author.contracts import AuthorStorySparkResponse
from rpg_backend.author.gateway import AuthorGatewayError
from rpg_backend.author.generation.runner import invoke_structured_generation_with_retries
from rpg_backend.generation_skill import ContextCard, GenerationSkillPacket, build_role_style_context
from rpg_backend.author.normalize import normalize_whitespace
from rpg_backend.config import Settings, get_settings
from rpg_backend.content_language import (
    ContentLanguage,
    is_chinese_language,
    localized_text,
    output_language_instruction,
    prompt_role_instruction,
)
from rpg_backend.llm_gateway import CapabilityGatewayCore
from rpg_backend.responses_transport import StructuredResponse

_SPARK_MAX_TOTAL_CHARS = 700
_SPARK_MAX_ENGLISH_WORDS = 100
_SPARK_MAX_CHINESE_CHARS = 120
_SPARK_MAX_SENTENCES = 4
_ENGLISH_WORD_PATTERN = re.compile(r"[a-z0-9']+")
_SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?。！？]+")
_CURATED_SPARK_SEED_PAIRS: tuple[tuple[str, str], ...] = (
    (
        "Quarantine has just widened around the port, but a harbor auditor finds a second manifest quietly routing restricted cargo into the relief lane. Someone wants dock rumor to harden into enforcement before anyone checks the paperwork. If she cannot surface the forged record before the escort boats depart, every later order will rest on a lie.",
        "港口刚刚宣布扩大检疫，码头上却流出另一份完全对不上的放行清单。负责稽核的她发现，有人故意把该扣下的货船混进救济航道里。要是她赶在护航队出发前拿不出证据，接下来所有关于戒严和配给的命令都会建立在假账上。",
    ),
    (
        "After a citywide blackout, the council is searching for one district to blame for the ration collapse. A municipal archivist discovers that the ledger most likely to clear them was sealed off just before the hearing. She has one afternoon to recover the original allocation book, or an entire neighborhood will be condemned for a shortage it did not create.",
        "大停电后的配给缺口正在逼市议会找一个替罪羊。档案员翻到一条被临时封存的账本索引，发现真正的调拨去向和公开说法完全相反。她必须在议会表决前把这本账找回来，不然整片街区会被当成囤积居奇的罪魁祸首。",
    ),
    (
        "Emergency tolls were supposed to expire when the flood receded, but the bridge authority now insists the river almost breached again. A bridge engineer finds that the floodgate numbers were altered after the fact, just enough to justify keeping the new powers. If she cannot prove the records were changed, a temporary crisis measure will become the city's new price of movement.",
        "洪水退了，桥上的临时收费却没有要撤的意思。负责闸门和桥体维护的工程师发现，事故当天的流量数字被人悄悄改写过。她要是拿不出闸门记录被篡改的证据，一项本该短期执行的紧急收费权，很快就会变成新常态。",
    ),
    (
        "Medical crates vanish from the harbor inventory overnight, and every faction claims the transfer was legal under emergency authority. The ward mediator can see that one more private seizure will shatter the coalition keeping the docks functional. She must force a public count of the missing stock before relief turns into a scramble run by whoever has the most muscle.",
        "港区的药箱一夜之间少了十几箱，各方都说自己是按规章临时调拨。负责街区协调的人知道，再这样含糊下去，所谓联合调度很快会变成谁有枪谁先拿。她必须把失踪药箱的数量和去向逼上公开台面，否则整份港务协定会先从医疗物资上裂开。",
    ),
    (
        "The storm bulletin reached the capital early enough to evacuate cleanly, yet the city waited until panic had already started. A records clerk notices that the official release time was quietly moved hours later in the archive. If she cannot identify who delayed the warning and for whose benefit, the state will write a preventable disaster into history as unavoidable chaos.",
        "风暴预警明明早到了几个小时，城市却是在最混乱的时候才开始疏散。一个负责值守记录的文员发现，原始通报被人压了时间戳。她若不能把这段延迟是谁下令、又替谁争取了时间说清楚，首都就会把本可避免的混乱写成无法避免的天灾。",
    ),
    (
        "Night ferries were halted after a sudden inspection order, cutting the river wards off from the rest of the city after dark. The transit superintendent finds the safety report behind the shutdown was built on falsified signatures and recycled defects. If she cannot reopen the line quickly, the river wards will be governed as a permanent exception zone instead of a temporary inconvenience.",
        "河岸几片街区靠夜渡维持基本通勤，可一纸突然冒出来的安检结论让所有夜班渡船全部停摆。交通总管翻到旧维修单，发现所谓不合格结论和真实检修记录根本对不上。要是她不能尽快恢复夜渡，河岸居民就会被整个城市默认为可以长期舍弃的例外人群。",
    ),
    (
        "The square patrols release only a faceless casualty count after the curfew sweep, while families insist names are already disappearing from the lists. A public ombudsman receives overlapping stop records that suggest the official roll is being cleaned for political safety. If she cannot verify who was stopped, injured, or taken, the crackdown will survive on paper without victims.",
        "宵禁过后，广场巡逻队只肯公布一份没有姓名的伤亡数字。负责公共申诉的官员收到多份互相矛盾的停留记录，发现有人正在把被拦下的人从正式名册里一笔笔抹掉。她必须赶在案卷封存前核实名单，不然谁被拦、为何出事，都会在制度上被宣布从未发生。",
    ),
    (
        "An emergency vote is being rushed into the shape of a lawful succession, and the chamber insists every safeguard was observed. The ballot certifier discovers that the one witness transcript capable of challenging the count has vanished from the official chain. If she cannot restore it before the result is sealed, a temporary compromise will harden into permanent authority.",
        "一次仓促启动的紧急投票，正在被包装成无可争议的权力交接。负责核验选票的官员发现，最关键的一份见证证词突然从归档链里消失了。她若不能在宣告结果前把证词找回来，那场本来只是权宜之计的表决，就会被钉成合法继承。",
    ),
    (
        "Relief convoys are being redirected according to a live heat map that always seems to calm down around politically loyal blocks. The shelter coordinator compares intake logs against the map and realizes the most crowded shelters are being smoothed out on purpose. If she cannot prove the data was manipulated, the next round of aid will bypass the people who actually need it most.",
        "避难安置点的热力图每天都在更新，但负责协调的人很快察觉，最拥挤的区域总在图上被压得格外平静。她怀疑有人篡改了数据，把救济车队故意引向更听话的街区。要是她证明不了热力图被做过手脚，最缺物资的人会在下一轮调度里继续被排除在外。",
    ),
    (
        "A quarantine breach at the docks has already been discovered, but trade brokers are racing to rewrite the chain of approvals before the public sees it. The customs examiner knows the inspection archive is the last clean record tying private pressure to a public failure. If she cannot keep the archive visible, the breach will be rewritten as a worker's mistake instead of a systemic arrangement.",
        "港口的检疫破口已经捅出来了，可商会和航运掮客都在抢着改写谁先放行、谁最后盖章。负责关务核验的人知道，一旦公开检查档案被拿走，整件事就会变成最弱势码头工人的责任。她得守住那批原始记录，才能阻止一次制度性放水被写成个人失职。",
    ),
    (
        "After a fogbound collision, the port is about to close under an emergency order that arrived suspiciously fast. The lighthouse registrar finds the warning lamps were dimmed deliberately during the exact window now cited as proof of danger. If she cannot establish that the darkness was engineered, a forged chain of authority will be enough to seize the harbor.",
        "雾夜里的港口本该靠灯塔警示线维持最低通航，可事故后却冒出一份要求全面封港的紧急授权。灯塔登记官回查值守记录，发现警示灯亮度在关键时段被人故意调低。她若不能证明那不是设备故障，整座港口就会在一纸假命令下被顺势接管。",
    ),
    (
        "Recovery law is moving through the chamber just as displaced families begin to disappear from the housing allocation record. A census advocate discovers that an earlier list included them clearly, but the revision used for compensation quietly removes whole blocks of temporary residents. If she cannot restore the original record, the city will erase them first in paperwork and then in policy.",
        "重建法案快通过了，可一批临时安置家庭却突然从住房分配记录里消失。长期做人口与居住申诉的倡议人发现，最早那版名单曾明确把他们纳入补偿范围。她必须把分配记录恢复出来，不然这些人会在制度文本里被安静地剔除，像从没住过这座城。",
    ),
    (
        "Water ration lines stretch longer every morning, and the official story blames maintenance failures no one can verify. A water-board clerk notices a concealed reservoir transfer that drained supply away from the districts now accused of wasting it. If she cannot expose the hidden diversion, the public will be taught to blame the street instead of the people who moved the water.",
        "城市开始限水后，排队的人都被告知是管线维护出了问题。水务署文员在一笔临时调度单上看见，真正的缺口来自一场从未公开的水库转移。她若不把这笔暗中调水揭开，接下来所有怒火都会被推到最先断供的街区身上。",
    ),
    (
        "The ministry announces that the emergency compact passed with unanimous consent before the hearing record is even complete. A court reporter still holds the redacted page where the most important objection was raised and dismissed. If she cannot publish that missing page, the compact will enter the archive as a consensus that never actually existed.",
        "一场决定城市命运的听证会刚结束，部里立刻对外宣布所有代表一致同意。法庭记录员手里却留着被删掉的一页速记，上面正好记着那次最关键的反对与保留。她若不能把这一页公开出去，整份协定就会在“全票通过”的谎言里生效。",
    ),
    (
        "When the bridge failed, the alarm system stayed silent long enough for military repair teams to arrive as the only ready answer. A signal inspector traces the outage and finds that someone suppressed the bridge alarm rather than missing it. If she cannot prove the silence was deliberate, martial repair powers will become the default answer to every future civic failure.",
        "桥梁险情发生时，警报系统并没有按设计拉响，随后的军管抢修却来得异常迅速。负责信号检查的人怀疑，是有人提前压住了告警，把事故变成接管理由。她要是找不到是谁让警报失声，军事化抢修就会被写成唯一可行的治理方式。",
    ),
    (
        "Hospital allocation software now decides which wards lose beds first, and administrators call the result neutral shortage math. The allocator compares the algorithm against an older triage ledger and realizes the current model hides a political decision inside technical language. If she cannot reopen the ledger, entire districts will be marked disposable by arithmetic no one is allowed to inspect.",
        "医院开始按算法分配急救床位后，几片街区的病人总是最先被挪到名单末尾。负责分配的主管翻到关闭已久的旧分诊账本，发现最初的判定逻辑和现在的缺口计算根本不是一回事。她若不把这本账重新摊开，‘资源最优先’很快就会变成决定谁能被放弃的冷静借口。",
    ),
    (
        "Shortage notices appear across the market overnight, followed immediately by a proposal for a riot tax to restore order. The market steward suspects the grain rolls were altered before the notices ever went up, making the crisis look worse than it is. If she cannot compare the official ledgers in public, hunger, taxation, and repression will be folded into one manufactured necessity.",
        "集市里突然贴出一轮粮食短缺通知，紧跟着就是新的维稳加税方案。负责市场秩序的人怀疑，所谓短缺根本不是库存问题，而是账面被人做了手脚。她必须在众人面前重新核对名册，不然饥饿、加税和镇压会被打包成一套顺理成章的政策。",
    ),
    (
        "The governor is already citing delayed burials as proof that civic order collapsed after the storm. A funeral registrar sees that the death register itself was rearranged, compressing names and dates to make the backlog look like failure rather than neglect. If she cannot correct the record in time, the dead will be used to justify a new round of emergency control.",
        "风暴后的死亡登记本被匆匆整理过一轮，很多名字和安葬时间都开始对不上。负责殡葬登记的人知道，一旦总督把这些延误说成城市失序的证据，接下来就会有更强硬的接管理由。她必须在公开发布前把名册纠正过来，至少让死者不会再被拿来充当政治证据。",
    ),
    (
        "The harbor coalition still calls itself a relief partnership, but more and more cargo moves only through exception permits issued to insiders. A dockside delegate sees that one remaining aid corridor still serves ordinary neighborhoods without tribute or favors. If she cannot keep that route open, the coalition will finish mutating from emergency coordination into a protection racket.",
        "港口联盟嘴上说是联合救援，私下却开始用‘例外许可’给熟人开路。来自码头一线的代表发现，真正还能送物资的只剩一条狭窄走廊。她必须守住这条线，不然联盟很快就会从协作机构变成收保护费的分赃机器。",
    ),
    (
        "A blackout cabinet proposes a sweeping recovery levy and claims the authority was already granted in an emergency charter. The tax notary discovers that the charter being cited is incomplete, patched together, and missing the chain that would make it lawful. If he cannot reconstruct the real levy text, reconstruction will be funded through a forged mandate everyone is told to obey.",
        "停电之后，临时内阁突然提出一项覆盖全城的新征费，说是为了尽快筹钱重建。税务公证人追查源头，发现那份征费章程连授权链都不完整。她若不能把章程原貌重建出来，这场以恢复之名发动的收钱行动就会靠伪造授权顺利落地。",
    ),
    (
        "Troop escorts take control of the freight wards within hours of a derailment that now defines the whole transport emergency. The rail dispatcher notices the timetable around the accident looks staged, with delays arranged too neatly to be organic. If she cannot prove the derailment window was engineered, military escort will stop being temporary assistance and become the governing logic of cargo movement.",
        "铁路脱轨之后，军方护送立刻接管了主要货运线，速度快得像早有准备。调度官回看时刻表和车次记录，发现所谓事故窗口被排得过分整齐。她若不能证明这场脱轨被人为设计过，货运区的治理权很快就会从临时协助变成永久接收。",
    ),
    (
        "Students are protesting vanished meals, but the administration is preparing to frame the unrest as coordinated criminal agitation. The school bursar discovers that the meal rosters were altered before the cuts were announced, hiding how many children were actually removed from support. If she cannot expose the rewritten lists, hunger will be prosecuted as conspiracy instead of acknowledged as policy.",
        "校园里爆发了关于供餐削减的抗议，校方却准备把它直接送进治安调查。负责学校预算和配餐款项的人查到账目时发现，学生餐名单被人改过，真正削掉的远不止公开那部分。她要是揭不开这份被改写的名单，一场因饥饿引发的 protest 会被包装成刑事合谋。",
    ),
    (
        "A citywide outbreak is already being pinned on a single migrant block, even though the contamination chain once pointed somewhere else entirely. The sanitation inspector knows the earlier file was real and knows when it disappeared from circulation. If she cannot reopen the contamination record, the ministry will lock the narrative before anyone can challenge who really spread the disease.",
        "整座城市的疫情正在扩散，部里却急着把源头定在一片移民聚居区。卫生检查官记得，更早的一份污染档案曾指向完全不同的输送链。她若不能把那份档案重新调出来，整个城市都会在一个更容易被牺牲的街区身上完成甩锅。",
    ),
    (
        "Emergency relocation orders along the riverfront are being sold as temporary protection, but the deed archive that could guarantee people a way back has vanished. The land recorder realizes the missing property records are the only barrier between evacuation and legal dispossession. If she cannot recover the archive, temporary safety will harden into permanent removal.",
        "河岸防洪工程刚启动，临时迁移令就已经在逼人搬走。负责地契登记的人发现，整批河岸档案在关键节点被抽离了原库。她若不能把这些地契找回来，眼下打着应急旗号的搬迁，很快就会顺势变成一场永久剥夺。",
    ),
    (
        "Rolling outages are now being described as necessary civic discipline, not as the policy choice they may actually be. A power-grid witness can identify which substations were cut deliberately and which truly failed under strain. If she cannot show the difference before the next briefing, punishment will be sold as maintenance and people will be told to accept it as order.",
        "城市开始轮流停电后，电力部门一直强调这是必要的秩序整顿。可现场见证人知道，有几座变电站不是超载，而是被人刻意切掉。她若不能把这些人为断点指出来，接下来所有停电都会被包装成应该服从的纪律安排。",
    ),
    (
        "Families were locked out of a shelter that still had space, and the mayor is already calling the whole incident a clerical delay. A neighborhood advocate gets hold of the admission list and sees that exclusion was structured, not accidental. If she cannot publish the list before the press cycle closes, a deliberate refusal will be rewritten as administrative inconvenience.",
        "暴雨后的避难所明明还有空位，却有一整批居民被挡在门外。街区倡议人拿到一份内部准入名单，发现和现场说法完全不一样。她若不能尽快公开这份名单，市长就会把一场刻意拒收说成普通的文书延误。",
    ),
    (
        "Fuel convoys are suddenly being prioritized by private risk logic instead of public need, and the published convoy order already looks suspect. A shipping judge finds the actual dispatch sequence differs from the official list in ways that benefit the best-connected districts. If she cannot certify the true convoy order, insurers will quietly decide which parts of the city still deserve to move.",
        "燃料车队进城顺序突然被改了，几家私人保险商开始趁机评估哪些街区值得继续供给。负责航运争议裁决的人发现，官方公布的顺序和实际出港记录并不一致。她若不能确认真正的车队次序，燃料分配就会被私营风控逻辑接管。",
    ),
    (
        "Recovery crews are preparing to erase the old market under emergency law, backed by demolition orders that appeared far too neatly after the disaster. A permits clerk discovers the approvals were backdated to make resistance look unlawful. If she cannot expose the forgery before machinery rolls in, the market will disappear under the paperwork of its own supposed rescue.",
        "旧市场还没从灾后恢复过来，重建队已经拿着紧急拆除令准备进场。一个负责许可归档的文员发现，这批命令全是事后倒签。她若不把时间线揭开，老市场会在‘依法重建’的名义下，被整块从城市地图上抹掉。",
    ),
    (
        "The court is preparing to say no one could have foreseen the storm in time to act, closing the door on accountability before it even opens. A weather observer still has the original forecast, precise enough to show that someone chose not to respond. If he cannot force that first forecast into the official record, negligence will be buried under the language of uncertainty.",
        "灾后问责刚启动，法庭那边已经准备把整件事定成‘无人可能提前预见’。气象观测员却还保留着最早那版明确到小时的原始预报。她必须想办法把它塞进正式记录，不然所有本该承担责任的人都会借这句‘没人知道’安全脱身。",
    ),
    (
        "The compensation register is almost ready for payout, but the public ledger keeper can already see that the losses carried by one set of streets are being reimbursed to a different set of loyal contractors. Once the money moves, the false narrative will be harder to unwind than the fraud itself. She must reconcile the register before the city pays the wrong people for damage others actually absorbed.",
        "灾后赔偿名册已经快走到拨款环节，公共账簿保管人却看出多笔赔付方向明显不对。真正承担损失的街区还在排队，几个和市府关系密切的承包商却先被列进补偿名单。她若不能赶在拨款前把这本账对清，所谓重建补偿就会彻底变成内部输送。",
    ),
)


@dataclass
class _SparkSimulationPool:
    seeds_by_language: dict[ContentLanguage, tuple[str, ...]]
    _rng_by_language: dict[ContentLanguage, Random]
    _queues_by_language: dict[ContentLanguage, deque[str]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def next_seed(self, language: ContentLanguage) -> str:
        with self._lock:
            queue = self._queues_by_language.get(language)
            if not queue:
                queue = deque(self.seeds_by_language[language])
                ordered = list(queue)
                self._rng_by_language[language].shuffle(ordered)
                queue = deque(ordered)
                self._queues_by_language[language] = queue
            if not queue:
                raise RuntimeError(f"simulated spark pool for {language} is empty")
            seed = queue.popleft()
            if not queue:
                ordered = list(self.seeds_by_language[language])
                self._rng_by_language[language].shuffle(ordered)
                self._queues_by_language[language] = deque(ordered)
            return seed


class _AuthorSparkSeedDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_seed: str = Field(min_length=1, max_length=_SPARK_MAX_TOTAL_CHARS)


def _fallback_story_spark(*, language: ContentLanguage = "en", rng: Random | None = None) -> AuthorStorySparkResponse:
    resolved_language: ContentLanguage = "zh" if language == "zh" else "en"
    resolved_rng = rng or Random()
    choices = _curated_seed_texts(resolved_language)
    prompt_seed = choices[resolved_rng.randrange(len(choices))]
    return AuthorStorySparkResponse(
        prompt_seed=prompt_seed,
        language=resolved_language,
    )


def _spark_prompt(language: ContentLanguage) -> tuple[str, str]:
    length_instruction = (
        "Two to four sentences are acceptable. Aim for roughly 55-90 words, and never exceed 100 words."
        if not is_chinese_language(language)
        else "可以写成两到四句，目标大约 80-110 个汉字，总长度不得超过 120 个汉字。"
    )
    base = (
        f"{prompt_role_instruction(language, en_role='a senior story concept editor for civic interactive fiction', zh_role='公共互动叙事的资深选题编辑')} "
        f"{output_language_instruction(language)} "
        "Return strict JSON matching the schema {\"prompt_seed\": string}. "
        "Write a rich but concise story seed for an editorial dossier style civic procedural thriller. "
        "The seed must include: a protagonist identity, a public-pressure situation, and one manipulated, buried, or compromised institutional problem. "
        "Add enough detail to suggest the local setting, the immediate risk, and what becomes irreversible if no one intervenes. "
        "Keep it grounded in records, authorization, public order, logistics, testimony, or civic legitimacy. "
        "Avoid romance-first, school-life, light comedy, generic fantasy adventure, criminal power fantasy, and open-world sandbox framing. "
        f"{length_instruction} "
        "No markdown, no explanation, no lists, no meta wrapper."
    )
    repair = (
        base
        + " Repair invalid output by returning only JSON with one prompt_seed string that stays inside the same civic procedural genre."
    )
    return base, repair


def _normalize_prompt_seed_text(prompt_seed: str, *, language: ContentLanguage) -> str:
    normalized = normalize_whitespace(prompt_seed)
    if not normalized:
        raise ValueError("prompt_seed is required")
    sentences = [part for part in _SENTENCE_SPLIT_PATTERN.split(normalized) if part.strip()]
    if len(sentences) > _SPARK_MAX_SENTENCES:
        raise ValueError("prompt_seed must be 1-2 sentences")
    if is_chinese_language(language):
        visible_chars = len(re.sub(r"\s+", "", normalized))
        if visible_chars > _SPARK_MAX_CHINESE_CHARS:
            raise ValueError(f"prompt_seed must be at most {_SPARK_MAX_CHINESE_CHARS} Chinese characters")
    else:
        word_count = len(_ENGLISH_WORD_PATTERN.findall(normalized.casefold()))
        if word_count > _SPARK_MAX_ENGLISH_WORDS:
            raise ValueError(f"prompt_seed must be at most {_SPARK_MAX_ENGLISH_WORDS} words")
    if len(normalized) > _SPARK_MAX_TOTAL_CHARS:
        raise ValueError(f"prompt_seed must be at most {_SPARK_MAX_TOTAL_CHARS} characters")
    return normalized


def _normalize_spark_payload(payload: dict[str, object], *, language: ContentLanguage) -> _AuthorSparkSeedDraft:
    prompt_seed = str(payload.get("prompt_seed") or payload.get("seed") or "").strip()
    if not prompt_seed:
        raise ValueError("prompt_seed is required")
    return _AuthorSparkSeedDraft(
        prompt_seed=_normalize_prompt_seed_text(prompt_seed, language=language),
    )


def _curated_seed_texts(language: ContentLanguage) -> tuple[str, ...]:
    resolved_language: ContentLanguage = "zh" if language == "zh" else "en"
    index = 1 if resolved_language == "zh" else 0
    return tuple(
        _normalize_prompt_seed_text(pair[index], language=resolved_language)
        for pair in _CURATED_SPARK_SEED_PAIRS
    )


def _build_simulated_seed_pool(*, language: ContentLanguage, seed_count: int, rng_seed: int) -> tuple[str, ...]:
    curated = list(_curated_seed_texts(language))
    if seed_count > len(curated):
        raise RuntimeError(f"unable to build {seed_count} simulated spark seeds for {language}; only {len(curated)} curated seeds available")
    rng = Random(rng_seed)
    rng.shuffle(curated)
    return tuple(curated[:seed_count])


def _build_simulation_pool(settings: Settings) -> _SparkSimulationPool:
    seed_count = settings.resolved_author_spark_simulation_seed_count()
    base_seed = settings.resolved_author_spark_simulation_rng_seed()
    return _SparkSimulationPool(
        seeds_by_language={
            "en": _build_simulated_seed_pool(language="en", seed_count=seed_count, rng_seed=base_seed),
            "zh": _build_simulated_seed_pool(language="zh", seed_count=seed_count, rng_seed=base_seed + 1),
        },
        _rng_by_language={
            "en": Random(base_seed + 101),
            "zh": Random(base_seed + 202),
        },
    )


_SIMULATION_POOLS: dict[tuple[int, int], _SparkSimulationPool] = {}
_SIMULATION_POOLS_LOCK = Lock()


def _get_simulation_pool(settings: Settings) -> _SparkSimulationPool:
    key = (
        settings.resolved_author_spark_simulation_seed_count(),
        settings.resolved_author_spark_simulation_rng_seed(),
    )
    with _SIMULATION_POOLS_LOCK:
        pool = _SIMULATION_POOLS.get(key)
        if pool is None:
            pool = _build_simulation_pool(settings)
            _SIMULATION_POOLS[key] = pool
        return pool


def _simulated_story_spark(
    *,
    language: ContentLanguage,
    settings: Settings,
    sleep_fn: Callable[[float], None],
) -> AuthorStorySparkResponse:
    resolved_language: ContentLanguage = "zh" if language == "zh" else "en"
    delay_rng = Random()
    delay_min = settings.resolved_author_spark_simulation_delay_min_seconds()
    delay_max = settings.resolved_author_spark_simulation_delay_max_seconds()
    delay_seconds = delay_rng.uniform(min(delay_min, delay_max), max(delay_min, delay_max))
    if delay_seconds > 0:
        sleep_fn(delay_seconds)
    prompt_seed = _get_simulation_pool(settings).next_seed(resolved_language)
    return AuthorStorySparkResponse(
        prompt_seed=prompt_seed,
        language=resolved_language,
    )


def _llm_story_spark(
    gateway: CapabilityGatewayCore,
    *,
    language: ContentLanguage = "en",
) -> StructuredResponse[_AuthorSparkSeedDraft]:
    prompts = _spark_prompt(language)
    role_style, _role_context = build_role_style_context(
        language=language,
        en_role="a senior story concept editor for civic interactive fiction",
        zh_role="公共互动叙事的资深选题编辑",
    )
    payload = {
        "language": language,
        "brand_direction": localized_text(
            language,
            en="editorial dossier, civic procedural thriller, public consequence",
            zh="社论档案式包装、公共程序惊悚、强调公共后果",
        ),
    }
    skill_packet = GenerationSkillPacket(
        skill_id="author.spark.seed",
        skill_version="v1",
        capability="author.spark_seed_generate",
        contract_mode="strict_json_schema",
        role_style=role_style,
        required_output_contract='Return exactly one JSON object with key "prompt_seed".',
        context_cards=(
            ContextCard("brief_card", {"language": language}, priority=10),
            ContextCard("theme_card", {"brand_direction": payload["brand_direction"]}, priority=20),
        ),
        task_brief=prompts[0],
        repair_mode="schema_repair",
        repair_note=prompts[1] if len(prompts) > 1 else "Repair invalid output by returning only JSON with one prompt_seed string.",
        final_contract_note=prompts[2] if len(prompts) > 2 else "Return raw JSON only.",
        extra_payload=payload,
    )
    return invoke_structured_generation_with_retries(
        gateway,
        capability="author.spark_seed_generate",
        primary_payload=payload,
        prompts=prompts,
        previous_response_id=None,
        max_output_tokens=gateway.text_policy("author.spark_seed_generate").max_output_tokens,
        operation_name="spark_seed_generate",
        skill_packet=skill_packet,
        parse_value=lambda raw_payload: _normalize_spark_payload(raw_payload, language=language),
    )


def build_story_spark(
    *,
    language: ContentLanguage = "en",
    gateway: CapabilityGatewayCore | None = None,
    rng: Random | None = None,
    settings: Settings | None = None,
    sleep_fn: Callable[[float], None] = sleep,
) -> AuthorStorySparkResponse:
    resolved_settings = settings or get_settings()
    resolved_language: ContentLanguage = "zh" if language == "zh" else "en"
    if resolved_settings.resolved_author_spark_mode() == "simulated_pool":
        return _simulated_story_spark(
            language=resolved_language,
            settings=resolved_settings,
            sleep_fn=sleep_fn,
        )
    if gateway is None:
        return _fallback_story_spark(language=resolved_language, rng=rng)
    try:
        result = _llm_story_spark(gateway, language=resolved_language)
        return AuthorStorySparkResponse(
            prompt_seed=result.value.prompt_seed,
            language=resolved_language,
        )
    except AuthorGatewayError:
        return _fallback_story_spark(language=resolved_language, rng=rng)

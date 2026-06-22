# Tiny Stories

<p align="center">
  <img src="./docs/demo-video/admissions-trailer-contact.jpg" alt="Tiny Stories 招生 demo contact sheet：product UI and reviewer evidence" width="100%" />
</p>

<p align="center">
  <strong>一个可检查的 AI 互动短剧 · An inspectable AI interactive story</strong>
</p>

<p align="center">
  移动端短篇互动剧情:先读场景 · 比较少量选择 · 行动一次 · 跟随后果 · 可分享结局 / replay
</p>

<p align="center">
  <strong>中文</strong> · <a href="./README.md">English</a> ·
  <a href="./docs/CURRENT_SYSTEM_MAP.md">Current System Map</a> ·
  <a href="./docs/CASE_STUDY.md">Case Study</a> ·
  <a href="./docs/PROJECT_PAUSE_2026-05-09.zh.md">项目暂停 memo</a> ·
  <a href="./ARCHITECTURE.zh.md">Architecture deep-dive</a> ·
  <a href="./CONTRIBUTING.zh.md">Contributing</a> ·
  <a href="./docs/devlog/2026-05-tiny-stories-9-mechanisms.zh.md">Design devlog</a> ·
  <a href="./docs/GOOD_FIRST_ISSUES.zh.md">Good first issues</a>
</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg" />
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-blue.svg" />
  <img alt="React 19" src="https://img.shields.io/badge/react-19-61dafb.svg" />
  <img alt="Status: portfolio case study" src="https://img.shields.io/badge/status-portfolio_case_study-6f42c1.svg" />
</p>

---

## 项目状态

当前请把 Tiny Stories 读作 **portfolio-grade AI product-system evidence**:
它证明的是类型化契约、持久化游玩记录、可检查评审路径、移动端可用的
游玩 / 回放 / 结局闭环,不是已经验证过的消费级游戏或大规模用户增长案例.

2026-05-09 的 [项目暂停 memo](./docs/PROJECT_PAUSE_2026-05-09.zh.md)
仍然是重要边界:真实用户需求、复玩、留存和自然分享没有被证明.当前英文主路径以
[README](./README.md)、[Current System Map](./docs/CURRENT_SYSTEM_MAP.md)
和 [Case Study](./docs/CASE_STUDY.md) 为准.下一层验证应按
[真实用户测试模板](./docs/playtest_report.md) 记录:玩家是否理解剧情、是否有选择信心、
是否看懂后果、移动端 UI 是否舒服、以及是否产生复玩/分享意愿.

## Demo

- [观看 75 秒 demo](https://youtu.be/RRJ7uyjW_nA)
- [打开 MP4 备份](./docs/demo-video/tiny-stories-admissions-demo-readme.mp4)
- [公开链接检查通过后再打开 GitHub Pages 展示页](https://lishehao.github.io/RPG_Demo/)

视频用于快速理解玩家看到的 loop;真正的申请材料证据仍然在 source、tests、
`#/portfolio`、`#/reviewer`、system map 和 engineering evidence packet 里.

如果要把公开链接发给招生、推荐人或招聘 reviewer,先运行公开链接检查:
`python3 tools/portfolio_public_evidence_preflight.py`.如果它提示本地 `HEAD`
领先 `origin/main`,或 GitHub Pages 缺少当前 marker,这些证据只能算
local-only.这包括 Story Desk、template detail、portfolio/reviewer 和 play
路径的本地改动.它会先汇总受影响的 reviewer surface,再列路径,避免本地分支很大时
template 或 Story Desk 变化被截断输出藏掉.直到目标分支 push、部署并重新检查通过,
才适合作为公开申请材料证据.

## 申请 / 作品集审阅路径

如果你是招生、推荐人或招聘 reviewer,推荐顺序是:

1. 先看 75 秒 demo,理解玩家看到的 loop.
2. 本地运行后打开 `#/portfolio`,看 guided case-study surface.
3. 从 portfolio 打开 reviewer run (`#/reviewer`),检查 locked seed、状态/后果证据钩子、
   replay / ending path.
   四个检查点要保持一致:可游玩状态、一次行动后的后果、证据边界、回放作品.
4. 如果需要稳定检查 Story Desk populated card 到首回合的入口体验,本地打开
   `#/qa/home-start`;这只是 local QA evidence,不要当作公开链接证据.
5. 如果需要稳定检查已完成局的回放作品,本地打开 `#/qa/replay`;
   这只是 local QA evidence,不要当作公开链接证据.
6. 再读 [Current System Map](./docs/CURRENT_SYSTEM_MAP.md)、
   [Case Study](./docs/CASE_STUDY.md)、
   [Engineering Evidence Packet](./docs/tiny-stories-engineering-evidence-packet.md)
   和对应 tests,确认哪些 claim 有 source evidence,哪些还只是下一步验证.

---

## 目标玩家 / 内容消费模型

Tiny Stories 面向的是想在移动端玩一段短篇互动剧情的 story-first player,
不是空白写作工具用户、无限小说流用户或系统 dashboard 用户.理想消费节奏是:
先读当前场景,比较少量但有意义的选择,行动一次,看清后果,再用这个后果进入
下一步选择.

这也是 UI 判断的来源:普通 Play 页面要把剧情上下文和决策上下文放近;选中的
行动要保留"为什么现在能做这步";内心动机要贴在已选行动上;评审证据则必须
留在普通玩家界面之外.

---

## TL;DR

你写一句故事开头.Tiny Stories 会把它整理成一个可玩的短篇互动剧:
角色身份、目标/资产、当前场景、少量有意义的选择、一次行动后的后果,
以及**可复制分享的结局标签** / 回放作品.

> 这不是聊天 bot,不是无穷模拟,是一个**有结构、有结局、可检查证据边界**的短剧引擎.

```
seed → 故事计划 → role + scene + choices
   ↓ each turn ↓
   读场景 → 选/写一次行动 → 看后果 → 带着后果进入下一步
   ↓ ending ↓
   ending + highlights/replay + reviewer 可检查证据边界
```

**这是给做 LLM-driven 产品的人的 portfolio case study**,不是给终端用户的 SaaS.
申请材料价值不在于声称已经有 consumer traction,而在于可运行的 player loop、
类型化契约、持久化游玩记录、评审证据和回放作品能互相对上.
读懂这个 repo 你能拿到的:结构化 prompt design、scheduler-driven LLM control
和跨层契约设计这一套实战 pattern.

---

## 它是什么

你写一句故事的开头(豪门年夜饭 / 颁奖礼上的爆料 / 婚礼前夜的电话…),
系统先整理故事计划,再生成可选身份、目标/资产、当前场景和首轮选择.

你选一个身份进入后,每回合先读场景,再从少量选择、自由行动或内心动机里
提交一个动作,随后看到后果和下一步菜单.后端把角色目标、leverage/inventory、
人物压力、行动后果和 ending/replay 串起来;前端把这些机制翻译成移动端可读的
scene → choice → consequence → replay flow.

完局后生成结局、highlight/replay 和 branch 信息,可以复制分享链接或回到
同一个 opening 重新开局.具体机制和数量边界放在下面的架构章节里,不把它们当作
已经验证过的消费级增长证据.

> **Status:** portfolio case study / open-source preview.机制链路完整,但
> **真人测试数据仍不是已证明的 consumer traction**.如果你 fork 跑起来玩了一局,
> 请按 [playtest report 模板](./docs/playtest_report.md) 记录剧情理解、选择信心、
> 反馈清晰度、移动端 UI 感受和复玩/分享意愿,不要把一次好评当作验证结论.

---

## 60 秒 Quickstart

需要:Python 3.11+ / Node 18+ / 一个 OpenAI 兼容 API key (DashScope / OpenAI / 本地 Ollama 都行).

```bash
# 1. 后端依赖
python3 -m pip install -e ".[dev]"

# 2. 配置 LLM endpoint
cp .env.example .env
# 编辑 .env,至少填:
#   APP_RESPONSES_PLAY_BASE_URL=...
#   APP_RESPONSES_PLAY_API_KEY=sk-...
#   APP_RESPONSES_PLAY_MODEL=...

# 3. 起后端 (port 8000)
uvicorn rpg_backend.main:app --host 127.0.0.1 --port 8000 --reload

# 4. 起前端 (新终端,port 8001,自动 proxy 到 8000)
cd frontend2
npm install
npm run dev
```

打开 `http://127.0.0.1:8001`.注册一个用户名 → 创建一个故事 → 选 role → 玩.

> **第一次创建模板** 会调 LLM 生成 opening + cast + roles + failure conditions + inter-NPC leverage 网络,大约 12-20 秒(qwen-flash class 模型).每回合推进约 5-8 秒.

---

## 架构 / 9 个机制

完整说明见 [ARCHITECTURE.zh.md](./ARCHITECTURE.zh.md).精简版:

```
opening 阶段:
  generate_opening
  → cast (含 hidden_objective + leverage_over_player + leverages_over_other_npcs)
  → 3-5 张 PlayerRole 卡 (含 hidden_objective + leverages_over_npcs + starting_assets)
  → player_goals + failure_conditions

每回合 advance_turn:
  ① _pick_npc_agenda      (gauntlet stage 调度 NPC 主动出招)
  ② _pick_twist_directive (reversal 强制翻转: leverage 揭穿 / 倒戈 / persona crack / 外人介入)
  ③ compute_current_inventory (walk-on-read,starting_assets + Σdeltas)
  ④ _summarize_recent_consequences (last_player_action + npc_pulse_trend + unused_leverage)
  ⑤ LLM compose 一段 200-400 字 narration + 3 个带 [intent tag] 选项
  ⑥ 输出: passage / options / npc_pulse[shift+reason] / inventory_delta

每回合 judge_failure (gauntlet only):
  → 触发某条 failure_condition → synthesize_early_ending (collapsed)

完局 _finalize_session:
  ⑦ synthesize_ending      (15 ending labels closed pool)
  ⑧ synthesize_highlights  (5 张关键时刻)
  ⑨ synthesize_branches    (2-3 张 "你没走的路" + alternate ending label)
```

加上视觉层:3-tier ending splash / peak close-up rotation / stage progression bar / pulse legend / oracle vignette.

---

## 项目结构

```
rpg_backend/             FastAPI + Pydantic + SQLite,核心目录
  narrative/             ← 9 个机制都在这里
    contracts.py         所有 Pydantic 类型 (单一真值源)
    engine.py            LLM prompts + scheduler + parser (~2200 行)
    repository.py        SQLite + idempotent migrations
    service.py           HTTP-side 业务流
    gateway.py           OpenAI-compatible LLM 客户端封装
  main.py                FastAPI app + routes
  auth/                  cookie session
  config.py              pydantic-settings,所有 APP_ 环境变量

frontend2/               React 19 + TypeScript + Vite,主前端
  src/api/contracts.ts   后端契约的 TS 镜像
  src/pages/play/        Play 容器 + StoryBeat / ActionArea / Advisor / Ending 等模块
  src/shared/ui/         StageProgressBar / LoadingShim / EmptyState
  src/shared/lib/        webtoon-assets, motion-presets
  public/webtoons/       AI-生成视觉素材 (10 shells / 20 avatars / 5 peaks / etc)

frontend/                旧前端 (legacy, 不再维护),保留供对照
specs/                   产品/设计文档
deploy/aws_ubuntu/       单机部署示例 (nginx + systemd)
tests/                   pytest (主要覆盖旧 author 模块,narrative 模块靠 LLM smoke)
```

---

## 试一下机制

后端跑起来后,无需前端,直接验证 LLM smoke:

```bash
# 生成一个故事 + 9 张牌全部就位
python -c "
from rpg_backend.narrative import engine
from rpg_backend.narrative.gateway import get_narrative_gateway
gw = get_narrative_gateway()
op = engine.generate_opening(gateway=gw, seed='豪门年夜饭你回到家,妻子笑得太多')
print(f'Title: {op.title}')
print(f'NPCs: {len(op.cast)} | Roles: {len(op.player_role_options)} | Inter-NPC edges: {sum(len(c.leverages_over_other_npcs) for c in op.cast)}')
"
```

---

## 配置

所有可调参数在 `rpg_backend/config.py`,通过 `APP_` 前缀环境变量覆盖.最小所需见 `.env.example`.

LLM endpoint 是唯一必填项 — 任何 OpenAI-compatible API 都能跑,包括本地 Ollama / vLLM / SGLang.

---

## 开发

```bash
# 后端类型检查 + 单测
python3 -m pytest -q

# 前端类型 + 生产构建
cd frontend2
npm run check        # tsc --noEmit
npm run build        # vite build
```

无 ruff / eslint / prettier — 质量门是 TypeScript strict + pytest.

如果 LLM 生成的 narration 看起来有问题,先看 `rpg_backend/narrative/engine.py` 里的 prompt(`_TURN_SYSTEM_PROMPT` / `_OPENING_SYSTEM_PROMPT` 等);改 prompt 比改代码常见.

---

## Roadmap

短期(open-source preview 期):
- [ ] CI 跑 pytest + frontend type-check
- [ ] 真人内测 5-10 人,看 share intent 数据
- [ ] 基于反馈决定第三轮机制 polish 方向

中期:
- [ ] 流式 narration (打字机效果)
- [ ] 持久化 in-game HUD (玩家随时看 leverage map)
- [ ] 多 LLM provider 混合调度 (敏感 prompt 走低成本 model)

长期:
- [ ] 多人异步博弈 (玩家 A 完成一局,玩家 B 接手对手 NPC)
- [ ] 玩家自定义 ending pool

---

## License

MIT — see [LICENSE](./LICENSE).视觉素材也在 MIT 范围内 (AI 生成,无第三方版权).

---

## 贡献

PR 欢迎.结构性改动建议先开 issue 讨论方向.特别欢迎:
- 新 LLM provider 适配 (gemini-compat / claude-compat 等)
- 真实玩家测试反馈 (open issue 描述你这一局发生了什么 + 体感)
- prompt 调优 (基于实测发现某个 prompt 输出不稳定时)

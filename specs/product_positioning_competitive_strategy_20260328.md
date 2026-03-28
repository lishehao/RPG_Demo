# RPG_Demo 产品定调与竞争力策略

本文件回答两个问题：

- `这个项目对产品用户到底是什么？`
- `它相比常见 AI 故事/角色扮演产品，真正的竞争力在哪里？`

这不是投资 pitch，也不是简历版技术复盘，而是一份面向产品用户的对外叙事底稿。

## 事实锚点

本文件所有结论只建立在当前仓库已存在的真实能力上，不做超前承诺。

- 题材与品牌真相：`specs/brand_genre_positioning_20260326.md`
- 产品主链：`README.zh.md`
- 最新真实 benchmark：`artifacts/benchmarks/resume_trace_eval_20260327_234954.json`

最新 benchmark 中，当前可直接引用的产品级证据为：

- `10 stories x 5 personas = 50 sessions`
- `50/50 completed`
- `judge_nonfallback_rate = 100%`
- `agent_trace_coverage_rate = 100%`
- `play_trace_coverage_rate = 100%`
- `render_fallback_rate = 1.0%`

## 一句话定位

`RPG_Demo 不是一个让 AI 随便编故事的工具，而是一款让你进入、编辑、推进并验证公共危机叙事的互动 dossier。`

更短版本：

`一款可编辑、可推进、可验证的互动叙事产品。`

更完整版本：

`一款围绕公共记录、制度压力与城市危机构建的 playable dossier；它不是一次性生成内容，而是把 author -> play 做成了可进入、可编辑、可回看、可验证的完整体验闭环。`

## 用户价值主张

RPG_Demo 给用户的不是“一段 AI 写出来的故事”，而是一套可以进入并施加影响的局势。

用户拿到的是：

- 一个已经被组织成 `story seed -> preview -> author -> publish -> play` 的可玩闭环
- 一个可以通过 Author Copilot 修改人物、剧情、结局倾向与玩法规则的编辑系统
- 一个带状态、反馈、后果与结局判断的 play runtime
- 一个已经可以被验证和回看的产品，而不是只靠截图证明“模型这次写得不错”

用更直接的话说：

- `不是只给你一段故事，而是给你一套可推进的局势`
- `不是黑盒续写，而是可编辑、可回看、可验证的叙事流程`
- `不是纯陪聊角色，而是有记录、后果、秩序压力和公开代价的互动世界`

## 它是什么 / 不是什么

### 它是什么

- `可编辑、可验证的互动叙事产品`
- `围绕公共危机与制度压力展开的 playable dossier`
- `把 authoring、runtime 和 evaluation 做成一个系统的 AI 产品`

### 它不是什么

- 不是泛题材故事引擎
- 不是“AI RPG 平台”这种过宽、不可验证的表述
- 不是通用角色扮演聊天或陪聊产品
- 不是一次性 prompt 成功就算成立的 demo
- 不是主要卖恋爱、成长、爽点或开放沙盒 improvisation 的体验

## 目标用户与使用场景

### 目标用户

当前最适合的产品用户不是“想和角色闲聊的人”，而是以下两类：

- `想进入一个有结构、有代价、有公共后果的互动世界的人`
- `想在 AI 生成基础上继续编辑、修改并验证结果的人`

他们通常想要的不是无限自由，而是：

- 更清晰的局势
- 更可感知的后果
- 更强的世界一致性
- 更低的“这只是模型乱编”的不信任感

### 核心使用场景

- 用户先从故事 seed 或 preview 感知题材和冲突，再进入可玩的 session
- 用户在玩之前或玩的过程中，可以用 Copilot 对故事方向做调整
- 用户推进剧情时，看到的是带反馈和代价的 runtime，而不是只拼接下一段 prose
- 团队或高级用户可以回看 benchmark 与 trace，判断这个系统是不是在稳定地产生“可玩的局”

## 竞争对手分组与差异化

不要把所有竞品混成一类。RPG_Demo 的竞争关系要分开讲。

### 1. AI 故事生成器

典型优势：

- 出稿快
- 上手门槛低
- 展示“模型会写”很直接

典型短板：

- 结果不可玩
- 生成后很难继续做结构化编辑
- 很少有 runtime、状态、可回看后果
- 很少有真实评测闭环

RPG_Demo 的差异：

- 不止生成故事，而是把故事做成可进入、可推进的局势
- 不止“改 prompt”，而是允许在结构层继续编辑
- 不止看文本质量，而是看整个 author -> play 链路是否稳定成立

### 2. 角色扮演 / 陪聊产品

典型优势：

- 情绪陪伴强
- 人物关系反馈即时
- 使用门槛低

典型短板：

- 更偏私人情绪驱动
- 公共系统、程序压力和制度后果很弱
- 世界状态常常依赖即兴维持，缺少闭环和验证

RPG_Demo 的差异：

- 冲突核心不是私人情绪，而是公共记录、授权、配给、见证与秩序
- 不是主要卖“角色陪伴”，而是卖“公共系统如何在压力下给出答案”
- runtime 有状态与后果，不是只看角色回复像不像人

### 3. IF / RPG Maker / Authoring 工具

典型优势：

- 作者控制力强
- 世界和流程可以手工搭建
- 更适合精细 authoring

典型短板：

- AI 协作编辑链路通常不是原生能力
- authoring 与 play 往往分离
- 质量验证多靠人工试玩，不靠结构化 benchmark

RPG_Demo 的差异：

- 原生支持 Author Copilot 编辑链路
- authoring 和 play runtime 本来就在一个产品闭环里
- 评测已经接到主链，不是事后补的脚本

### 4. AI Dungeon / DM 类体验

典型优势：

- improvisation 强
- 开放感强
- 即时反馈自然

典型短板：

- 容易跑向“能接但不稳”
- 结构稳定性和可追溯性弱
- 很难解释某一局为什么成功或失败

RPG_Demo 的差异：

- 不追求无限自由，而追求“局势可玩、后果可感、质量可解释”
- 有明确 runtime stage、结局判断与 trace
- 真正的优势不是写得更狂，而是系统更闭环

## 四条核心竞争力

### 1. 完整工作流

RPG_Demo 的第一竞争力不是“模型会写”，而是：

`从 story seed 到 preview、author、publish、play，这是一条真正被做成系统的主链。`

用户能感知到的价值是：

- 不是一段孤立文本
- 不是 demo 拼接
- 是一个可以从创作走到游玩的完整体验

### 2. 可控编辑

RPG_Demo 的第二竞争力是：

`Copilot 不是直接覆写内容，而是给出结构化建议、预览 diff、应用/撤销。`

这意味着：

- 用户可以修改人物、剧情、结局倾向、玩法规则
- 修改不是黑箱替换
- 编辑过程可控、可回退、可对比

这比“再输一版 prompt 试试”高一个产品层级。

### 3. 状态化运行时

RPG_Demo 的第三竞争力是：

`Play 不是聊天，而是 runtime。`

具体体现在：

- 有 session
- 有状态反馈
- 有后果累积
- 有结局判断
- 有 checkpoint / 恢复能力

用户真正感知到的是：这个世界不是只会回一句话，而是在持续结算你的选择。

### 4. 可验证质量

RPG_Demo 的第四竞争力是：

`它已经有一套真实跑通的 LLM-as-a-Judge + Trace-based Evaluation。`

这不是内部花活，而是一个非常稀缺的产品信号：

- 说明产品质量不是靠截图证明
- 说明失败可以定位，而不是只能靠感觉
- 说明内容、runtime 和 evaluation 已经形成闭环

对用户来说，这可以翻译成一句最重要的话：

`它不是偶尔成功的 prompt，而是一条稳定可跑、可解释、可持续变好的产品链路。`

## 竞争力主叙事

推荐默认使用下面这句，作为所有对外介绍的骨架：

`真正的优势不在“模型会写”，而在“内容、运行时和评测已经被做成一个闭环系统”。`

展开时按下面顺序说：

1. 它是一个围绕公共危机叙事的互动 dossier
2. 它有完整的 author -> play 工作流
3. 它支持可控编辑，不是黑盒覆写
4. 它有状态化 runtime，不是普通聊天
5. 它已经有真实 benchmark 和 trace 证明产品质量

## 证据清单

以下证据是当前最适合直接引用的产品级信号。

### 工作流与运行时证据

- `story seed -> preview -> author -> publish -> play` 主链已打通
- `author job / play session / checkpoint` 支持跨重启恢复
- play runtime 已拆成 `interpret -> ending judge -> pyrrhic critic -> render`

### 真实评测证据

来自 `artifacts/benchmarks/resume_trace_eval_20260327_234954.json`：

- `10 stories x 5 personas = 50 sessions`
- `50/50 completed`
- `judge_nonfallback_rate = 100%`
- `agent_trace_coverage_rate = 100%`
- `play_trace_coverage_rate = 100%`
- `render_fallback_rate = 1.0%`
- `median_first_submit_turn_seconds = 11.724s`

### 对用户最有解释力的翻译

- `50/50 completed`
  - 整条游玩链路稳定可跑，不是偶尔成功的 prompt
- `judge non-fallback 100%`
  - 质量判断链路本身可用，不靠人工硬看
- `trace coverage 100%`
  - 问题能定位、可解释、可迭代
- `render fallback 1.0%`
  - 最终叙事文本稳定性已经接近可控

## 用词边界

### 建议说

- `可编辑、可验证的互动叙事产品`
- `围绕公共危机与制度压力展开的 playable dossier`
- `完整的 author -> play 体验闭环`
- `状态化 runtime`
- `LLM-as-a-Judge + Trace-based Evaluation`

### 不建议说

- `AI RPG 平台`
- `通用故事引擎`
- `开放式角色扮演聊天`
- `泛题材内容产品`
- `主要是陪聊 / 情绪陪伴`

### 术语翻译原则

不要把工程词直接甩给用户。

- `trace`
  - 优先翻成 `可追溯记录` / `可解释链路`
- `fallback`
  - 优先翻成 `兜底机制` / `异常恢复`
- `schema`
  - 不直接说，改说 `结构化约束`
- `runtime`
  - 对外可说 `运行中的故事系统` / `状态化游玩系统`

## 可直接复用的话术

### 首页 Hero 候选

- `进入一场会留下记录与后果的公共危机叙事。`
- `不是让 AI 随便编故事，而是让你推进一套可验证的互动局势。`

### 项目页 Summary 候选

`RPG_Demo 是一款围绕公共记录、制度压力与城市危机构建的互动叙事产品。它把故事生成、AI 编辑、状态化游玩运行时与真实评测闭环接在一起，让用户拿到的不只是一段故事，而是一套可进入、可推进、可回看、可验证的局势。`

### 面试 / 对外介绍 30 秒版

`RPG_Demo 不是通用 AI 写故事工具，而是一款可编辑、可验证的互动叙事产品。它的核心优势是把 author -> play 做成了完整工作流，同时有 Copilot 编辑链路、状态化 runtime，以及真实的 LLM-as-a-Judge + trace-based evaluation 去验证质量。`

### 2 分钟版

`我们没有把这个项目做成泛题材故事引擎，而是收口在 editorial dossier 风格的 civic procedural thriller。用户不是只拿到一段 AI 生成的故事，而是拿到一个可以进入、推进、承担后果的局势。系统从 story seed 到 preview、author、publish、play 是完整打通的。Author Copilot 让修改人物、剧情、结局倾向和玩法规则变成结构化编辑，而不是黑盒覆写。Play 端不是陪聊，而是有状态、反馈和结局判断的 runtime。更重要的是，这条链路已经接上了真实 benchmark；我们最近一轮本地评测跑了 10 stories x 5 personas，共 50 个 session，全量完成，judge 和 trace 覆盖都是 100%。所以这个项目的竞争力不在“模型会写”，而在“内容、运行时和评测已经做成了闭环系统”。`

### 5 分钟版提纲

1. 先讲它不是泛故事引擎，而是公共危机叙事产品
2. 再讲完整主链：seed -> preview -> author -> publish -> play
3. 再讲 Copilot：结构化编辑、预览、应用/撤销
4. 再讲 play runtime：状态、反馈、结局判断、恢复
5. 最后讲 benchmark：LLM-as-a-Judge + Trace-based Evaluation，说明为什么这不是 demo，而是可验证系统

## 最终收口

如果只能留下一句话，推荐保留这一句：

`RPG_Demo 的竞争力不在“AI 会写故事”，而在“它把互动叙事的内容、运行时和评测做成了一个可编辑、可验证的闭环系统”。`

# Play Ending Text Recommendations

本文件是给后端的文风与文本整改 handoff，不涉及前端实现。

目标不是改 UI，而是修正当前 `play` 文本里两个已经会直接伤害产品质感的问题：

- narration 穿帮
- ending 文案过薄

## 当前问题

### 1. Render narration 穿帮

当前真实 completed / active session 中仍能看到：

- `Here is the JSON requested`
- `Here is the JSON requested: Proof moved into the open.`

这类文本会直接击穿产品气质。它不是“小瑕疵”，而是让整个 dossier 体验掉回调试界面。

从产品感受上说，这类文本的问题有三层：

- 它不是叙事
- 它不是制度结果
- 它暴露了 transport / wrapper / prompt protocol

因此它必须被视为阻塞级文本污染。

### 2. Ending summary 过薄

当前前端只拿到：

- `ending.label`
- `ending.summary`

而 `ending.summary` 往往只有一句 ending 类型解释，例如：

- `Success arrives only through a steep civic or personal cost.`

这只能说明“pyrrhic 是什么”，但还不能说明：

- 这局到底保住了什么
- 这局到底失去了什么
- 为什么是这个 ending，而不是别的
- 这份结果在公共世界里留下了什么余震

从产品体验上，这让 completed session 没有真正的收束感。

## 后端整改建议

### A. narration 输出必须彻底去 meta-wrapper

后端必须保证任何用户可见 narration 都不包含：

- `Here is the JSON requested`
- `Here is the requested JSON`
- `requested output`
- `````json`
- 任何 “下面是你要的格式化输出” 一类 meta wrapper

建议执行方式：

- 在 render 结果进入 state/history 前，增加一层 final narration sanitizer
- sanitizer 要做的不是轻微 trim，而是明确剥离 transport/meta wrapper 句子
- 如果剥离后剩余文本过短、像 consequence slogan、或仍不成文，则直接触发 fallback narration 重建

具体判断建议：

- 若 narration 命中 meta markers，直接视为无效输出
- 若 narration 清洗后低于一个最小 word-count 阈值，也视为无效输出
- 若 narration 只是 consequence 复述而不是 scene narration，也视为无效输出

### B. ending summary 必须从“定义句”升级为“结果句”

ending 文案必须像 verdict，而不是 taxonomy description。

后端应该优先输出这种信息结构：

- `outcome_statement`
  - 一句话说清本局最终结果
- `what_saved`
  - 保住了什么
- `what_broke`
  - 损坏了什么
- `civic_cost_summary`
  - 公共代价是什么
- `institutional_aftertaste`
  - 这份结果在制度上留下了什么后味

如果这轮不想改 contract，也至少要把 `ending.summary` 本身改写成：

- 不是 ending 类型释义
- 而是带有 story-specific 的结果判断句

### C. 三类 ending 的句法要明确区分

#### collapse

应强调：

- 系统失手
- 公共协调断裂
- 压力超过可治理阈值

句法建议：

- 更像崩断判词
- 更像记录“哪里失守了”
- 不要写成普通失败标签说明

#### pyrrhic

应强调：

- 城市或程序没有完全失败
- 但结果是靠明显代价换来的
- 代价必须具名

句法建议：

- 先说保住了什么
- 再说代价如何永久写进记录

#### mixed

应强调：

- 系统找到了一个可继续运转的答案
- 但问题没有被真正清空
- 留下的是 ambiguity / compromise / incomplete settlement

句法建议：

- 不要写成“普通中间态”
- 要写成“可维持，但不干净”

## 文风准则

结束文案必须继续服从当前项目的品牌与题材真相：

- civic
- dossier
- procedural
- restrained
- public consequence

因此应坚持：

- 像 verdict，不像 label glossary
- 像公共结果记录，不像 GM 注解
- 像会进入档案的结论，不像模型解释自己为什么选了某 ending

明确反对：

- 游戏化 hype
- 抽象大词空转
- 纯情绪化结尾
- 把 ending 写成世界观旁白

## 推荐最小后端改法

如果要最小成本推进，建议分两步：

### 第一步：不改 contract

- 修 narration sanitizer
- 重写 `ending.summary` 生成准则
- 让 `ending.summary` 直接输出 story-specific verdict sentence

### 第二步：additive 扩字段

在 `PlaySessionSnapshot.ending` 下考虑 additive 增加：

- `outcome_statement`
- `what_saved`
- `what_broke`
- `civic_cost_summary`
- `institutional_aftertaste`

前端届时可以直接把 completed 页面做成真正的结论页，而不是从 ledger 上做二次推断。

## 成功标准

后端完成整改后，前端 completed session 应满足：

- transcript 中不再出现任何 transport/meta wrapper 穿帮句
- ending hero 的核心结论不再只是 ending 类型释义
- 用户能一眼看懂：
  - 本局保住了什么
  - 本局损坏了什么
  - 为什么它是这个 ending

## Final Voices 建议

如果 completed 页继续扩成带人物余波的结局页，建议后端在 `PlaySessionSnapshot` 上 additive 增加：

- `epilogue_reactions`

每个 reaction 至少包含：

- `npc_id`
- `name`
- `stance_value`
- `current_expression`
- `current_portrait_url`
- `portrait_variants`
- `closing_line`

其中 `closing_line` 的准则应固定为：

- 它是角色在结局之后留给玩家的一句收束话，不是 another summary
- 长度控制在 `1-2` 句，短卡片可承载
- 要同时带出：
  - 这局结果对这个角色意味着什么
  - 这个角色现在如何看玩家
- 不要和 `ending.summary` 改写成几乎同义
- 不要写成 lore dump、感谢模板、责备模板、或模型解释
- 更像：
  - post-hearing remark
  - dossier margin note spoken aloud
  - 公共后果落到私人关系上的一句记录

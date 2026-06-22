# Tiny Stories 招生评审版 Demo 脚本

## 判断前提

如果这个 demo 是给美国 CS / Software Engineering / AI 相关硕士项目的招生评审看，他们最想确认的不是“这个游戏好不好玩”，而是：

1. 这是不是一个真实跑起来的系统，而不是概念视频。
2. 你本人做了哪些技术和产品决策。
3. 这个项目有没有非平凡的工程复杂度。
4. 你对 LLM 产品的可靠性、状态管理、可解释性和用户体验有没有清晰理解。
5. 你是否能把一个模糊想法做成完整闭环，并且知道下一步怎么改进。

所以这版视频不要拍成“纯氛围互动故事宣传片”，而要拍成“一个 technical AI product builder 的项目证明”。电影感素材仍然保留，但它只是章节转场；真正的主角是系统能力和真实 UI。

## 视频定位

目标时长：100-120 秒。

成片语言：英文。

叙事目标：

> I built a playable AI story loop: a user writes one seed, the system shapes a Story Brief, generates a first scene with roles and choices, preserves player state, supports fixed and free-form moves, keeps advisor help bounded, and produces a shareable ending.

给招生看的核心信息：

> 这不是一个 prompt demo。它是一个 full-stack, stateful, inspectable AI product prototype.

## 总体节奏

1. 先用真实 UI 证明它能跑。
2. 再解释系统到底复杂在哪里。
3. 再展示用户真实游玩。
4. 最后用反思收束：我学到了什么，下一步会怎么让它更可靠。

## Shot 1: 真实问题，而不是炫技开场

时间：0:00-0:10

画面：

- 先不要直接大字标题。
- 真实 create page 画面，光标停在 seed 输入框。
- 背景可以淡入电影感婚礼关键帧，但 UI 要清楚可读。

屏幕文字：

`Tiny Stories: a playable AI story loop`

旁白英文：

`Most AI story demos generate text. I wanted to build something closer to a playable system.`

设计意图：

评审一上来就知道：这是 LLM + product + system，不是单纯写故事。

## Shot 2: 一句话输入，真实开始

时间：0:10-0:24

画面：

- 浏览器真实录屏。
- 输入 seed：

`At my wedding, the groom asks me to sign away my shares before the ceremony starts.`

- 点击 `Send opening`。
- 如果出现 visibility prompt，选择 `Just me`。
- 展示 Story Brief 的顶部 summary。
- 点击 `Generate and enter story`。

屏幕文字：

`Input: one dramatic premise`

旁白英文：

`The user starts with one sentence. The product turns it into a playable run, not a static completion.`

设计意图：

招生评审需要看到“用户真的能操作”，所以这里必须是真实录屏，不要用静态 mock。

## Shot 3: 生成过程展示系统结构

时间：0:24-0:42

画面：

- 真实 Story Brief review 和 generation handoff。
- 展示系统正在生成：
  - player role
  - first scene
  - first moves
  - saved Story Brief context
- 中间穿插 1-2 秒 AI 生成的 evidence board / story engine 关键帧。
- 叠加一层简单系统图，不要复杂：

`Seed -> Story Brief -> Player role -> First scene -> Choices`

屏幕文字：

`Generation is structured before the first turn begins`

旁白英文：

`Before the first turn, the product turns the seed into a scene plan, player role, opening passage, and choices the user can actually press.`

设计意图：

这里要让评审看到技术含量：你不是只调用 LLM 写一段文本，而是在做结构化生成和状态初始化。

## Shot 4: 玩家身份和隐藏状态

时间：0:42-0:58

画面：

- 真实 play page。
- 镜头裁切到：
  - cast strip
  - stage progress bar
  - `This run, you are...`
  - player role banner
  - private objective
  - leverage cards / assets

屏幕文字：

`The player gets a role, private objective, and usable cards`

旁白英文：

`Each run gives the player a concrete role. The system tracks what the player wants, what they know, and what they can use in later moves.`

设计意图：

这是 portfolio 里非常关键的一段：说明你理解“交互故事”必须有 player model 和 state，而不是只有 narration。

## Shot 5: 固定选项证明玩法

时间：0:58-1:12

画面：

- 展示第一段 narration。
- 展示 3 个 options。
- 点一个最有策略感的选项。
- 显示 pending receipt：`Move sent` / `Room reacting` / `Next moves forming`
- 闪回 0.5 秒 AI choice keyframe 作为情绪转场。

屏幕文字：

`Choice -> state update -> next narrative beat`

旁白英文：

`A choice is not just a branch label. It becomes input to the next state transition and changes the following beat.`

设计意图：

招生评审要看到你会把 LLM 放进明确的交互循环里，而不是做“聊天式故事”。

## Shot 6: 自由输入证明开放性

时间：1:12-1:30

画面：

- 点击 `Write your own move`。
- 输入：

`I ask the lawyer to read the clause aloud, then secretly record his answer.`

- 可选：打开 `Add inner motive`，输入：

`If he hesitates, I know the witness was coached.`

- 点击 `Submit with motive`。
- 展示新 narrator beat 出现。

屏幕文字：

`Fixed choices when useful. Free-form action when needed.`

旁白英文：

`I kept structured choices for readability, but also allowed free-form actions so the player can invent tactics the UI did not pre-list.`

设计意图：

这段证明你在做产品权衡：既要降低门槛，也要保留 LLM 产品的开放性。

## Shot 7: Advisor 和可检查状态

时间：1:30-1:48

画面：

- 点击 floating advisor。
- 输入：

`Should I expose him now or stall for one more turn?`

- 展示 advisor 回复。
- 如果使用 reviewer capture，切到 reviewer evidence；不要把它伪装成普通玩家 UI：
  - current stage
  - turns played
  - inventory state
  - ending compiler

屏幕文字：

`Advisor boundary + reviewer evidence`

旁白英文：

`The advisor is not a random chatbot. It reads the current run context and gives strategy without taking control away from the player.`

设计意图：

这段要服务你的申请主线：reliable / inspectable AI workflow systems。它能说明你关心可检查状态、上下文边界和用户控制权。

## Shot 8: 结果反馈和 ending compiler

时间：1:48-2:05

画面：

- 快速 montage：
  - player bubble
  - new narration
  - character reaction
  - inventory changed
  - stage bar moved
- 切到 ending screen：
  - ending label
  - pivotal moments
  - paths not taken
  - share copied state
- AI ending keyframe 用作背景情绪，不要盖住 UI。

屏幕文字：

`The ending is compiled from the path the player actually took`

旁白英文：

`At the end, the system summarizes the route, the pivotal moments, and paths not taken. The output is shareable because it represents a played run, not just generated text.`

设计意图：

这里证明“闭环”：输入、生成、游玩、反馈、结局、分享，全都能落地。

## Shot 9: 工程总结和个人贡献

时间：2:05-2:20

画面：

- 左侧：真实 UI 小窗快速轮播。
- 右侧：简单 architecture overlay。
- 底部列 5 个关键词：

`Full-stack prototype`
`Structured LLM generation`
`Stateful gameplay loop`
`Advisor context`
`Shareable ending`

屏幕文字：

`Built as a personal CS/product project`

旁白英文：

`This project helped me think about LLM products as systems: structured generation, state transitions, user agency, and evaluation. The next validation step is a small real-user playtest: can story-first players understand the scene, choose with confidence, read the consequence, and want to replay or share the result?`

设计意图：

招生评审喜欢看到成熟的反思。不要只说“我做完了”，也不要把本地 QA 当成用户验证；
要说清楚下一层证据是目标用户是否真的理解剧情、愿意选择、能读懂反馈并产生复玩/分享意愿。

## 最终视频结构压缩版

如果需要压到 90 秒，保留这些镜头：

1. Seed 输入。
2. Story Brief 和 generation handoff。
3. Role/private objective/assets page。
4. Option click。
5. Free-form action。
6. Advisor。
7. Ending。
8. Engineering reflection。

可以删掉：

- 过长的纯氛围镜头。
- 太多艺术图 montage。
- 过多的剧情阅读。

## 这版和普通 portfolio trailer 的区别

普通 trailer 强调：

- 画面好看。
- 剧情刺激。
- 产品像游戏。

招生版强调：

- 系统真实可用。
- LLM 输出被结构化。
- 用户行为会进入状态转移。
- UI 设计降低门槛但保留开放性。
- 你知道这个系统的可靠性问题在哪里。

## 拍摄优先级

必须拍到：

1. seed 输入和点击创建。
2. Story Brief 和生成 handoff 的结构化提示。
3. role / private objective / assets。
4. option click 后的 pending receipt 和下一段。
5. free-form action 输入。
6. advisor 问答。
7. ending screen。

加分镜头：

1. reviewer evidence panel。
2. stage progress bar 变化。
3. character reaction。
4. paths not taken。
5. share copied。

## 最重要的剪辑原则

每 10-15 秒回答招生评审的一个问题：

1. 这是真产品吗？
2. 技术复杂点在哪里？
3. 用户怎么操作？
4. LLM 怎么被约束和检查？
5. 结果怎么闭环？
6. 这个项目说明申请人是什么类型的人？

最后一个问题的答案应该是：

> A technical AI product builder who can turn ambiguous generative AI ideas into usable, inspectable, end-to-end systems.

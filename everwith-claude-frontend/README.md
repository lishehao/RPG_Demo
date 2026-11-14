# Everwith · Claude 独立重建前端（本地演示）

依据 Dropbox `/Everwith_Claude_Frontend_Handoff_2026-10-13`（00–10 文档、`reference/`、`assets/`、`verification/`）新建的**独立、可运行**桌面网页前端。不修改原产品，不读取原项目 `.env`/会话/数据库，不连接任何真实服务。

- **完整功能面**：发现（全部/角色/世界/游戏、搜索、空态/失败态区分）、好友、角色详情（明确加好友+命名、同源多好友）、一对一私聊（流式段落、停止、可重试、结果未知查询、晚到旧流丢弃、回退/纠错/重命名/重置/移除）、故事详情→准备→游玩（场景/文字、已知状态、继续剧情、回退、局中加好友）、三款桌游（Royale / Splendor / CABO：准备→明确开始→完整对局→结果→原桌再开）、最近（逐局记录、继续/回看/归档/删除）、创作（类型→命名→编辑→AI 模板改稿可撤销→隔离试演→保存版本→显式分享→用版本加好友）、账号（邮箱密码、Persona、中英切换、减少动态）。
- **五位角色 Live2D**：Lena / Arthur / Marcus / Nora / Iris，Cubism Core 6.0.1 + Framework（来自交接包），冻结的 verified frame writer 单写者、表情眨眼换脸、口型只跟演示音轨、Nora 不写眼球（gaze OFF）、离屏/后台暂停、销毁释放、context loss 恢复。
- **生成素材（GPT batch v2-batch-01）**：故事封面与逐拍场景、五位角色各自的房间背景（Live2D 后面）、三款游戏封面、空/错/登录状态插画、Persona 头像、作品封面、品牌标记与图标。来源、哈希与 prompt 见 `docs/GENERATED_ASSETS.md`；权利标签“用户经 GPT 生成并提供；商用/再分发权未核实”。
- **全部服务都是本地 mock**：界面与 API 之间只有一个适配层（`src/api/adapter.ts`）。默认在浏览器内运行模拟服务端（数据存 `localStorage`），所有页面带“本地演示”标识，桌游标“规则模拟陪玩”，故事标“本地模拟叙事”。**没有任何真实 Luna/JEV/TTS/账号/存储接入。**

## 版本

| 项 | 版本 |
|---|---|
| Node.js | ≥ 20.19（验证于 22.22.0），npm 10.9 |
| React / React DOM | 19.2.0 |
| Vite / @vitejs/plugin-react | 7.1.12 / 5.1.0 |
| TypeScript | 5.9.3（strict） |
| Vitest / jsdom / Testing Library | 4.0.6 / 27.0.1 / 16.3.0 |
| Playwright | 1.56.0（Chromium 141，revision 1194） |
| 图标 | lucide-react 0.545.0 |

所有版本在 `package.json` 中精确锁定，`package-lock.json` 已提交。

## 干净环境启动

```bash
cd everwith-claude-frontend
npm ci                                   # 安装锁定依赖

# 1) 从交接包按字节复制素材（不下载、不转码），并用包内 SHA256SUMS 逐个核对
npm run assets:sync -- --from "/path/to/Everwith_Claude_Frontend_Handoff_2026-10-13"
#    也可用环境变量：EVERWITH_HANDOFF_DIR=/path/to/handoff npm run assets:sync
npm run assets:check                     # 只重新计算 hash，不复制
npm run assets:refs                      # 检查代码里写死的素材路径没有断链
npm run assets:generated                 # 核对随源码提交的生成素材（public/generated）sha256 与引用

# 2) 开发
npm run dev                              # http://127.0.0.1:5173

# 3) 检查与构建
npm run check                            # tsc --noEmit + 全部单元测试
npm run rules:check                      # 三款冻结引擎完整对局 + 投影不泄密检查
npm run build                            # tsc + vite build → dist/
npm run preview                          # http://127.0.0.1:4173（生产构建）

# 4) 端到端（Playwright，自动 build + preview）
npx playwright install chromium          # 本机首次需要
npm run test:e2e                         # 全部 29 项，约 45 分钟（三局完整对局正常速度录屏约 22 分钟）
npm run test:e2e:quick                   # 跳过 @long（完整对局、Live2D 30 秒采样、四宽度矩阵）
```

`assets:sync` 会生成 `public/handoff/`（≈135 MB，186 个文件）和 `src/vendor/cubism-framework/`（Cubism Framework TypeScript 源码，由 Vite 编译）。这两个目录**不随源码打包**（`.gitignore` 已排除），必须由上面的命令从交接包复制。若素材缺失，应用会退化为同一角色静态图/中性占位/文字，并明确显示“动态形象不可用”，聊天与规则仍可用。

生成素材的网页副本（`public/generated/batch-01/`，46 个文件，约 3.9 MB）**随源码提交**，不需要同步。它们是 Dropbox `generated-assets/batch-01/` 原图的缩放副本；想从原图重新生成：`python3 -I scripts/derive-generated.py --from "<…>/generated-assets/batch-01"`（需要 Pillow，可选）。

## 目录

```
src/
  api/            适配层（mock / real）、类型化客户端、响应校验（拒绝含 truth/rng/seed 的桌游投影）
  contracts/      从 reference/contracts 移植的协议解析器（private-public-segments.v1 等）
  mock/           本地模拟服务端：账号、目录、好友、私聊（NDJSON 流）、故事、桌游权威状态、记录、创作、场景开关
  games/engines/  三款游戏的冻结纯引擎（与交接包逐字节一致，见 PROVENANCE.json）+ 新增 .d.ts
  live2d/         运行时、导演（单 RAF）、表演器、冻结 frame writer / Iris carrier 单位、舞台组件（静态图下面一层是角色房间背景）
  art/            生成素材登记（背景、状态插画、作品封面与 Persona 头像的 id → 路径；只做呈现，不参与身份）
  chat/           私聊控制器（generation/receipt/retry/lookup）、IME 安全输入框、安全富文本
  features/       各页面（discover / friends / character / chat / story / games / recent / create / account / mock）
  styles/         设计令牌与页面样式（无 CSS 框架）
scripts/          assets:sync / assets:check / assets:refs / assets:generated（check-generated.mjs）/ derive-generated.py（可选，从原图生成网页副本）
public/generated/ 生成素材网页副本（随源码提交）
tests/            Vitest 单元与集成测试
e2e/              Playwright 端到端（证据写入 evidence/）
evidence/         截图、录屏、Live2D 采样、JSON 报告（本次运行产物）
docs/ASSET_LOCK.json   复制素材清单（相对路径、字节数、sha256、权利标签）
docs/IMAGE_GENERATION_REQUESTS.md   图片生成需求单 v2（已交付并接入）
docs/GENERATED_ASSETS.md / .json     生成素材接入记录：每张用在哪里、原图与副本 sha256、实际 prompt、未用候选
```

## Mock 与真实服务

| 层 | 当前状态 |
|---|---|
| 账号 | **MOCK**：邮箱+密码（加盐 SHA-256，仅避免明文存储，不是生产认证），游客→登录后安全归并，无找回 |
| 目录/发现 | **MOCK**：5 位官方角色、2 个故事、3 款游戏；无伪热度 |
| 好友 | **MOCK**：幂等 key、epoch/重置/移除、来源版本 |
| 私聊回复 | **MOCK**：本地固定回复片段（`simulated_fixed_reply`），流式分段帧、可停止/重试/晚到旧流 |
| 故事叙事 | **MOCK**：固定剧情节拍，整轮校验后原子提交（“本地模拟叙事”） |
| 桌游 NPC | **MOCK**：冻结引擎自带的固定策略，只用本席投影（“规则模拟陪玩”）；**JEV 未接通** |
| 创作“AI 改稿” | **MOCK**：本地模板（不调用模型），可撤销 |
| 语音/口型 | 仅本地演示音轨驱动口型；**无 TTS/viseme 服务** |

真实适配器开关（只写名称，不提供任何密钥）：
- `VITE_EVERWITH_ADAPTER=real` 选择网络传输；
- 同时还必须设置 `VITE_EVERWITH_ALLOW_NETWORK=1` 才会真正发请求；`VITE_EVERWITH_API_BASE` 为可选前缀；
- 未开启网络时所有请求返回 `real_adapter_not_enabled` 并在页面顶部显示红色提示，**不会静默回落到 mock**。

接真实服务前的已知缺口（同时显示在“账号与设置”页）：账号形状与 CSRF 引导、`/discover` 等候选端点、好友 rename/reset/remove 与 origin 绑定、私聊 `{operation, admission}`/receipt/public-stream、全部 story-sessions、game-sessions 与 JEV 决策接缝、works/previews、TTS。详见 `src/api/adapter.ts` 的 `REAL_ADAPTER_GAPS`。

### 演示场景开关

左侧导航“演示控制”（桌游牌桌内为工具栏烧瓶按钮）可打开以下场景，用来走异常分支（一次性场景被下一个相关请求消费）：

`chat.retryable_failure`、`chat.commit_before_cancel`、`chat.unknown_result`、`chat.late_old_stream`、`chat.stale_head`、`chat.friend_reset_elsewhere`、`auth.expired`、`auth.forbidden`、`net.slow`、`discover.error`、`discover.append_error`、`live2d.model_missing`、`assets.missing`、`game.text_failed`、`game.unknown_start`、`story.retryable_failure`。面板里还可以导入一个 Splendor v1 旧存档样例（按 v1 原规则继续）和清空本地数据。

## 素材与权利

两类来源，分开记录，界面“账号与设置 → 素材来源”里也写明：

**交接包素材**
- **逐字节复制**并按包内 `verification/SHA256SUMS.txt` 核对；未生成、未缩放、未重新编码。清单见 `docs/ASSET_LOCK.json`（每项含相对路径、字节数、sha256、权利标签）。
- 权利标签：**“用户授权私人交接；商业/再分发权未核实”**。仅用于本次私人交接与本地演示，不得公开发布或商用。
- 用途：角色头像与 feed 图（`assets/companions/portraits|feed`）、游戏悬停预览视频（`game-previews/v1`）、Live2D 五个冻结运行时（`assets/live2d`）、Cubism Core/Framework（`assets/runtime/cubism`，Live2D 许可文本随附）、Royale 赌场插画 atlas r7 与钞票纹样、Splendor 文艺复兴卡面/贵族/牌背/宝石/台布、CABO 14 张点数插画与牌背（manifest 校验后使用）。交接包的候选游戏封面没有用作默认。

**生成素材（GPT batch v2-batch-01，用户经 GPT 生成并提供）**
- 45 个素材位 / 59 张图，按批次自带的 `SHA256SUMS.json`、`manifest.json` 核对后，只做缩放和格式转换（WebP/PNG）；A/B 两版一律选 a。逐张记录见 `docs/GENERATED_ASSETS.md`（人读）与 `.json`（含原图/副本 sha256、实际 prompt、QA 结论、未用候选）。
- 权利标签：**“用户经 GPT 生成并提供；商用/再分发权未核实”**。同样只用于本次私人演示。
- 用途：故事竖/横封面与 8 张逐拍场景（场景横幅按审过的 5:1 区域定位，并显示地点名）、五位角色各自的房间背景 + 通用背景（Live2D 与静态图下面一层，缺图时回到原来的渐变）、三款游戏封面（默认海报；交接包原海报仍在，`src/mock/catalog.ts` 一行切回）、六张状态插画、两张新建类型插画、六张作品封面（作品草稿只存 id）、八个 Persona 头像（物件，不是人像，只存 id）、品牌标记与浏览器/主屏图标。
- “图片素材缺失”场景同样覆盖生成素材：全部安静消失、显示原来的渐变/字母/图标，不出现破图，也不拿别的角色顶替。

规则数字、骰点、钞票金额、筹码、卡牌数字与 6/9 标记、能力文字、场景地点名全部由代码绘制，图片只提供插画。

## 冻结来源（未改动的部分）

- `src/games/engines/**/*.js|ts`：Royale `engine.ts`、Splendor `data.js / engine.js / rules.js / rules-v2.js / npc.js`、CABO `engine.js / core.js / rule-evidence.js`——与 `reference/games` 逐字节一致（`npm run rules:check` 会重新计算 hash）。
- `src/live2d/verified-frame-writer.ts`、`carrier-parameter-units.ts`：逐字移植。
- `src/contracts/public-events.ts`、`dialogue-expression-client.ts`：逐字移植；其余合约文件只改了 import 路径。

## 测试与证据

- `npm run check`：TypeScript strict（含 e2e 目录）+ Vitest 54 项：
  - `engines.test`：冻结引擎与交接包逐字节一致；三款游戏 2–5 人完整对局、Splendor v1 旧存档按原规则完成、未知规则档案拒绝升级、CABO provisional 标注；
  - `cabo-rules.test`：射月、失败 CABO +5、叫牌者并列最低获胜、恰好 100 → 50 一次、>100 终局；
  - `mock-api.test`：好友幂等/同源多人/epoch 重置、私聊控制器（提交一次、并发发送拒绝、可重试同一操作、结果未知查原 key、停止输给提交、旧 run 晚到帧、真实取消）、开局幂等与查询、一个好友一个席位、故事选角限制、入局好友不带私聊内容、好友重置后故事只读、创作草稿 base revision 与分享前置；生成素材接线（故事封面、逐拍场景与开放模式结尾地点、旧存档场景键回推、记录缩略图、Persona 头像只收预设 id、作品封面默认值与校验）；
  - `richtext-router.test`：`*动作*` 与奇偶反斜杠转义、HTML 不执行、换行保留；路由与旧深链；
  - `components.test`：IME 合成事件不发送、选区加星号、双击发送只一次且第二击不触发“停止”、CABO/Splendor 不渲染未知值；舞台背景按角色选择（自创角色用通用背景、可关闭）、缺图场景路径改写、背景/插画加载失败时直接消失。
- `npx playwright test`（生产构建 + Chromium；Linux 下 SwiftShader 软件 WebGL）——本次 29/29 通过：
  - `art.spec`：生成素材在用到的地方都真实加载（视口内逐张检查 naturalWidth）、故事场景随提交的节拍切换并在开放模式到达结尾地点、记录缩略图、状态插画、新建类型插画、图标；Persona 头像与作品封面选择后刷新仍在并出现在导航/席位/作品卡；“图片素材缺失”下七个页面无破图、无生成图、品牌回到字母。
  - `core.spec`：发现页、搜索空态 vs 加载失败、深链与 Back；加好友中途登录、名字恢复、私聊发送/草稿刷新保留/停止/可重试/结果未知；好友“一起玩”进入桌游准备。
  - `story-create.spec`：故事开局、整轮提交、继续剧情不伪造玩家发言（场景随节拍切换）、回退恢复草稿（场景一起退回）、可重试失败、局中把当前人物加为好友；创作全流程（试演不进入正式会话；自创角色私聊用通用背景）。
  - `extra.spec`：牌友原位转好友、登录取消不丢位置、放弃本局只读；最近“继续”回到原局、回访落到好友页、Splendor v1 旧存档；模型/图片缺失降级；Shift+Tab。
  - `edge.spec`：双击发送、停止输给提交、停止后表情回中性、旧 run 晚到帧、另一窗口先提交、好友在别处重置、生成中离开、登录过期；阅读旧消息不被拉底与阅读位置/草稿/选区保留；开局回执丢失、打开不存在的局、桌聊台词失败；拒绝全屏/两次 Esc 后牌桌仍可操作。
  - `layout-a11y.spec`：1024/1280/1440/1920 × 中/英无横向溢出（@long）、200% 缩放、跳转链接/Tab/Esc/焦点归还、减少动态、CDP 合成 IME。
  - `live2d.spec`（@long）：五位角色 1× 大脸、≥4 fps 采样 30 秒、表情、通道清单无眼球写入；切换/放大/隐藏标签页/离屏/牌桌侧栏的资源释放与暂停、WebGL context loss 恢复。
  - `games.spec`（@long）：Royale 4 人三轮、Splendor 4 人 15 分补齐轮、CABO 4 人累计 >100，**正常速度录屏**，局中检查暂停/侧栏/沉浸/全屏/刷新后同一局继续、结束后可聊且锁分、原桌再开。
- 证据目录 `evidence/`：`screenshots/`（含 `matrix/` 40 张、`zoom200/`、`compare/` 新旧并排）、`videos/`（三局完整录屏 .webm）、`live2d/<角色>/`（大脸、表情、采样帧、帧差）、`reports/*.json`。

所有截图与录屏都来自云端容器里的 headless Chromium（软件 WebGL、无声音、无真实输入法），不是你本机的真实浏览器；验收逐项状态与未完成项见 `ACCEPTANCE.md`。

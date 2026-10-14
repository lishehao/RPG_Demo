# 生成素材接入记录（v2-batch-01）

- 来源：Dropbox `/Everwith_Claude_Frontend_Rebuild_2026-10-13/generated-assets/batch-01/`（45 个素材位、59 张图；`manifest.json` sha256 `03e10cd7e985b70a2edd4fc4b3ca25ac71ee6ca6b2d35a9d3be518d59f1d533d`，`SHA256SUMS.json` sha256 `f14a47a4366fb3c58dd34a710e78ffd825ecd0830339466a3f960c4a9d1c9ed7`）。
- 生成：GPT 内置图片工具（`built-in image_gen.imagegen`，模型名未披露）；每张的实际 prompt、生成时间、QA 结论都抄在 `GENERATED_ASSETS.json` 里。
- **权利标签：用户经 GPT 生成并提供；商用/再分发权未核实**。不是交接包的一部分；只用于这次私人交接与本地演示，不公开发布、不商用。
- 处理：只做缩放（Lanczos）和格式转换（WebP/PNG），没有修图、调色或裁切；唯一例外是浏览器图标把圆角外的纯黑角改成透明（主屏图标则用图块边缘色填平）。原图全部先按批次自带的 `SHA256SUMS.json` 和 `manifest.json` 核对。
- 网页副本在 `public/generated/batch-01/`（46 个文件，共 3.85 MB），随源码一起提交；`npm run assets:generated` 会逐个核对 sha256、检查代码里引用的文件都在清单里。重新生成：`python3 -I scripts/derive-generated.py --from <batch-01 文件夹>`（需要 Pillow；不同 Pillow/libwebp 版本字节可能不同，以 JSON 记录为准）。
- A/B 两版的素材位一律选 `__a`（两版都通过了 QA；a 版多为正面、居中构图，裁成卡片和圆形时更稳）。未用的 `__b` 留在 Dropbox，没有复制进项目。
- 游戏海报默认改用生成封面（原交接包 480×480 海报仍同步在 `public/handoff`，在 `src/mock/catalog.ts` 里把 `poster` 改回 `${V}/…-poster.webp` 一行即可切回）；悬停预览短片仍用交接包的。

| 素材位 | 选用 | 用在哪里 | 原图 | 网页副本 | 未用候选 |
|---|---|---|---|---|---|
| `story-last-train-cover-tall` | a | 发现页故事卡（4:5）、故事准备页海报（3:4）、最近 / 继续 / 一起玩的缩略图 | 1024×1536 · `916afdf6d0d0…` | `story-last-train-cover-tall.webp` 768×1152 · 147 KB | story-last-train-cover-tall__b.png |
| `story-last-train-cover-wide` | a | 故事详情页大图（4:3） | 1536×1024 · `5f8b1a0ab5c9…` | `story-last-train-cover-wide.webp` 1280×853 · 184 KB | story-last-train-cover-wide__b.png |
| `story-last-train-scene-waiting-room` | 单张 | 游玩页场景横幅：开场与第 1 拍 | 1536×1024 · `f5a2ad0a9b4e…` | `story-last-train-scene-waiting-room.webp` 1280×853 · 125 KB | — |
| `story-last-train-scene-corner` | 单张 | 场景横幅：第 2 拍 | 1536×1024 · `2c2ecbb9b641…` | `story-last-train-scene-corner.webp` 1280×853 · 165 KB | — |
| `story-last-train-scene-duty-room` | 单张 | 场景横幅：第 3 拍 | 1536×1024 · `73aedfb7f2bd…` | `story-last-train-scene-duty-room.webp` 1280×853 · 103 KB | — |
| `story-last-train-scene-platform-dawn` | 单张 | 场景横幅：最后一拍之后的自由行动（开放模式） | 1536×1024 · `a5817285ec76…` | `story-last-train-scene-platform-dawn.webp` 1280×853 · 163 KB | — |
| `story-promise-rain-cover-tall` | a | 发现页故事卡、故事准备页海报、缩略图 | 1024×1536 · `7ebd34d35659…` | `story-promise-rain-cover-tall.webp` 768×1152 · 240 KB | story-promise-rain-cover-tall__b.png |
| `story-promise-rain-cover-wide` | a | 故事详情页大图 | 1536×1024 · `c6520259facf…` | `story-promise-rain-cover-wide.webp` 1280×853 · 298 KB | story-promise-rain-cover-wide__b.png |
| `story-promise-rain-scene-entrance-rain` | 单张 | 场景横幅：开场与第 1 拍 | 1536×1024 · `459fae2184ac…` | `story-promise-rain-scene-entrance-rain.webp` 1280×853 · 275 KB | — |
| `story-promise-rain-scene-backstage` | 单张 | 场景横幅：第 2 拍 | 1536×1024 · `e50d3e4e50d8…` | `story-promise-rain-scene-backstage.webp` 1280×853 · 138 KB | — |
| `story-promise-rain-scene-office` | 单张 | 场景横幅：第 3 拍 | 1536×1024 · `bf0fc897ce1f…` | `story-promise-rain-scene-office.webp` 1280×853 · 111 KB | — |
| `story-promise-rain-scene-entrance-after-rain` | 单张 | 场景横幅：第 4 拍 | 1536×1024 · `ea887326d14d…` | `story-promise-rain-scene-entrance-after-rain.webp` 1280×853 · 294 KB | — |
| `backdrop-lena` | a | Lena 的舞台背景：角色页、私聊、牌桌侧栏、故事左栏、发现卡、好友列表头像底 | 1024×1536 · `b5da63d9316c…` | `backdrop-lena.webp` 768×1152 · 93 KB | backdrop-lena__b.png |
| `backdrop-arthur` | a | Arthur 的舞台背景：角色页、私聊、牌桌侧栏、故事左栏、发现卡、好友列表头像底 | 1024×1536 · `877725684588…` | `backdrop-arthur.webp` 768×1152 · 72 KB | backdrop-arthur__b.png |
| `backdrop-marcus` | a | Marcus 的舞台背景：角色页、私聊、牌桌侧栏、故事左栏、发现卡、好友列表头像底 | 1024×1536 · `db527378ef41…` | `backdrop-marcus.webp` 768×1152 · 69 KB | backdrop-marcus__b.png |
| `backdrop-nora` | a | Nora 的舞台背景：角色页、私聊、牌桌侧栏、故事左栏、发现卡、好友列表头像底 | 1024×1536 · `9c519d994bc8…` | `backdrop-nora.webp` 768×1152 · 100 KB | backdrop-nora__b.png |
| `backdrop-iris` | a | Iris 的舞台背景：角色页、私聊、牌桌侧栏、故事左栏、发现卡、好友列表头像底 | 1024×1536 · `be814c797aed…` | `backdrop-iris.webp` 768×1152 · 100 KB | backdrop-iris__b.png |
| `backdrop-generic` | 单张 | 自创角色（没有专属房间）的舞台背景 | 1024×1536 · `43f0e979fe75…` | `backdrop-generic.webp` 768×1152 · 75 KB | — |
| `game-royale-cover` | a | 游戏海报：发现页（1:1）、准备页（3:4）、一起玩 / 最近缩略图 | 1024×1536 · `955c06a04e47…` | `game-royale-cover.webp` 768×1152 · 153 KB | game-royale-cover__b.png |
| `game-splendor-cover` | a | 同上 | 1024×1536 · `98acbe94447f…` | `game-splendor-cover.webp` 768×1152 · 163 KB | game-splendor-cover__b.png |
| `game-cabo-cover` | a | 同上 | 1024×1536 · `a1d9d60fd0a3…` | `game-cabo-cover.webp` 768×1152 · 138 KB | game-cabo-cover__b.png |
| `empty-friends` | 单张 | 好友页：还没有好友 | 1254×1254 · `a22a1b2773e5…` | `empty-friends.webp` 480×480 · 43 KB | — |
| `empty-recent` | 单张 | 最近页：还没有记录 / 没有归档 | 1254×1254 · `3fc5aabb0c64…` | `empty-recent.webp` 480×480 · 31 KB | — |
| `empty-create` | 单张 | 创作页：还没有作品 | 1254×1254 · `28cd27c2e0b0…` | `empty-create.webp` 480×480 · 43 KB | — |
| `state-not-found` | 单张 | 找不到（页面、角色、故事、局、好友、作品） | 1254×1254 · `270604800fb0…` | `state-not-found.webp` 480×480 · 60 KB | — |
| `state-load-error` | 单张 | 加载失败（与“没有内容”区分） | 1254×1254 · `e960e7744fe0…` | `state-load-error.webp` 480×480 · 44 KB | — |
| `state-signin` | 单张 | 需要登录（好友页、私聊）与登录弹窗 | 1254×1254 · `449188d214ae…` | `state-signin.webp` 480×480 · 47 KB | — |
| `create-type-story` | 单张 | 新建作品弹窗：故事 | 1254×1254 · `4a79ba3d9440…` | `create-type-story.webp` 320×320 · 19 KB | — |
| `create-type-character` | 单张 | 新建作品弹窗：角色 | 1254×1254 · `fabbf59b09a5…` | `create-type-character.webp` 320×320 · 22 KB | — |
| `work-cover-01` | 单张 | 作品封面候选：作品卡片、编辑页 | 1024×1536 · `906577580226…` | `work-cover-01.webp` 600×900 · 76 KB | — |
| `work-cover-02` | 单张 | 作品封面候选：作品卡片、编辑页 | 1024×1536 · `47a013e6b4ef…` | `work-cover-02.webp` 600×900 · 58 KB | — |
| `work-cover-03` | 单张 | 作品封面候选：作品卡片、编辑页 | 1024×1536 · `de8aeeb76bc7…` | `work-cover-03.webp` 600×900 · 49 KB | — |
| `work-cover-04` | 单张 | 作品封面候选：作品卡片、编辑页 | 1024×1536 · `d8a327a6d775…` | `work-cover-04.webp` 600×900 · 70 KB | — |
| `work-cover-05` | 单张 | 作品封面候选：作品卡片、编辑页 | 1024×1536 · `7026c494c9c2…` | `work-cover-05.webp` 600×900 · 43 KB | — |
| `work-cover-06` | 单张 | 作品封面候选：作品卡片、编辑页 | 1024×1536 · `6bbe9303fcd6…` | `work-cover-06.webp` 600×900 · 40 KB | — |
| `persona-avatar-01` | 单张 | Persona 头像候选：账号页、导航、自己的牌桌席位 | 1254×1254 · `ceb1244f6245…` | `persona-avatar-01.webp` 256×256 · 6 KB | — |
| `persona-avatar-02` | 单张 | Persona 头像候选：账号页、导航、自己的牌桌席位 | 1254×1254 · `201acb19cea5…` | `persona-avatar-02.webp` 256×256 · 8 KB | — |
| `persona-avatar-03` | 单张 | Persona 头像候选：账号页、导航、自己的牌桌席位 | 1254×1254 · `b7c887524b58…` | `persona-avatar-03.webp` 256×256 · 9 KB | — |
| `persona-avatar-04` | 单张 | Persona 头像候选：账号页、导航、自己的牌桌席位 | 1254×1254 · `2bca1e74c1a2…` | `persona-avatar-04.webp` 256×256 · 6 KB | — |
| `persona-avatar-05` | 单张 | Persona 头像候选：账号页、导航、自己的牌桌席位 | 1254×1254 · `d52897880eeb…` | `persona-avatar-05.webp` 256×256 · 8 KB | — |
| `persona-avatar-06` | 单张 | Persona 头像候选：账号页、导航、自己的牌桌席位 | 1254×1254 · `da249ee730e1…` | `persona-avatar-06.webp` 256×256 · 10 KB | — |
| `persona-avatar-07` | 单张 | Persona 头像候选：账号页、导航、自己的牌桌席位 | 1254×1254 · `67fe0ed5bc85…` | `persona-avatar-07.webp` 256×256 · 5 KB | — |
| `persona-avatar-08` | 单张 | Persona 头像候选：账号页、导航、自己的牌桌席位 | 1254×1254 · `8da62c6a1189…` | `persona-avatar-08.webp` 256×256 · 4 KB | — |
| `brand-emblem` | a | 左侧导航品牌标记、首次加载画面 | 1254×1254 · `73b30be0ccd1…` | `brand-emblem.png` 128×128 · 8 KB | brand-emblem__b.png |
| `app-icon` | a | 浏览器标签图标 / 主屏图标 | 1254×1254 · `39c5f0e39ae4…` | `favicon-64.png` 64×64 · 5 KB | app-icon__b.png |
| `app-icon` | a | 浏览器标签图标 / 主屏图标 | 1254×1254 · `39c5f0e39ae4…` | `apple-touch-icon.png` 180×180 · 24 KB | app-icon__b.png |

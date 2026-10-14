# 图片生成需求单 v2（给 GPT）

> **状态（2026-10-14）：batch-01 已全部收到并接入。** 45 个素材位 / 59 张图，逐个与批次自带的 `SHA256SUMS.json`、`manifest.json` 核对一致；A/B 两版一律选 `__a`。每张图用在哪里、原图与网页副本的 sha256、实际 prompt 见 `GENERATED_ASSETS.md` / `GENERATED_ASSETS.json`。下面是需求原文，保留不改，供追溯。

共 **45 个素材位**（P0 4 · P1 14 · P2 9 · P3 18），按候选数算约 **59 张图**。每条都有可以直接粘贴的英文 prompt；同一份清单的机器可读版本是 `IMAGE_GENERATION_REQUESTS.json`。

## 现在视觉上不合适的地方（这批图要解决的）

1. 故事《末班车之后》完全没有图：发现页卡片是书本图标，详情/准备页是空渐变，游玩页场景横幅是一块灰蓝色。
2. 故事《雨中的约定》借用了不相干的图：封面和后台/办公室场景用的是 Lena 的私人书房，“剧院门口淋雨”用的是一张现代高楼休息室，和 1920 年代剧院对不上。
3. 三款游戏的封面其实是 480×480 的首页预览视频首帧（棋盘截图），在发现页和准备页上偏糊、也不像封面。交接包里的候选封面你没有接受过，所以没用。
4. 角色页、私聊、牌桌侧栏、故事左栏里，Live2D 角色背后只有一层纯色渐变，角色页右侧还有大片空白。
5. 好友、最近、创作、找不到内容、加载失败等状态只有一行文字，页面大面积空。
6. 用户自建的角色/故事没有封面，账号页的 Persona 没有头像，品牌标记只是 CSS 画的字母。

## 交付方式（请让 GPT 照这个放）

- Dropbox 目录：`/Everwith_Claude_Frontend_Rebuild_2026-10-13/generated-assets/batch-01/`
- 文件名就是素材 ID：`<id>.png`；条目写“候选 2 张”的，用 `<id>__a.png`、`<id>__b.png`。
- 尺寸：按条目的**比例**出图，用工具原生的最大尺寸即可（例如横 1536×1024、竖 1024×1536、方 1024×1024），**不要放大**；裁切由我来做，所以请遵守每条的“安全区”。
- 透明背景：条目标“透明”的出透明 PNG；做不到就用纯色 #1B1311 背景。
- 同目录放一个 `manifest.md`（或 `manifest.json`），每张图一行：ID、文件名、工具/模型名、生成日期、实际使用的 prompt（如有改动）、备注。
- 默认只用文字 prompt。附交接包里的图做风格参考，等于把私人素材上传给第三方，由你决定。

## 全部素材共同的规则

- 不要任何文字、字母、数字、招牌字、水印、Logo（标题、点数、金额、能力说明都由代码绘制）。
- 场景和背景里不要人物（五位角色只能用冻结的 source/version 素材，生成图里出现人会和选角、Live2D 冲突）。
- 不模仿任何已出版桌游的盒面/卡面、真实赌场或铁路公司品牌。
- 风格向现有素材靠拢：暖琥珀/黄铜色灯光 × 冷蓝青夜色、半写实绘画感；游戏 CABO 那张是水粉感童话插画。
- 权利记录口径：“用户经 GPT 生成并提供；商用/再分发权未核实”。

## 一览

| 优先级 | ID | 比例 | 候选 | 透明 | 用在哪里 |
|---|---|---|---|---|---|
| P0 | `story-last-train-cover-tall` | 2:3 | 2 |  | 发现页故事卡片（裁成 4:5）、准备页海报（裁成 3:4）、最近记录图标 |
| P0 | `story-last-train-cover-wide` | 3:2 | 2 |  | 故事详情页大图（4:3 区域） |
| P0 | `story-last-train-scene-waiting-room` | 3:2 | 1 |  | 游玩页场景横幅：开场与第 1–2 拍（会被裁成约 5:1 的扁条） |
| P1 | `story-last-train-scene-corner` | 3:2 | 1 |  | 第 2 拍（角落里的旅人走过来） |
| P0 | `story-last-train-scene-duty-room` | 3:2 | 1 |  | 第 3 拍（登记、锁进值班室、天快亮） |
| P1 | `story-last-train-scene-platform-dawn` | 3:2 | 1 |  | 结尾 / 开放模式 |
| P1 | `story-promise-rain-cover-tall` | 2:3 | 2 |  | 发现页故事卡片、准备页海报、最近记录图标 |
| P1 | `story-promise-rain-cover-wide` | 3:2 | 2 |  | 故事详情页大图 |
| P1 | `story-promise-rain-scene-entrance-rain` | 3:2 | 1 |  | 开场与第 1 拍（门口、名单被划掉） |
| P1 | `story-promise-rain-scene-backstage` | 3:2 | 1 |  | 第 2 拍（后台签到簿） |
| P1 | `story-promise-rain-scene-office` | 3:2 | 1 |  | 第 3 拍（经理办公室、沾墨的钥匙） |
| P1 | `story-promise-rain-scene-entrance-after-rain` | 3:2 | 1 |  | 第 4 拍（雨小了、灯重新亮起、开场铃响） |
| P1 | `backdrop-lena` | 2:3 | 2 |  | Lena（剧院调查员）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景） |
| P1 | `backdrop-arthur` | 2:3 | 2 |  | Arthur（剧院经理）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景） |
| P1 | `backdrop-marcus` | 2:3 | 2 |  | Marcus（舞台监督）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景） |
| P1 | `backdrop-nora` | 2:3 | 2 |  | Nora（好奇的同伴）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景） |
| P1 | `backdrop-iris` | 2:3 | 2 |  | Iris（细心的倾听者）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景） |
| P1 | `backdrop-generic` | 2:3 | 1 |  | 创作的角色（通用）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景） |
| P2 | `game-royale-cover` | 2:3 | 2 |  | 发现页游戏卡片（居中裁成正方形）、准备页海报（3:4）、“一起玩”弹窗 |
| P2 | `game-splendor-cover` | 2:3 | 2 |  | 同上 |
| P2 | `game-cabo-cover` | 2:3 | 2 |  | 同上 |
| P2 | `empty-friends` | 1:1 | 1 | 是 | 好友页空状态（还没有好友 / 需要登录） |
| P2 | `empty-recent` | 1:1 | 1 | 是 | 最近页空状态 |
| P2 | `empty-create` | 1:1 | 1 | 是 | 创作页空状态 |
| P2 | `state-not-found` | 1:1 | 1 | 是 | 找不到内容 / 局不存在 |
| P2 | `state-load-error` | 1:1 | 1 | 是 | 加载失败（不是“没有内容”） |
| P2 | `state-signin` | 1:1 | 1 | 是 | 需要登录的提示 |
| P3 | `create-type-story` | 1:1 | 1 | 是 | 新建作品弹窗里的“故事”类型卡片 |
| P3 | `create-type-character` | 1:1 | 1 | 是 | 新建作品弹窗里的“角色”类型卡片 |
| P3 | `work-cover-01` | 2:3 | 1 |  | 用户自建作品的默认封面（作品卡片、试演、最近） |
| P3 | `work-cover-02` | 2:3 | 1 |  | 用户自建作品的默认封面（作品卡片、试演、最近） |
| P3 | `work-cover-03` | 2:3 | 1 |  | 用户自建作品的默认封面（作品卡片、试演、最近） |
| P3 | `work-cover-04` | 2:3 | 1 |  | 用户自建作品的默认封面（作品卡片、试演、最近） |
| P3 | `work-cover-05` | 2:3 | 1 |  | 用户自建作品的默认封面（作品卡片、试演、最近） |
| P3 | `work-cover-06` | 2:3 | 1 |  | 用户自建作品的默认封面（作品卡片、试演、最近） |
| P3 | `persona-avatar-01` | 1:1 | 1 |  | 账号页“我的 Persona”可选头像（不是人物，避免和角色混淆） |
| P3 | `persona-avatar-02` | 1:1 | 1 |  | 账号页“我的 Persona”可选头像（不是人物，避免和角色混淆） |
| P3 | `persona-avatar-03` | 1:1 | 1 |  | 账号页“我的 Persona”可选头像（不是人物，避免和角色混淆） |
| P3 | `persona-avatar-04` | 1:1 | 1 |  | 账号页“我的 Persona”可选头像（不是人物，避免和角色混淆） |
| P3 | `persona-avatar-05` | 1:1 | 1 |  | 账号页“我的 Persona”可选头像（不是人物，避免和角色混淆） |
| P3 | `persona-avatar-06` | 1:1 | 1 |  | 账号页“我的 Persona”可选头像（不是人物，避免和角色混淆） |
| P3 | `persona-avatar-07` | 1:1 | 1 |  | 账号页“我的 Persona”可选头像（不是人物，避免和角色混淆） |
| P3 | `persona-avatar-08` | 1:1 | 1 |  | 账号页“我的 Persona”可选头像（不是人物，避免和角色混淆） |
| P3 | `brand-emblem` | 1:1 | 2 | 是 | 左侧导航的品牌标记、加载页 |
| P3 | `app-icon` | 1:1 | 2 |  | 浏览器标签图标 / 桌面图标 |

## 故事《末班车之后》

### `story-last-train-cover-tall` · P0 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：发现页故事卡片（裁成 4:5）、准备页海报（裁成 3:4）、最近记录图标
- 现状：没有图，显示书本图标
- 安全区：手提箱和长椅放在画面中央的正方形里

**Prompt**

```text
Portrait 2:3 illustration of the waiting room of a small old railway station on a rainy night, just after the last train has left. In the lower center a worn vintage brown leather suitcase with brass corners stands upright beside an empty wooden bench; a rain-soaked paper luggage tag hangs from its handle, its ink run and unreadable. Two old pendant lamps pool warm amber light on the bench and the terrazzo floor; behind them a tall window shows a wet, empty platform under deep blue night, rain streaks on the glass and a distant red signal light. Quiet, gentle mystery: a little lonely but safe. Keep the suitcase and the bench inside the central square of the frame. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-last-train-cover-wide` · P0 · 3:2（≥ 1536×1024） · 候选 2 张

- 用在：故事详情页大图（4:3 区域）
- 现状：没有图，显示书本图标
- 安全区：主体在中间 2/3 宽度内

**Prompt**

```text
Landscape 3:2 illustration of the waiting room of a small old railway station on a rainy night, just after the last train has left. Centered: a worn vintage brown leather suitcase with brass corners standing beside an empty wooden bench, a rain-soaked paper luggage tag with run, unreadable ink. Warm amber pendant lamps; tall windows on both sides show a wet empty platform under deep blue night, rain streaks, a distant red signal light. Quiet, gentle mystery, a little lonely but safe. Keep the suitcase and bench within the middle two-thirds of the width. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-last-train-scene-waiting-room` · P0 · 3:2（≥ 1536×1024）

- 用在：游玩页场景横幅：开场与第 1–2 拍（会被裁成约 5:1 的扁条）
- 现状：纯色渐变
- 安全区：关键物体都在画面垂直方向 35%–70% 的中段

**Prompt**

```text
Wide landscape 3:2 view of the waiting room of a small old railway station on a rainy night, just after the last train has left, at about 1 a.m.: rows of wooden benches, a shuttered ticket window, a round wall clock with plain hands and no numerals, a small lost-and-found counter with a brass bell and a closed logbook, and an old brown leather suitcase standing beside a bench in the middle ground. Only a few warm lamps are on; the rest falls into soft blue shadow; rain on tall windows, a wet platform glimpsed outside. Calm, slightly mysterious slice-of-life mood; an ordinary working station, not abandoned. Keep all key objects in the middle horizontal band of the frame. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-last-train-scene-corner` · P1 · 3:2（≥ 1536×1024）

- 用在：第 2 拍（角落里的旅人走过来）
- 现状：纯色渐变
- 安全区：中段横条

**Prompt**

```text
Wide landscape 3:2 view of a quiet corner of the waiting room of a small old railway station on a rainy night, just after the last train has left: an old cast-iron radiator, a single bench with a folded woollen scarf and a paper cup of tea left on it, a dim wall lamp, a rain-streaked window with the blue platform lights beyond. Tender, hesitant mood, as if someone has just stood up. Keep the bench and the scarf in the middle horizontal band. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-last-train-scene-duty-room` · P0 · 3:2（≥ 1536×1024）

- 用在：第 3 拍（登记、锁进值班室、天快亮）
- 现状：纯色渐变
- 安全区：中段横条

**Prompt**

```text
Wide landscape 3:2 view of the small duty room / lost-property office of the same old railway station just before dawn: a tidy wooden desk with an open logbook and a fountain pen (handwriting not legible), a metal flashlight, a wall board with several keys on hooks, and the old brown leather suitcase placed on a shelf inside a wire-mesh locker. A green-shaded desk lamp gives warm light while the window shows the sky turning pale blue-grey at dawn. Orderly, calm, reassuring. Key objects in the middle horizontal band. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, pale dawn light meeting warm lamplight, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-last-train-scene-platform-dawn` · P1 · 3:2（≥ 1536×1024）

- 用在：结尾 / 开放模式
- 现状：纯色渐变
- 安全区：中段横条

**Prompt**

```text
Wide landscape 3:2 view of an empty small-town railway platform at dawn after a rainy night: wet concrete reflecting a pale peach-and-blue sky, rails curving away into light mist, a single wooden bench, an illuminated departure board glowing softly with abstract light rows only (no characters), overhead wires catching the first light. Hopeful, quiet morning. Key elements in the middle horizontal band. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, pale dawn light meeting warm lamplight, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

## 故事《雨中的约定》

### `story-promise-rain-cover-tall` · P1 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：发现页故事卡片、准备页海报、最近记录图标
- 现状：借用 Lena 的书房插画（不是剧院）
- 安全区：门口和讲台在中央正方形内

**Prompt**

```text
Portrait 2:3 illustration of the entrance of an old ornate 1920s theatre at night in heavy rain. A marquee lined with warm light bulbs, a few of them flickering, carries no lettering at all. Under the awning: a red velvet rope, a wooden doorman's lectern with a clipboard guest list whose writing is not legible, and a dark umbrella leaning against it. Wet pavement and puddles reflect gold and crimson light; rain falls in visible streaks against deep blue night. Mystery with a touch of romance. Keep the doorway and the lectern inside the central square. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-promise-rain-cover-wide` · P1 · 3:2（≥ 1536×1024） · 候选 2 张

- 用在：故事详情页大图
- 现状：借用 Lena 的书房插画
- 安全区：主体在中间 2/3 宽度内

**Prompt**

```text
Landscape 3:2 illustration of the entrance of an old ornate 1920s theatre at night in heavy rain: bulb-lined marquee with no lettering, glass doors glowing warm, a red velvet rope, a doorman's lectern with an illegible guest list on a clipboard, a dark umbrella, gold and crimson reflections in puddles, rain streaks against deep blue night. Mystery with a touch of romance. Keep the doorway and lectern within the middle two-thirds of the width. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-promise-rain-scene-entrance-rain` · P1 · 3:2（≥ 1536×1024）

- 用在：开场与第 1 拍（门口、名单被划掉）
- 现状：借用了一张现代高楼休息室（与 1920 年代剧院不符）
- 安全区：中段横条

**Prompt**

```text
Wide landscape 3:2 view of the entrance of an old ornate 1920s theatre at night in heavy rain, seen from across a wet cobblestone street: a glowing bulb marquee with no lettering, glass doors with warm light behind them, a velvet rope and a doorman's lectern under the awning, an umbrella, reflections in puddles, rain streaks. Mysterious but inviting. Key elements in the middle horizontal band. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-promise-rain-scene-backstage` · P1 · 3:2（≥ 1536×1024）

- 用在：第 2 拍（后台签到簿）
- 现状：借用 Lena 的书房插画
- 安全区：中段横条

**Prompt**

```text
Wide landscape 3:2 view of a quiet backstage corridor of an old ornate 1920s theatre at night: exposed brick wall, a costume rack with velvet garments, coiled ropes and a sandbag, a stage door with a small round window, and a wooden desk under a green-shaded lamp holding an open sign-in book (handwriting not legible) and a pen. A small locked wooden key cabinet hangs on the wall. Hushed, intimate, faintly suspenseful; muted crimson and brass. Key elements in the middle horizontal band. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-promise-rain-scene-office` · P1 · 3:2（≥ 1536×1024）

- 用在：第 3 拍（经理办公室、沾墨的钥匙）
- 现状：借用 Lena 的书房插画
- 安全区：中段横条

**Prompt**

```text
Wide landscape 3:2 view of the theatre manager's small office at night, the door half open: a heavy wooden desk with a single brass key whose paper tag is smudged with dark ink, an inkwell, a neat stack of programs with no readable printing, a framed photograph too far away to make out, rain on the window behind, a warm desk lamp. Calm, a little melancholy, quietly revealing. Key elements in the middle horizontal band. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `story-promise-rain-scene-entrance-after-rain` · P1 · 3:2（≥ 1536×1024）

- 用在：第 4 拍（雨小了、灯重新亮起、开场铃响）
- 现状：借用现代休息室图
- 安全区：中段横条

**Prompt**

```text
Wide landscape 3:2 view of the same entrance of an old ornate 1920s theatre as the rain eases: last drops in puddles, the bulb marquee now fully and steadily lit (no lettering), the glass doors open and spilling warm golden light, a closed umbrella hanging on a rope post, the faint glow of the auditorium beyond. Relieved, warm ending. Key elements in the middle horizontal band. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

## 角色背景（Live2D 背后）

### `backdrop-lena` · P1 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：Lena（剧院调查员）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景）
- 现状：纯色渐变
- 安全区：中间一半宽度保持干净、虚化（人物会叠在中间）

**Prompt**

```text
Portrait 2:3 background illustration of an investigator's study in an old theatre district at night: a tall arched window on the left with rain and soft city lights, bookshelves and neatly tied case folders on the right, a brass desk lamp glowing, a pinned street map with red string on a cork board (no writing). This is a background plate: an animated character will be composited in the center, so keep the central half of the width calm, softly out of focus and low in contrast (a wall, window glow or gentle bokeh), with the interesting detail toward the edges and the top. Eye-level camera, shallow depth of field. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `backdrop-arthur` · P1 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：Arthur（剧院经理）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景）
- 现状：纯色渐变
- 安全区：中间一半宽度保持干净、虚化（人物会叠在中间）

**Prompt**

```text
Portrait 2:3 background illustration of a theatre manager's office above a grand old stage: dark wood panelling, deep red velvet curtains, a brass key board, leather ledgers, framed playbills seen from too far to read, and an interior window looking down on a softly lit, empty stage. This is a background plate: an animated character will be composited in the center, so keep the central half of the width calm, softly out of focus and low in contrast (a wall, window glow or gentle bokeh), with the interesting detail toward the edges and the top. Eye-level camera, shallow depth of field. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `backdrop-marcus` · P1 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：Marcus（舞台监督）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景）
- 现状：纯色渐变
- 安全区：中间一半宽度保持干净、虚化（人物会叠在中间）

**Prompt**

```text
Portrait 2:3 background illustration of a stage manager's prompt corner backstage: a cue-light panel with small coloured bulbs, a headset hanging on a hook, ropes and pulleys of the fly system rising into darkness, painted scenery flats leaning against the wall, a clamp work lamp with warm light against the dark stage. This is a background plate: an animated character will be composited in the center, so keep the central half of the width calm, softly out of focus and low in contrast (a wall, window glow or gentle bokeh), with the interesting detail toward the edges and the top. Eye-level camera, shallow depth of field. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `backdrop-nora` · P1 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：Nora（好奇的同伴）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景）
- 现状：纯色渐变
- 安全区：中间一半宽度保持干净、虚化（人物会叠在中间）

**Prompt**

```text
Portrait 2:3 background illustration of a curious explorer's attic workshop at golden hour: a round window with low warm sun, old maps and a globe, potted plants, small brass gadgets and a telescope, open notebooks with sketches only (no writing); warm and inviting. This is a background plate: an animated character will be composited in the center, so keep the central half of the width calm, softly out of focus and low in contrast (a wall, window glow or gentle bokeh), with the interesting detail toward the edges and the top. Eye-level camera, shallow depth of field. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm golden-hour sunlight with soft teal shadows, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `backdrop-iris` · P1 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：Iris（细心的倾听者）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景）
- 现状：纯色渐变
- 安全区：中间一半宽度保持干净、虚化（人物会叠在中间）

**Prompt**

```text
Portrait 2:3 background illustration of a quiet reading nook by a rainy window at dusk: a window seat with a soft knitted blanket, a tea set, a small stack of letters and a fountain pen (no readable writing), candle light meeting blue-grey dusk; calm and gentle. This is a background plate: an animated character will be composited in the center, so keep the central half of the width calm, softly out of focus and low in contrast (a wall, window glow or gentle bokeh), with the interesting detail toward the edges and the top. Eye-level camera, shallow depth of field. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

### `backdrop-generic` · P1 · 2:3（≥ 1024×1536）

- 用在：创作的角色（通用）：角色页舞台、私聊左侧舞台、牌桌侧栏、故事左栏（作为 Live2D 后面的背景）
- 现状：纯色渐变
- 安全区：中间一半宽度保持干净、虚化（人物会叠在中间）

**Prompt**

```text
Portrait 2:3 background illustration of a neutral cozy room at night with a window, warm lamps and soft bokeh lights, no specific profession; suits any character. This is a background plate: an animated character will be composited in the center, so keep the central half of the width calm, softly out of focus and low in contrast (a wall, window glow or gentle bokeh), with the interesting detail toward the edges and the top. Eye-level camera, shallow depth of field. Style: painterly cinematic digital illustration, semi-realistic, fine brushwork, soft volumetric light, warm amber and brass lamplight against cool teal-blue night, rich but muted colors, high detail. No people, no faces, no human silhouettes. No text, letters, numbers, readable writing, signage, logos, watermarks or UI elements. Not photographic, not cartoon or chibi, no horror.
```

## 游戏封面（候选）

### `game-royale-cover` · P2 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：发现页游戏卡片（居中裁成正方形）、准备页海报（3:4）、“一起玩”弹窗
- 现状：480×480 的首页预览视频首帧（棋盘截图，偏糊）
- 安全区：主体在中央正方形内

**Prompt**

```text
Original key art for a casino dice board game. A stylized night boulevard of six glamorous fictional casino buildings in black-and-gold art-deco style with neon accents, seen from slightly above; in the foreground on green felt, a handful of colourful six-sided dice with white pips tumbling mid-roll beside a fan of fictional pastel banknotes decorated only with abstract guilloche patterns; gold light bokeh. Rich black, gold, emerald and ruby; polished premium tabletop-game illustration. Main subject inside the central square of a portrait 2:3 frame. No text, letters or numbers anywhere (titles and values are drawn by the app), no logos or publisher marks, no watermarks, no people; do not imitate any published board game's box or card art. No real casino names, city signs or real currency designs.
```

### `game-splendor-cover` · P2 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：同上
- 现状：同上
- 安全区：主体在中央正方形内

**Prompt**

```text
Original key art evoking the Renaissance gem trade. A merchant's walnut table by an arched stone window overlooking a Renaissance harbour city at golden hour; on a deep velvet cloth lie piles of cut and uncut gemstones — emerald green, sapphire blue, ruby red, diamond white and onyx black — with a few plain gold tokens, a brass balance scale and a closed leather ledger tied with a ribbon. Oil-painting look, warm light, rich textures. Main subject inside the central square of a portrait 2:3 frame. No text, letters or numbers anywhere (titles and values are drawn by the app), no logos or publisher marks, no watermarks, no people; do not imitate any published board game's box or card art.
```

### `game-cabo-cover` · P2 · 2:3（≥ 1024×1536） · 候选 2 张

- 用在：同上
- 现状：同上
- 安全区：主体在中央正方形内

**Prompt**

```text
Original whimsical storybook illustration for a light card game. Four playing cards fan out in the center against a deep forest-green background with a subtle leaf pattern; each card shows a cute creature in lush leaves, flowers and mushrooms — a fox, a small octopus, an owl and a rabbit — and a fifth card lies face down showing an ornamental pattern of overlapping green, teal and yellow leaf scales. Bright friendly colours, gouache-like texture, clean shapes, soft shading, children's-book quality. The cards carry no numbers, letters or symbols. Main subject inside the central square of a portrait 2:3 frame. No text, letters or numbers anywhere (titles and values are drawn by the app), no logos or publisher marks, no watermarks, no people; do not imitate any published board game's box or card art. No scary creatures.
```

## 空状态 / 错误状态插画

### `empty-friends` · P2 · 1:1（≥ 1024×1024） · 透明

- 用在：好友页空状态（还没有好友 / 需要登录）
- 现状：只有文字，页面大面积空白
- 安全区：主体居中，四周留白

**Prompt**

```text
two cups of tea side by side on a windowsill, gentle rain outside the window, a small potted plant; cozy and inviting. Minimal line-and-wash spot illustration on a transparent background (if transparency is impossible, use a flat #1B1311 background). Palette limited to warm amber #E3B997, terracotta #CB5367 and muted teal #4B94B5 with cream highlights; thin confident lines, lots of negative space, readable at 160 px wide. No text, no letters, no numbers, no people.
```

### `empty-recent` · P2 · 1:1（≥ 1024×1024） · 透明

- 用在：最近页空状态
- 现状：只有文字，页面大面积空白
- 安全区：主体居中，四周留白

**Prompt**

```text
a small neat stack of blank ticket stubs, a ribbon bookmark and a single die, loosely arranged. Minimal line-and-wash spot illustration on a transparent background (if transparency is impossible, use a flat #1B1311 background). Palette limited to warm amber #E3B997, terracotta #CB5367 and muted teal #4B94B5 with cream highlights; thin confident lines, lots of negative space, readable at 160 px wide. No text, no letters, no numbers, no people.
```

### `empty-create` · P2 · 1:1（≥ 1024×1024） · 透明

- 用在：创作页空状态
- 现状：只有文字，页面大面积空白
- 安全区：主体居中，四周留白

**Prompt**

```text
an open sketchbook with a pencil resting on it and a small desk lamp glowing beside it; hopeful. Minimal line-and-wash spot illustration on a transparent background (if transparency is impossible, use a flat #1B1311 background). Palette limited to warm amber #E3B997, terracotta #CB5367 and muted teal #4B94B5 with cream highlights; thin confident lines, lots of negative space, readable at 160 px wide. No text, no letters, no numbers, no people.
```

### `state-not-found` · P2 · 1:1（≥ 1024×1024） · 透明

- 用在：找不到内容 / 局不存在
- 现状：只有文字，页面大面积空白
- 安全区：主体居中，四周留白

**Prompt**

```text
a small wooden door slightly ajar with a soft lamp glow behind it and a few fallen leaves on the step; calm, not alarming. Minimal line-and-wash spot illustration on a transparent background (if transparency is impossible, use a flat #1B1311 background). Palette limited to warm amber #E3B997, terracotta #CB5367 and muted teal #4B94B5 with cream highlights; thin confident lines, lots of negative space, readable at 160 px wide. No text, no letters, no numbers, no people.
```

### `state-load-error` · P2 · 1:1（≥ 1024×1024） · 透明

- 用在：加载失败（不是“没有内容”）
- 现状：只有文字，页面大面积空白
- 安全区：主体居中，四周留白

**Prompt**

```text
a short string of warm fairy lights, slightly tangled, with one bulb dimmed; gentle "something went wrong", not alarming. Minimal line-and-wash spot illustration on a transparent background (if transparency is impossible, use a flat #1B1311 background). Palette limited to warm amber #E3B997, terracotta #CB5367 and muted teal #4B94B5 with cream highlights; thin confident lines, lots of negative space, readable at 160 px wide. No text, no letters, no numbers, no people.
```

### `state-signin` · P2 · 1:1（≥ 1024×1024） · 透明

- 用在：需要登录的提示
- 现状：只有文字，页面大面积空白
- 安全区：主体居中，四周留白

**Prompt**

```text
a small brass key resting on a folded letter sealed with a blank wax seal (no letters on the seal). Minimal line-and-wash spot illustration on a transparent background (if transparency is impossible, use a flat #1B1311 background). Palette limited to warm amber #E3B997, terracotta #CB5367 and muted teal #4B94B5 with cream highlights; thin confident lines, lots of negative space, readable at 160 px wide. No text, no letters, no numbers, no people.
```

## 创作工作室

### `create-type-story` · P3 · 1:1（≥ 1024×1024） · 透明

- 用在：新建作品弹窗里的“故事”类型卡片
- 现状：只有图标
- 安全区：居中

**Prompt**

```text
An open book with a tiny pop-up theatre stage and curtain rising from its pages. Minimal line-and-wash spot illustration on a transparent background (if transparency is impossible, use a flat #1B1311 background). Palette limited to warm amber #E3B997, terracotta #CB5367 and muted teal #4B94B5 with cream highlights; thin confident lines, lots of negative space, readable at 160 px wide. No text, no letters, no numbers, no people.
```

### `create-type-character` · P3 · 1:1（≥ 1024×1024） · 透明

- 用在：新建作品弹窗里的“角色”类型卡片
- 现状：只有图标
- 安全区：居中

**Prompt**

```text
An empty ornate oval portrait frame standing on a small easel, a few soft sparkles around it, no face or figure inside the frame. Minimal line-and-wash spot illustration on a transparent background (if transparency is impossible, use a flat #1B1311 background). Palette limited to warm amber #E3B997, terracotta #CB5367 and muted teal #4B94B5 with cream highlights; thin confident lines, lots of negative space, readable at 160 px wide. No text, no letters, no numbers, no people.
```

### `work-cover-01` · P3 · 2:3（≥ 1024×1536）

- 用在：用户自建作品的默认封面（作品卡片、试演、最近）
- 现状：没有封面
- 安全区：中央保持安静，方便叠标题

**Prompt**

```text
Soft painterly abstract cover background: rain running down a window pane over warm out-of-focus lights. Calm center area for an overlaid title, works at small sizes, warm amber, terracotta and muted teal palette. No text, letters, numbers, logos or people.
```

### `work-cover-02` · P3 · 2:3（≥ 1024×1536）

- 用在：用户自建作品的默认封面（作品卡片、试演、最近）
- 现状：没有封面
- 安全区：中央保持安静，方便叠标题

**Prompt**

```text
Soft painterly abstract cover background: a parted deep red velvet stage curtain with a warm glow behind it. Calm center area for an overlaid title, works at small sizes, warm amber, terracotta and muted teal palette. No text, letters, numbers, logos or people.
```

### `work-cover-03` · P3 · 2:3（≥ 1024×1536）

- 用在：用户自建作品的默认封面（作品卡片、试演、最近）
- 现状：没有封面
- 安全区：中央保持安静，方便叠标题

**Prompt**

```text
Soft painterly abstract cover background: a night sky with constellations drawn as dotted lines and small stars (no letters). Calm center area for an overlaid title, works at small sizes, warm amber, terracotta and muted teal palette. No text, letters, numbers, logos or people.
```

### `work-cover-04` · P3 · 2:3（≥ 1024×1536）

- 用在：用户自建作品的默认封面（作品卡片、试演、最近）
- 现状：没有封面
- 安全区：中央保持安静，方便叠标题

**Prompt**

```text
Soft painterly abstract cover background: layered paper-cut leaves in teal and amber. Calm center area for an overlaid title, works at small sizes, warm amber, terracotta and muted teal palette. No text, letters, numbers, logos or people.
```

### `work-cover-05` · P3 · 2:3（≥ 1024×1536）

- 用在：用户自建作品的默认封面（作品卡片、试演、最近）
- 现状：没有封面
- 安全区：中央保持安静，方便叠标题

**Prompt**

```text
Soft painterly abstract cover background: soft ink-wash waves in muted teal with a thin gold horizon. Calm center area for an overlaid title, works at small sizes, warm amber, terracotta and muted teal palette. No text, letters, numbers, logos or people.
```

### `work-cover-06` · P3 · 2:3（≥ 1024×1536）

- 用在：用户自建作品的默认封面（作品卡片、试演、最近）
- 现状：没有封面
- 安全区：中央保持安静，方便叠标题

**Prompt**

```text
Soft painterly abstract cover background: a few glowing paper lanterns floating in warm dusk. Calm center area for an overlaid title, works at small sizes, warm amber, terracotta and muted teal palette. No text, letters, numbers, logos or people.
```

## 我的 Persona 头像

### `persona-avatar-01` · P3 · 1:1（≥ 1024×1024）

- 用在：账号页“我的 Persona”可选头像（不是人物，避免和角色混淆）
- 现状：没有头像
- 安全区：圆形裁切安全

**Prompt**

```text
An umbrella in light rain. Flat storybook illustration inside a circle-safe composition (the image will be cropped to a circle), deep warm brown background #2A1D19, simple bold shapes in amber, terracotta, teal and cream, readable at 48 px. No text, no letters, no people.
```

### `persona-avatar-02` · P3 · 1:1（≥ 1024×1024）

- 用在：账号页“我的 Persona”可选头像（不是人物，避免和角色混淆）
- 现状：没有头像
- 安全区：圆形裁切安全

**Prompt**

```text
A glowing paper lantern. Flat storybook illustration inside a circle-safe composition (the image will be cropped to a circle), deep warm brown background #2A1D19, simple bold shapes in amber, terracotta, teal and cream, readable at 48 px. No text, no letters, no people.
```

### `persona-avatar-03` · P3 · 1:1（≥ 1024×1024）

- 用在：账号页“我的 Persona”可选头像（不是人物，避免和角色混淆）
- 现状：没有头像
- 安全区：圆形裁切安全

**Prompt**

```text
A steaming teacup. Flat storybook illustration inside a circle-safe composition (the image will be cropped to a circle), deep warm brown background #2A1D19, simple bold shapes in amber, terracotta, teal and cream, readable at 48 px. No text, no letters, no people.
```

### `persona-avatar-04` · P3 · 1:1（≥ 1024×1024）

- 用在：账号页“我的 Persona”可选头像（不是人物，避免和角色混淆）
- 现状：没有头像
- 安全区：圆形裁切安全

**Prompt**

```text
A small sitting fox. Flat storybook illustration inside a circle-safe composition (the image will be cropped to a circle), deep warm brown background #2A1D19, simple bold shapes in amber, terracotta, teal and cream, readable at 48 px. No text, no letters, no people.
```

### `persona-avatar-05` · P3 · 1:1（≥ 1024×1024）

- 用在：账号页“我的 Persona”可选头像（不是人物，避免和角色混淆）
- 现状：没有头像
- 安全区：圆形裁切安全

**Prompt**

```text
A sleeping cat curled up. Flat storybook illustration inside a circle-safe composition (the image will be cropped to a circle), deep warm brown background #2A1D19, simple bold shapes in amber, terracotta, teal and cream, readable at 48 px. No text, no letters, no people.
```

### `persona-avatar-06` · P3 · 1:1（≥ 1024×1024）

- 用在：账号页“我的 Persona”可选头像（不是人物，避免和角色混淆）
- 现状：没有头像
- 安全区：圆形裁切安全

**Prompt**

```text
A round little owl. Flat storybook illustration inside a circle-safe composition (the image will be cropped to a circle), deep warm brown background #2A1D19, simple bold shapes in amber, terracotta, teal and cream, readable at 48 px. No text, no letters, no people.
```

### `persona-avatar-07` · P3 · 1:1（≥ 1024×1024）

- 用在：账号页“我的 Persona”可选头像（不是人物，避免和角色混淆）
- 现状：没有头像
- 安全区：圆形裁切安全

**Prompt**

```text
A folded paper boat on a ripple. Flat storybook illustration inside a circle-safe composition (the image will be cropped to a circle), deep warm brown background #2A1D19, simple bold shapes in amber, terracotta, teal and cream, readable at 48 px. No text, no letters, no people.
```

### `persona-avatar-08` · P3 · 1:1（≥ 1024×1024）

- 用在：账号页“我的 Persona”可选头像（不是人物，避免和角色混淆）
- 现状：没有头像
- 安全区：圆形裁切安全

**Prompt**

```text
A crescent moon with one star. Flat storybook illustration inside a circle-safe composition (the image will be cropped to a circle), deep warm brown background #2A1D19, simple bold shapes in amber, terracotta, teal and cream, readable at 48 px. No text, no letters, no people.
```

## 品牌（仅候选，由你决定）

### `brand-emblem` · P3 · 1:1（≥ 1024×1024） · 透明 · 候选 2 张

- 用在：左侧导航的品牌标记、加载页
- 现状：CSS 画的字母 e
- 安全区：居中

**Prompt**

```text
A simple warm emblem for an app about companionship and playing together: two overlapping circles forming a soft lantern-like glow with a tiny spark where they meet. Flat geometric shapes in amber and cream on a transparent background, elegant, readable at 24 px. No letters, no text, no people.
```

### `app-icon` · P3 · 1:1（≥ 1024×1024） · 候选 2 张

- 用在：浏览器标签图标 / 桌面图标
- 现状：没有
- 安全区：居中，四周留出圆角安全区

**Prompt**

```text
The same warm emblem (two overlapping circles forming a soft lantern-like glow with a tiny spark where they meet), centered on a rounded-square tile of deep warm brown #1E1412 with a subtle radial glow. Flat, crisp, readable at 32 px. No letters, no text, no people.
```

## 不需要生成的

- 五位角色的立绘、头像、Live2D：必须用冻结素材。
- 三款游戏的卡面/板面：Royale 赌场 atlas、Splendor 卡面/贵族/宝石、CABO 14 张点数插画都已在交接包里。

## 图到了之后我会做什么

1. 从 `generated-assets/batch-01/` 取图，放进项目的 `public/generated/batch-01/`（不混入哈希锁定的交接包素材），生成 `docs/GENERATED_ASSETS.json`：路径、字节数、sha256、对应 prompt、工具/模型、日期、权利标签；候选图挑一张，没选中的也记录在案。
2. 接入：两个故事的封面与逐拍场景（故事数据里给每一拍指定场景）、角色背景（角色页、私聊、牌桌侧栏、故事左栏，人物居中叠在上面）、空/错误状态插画；游戏封面先作为候选，你确认后再设为默认。
3. P3 需要加小功能：作品默认封面可选、Persona 头像选择、品牌标记——你确认要哪些再做。
4. 加 `assets:generated:check` 校验哈希；重拍截图、跑四宽度矩阵和全部测试，更新 `ACCEPTANCE.md`。

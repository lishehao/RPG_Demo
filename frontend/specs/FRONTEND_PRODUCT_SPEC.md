# Frontend Product Spec

## 项目目的

这个项目的产品目标不是“做一个通用内容平台”，而是一个明确的短循环：

1. 用户输入一个英文 seed
2. 后端生成 preview
3. 用户触发 author job
4. 前端展示等待态和生成进度
5. 生成完成后发布进 story library
6. 用户从 library 里选择故事开始游玩
7. 游玩过程以自然语言输入为主，建议动作只是辅助

当前产品重点：

- 英文优先
- async author generation
- shared story library
- 10 分钟左右短局 play session
- visible state bars
- second-person GM narration

## 用户心智

用户不是在“写配置”，而是在做三件事：

1. `Pitch a story`
   用户想快速给一个主题或句子，看系统会把它理解成什么故事。
2. `Watch it take shape`
   用户知道生成要花时间，所以等待页必须持续告诉他“故事正在怎么成型”。
3. `Pick and play`
   用户把最终结果当作一个可玩的故事卡片，而不是一堆后台工件。

前端要围绕这三个心智组织：

- 输入页：像投一个 story concept
- 等待页：像看故事骨架逐步成型
- library：像挑选要玩的 episode
- play：像和 GM 对话，而不是点树状菜单

## 页面与流程

建议前端第一版至少包含这几页：

1. `Seed Input`
   - 输入 `prompt_seed`
   - 调 `POST /author/story-previews`
   - 展示 preview card
   - 调 `POST /author/jobs`

2. `Author Loading`
   - 轮询 `GET /author/jobs/{job_id}` 或使用 `GET /author/jobs/{job_id}/events`
   - 主要展示 `progress_snapshot.loading_cards`
   - 完成后调 `GET /author/jobs/{job_id}/result`
   - 用户点击发布时调 `POST /author/jobs/{job_id}/publish`

3. `Story Library`
   - 调 `GET /stories`
   - 点击单个 story 调 `GET /stories/{story_id}`
   - 用户点击 `Play` 调 `POST /play/sessions`

4. `Play Session`
   - 调 `GET /play/sessions/{session_id}` 获取最新状态
   - 调 `GET /play/sessions/{session_id}/history` 获取稳定 transcript 历史
   - 调 `POST /play/sessions/{session_id}/turns` 提交自然语言输入
   - 展示：
     - narration
     - state bars
     - 3 条 suggested actions
     - ending

## API 对应

Interface governance source:

- canonical contract governance: `specs/interface_governance_20260319.md`
- backend contract source of truth:
  - `rpg_backend/author/contracts.py`
  - `rpg_backend/library/contracts.py`
  - `rpg_backend/play/contracts.py`
- frontend mirrors:
  - `frontend/src/api/contracts.ts`
  - `frontend/src/api/route-map.ts`
  - `frontend/src/api/http-client.ts`

前端占位 API 必须一一对应当前后端：

| Frontend method | Backend route | Purpose |
| --- | --- | --- |
| `createStoryPreview` | `POST /author/story-previews` | 生成 preview |
| `createAuthorJob` | `POST /author/jobs` | 启动 author job |
| `getAuthorJob` | `GET /author/jobs/{job_id}` | 轮询 job 状态 |
| `streamAuthorJobEvents` | `GET /author/jobs/{job_id}/events` | SSE 进度流 |
| `getAuthorJobResult` | `GET /author/jobs/{job_id}/result` | 取最终结果 |
| `publishAuthorJob` | `POST /author/jobs/{job_id}/publish` | 发布进 library |
| `listStories` | `GET /stories` | library 列表，支持 `q/theme/limit/cursor/sort` |
| `getStory` | `GET /stories/{story_id}` | story 详情 |
| `createPlaySession` | `POST /play/sessions` | 从 published story 开局 |
| `getPlaySession` | `GET /play/sessions/{session_id}` | 取当前局面 |
| `getPlaySessionHistory` | `GET /play/sessions/{session_id}/history` | 取公共 transcript 历史 |
| `submitPlayTurn` | `POST /play/sessions/{session_id}/turns` | 提交一回合 |

## 前端依赖边界

前端当前可以稳定依赖：

- 路由名
- 主要请求字段
- 主要响应 shape
- `preview` / `progress_snapshot` / `summary` / `story` / `play session snapshot`
- additive play fields:
  - `protagonist`
  - `feedback`
  - `progress`
  - `support_surfaces`
- additive play route:
  - `GET /play/sessions/{session_id}/history`
- story detail additive fields:
  - `presentation`
  - `play_overview`

前端当前不应该写死：

- ending 分布
- suggested actions 的文案风格
- play 在第几回合一定结束
- 任意内部 telemetry 字段
- author bundle 内部细粒度结构
- `/benchmark/*` 诊断路由的任何字段

## Placeholder API 约束

当前 placeholder API 的设计要求：

- 方法名一一对应后端路由
- 主要字段名与后端保持一致
- placeholder job 会模拟阶段推进
- placeholder story library 会预置少量 demo stories，同时支持从 author job 发布
- placeholder play session 会返回 narration、state bars、suggested actions 和 ending

占位层的目标不是完全复刻后台逻辑，而是：

- 让前端页面可以先开发
- 让页面流和字段依赖先稳定下来
- 以后切换真实后端时不需要重写组件层调用方式

## 当前最适合前端先做的东西

1. 输入页与 preview 卡片
2. loading 页与 loading cards
3. library 卡片列表与详情
4. play 页的 narration + state bars + chat input + suggested actions
5. optional story detail dossier metadata built from stable additive fields

## 非目标

当前这份 frontend spec 不包含：

- 具体 UI 框架选择
- 最终视觉设计
- auth / user ownership
- moderation / review flows
- 多人协作

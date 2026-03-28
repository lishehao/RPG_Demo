# RPG Demo Rebuild

## 项目是什么

这是一个前后端同仓的互动叙事 Demo，产品闭环很短：

1. 输入英文 story seed
2. 生成 preview
3. 启动 author job
4. 发布到 library
5. 从 library 进入 play session
6. 用自然语言推进剧情

当前项目以现有接口治理和产品主链为准。

## 技术栈

- 后端：FastAPI + Pydantic + LangGraph
- 前端：React 19 + TypeScript + Vite
- 存储：SQLite
- 身份：真实 cookie session auth

主要后端域：

- `rpg_backend/author/`
- `rpg_backend/library/`
- `rpg_backend/play/`
- `rpg_backend/benchmark/`

## 当前状态

- `author -> publish -> play` 全链路可用
- public library / private owned story / protected play session 权限边界已打通
- author job、play session、author checkpoint 可跨重启恢复
- 部署形态仍建议单机单进程，不支持多实例共享

## 本地运行

先复制配置：

```bash
cp .env.example .env
```

当前统一配置入口：

- `APP_GATEWAY_*`：统一 text / embedding gateway 配置
- `APP_HELPER_GATEWAY_*`：内部 helper agent 专用配置，供 benchmark 或后续 UI agent 直接调用，不回退主生成模型
- `APP_ROSTER_ENABLED` / `APP_ROSTER_SOURCE_CATALOG_PATH` / `APP_ROSTER_RUNTIME_CATALOG_PATH`：character roster 正式运行时开关与 catalog 路径

推荐 text gateway 写法：

```env
APP_GATEWAY_BASE_URL=https://dashscope-us.aliyuncs.com/compatible-mode/v1
APP_GATEWAY_API_KEY=replace_me
APP_GATEWAY_MODEL=qwen3.5-flash
# 如需单独把 play.* 切到更强模型，再额外配置：
# APP_GATEWAY_PLAY_MODEL=qwen3.5-plus
# 如果 responses 端点和 chat_completions 端点不同，再额外配置：
# APP_GATEWAY_RESPONSES_BASE_URL=https://dashscope-us.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1
```

独立 embedding 推荐写法：

```env
APP_ROSTER_ENABLED=true
APP_ROSTER_SOURCE_CATALOG_PATH=data/character_roster/catalog.json
APP_ROSTER_RUNTIME_CATALOG_PATH=artifacts/character_roster_runtime.json
APP_ROSTER_MAX_SUPPORTING_CAST_SELECTIONS=3
APP_GATEWAY_EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
APP_GATEWAY_EMBEDDING_API_KEY=replace_me
APP_GATEWAY_EMBEDDING_MODEL=gemini-embedding-001
APP_LOCAL_PORTRAIT_BASE_URL=http://127.0.0.1:8000
```

同一套 `APP_GATEWAY_BASE_URL / API_KEY / MODEL` 可以由不同调用点分别走 `responses` 或 `chat_completions`。
具体 transport 由脚本或 gateway 入口决定，不再通过 env 全局切换。
如果 provider 的 responses 端点单独分开，就只额外补一个 `APP_GATEWAY_RESPONSES_BASE_URL`。

如需显式控制 session cache header，也统一使用 `APP_GATEWAY_SESSION_CACHE_HEADER` / `APP_GATEWAY_SESSION_CACHE_VALUE`。

如需给内部 helper agent 单独挂模型，可额外配置：

```env
APP_HELPER_GATEWAY_BASE_URL=https://api.openai.com/v1
APP_HELPER_GATEWAY_API_KEY=replace_me
APP_HELPER_GATEWAY_MODEL=gpt-5-mini
# 如果 helper 的 responses 端点与 chat_completions 不同，再额外补：
# APP_HELPER_GATEWAY_RESPONSES_BASE_URL=https://api.openai.com/v1
```

helper 配置不会自动回退到主 `APP_GATEWAY_*`。启用 helper 模式时，四项里至少要填 `BASE_URL / API_KEY / MODEL`。
benchmark / playtest agent 会直接复用这组 `APP_HELPER_GATEWAY_*` 作为实验 provider。
如果 helper 在 `chat_completions` 下不支持 `json_schema` structured output，benchmark agent 会自动回退到主 `APP_GATEWAY_*`。
当前 `www.jnm.lol / gpt-5.4-mini` 这组 provider 只按 `chat_completions` 验证通过，不建议给它配置 responses 端点。

本地头像批量生成：

```env
PORTRAIT_IMAGE_API_KEY=replace_me
```

后端：

```bash
pip install -e ".[dev]"
uvicorn rpg_backend.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

如果本地 SQLite 或运行时产物来自旧 schema，不再做兼容修复，直接重建：

```bash
python tools/reset_local_databases.py
rm -f artifacts/character_roster_runtime.json
python tools/character_roster_admin.py build
```

## 常用验证

后端测试：

```bash
pytest -q
```

前端检查：

```bash
cd frontend
npm run check
```

真实 HTTP smoke：

```bash
python tools/http_product_smoke.py --base-url http://127.0.0.1:8000
```

带 benchmark 诊断的 smoke：

```bash
python tools/http_product_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --include-benchmark-diagnostics
```

helper benchmark driver 可选切到独立 helper 模型：

```bash
python tools/play_benchmarks/live_api_playtest.py \
  --base-url http://127.0.0.1:8000 \
  --use-helper-agent \
  --agent-transport-style chat_completions
```

## 部署

生产域名：

- `https://rpg.shehao.app`

AWS 单机部署材料：

- `deploy/aws_ubuntu/DEPLOY.md`
- `deploy/aws_ubuntu/.env.production.example`
- `deploy/aws_ubuntu/rpg-demo-backend.service`
- `deploy/aws_ubuntu/nginx-rpg-demo.conf`

## 相关文档

- `specs/interface_governance_20260319.md`
- `specs/interface_stability_matrix_20260319.md`
- `frontend/specs/FRONTEND_PRODUCT_SPEC.md`

import type { StoryLanguage } from "../../index"
import { uiText } from "../lib/ui-language"

export function SceneLoadingShell({
  routeName,
  uiLanguage,
}: {
  routeName: "auth" | "create-story" | "author-loading" | "story-library" | "story-detail" | "play-session"
  uiLanguage: StoryLanguage
}) {
  const copy = {
    auth: {
      title: uiText(uiLanguage, { en: "Loading account access", zh: "正在加载账号入口" }),
      body: uiText(uiLanguage, { en: "Preparing sign-in and session controls.", zh: "正在准备登录和会话相关界面。" }),
    },
    "create-story": {
      title: uiText(uiLanguage, { en: "Loading story creation", zh: "正在加载创作页" }),
      body: uiText(uiLanguage, { en: "Preparing the seed composer and preview pane.", zh: "正在准备故事种子输入区和预览面板。" }),
    },
    "author-loading": {
      title: uiText(uiLanguage, { en: "Loading author session", zh: "正在加载创作会话" }),
      body: uiText(uiLanguage, { en: "Preparing the current authoring job and studio state.", zh: "正在准备当前生成任务和编辑工作台状态。" }),
    },
    "story-library": {
      title: uiText(uiLanguage, { en: "Loading library", zh: "正在加载故事库" }),
      body: uiText(uiLanguage, { en: "Preparing stories, filters, and the current view.", zh: "正在准备故事列表、筛选项和当前视图。" }),
    },
    "story-detail": {
      title: uiText(uiLanguage, { en: "Loading story detail", zh: "正在加载故事详情" }),
      body: uiText(uiLanguage, { en: "Preparing the reading flow and play handoff.", zh: "正在准备阅读内容和试玩入口。" }),
    },
    "play-session": {
      title: uiText(uiLanguage, { en: "Loading play session", zh: "正在加载试玩会话" }),
      body: uiText(uiLanguage, { en: "Preparing the transcript, state, and action surfaces.", zh: "正在准备文本记录、状态面板和行动输入区。" }),
    },
  }[routeName]

  return (
    <main className="editorial-page-shell">
      <section className="editorial-page scene-loading-shell">
        <div className="editorial-empty-state">
          <h3>{copy.title}</h3>
          <p>{copy.body}</p>
        </div>
      </section>
    </main>
  )
}

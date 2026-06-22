import { type CSSProperties, type ReactNode } from "react"
import { Header } from "../../shared/ui/header"
import { useLanguage } from "../../shared/lib/i18n"

/**
 * Bilingual project/about page for the portfolio demo. This is not a legal
 * terms page; it keeps the player-facing loop, local evidence boundary, and
 * AI-content limits aligned with the README/reviewer path.
 */
export function AboutPage({
  onBackHome,
  onOpenCreate,
}: {
  onBackHome: () => void
  onOpenCreate: () => void
}) {
  const { lang } = useLanguage()
  const content = lang === "en" ? aboutContentEn : aboutContentZh
  return (
    <div style={apStyles.page}>
      <Header onHome={onBackHome} onCreate={onOpenCreate} showBackButton />
      <main style={apStyles.main} data-about-page="true">
        <h1 style={apStyles.title}>{content.title}</h1>
        {content.sections.map((section, i) => (
          <section style={apStyles.section} key={i} data-about-section={section.id}>
            <h2 style={apStyles.h2}>{section.heading}</h2>
            {section.body}
          </section>
        ))}
      </main>
    </div>
  )
}

type AboutContent = {
  title: string
  sections: ReadonlyArray<{ id: string; heading: string; body: ReactNode }>
}

const apStyles: Record<string, CSSProperties> = {
  page: { minHeight: "100%", background: "var(--bg)" },
  main: { maxWidth: 720, margin: "0 auto", padding: "56px 32px 80px" },
  title: {
    fontFamily: "var(--font-narrative)",
    fontSize: 36,
    fontWeight: 400,
    margin: "0 0 36px",
  },
  section: { marginBottom: 36 },
  h2: {
    fontFamily: "var(--font-narrative)",
    fontSize: 20,
    fontWeight: 500,
    margin: "0 0 14px",
    color: "var(--text)",
  },
  p: {
    fontSize: 15,
    lineHeight: 1.75,
    color: "var(--text-muted)",
    margin: "0 0 14px",
  },
  ul: {
    fontSize: 15,
    lineHeight: 1.75,
    color: "var(--text-muted)",
    paddingLeft: 22,
    margin: "0 0 14px",
  },
  link: { color: "var(--accent)", textDecoration: "underline" },
}

const aboutContentZh: AboutContent = {
  title: "关于 / 隐私",
  sections: [
    {
      id: "what-this-is",
      heading: "这是什么",
      body: (
        <>
          <p style={apStyles.p}>
            Tiny Stories 是作品集案例里的互动短剧演示。你写下一个戏剧瞬间,
            系统把它变成角色、目标、开场场景和少量可选行动; 你读场景、
            比较选择、行动一次,再根据可见后果进入下一回合.
          </p>
          <p style={apStyles.p}>
            它的目标不是无穷小说流或聊天机器人,而是一个短篇、可结束、可回放的
            AI 互动短剧系统。当前请把它读作作品集/申请材料证据,不是已经上线的
            消费级服务.
          </p>
        </>
      ),
    },
    {
      id: "data-boundary",
      heading: "数据和本地边界",
      body: (
        <>
          <ul style={apStyles.ul}>
            <li>本地运行会保存故事模板、游玩记录、选择、顾问对话和回放。</li>
            <li>公开/私有/凭链接的可见性用于 demo 路径,不是已发布的商业账户系统.</li>
            <li>不要在开场设定、自由输入或私下动机里写真实秘密、账号、密钥或私人身份信息。</li>
          </ul>
          <p style={apStyles.p}>
            申请材料里可验证的是工程闭环: 类型化数据约束、持久化状态、评审证据、
            失败恢复路径和移动端 UI。如果公开证据预检失败,请把当前 `#/portfolio`、
            `#/reviewer`、Create、Play 和 Replay 都标成本地证据.
          </p>
        </>
      ),
    },
    {
      id: "content-boundary",
      heading: "内容与边界",
      body: (
        <>
          <p style={apStyles.p}>
            故事内容由 AI 生成,可能出现不连贯、不合逻辑或与你预期不同的情节.
            这正是项目需要可见状态、回合边界、回放和评审证据的原因:
            让人能检查系统如何处理不确定性.
          </p>
          <p style={apStyles.p}>
            <strong>请不要:</strong>
            生成涉及未成年人的不当内容、教唆暴力或自残、造谣针对真实人物的
            内容,或把真实敏感信息放进剧情.
          </p>
        </>
      ),
    },
    {
      id: "review-path",
      heading: "怎么审阅这个项目",
      body: (
        <>
          <p style={apStyles.p}>
            推荐顺序:先看 75 秒 demo,再本地打开 `#/portfolio`,从那里启动
            `#/reviewer`,最后对照 README、系统地图、案例文档和测试.
          </p>
          <p style={apStyles.p}>
            普通玩家界面应该只显示剧情和选择;评审证据应该留在专门路径里,
            用来检查可游玩状态、一次行动后的可见变化和证据边界.
          </p>
        </>
      ),
    },
  ],
}

const aboutContentEn: AboutContent = {
  title: "About / Privacy",
  sections: [
    {
      id: "what-this-is",
      heading: "What this is",
      body: (
        <>
          <p style={apStyles.p}>
            Tiny Stories is an interactive short-drama demo inside a
            portfolio case study. You write a dramatic moment; the
            system turns it into roles, goals, an opening scene, and a
            small set of playable moves. You read the scene, compare
            choices, act once, then use the visible consequence to pick
            the next beat.
          </p>
          <p style={apStyles.p}>
            The goal is not an infinite fiction feed or a chat bot. It
            is a compact AI story game with a bounded episode,
            visible state, ending, and replay. Read it as portfolio and
            application evidence, not as a launched consumer service.
          </p>
        </>
      ),
    },
    {
      id: "data-boundary",
      heading: "Data and local boundary",
      body: (
        <>
          <ul style={apStyles.ul}>
            <li>Local runs store story templates, play sessions, choices, advisor messages, and replays.</li>
            <li>Public, private, and link-only visibility support the demo path; they are not proof of a shipped account system.</li>
            <li>Do not put real secrets, credentials, keys, or private identity details into seeds, free actions, or inner motives.</li>
          </ul>
          <p style={apStyles.p}>
            The application evidence is the engineered loop: typed
            contracts, persistent state, reviewer evidence, recovery
            paths, and mobile UI. If the public preflight fails, treat
            `#/portfolio`, `#/reviewer`, Create, Play, and Replay as
            local-only evidence until the intended branch is deployed.
          </p>
        </>
      ),
    },
    {
      id: "content-boundary",
      heading: "Content boundaries",
      body: (
        <>
          <p style={apStyles.p}>
            Story content is generated by AI and can be inconsistent,
            implausible, or different from what you expected. That is
            why the project keeps state, turn boundaries, replay, and
            reviewer evidence visible: the system should be inspectable
            when generation is uncertain.
          </p>
          <p style={apStyles.p}>
            <strong>Please don't:</strong> generate inappropriate
            content involving minors, incite violence or self-harm,
            post defamatory content about real people, or place real
            sensitive information into the story.
          </p>
        </>
      ),
    },
    {
      id: "review-path",
      heading: "How to review it",
      body: (
        <>
          <p style={apStyles.p}>
            Recommended path: watch the 75-second demo, run locally,
            open `#/portfolio`, launch `#/reviewer`, then compare the
            result with the README, Current System Map, Case Study, and
            contract tests.
          </p>
          <p style={apStyles.p}>
            Normal players should see story and decisions. Reviewer
            evidence stays on the dedicated inspection path so it can
            check playable state, visible change after a move, and evidence limits
            without turning Play into a dashboard.
          </p>
        </>
      ),
    },
  ],
}

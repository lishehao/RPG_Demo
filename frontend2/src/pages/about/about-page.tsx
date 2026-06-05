import { type CSSProperties, type ReactNode } from "react"
import { Header } from "../../shared/ui/header"
import { useLanguage } from "../../shared/lib/i18n"
import { PAGE_BG } from "../../shared/lib/webtoon-assets"

/**
 * Minimal "About / Terms / Privacy" stub. Single page covering:
 *   - what this product is
 *   - what we store / don't share
 *   - how to report broken / inappropriate content
 *   - contact
 *
 * Pre-launch this is enough to satisfy a basic legal floor and
 * give users somewhere to link from a footer. Replace with a real
 * legal review before any commercial launch.
 *
 * Content is bilingual: zh and en branches render entirely separate
 * paragraph blocks rather than translating field-by-field, because
 * the prose flow matters and word-level translation produces a
 * stilted page.
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
      <Header onHome={onBackHome} onCreate={onOpenCreate} />
      <main style={apStyles.main}>
        <h1 style={apStyles.title}>{content.title}</h1>
        {content.sections.map((section, i) => (
          <section style={apStyles.section} key={i}>
            <h2 style={apStyles.h2}>{section.heading}</h2>
            {section.body}
          </section>
        ))}
        <div style={apStyles.footer}>
          <button
            style={apStyles.backAction}
            onClick={onBackHome}
            type="button"
          >
            {content.backToHome}
          </button>
        </div>
      </main>
    </div>
  )
}

type AboutContent = {
  title: string
  sections: ReadonlyArray<{ heading: string; body: ReactNode }>
  backToHome: string
}

const apStyles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100%",
    background:
      `linear-gradient(90deg, rgba(8,8,12,0.98) 0%, rgba(8,8,12,0.92) 58%, rgba(8,8,12,0.72) 100%), linear-gradient(180deg, rgba(8,8,12,0.06) 0%, var(--bg) 92%), url(${PAGE_BG.login})`,
    backgroundSize: "cover",
    backgroundPosition: "center",
    color: "var(--text)",
  },
  main: { maxWidth: 820, margin: "0 auto", padding: "64px 32px 88px" },
  title: {
    fontFamily: "var(--font-narrative)",
    fontSize: 42,
    fontWeight: 400,
    margin: "0 0 40px",
    color: "rgba(255,250,242,0.98)",
  },
  section: {
    marginBottom: 0,
    padding: "26px 0 28px",
    borderTop: "1px solid rgba(255,255,255,0.10)",
  },
  h2: {
    fontFamily: "var(--font-ui)",
    fontSize: 13,
    fontWeight: 760,
    margin: "0 0 14px",
    color: "rgba(245,200,120,0.88)",
    letterSpacing: 0,
  },
  p: {
    fontSize: 15,
    lineHeight: 1.75,
    color: "rgba(244,239,230,0.82)",
    margin: "0 0 14px",
  },
  ul: {
    fontSize: 15,
    lineHeight: 1.75,
    color: "rgba(244,239,230,0.82)",
    paddingLeft: 22,
    margin: "0 0 14px",
  },
  link: { color: "var(--accent)", textDecoration: "underline" },
  footer: {
    paddingTop: 32,
    borderTop: "1px solid rgba(255,255,255,0.10)",
    marginTop: 24,
  },
  backAction: {
    padding: "0 0 5px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid var(--line-strong)",
    borderRadius: 0,
    color: "rgba(244,239,230,0.78)",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 700,
  },
}

const aboutContentZh: AboutContent = {
  title: "关于 Tiny Stories",
  backToHome: "← 回到首页",
  sections: [
    {
      heading: "这是什么",
      body: (
        <>
          <p style={apStyles.p}>
            Tiny Stories 是一个 Brief-first 的互动短剧 beta。你先把想玩的场面
            告诉 Story Guide；它会判断这个想法是否适合当前运行时，并整理成
            Brief Story Card。确认后，系统生成第一幕，你通过选择和自由输入推进
            剧情，12 回合左右走到一个有标签的结局。
          </p>
          <p style={apStyles.p}>
            当前版本优先保证可玩、可回放、可审查的完整路径。部分环境会使用
            可靠的本地规划或固定回退，而不是承诺每一次都由在线模型即时生成。
            这让 demo 更稳定，也更诚实地暴露了 beta 阶段的边界。
          </p>
        </>
      ),
    },
    {
      heading: "我们存什么",
      body: (
        <>
          <ul style={apStyles.ul}>
            <li>你的用户名(仅用于登录与展示)</li>
            <li>你创建的故事模板和你玩的局(包括叙述、选择、顾问对话)</li>
            <li>你的故事是公开还是私有,由你自己决定</li>
          </ul>
          <p style={apStyles.p}>
            <strong>不会做:</strong>
            出售你的数据、把你的故事训练成第三方的模型、把你设为私有的故事公开.
            公开模板的访问者能看到你的玩法回放(这是产品核心机制);
            如果你不希望被看到,把模板设为"只有我"或"凭链接".
          </p>
        </>
      ),
    },
    {
      heading: "内容与边界",
      body: (
        <>
          <p style={apStyles.p}>
            Story Guide 会先检查输入是否适合当前 Tiny Stories 形状：3 个以上人物
            或阵营、一个公开争议物或决定，以及清楚的时间/社交压力。若请求暂时
            不适合，它会解释原因，并给出可直接补强的改写方向。
          </p>
          <p style={apStyles.p}>
            <strong>请不要:</strong>
            生成涉及未成年人的不当内容、教唆暴力或自残、造谣针对真实人物的
            内容.我们保留删除任何违反公序良俗或法律的故事的权利.
          </p>
          <p style={apStyles.p}>
            发现问题内容?给我们发邮件:{" "}
            <a href="mailto:hello@tinystories.app" style={apStyles.link}>
              hello@tinystories.app
            </a>
          </p>
        </>
      ),
    },
    {
      heading: "免责",
      body: (
        <p style={apStyles.p}>
          这是一个 AI 生成内容的产品.所有故事、角色、对话都是虚构的.
          如果某个情节恰好与现实人物或事件相似,那是生成系统的巧合,
          不代表本产品的立场.剧情中的选择、顾问的建议都不是任何形式的
          生活/法律/情感建议 — 它们是戏剧的一部分.
        </p>
      ),
    },
  ],
}

const aboutContentEn: AboutContent = {
  title: "About Tiny Stories",
  backToHome: "← Back to home",
  sections: [
    {
      heading: "What this is",
      body: (
        <>
          <p style={apStyles.p}>
            Tiny Stories is a brief-first interactive short-drama beta.
            You tell the Story Guide what kind of scene you want; it checks
            whether the idea fits the current runtime and turns it into a
            Brief Story Card. Once you confirm it, the system creates the
            first scene. You drive the plot through choices and free-form
            actions, then land on a labeled ending after roughly 12 turns.
          </p>
          <p style={apStyles.p}>
            The current build prioritizes a stable, replayable, inspectable
            product loop. Some environments use reliable local planning or
            deterministic fallbacks rather than promising that every step is
            freshly generated by an online model. That makes the demo more
            stable and makes the beta boundary explicit.
          </p>
        </>
      ),
    },
    {
      heading: "What we store",
      body: (
        <>
          <ul style={apStyles.ul}>
            <li>Your username (for sign-in and display only).</li>
            <li>The story templates you create and the sessions you play (narration, choices, advisor messages).</li>
            <li>Whether each story is public or private — your call.</li>
          </ul>
          <p style={apStyles.p}>
            <strong>What we don't do:</strong> sell your data, train
            third-party models on your stories, or make a private
            story public. Visitors to a public template can replay
            your run (that's the core social mechanic). If you don't
            want that, set the template to "private" or "link only."
          </p>
        </>
      ),
    },
    {
      heading: "Content boundaries",
      body: (
        <>
          <p style={apStyles.p}>
            The Story Guide checks whether a seed fits the current Tiny Stories
            shape: three or more people or factions, a contested object or
            decision, and clear social or time pressure. If an idea is not a
            fit yet, it should explain why and suggest concrete revisions.
          </p>
          <p style={apStyles.p}>
            <strong>Please don't:</strong> generate inappropriate
            content involving minors, incite violence or self-harm,
            or post defamatory content about real people. We reserve
            the right to remove any story that violates community
            norms or applicable law.
          </p>
          <p style={apStyles.p}>
            See something concerning? Email us at{" "}
            <a href="mailto:hello@tinystories.app" style={apStyles.link}>
              hello@tinystories.app
            </a>
          </p>
        </>
      ),
    },
    {
      heading: "Disclaimer",
      body: (
        <p style={apStyles.p}>
          This product generates AI content. All stories, characters,
          and dialogue are fictional. Any resemblance to real people
          or events is a coincidence of live generation, not an
          endorsement by us. In-story choices and advisor suggestions
          are NOT life, legal or emotional advice — they're part of
          the drama.
        </p>
      ),
    },
  ],
}

import type { PublishedStoryListView, StoryLanguage } from "../../index"
import { formatStoryLanguageLabel, normalizeStoryLanguage } from "./story-language"
import { uiText } from "./ui-language"

function storyShelfLabel(language: StoryLanguage, uiLanguage: StoryLanguage) {
  if (uiLanguage === "zh") {
    return language === "zh" ? "中文故事" : "英文故事"
  }
  return language === "zh" ? "Chinese stories" : "English stories"
}

export function getLibraryViewOptionLabel(view: PublishedStoryListView, uiLanguage: StoryLanguage) {
  switch (view) {
    case "mine":
      return uiText(uiLanguage, { en: "My Stories", zh: "我的故事" })
    case "public":
      return uiText(uiLanguage, { en: "Public Shelf", zh: "公开故事" })
    default:
      return uiText(uiLanguage, { en: "Open Now", zh: "现在可看" })
  }
}

export function getLibraryResultsSummary(view: PublishedStoryListView, uiLanguage: StoryLanguage, language: StoryLanguage) {
  const shelf = storyShelfLabel(language, uiLanguage)
  switch (view) {
    case "mine":
      return uiText(uiLanguage, {
        en: `Your ${shelf}`,
        zh: `你的${shelf}`,
      })
    case "public":
      return uiText(uiLanguage, {
        en: `Public ${shelf}`,
        zh: `当前公开的${shelf}`,
      })
    default:
      return uiText(uiLanguage, {
        en: `${shelf} you can open now`,
        zh: `当前可浏览的${shelf}`,
      })
  }
}

export function getLibraryEmptyStateCopy({
  authenticated,
  hasActiveFilters,
  language,
  uiLanguage,
  view,
}: {
  authenticated: boolean
  hasActiveFilters: boolean
  language: StoryLanguage
  uiLanguage: StoryLanguage
  view: PublishedStoryListView
}) {
  const shelf = storyShelfLabel(language, uiLanguage)
  if (hasActiveFilters) {
    return {
      title: uiText(uiLanguage, {
        en: `No ${shelf} match this search`,
        zh: `当前没有匹配条件的${shelf}`,
      }),
      body: uiText(uiLanguage, {
        en: "Try another keyword, clear the current filters, or switch interface language to browse a different shelf.",
        zh: "换个关键词、清掉当前筛选，或者切换界面语言看看别的故事书架。",
      }),
    }
  }

  if (view === "mine") {
    return {
      title: uiText(uiLanguage, {
        en: `You have no ${shelf} yet`,
        zh: `你还没有${shelf}`,
      }),
      body: uiText(uiLanguage, {
        en: "Create and publish a story in this language to start building your shelf.",
        zh: "先用当前语言创作并发布故事，才能把这格书架慢慢填起来。",
      }),
    }
  }

  if (view === "public") {
    return {
      title: uiText(uiLanguage, {
        en: `No public ${shelf} right now`,
        zh: `当前没有公开的${shelf}`,
      }),
      body: uiText(uiLanguage, {
        en: "Switch interface language to browse a different public shelf.",
        zh: "可以切换界面语言，去看另一种语言下的公开故事。",
      }),
    }
  }

  return {
    title: uiText(uiLanguage, {
      en: `No ${shelf} available right now`,
      zh: `当前没有可浏览的${shelf}`,
    }),
    body: authenticated
      ? uiText(uiLanguage, {
          en: "Switch interface language to browse a different shelf, or start a new story in this language.",
          zh: "可以切换界面语言去看另一格书架，或者直接用当前语言开始一个新故事。",
        })
      : uiText(uiLanguage, {
          en: "Sign in to create your own stories, or switch interface language to browse a different shelf.",
          zh: "登录后可以开始写自己的故事，或者先切换界面语言去看另一格书架。",
        }),
  }
}

export function getLanguageMismatchCopy({
  storyLanguage,
  surface,
  uiLanguage,
}: {
  storyLanguage: StoryLanguage | string | null | undefined
  surface: "detail" | "play"
  uiLanguage: StoryLanguage
}) {
  const resolvedStoryLanguage = normalizeStoryLanguage(storyLanguage)
  const targetLanguageLabel = formatStoryLanguageLabel(resolvedStoryLanguage, uiLanguage)

  return {
    title: surface === "play"
      ? uiText(uiLanguage, {
          en: `This session is only available in ${targetLanguageLabel}`,
          zh: `这个试玩会话只在${targetLanguageLabel}界面下显示`,
        })
      : uiText(uiLanguage, {
          en: `This story is only available in ${targetLanguageLabel}`,
          zh: `这篇故事只在${targetLanguageLabel}界面下显示`,
        }),
    body: surface === "play"
      ? uiText(uiLanguage, {
          en: `Your interface is set to ${formatStoryLanguageLabel(uiLanguage, "en")}. Switch to ${formatStoryLanguageLabel(resolvedStoryLanguage, "en")} before continuing this session.`,
          zh: `你当前的界面语言是${formatStoryLanguageLabel(uiLanguage, "zh")}。先切到${targetLanguageLabel}，再继续这个试玩会话。`,
        })
      : uiText(uiLanguage, {
          en: `Your interface is set to ${formatStoryLanguageLabel(uiLanguage, "en")}. Switch to ${formatStoryLanguageLabel(resolvedStoryLanguage, "en")} before opening this story dossier.`,
          zh: `你当前的界面语言是${formatStoryLanguageLabel(uiLanguage, "zh")}。先切到${targetLanguageLabel}，再打开这篇故事档案。`,
        }),
    switchAction: uiText(uiLanguage, {
      en: `Switch to ${formatStoryLanguageLabel(resolvedStoryLanguage, "en")}`,
      zh: `切换到${targetLanguageLabel}`,
    }),
    backAction: uiText(uiLanguage, { en: "Back to Library", zh: "返回故事库" }),
  }
}

export function getCreateSurfaceCopy(uiLanguage: StoryLanguage) {
  return {
    lockedStoryLanguage: uiText(uiLanguage, { en: "Story Language", zh: "故事语言" }),
    lockedStoryLanguageHelp: uiText(uiLanguage, {
      en: "New stories follow the current interface language. Switch the interface first if you want a different language.",
      zh: "新故事会沿用当前界面语言。想换语言，先切界面再开始。",
    }),
    previewHeading: uiText(uiLanguage, { en: "Preview Dossier", zh: "预览档案" }),
    awaitingInput: uiText(uiLanguage, { en: "Awaiting Seed", zh: "等待种子" }),
    premiseArchetype: uiText(uiLanguage, { en: "Story Premise", zh: "故事梗概" }),
    toneProfile: uiText(uiLanguage, { en: "Overall Tone", zh: "整体调性" }),
    themeSignal: uiText(uiLanguage, { en: "Theme Read:", zh: "主题线索：" }),
    noThemeSignal: uiText(uiLanguage, { en: "No theme read yet", zh: "还没有主题线索" }),
    whatHappensNext: uiText(uiLanguage, { en: "What comes after this", zh: "接下来会发生什么" }),
    sparkLabel: uiText(uiLanguage, { en: "Spark", zh: "来个点子" }),
    sparkSupport: uiText(uiLanguage, {
      en: "Need a faster start? Spark gives you one random seed in the current story language. You still confirm before preview.",
      zh: "想快一点开始？先给你一个随机点子，再决定要不要继续展开成预览。",
    }),
    sparkAction: uiText(uiLanguage, { en: "Spark a seed", zh: "来个点子" }),
    sparkAgain: uiText(uiLanguage, { en: "Spark another", zh: "换一个点子" }),
    sparkLoading: uiText(uiLanguage, { en: "Sparking...", zh: "正在想点子..." }),
    sparkOverwriteConfirm: uiText(uiLanguage, {
      en: "Spark will replace the current seed and clear the current preview. Continue?",
      zh: "新点子会替换当前种子，并清空现在的预览。要继续吗？",
    }),
  }
}

export function getAuthSurfaceCopy(uiLanguage: StoryLanguage) {
  return {
    kicker: uiText(uiLanguage, { en: "Enter the Studio", zh: "叙事会馆" }),
    createAccountTitle: uiText(uiLanguage, { en: "Create an account", zh: "注册账号" }),
    loginTitle: uiText(uiLanguage, { en: "Sign in to continue", zh: "登录后继续" }),
    createAccountBody: uiText(uiLanguage, {
      en: "Create an account to save drafts, publish stories, and keep your sessions under one identity.",
      zh: "注册后，你可以保存草稿、发布故事，也能把试玩记录都留在同一个账号下。",
    }),
    loginBody: uiText(uiLanguage, {
      en: "Sign in to create, publish, and resume sessions under your own account.",
      zh: "登录后，你就可以用自己的账号创作、发布，并继续之前的试玩。",
    }),
    browseLibrary: uiText(uiLanguage, { en: "Browse the library first", zh: "先逛故事库" }),
  }
}

export function getDetailSurfaceTerms(uiLanguage: StoryLanguage) {
  return {
    roleBrief: uiText(uiLanguage, { en: "Lead Dossier", zh: "主角档案" }),
    castFiles: uiText(uiLanguage, { en: "Cast Files", zh: "人物名单" }),
    sessionEntry: uiText(uiLanguage, { en: "Session Entry", zh: "开始试玩" }),
    sessionFrame: uiText(uiLanguage, { en: "Session Frame", zh: "玩法形式" }),
    turnCap: uiText(uiLanguage, { en: "Turn Cap", zh: "回合上限" }),
    readyToPlay: uiText(uiLanguage, { en: "Open for Play", zh: "可以试玩" }),
  }
}

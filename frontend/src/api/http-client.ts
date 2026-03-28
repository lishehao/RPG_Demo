import {
  type AuthLoginRequest,
  type AuthRegisterRequest,
  type AuthSessionResponse,
  type ApiRequestOptions,
  type AuthorJobCreateRequest,
  type AuthorCopilotApplyResponse,
  type AuthorCopilotUndoResponse,
  type AuthorCopilotSessionCreateRequest,
  type AuthorCopilotSessionMessageRequest,
  type AuthorCopilotSessionResponse,
  type AuthorCopilotPreviewResponse,
  type AuthorCopilotProposalRequest,
  type AuthorCopilotProposalResponse,
  type AuthorEditorStateResponse,
  type AuthorJobEvent,
  type AuthorJobEventName,
  type AuthorJobResultResponse,
  type AuthorJobStatusResponse,
  type AuthorPreviewRequest,
  type AuthorPreviewResponse,
  type AuthorStorySparkRequest,
  type AuthorStorySparkResponse,
  type CurrentActorResponse,
  type DeleteStoryResponse,
  type FrontendApiError,
  type ListStoriesParams,
  type PlaySessionCreateRequest,
  type PlaySessionHistoryResponse,
  type PlaySessionSnapshot,
  type PlayTurnRequest,
  type PublishedStoryCard,
  type PublishedStoryDetailResponse,
  type PublishedStoryListResponse,
  type UpdateStoryVisibilityRequest,
} from "./contracts"
import { BACKEND_ROUTE_MAP } from "./route-map"

export type FrontendApiClient = {
  getAuthSession(): Promise<AuthSessionResponse>
  registerAuth(request: AuthRegisterRequest): Promise<AuthSessionResponse>
  loginAuth(request: AuthLoginRequest): Promise<AuthSessionResponse>
  logoutAuth(): Promise<void>
  getCurrentActor(): Promise<CurrentActorResponse>
  createStorySpark(request: AuthorStorySparkRequest): Promise<AuthorStorySparkResponse>
  createStoryPreview(request: AuthorPreviewRequest): Promise<AuthorPreviewResponse>
  createAuthorJob(request: AuthorJobCreateRequest): Promise<AuthorJobStatusResponse>
  getAuthorJob(jobId: string): Promise<AuthorJobStatusResponse>
  streamAuthorJobEvents(jobId: string, lastEventId?: number): AsyncGenerator<AuthorJobEvent, void, void>
  getAuthorJobResult(jobId: string): Promise<AuthorJobResultResponse>
  getAuthorJobEditorState(jobId: string): Promise<AuthorEditorStateResponse>
  createAuthorCopilotSession(jobId: string, request: AuthorCopilotSessionCreateRequest): Promise<AuthorCopilotSessionResponse>
  getAuthorCopilotSession(jobId: string, sessionId: string): Promise<AuthorCopilotSessionResponse>
  appendAuthorCopilotSessionMessage(jobId: string, sessionId: string, request: AuthorCopilotSessionMessageRequest): Promise<AuthorCopilotSessionResponse>
  createAuthorCopilotSessionProposal(jobId: string, sessionId: string): Promise<AuthorCopilotProposalResponse>
  createAuthorCopilotProposal(jobId: string, request: AuthorCopilotProposalRequest): Promise<AuthorCopilotProposalResponse>
  getAuthorCopilotProposal(jobId: string, proposalId: string): Promise<AuthorCopilotProposalResponse>
  previewAuthorCopilotProposal(jobId: string, proposalId: string): Promise<AuthorCopilotPreviewResponse>
  applyAuthorCopilotProposal(jobId: string, proposalId: string): Promise<AuthorCopilotApplyResponse>
  undoAuthorCopilotProposal(jobId: string, proposalId: string): Promise<AuthorCopilotUndoResponse>
  publishAuthorJob(jobId: string, visibility?: "private" | "public"): Promise<PublishedStoryCard>
  listStories(params?: ListStoriesParams, options?: ApiRequestOptions): Promise<PublishedStoryListResponse>
  getStory(storyId: string, options?: ApiRequestOptions): Promise<PublishedStoryDetailResponse>
  updateStoryVisibility(storyId: string, request: UpdateStoryVisibilityRequest): Promise<PublishedStoryCard>
  deleteStory(storyId: string): Promise<DeleteStoryResponse>
  createPlaySession(request: PlaySessionCreateRequest): Promise<PlaySessionSnapshot>
  getPlaySession(sessionId: string, options?: ApiRequestOptions): Promise<PlaySessionSnapshot>
  getPlaySessionHistory(sessionId: string, options?: ApiRequestOptions): Promise<PlaySessionHistoryResponse>
  submitPlayTurn(sessionId: string, request: PlayTurnRequest): Promise<PlaySessionSnapshot>
}

type RouteParams = Record<string, string | number>

class ApiRequestError extends Error {
  statusCode: number
  errorCode?: string

  constructor(message: string, statusCode: number, errorCode?: string) {
    super(message)
    this.name = "ApiRequestError"
    this.statusCode = statusCode
    this.errorCode = errorCode
  }
}

function resolvePath(template: string, params: RouteParams = {}): string {
  return template.replace(/:([a-z_]+)/gi, (_, key) => encodeURIComponent(String(params[key])))
}

async function readErrorPayload(response: Response): Promise<{ message: string; code?: string }> {
  try {
    const payload = (await response.json()) as FrontendApiError
    if (payload.error?.message) {
      return {
        message: payload.error.message,
        code: payload.error.code,
      }
    }
  } catch {
    return { message: `Request failed with status ${response.status}` }
  }

  return { message: `Request failed with status ${response.status}` }
}

function parseSseEvent(block: string): AuthorJobEvent | null {
  let id = 0
  let event = "stage_changed" as AuthorJobEventName
  const dataLines: string[] = []

  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) {
      continue
    }

    if (line.startsWith("id:")) {
      id = Number(line.slice(3).trim())
      continue
    }

    if (line.startsWith("event:")) {
      event = line.slice(6).trim() as AuthorJobEventName
      continue
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim())
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  return {
    id,
    event,
    data: JSON.parse(dataLines.join("\n")) as Record<string, unknown>,
  }
}

export function createHttpApiClient(baseUrl: string): FrontendApiClient {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "")

  async function requestJson<TResponse>(
    routeKey: keyof typeof BACKEND_ROUTE_MAP,
    options: {
      params?: RouteParams
      body?: unknown
      query?: Record<string, string | number | undefined>
      signal?: AbortSignal
    } = {},
  ): Promise<TResponse> {
    const route = BACKEND_ROUTE_MAP[routeKey]
    const url = new URL(resolvePath(route.path, options.params), `${normalizedBaseUrl}/`)

    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value))
      }
    }

    const response = await fetch(url.toString(), {
      method: route.method,
      credentials: "include",
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
      },
      signal: options.signal,
      body: options.body ? JSON.stringify(options.body) : undefined,
    })

    if (!response.ok) {
      const errorPayload = await readErrorPayload(response)
      throw new ApiRequestError(errorPayload.message, response.status, errorPayload.code)
    }

    if (response.status === 204) {
      return undefined as TResponse
    }

    return (await response.json()) as TResponse
  }

  return {
    getAuthSession() {
      return requestJson<AuthSessionResponse>("getAuthSession")
    },

    registerAuth(request: AuthRegisterRequest) {
      return requestJson<AuthSessionResponse>("registerAuth", { body: request })
    },

    loginAuth(request: AuthLoginRequest) {
      return requestJson<AuthSessionResponse>("loginAuth", { body: request })
    },

    async logoutAuth() {
      const route = BACKEND_ROUTE_MAP.logoutAuth
      const url = new URL(resolvePath(route.path), `${normalizedBaseUrl}/`)
      const response = await fetch(url.toString(), {
        method: route.method,
        credentials: "include",
      })
      if (!response.ok) {
        const errorPayload = await readErrorPayload(response)
        throw new ApiRequestError(errorPayload.message, response.status, errorPayload.code)
      }
    },

    getCurrentActor() {
      return requestJson<CurrentActorResponse>("getCurrentActor")
    },

    createStorySpark(request: AuthorStorySparkRequest) {
      return requestJson<AuthorStorySparkResponse>("createStorySpark", { body: request })
    },

    createStoryPreview(request: AuthorPreviewRequest) {
      return requestJson<AuthorPreviewResponse>("createStoryPreview", { body: request })
    },

    createAuthorJob(request: AuthorJobCreateRequest) {
      return requestJson<AuthorJobStatusResponse>("createAuthorJob", { body: request })
    },

    getAuthorJob(jobId: string) {
      return requestJson<AuthorJobStatusResponse>("getAuthorJob", { params: { job_id: jobId } })
    },

    async *streamAuthorJobEvents(jobId: string, lastEventId = 0) {
      const route = BACKEND_ROUTE_MAP.streamAuthorJobEvents
      const url = new URL(resolvePath(route.path, { job_id: jobId }), `${normalizedBaseUrl}/`)
      if (lastEventId > 0) {
        url.searchParams.set("last_event_id", String(lastEventId))
      }

      const response = await fetch(url.toString(), {
        credentials: "include",
        headers: {
          Accept: "text/event-stream",
        },
      })

      if (!response.ok) {
        const errorPayload = await readErrorPayload(response)
        throw new ApiRequestError(errorPayload.message, response.status, errorPayload.code)
      }

      if (!response.body) {
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { value, done } = await reader.read()
        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split("\n\n")
        buffer = blocks.pop() ?? ""

        for (const block of blocks) {
          const event = parseSseEvent(block.trim())
          if (event) {
            yield event
          }
        }
      }

      const trailingEvent = parseSseEvent(buffer.trim())
      if (trailingEvent) {
        yield trailingEvent
      }
    },

    getAuthorJobResult(jobId: string) {
      return requestJson<AuthorJobResultResponse>("getAuthorJobResult", { params: { job_id: jobId } })
    },

    getAuthorJobEditorState(jobId: string) {
      return requestJson<AuthorEditorStateResponse>("getAuthorJobEditorState", { params: { job_id: jobId } })
    },

    createAuthorCopilotSession(jobId: string, request: AuthorCopilotSessionCreateRequest) {
      return requestJson<AuthorCopilotSessionResponse>("createAuthorCopilotSession", {
        params: { job_id: jobId },
        body: request,
      })
    },

    getAuthorCopilotSession(jobId: string, sessionId: string) {
      return requestJson<AuthorCopilotSessionResponse>("getAuthorCopilotSession", {
        params: { job_id: jobId, session_id: sessionId },
      })
    },

    appendAuthorCopilotSessionMessage(jobId: string, sessionId: string, request: AuthorCopilotSessionMessageRequest) {
      return requestJson<AuthorCopilotSessionResponse>("appendAuthorCopilotSessionMessage", {
        params: { job_id: jobId, session_id: sessionId },
        body: request,
      })
    },

    createAuthorCopilotSessionProposal(jobId: string, sessionId: string) {
      return requestJson<AuthorCopilotProposalResponse>("createAuthorCopilotSessionProposal", {
        params: { job_id: jobId, session_id: sessionId },
      })
    },

    createAuthorCopilotProposal(jobId: string, request: AuthorCopilotProposalRequest) {
      return requestJson<AuthorCopilotProposalResponse>("createAuthorCopilotProposal", {
        params: { job_id: jobId },
        body: request,
      })
    },

    getAuthorCopilotProposal(jobId: string, proposalId: string) {
      return requestJson<AuthorCopilotProposalResponse>("getAuthorCopilotProposal", {
        params: { job_id: jobId, proposal_id: proposalId },
      })
    },

    previewAuthorCopilotProposal(jobId: string, proposalId: string) {
      return requestJson<AuthorCopilotPreviewResponse>("previewAuthorCopilotProposal", {
        params: { job_id: jobId, proposal_id: proposalId },
      })
    },

    applyAuthorCopilotProposal(jobId: string, proposalId: string) {
      return requestJson<AuthorCopilotApplyResponse>("applyAuthorCopilotProposal", {
        params: { job_id: jobId, proposal_id: proposalId },
      })
    },

    undoAuthorCopilotProposal(jobId: string, proposalId: string) {
      return requestJson<AuthorCopilotUndoResponse>("undoAuthorCopilotProposal", {
        params: { job_id: jobId, proposal_id: proposalId },
      })
    },

    publishAuthorJob(jobId: string, visibility = "private") {
      return requestJson<PublishedStoryCard>("publishAuthorJob", {
        params: { job_id: jobId },
        query: {
          visibility,
        },
      })
    },

    listStories(params: ListStoriesParams = {}, options: ApiRequestOptions = {}) {
      return requestJson<PublishedStoryListResponse>("listStories", {
        query: {
          q: params.q ?? undefined,
          theme: params.theme ?? undefined,
          language: params.language ?? undefined,
          view: params.view ?? undefined,
          limit: params.limit ?? undefined,
          cursor: params.cursor ?? undefined,
          sort: params.sort ?? undefined,
        },
        signal: options.signal,
      })
    },

    getStory(storyId: string, options: ApiRequestOptions = {}) {
      return requestJson<PublishedStoryDetailResponse>("getStory", {
        params: { story_id: storyId },
        signal: options.signal,
      })
    },

    updateStoryVisibility(storyId: string, request: UpdateStoryVisibilityRequest) {
      return requestJson<PublishedStoryCard>("updateStoryVisibility", {
        params: { story_id: storyId },
        body: request,
      })
    },

    deleteStory(storyId: string) {
      return requestJson<DeleteStoryResponse>("deleteStory", {
        params: { story_id: storyId },
      })
    },

    createPlaySession(request: PlaySessionCreateRequest) {
      return requestJson<PlaySessionSnapshot>("createPlaySession", { body: request })
    },

    getPlaySession(sessionId: string, options: ApiRequestOptions = {}) {
      return requestJson<PlaySessionSnapshot>("getPlaySession", {
        params: { session_id: sessionId },
        signal: options.signal,
      })
    },

    getPlaySessionHistory(sessionId: string, options: ApiRequestOptions = {}) {
      return requestJson<PlaySessionHistoryResponse>("getPlaySessionHistory", {
        params: { session_id: sessionId },
        signal: options.signal,
      })
    },

    submitPlayTurn(sessionId: string, request: PlayTurnRequest) {
      return requestJson<PlaySessionSnapshot>("submitPlayTurn", {
        params: { session_id: sessionId },
        body: request,
      })
    },
  }
}

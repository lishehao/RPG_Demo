// AUTO-GENERATED FILE. DO NOT EDIT.
// Source: scripts/generate_frontend_sdk.py
// OpenAPI source: contracts/openapi/backend.openapi.json
// OpenAPI sha256: cae3ef5bfeed1bcbbcf5cf8f5005aea4504585d648b0040c73243033a86475a7

export type ApiHttpMethod =
  | 'GET'
  | 'POST'
  | 'PUT'
  | 'PATCH'
  | 'DELETE'
  | 'OPTIONS'
  | 'HEAD'
  | 'TRACE';

export type ApiOperationMeta = {
  operationId: string;
  method: ApiHttpMethod;
  path: string;
  tags: string[];
  hasRequestBody: boolean;
  hasParameters: boolean;
  responseCodes: string[];
};

export const BACKEND_OPENAPI_SHA256 = 'cae3ef5bfeed1bcbbcf5cf8f5005aea4504585d648b0040c73243033a86475a7' as const;

export const API_OPERATIONS: ApiOperationMeta[] = [
  {
    "operationId": "admin_login_admin_auth_login_post",
    "method": "POST",
    "path": "/admin/auth/login",
    "tags": [],
    "hasRequestBody": true,
    "hasParameters": false,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  {
    "operationId": "health_health_get",
    "method": "GET",
    "path": "/health",
    "tags": [],
    "hasRequestBody": false,
    "hasParameters": false,
    "responseCodes": [
      "200"
    ]
  },
  {
    "operationId": "create_session_sessions_post",
    "method": "POST",
    "path": "/sessions",
    "tags": [],
    "hasRequestBody": true,
    "hasParameters": false,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  {
    "operationId": "get_session_sessions__session_id__get",
    "method": "GET",
    "path": "/sessions/{session_id}",
    "tags": [],
    "hasRequestBody": false,
    "hasParameters": true,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  {
    "operationId": "get_session_history_sessions__session_id__history_get",
    "method": "GET",
    "path": "/sessions/{session_id}/history",
    "tags": [],
    "hasRequestBody": false,
    "hasParameters": true,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  {
    "operationId": "step_session_sessions__session_id__step_post",
    "method": "POST",
    "path": "/sessions/{session_id}/step",
    "tags": [],
    "hasRequestBody": true,
    "hasParameters": true,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  {
    "operationId": "list_stories_stories_get",
    "method": "GET",
    "path": "/stories",
    "tags": [],
    "hasRequestBody": false,
    "hasParameters": false,
    "responseCodes": [
      "200"
    ]
  },
  {
    "operationId": "generate_story_stories_generate_post",
    "method": "POST",
    "path": "/stories/generate",
    "tags": [],
    "hasRequestBody": true,
    "hasParameters": false,
    "responseCodes": [
      "200",
      "422"
    ]
  }
] as ApiOperationMeta[];

export const API_OPERATION_MAP: Record<string, ApiOperationMeta> = {
  "admin_login_admin_auth_login_post": {
    "operationId": "admin_login_admin_auth_login_post",
    "method": "POST",
    "path": "/admin/auth/login",
    "tags": [],
    "hasRequestBody": true,
    "hasParameters": false,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  "health_health_get": {
    "operationId": "health_health_get",
    "method": "GET",
    "path": "/health",
    "tags": [],
    "hasRequestBody": false,
    "hasParameters": false,
    "responseCodes": [
      "200"
    ]
  },
  "create_session_sessions_post": {
    "operationId": "create_session_sessions_post",
    "method": "POST",
    "path": "/sessions",
    "tags": [],
    "hasRequestBody": true,
    "hasParameters": false,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  "get_session_sessions__session_id__get": {
    "operationId": "get_session_sessions__session_id__get",
    "method": "GET",
    "path": "/sessions/{session_id}",
    "tags": [],
    "hasRequestBody": false,
    "hasParameters": true,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  "get_session_history_sessions__session_id__history_get": {
    "operationId": "get_session_history_sessions__session_id__history_get",
    "method": "GET",
    "path": "/sessions/{session_id}/history",
    "tags": [],
    "hasRequestBody": false,
    "hasParameters": true,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  "step_session_sessions__session_id__step_post": {
    "operationId": "step_session_sessions__session_id__step_post",
    "method": "POST",
    "path": "/sessions/{session_id}/step",
    "tags": [],
    "hasRequestBody": true,
    "hasParameters": true,
    "responseCodes": [
      "200",
      "422"
    ]
  },
  "list_stories_stories_get": {
    "operationId": "list_stories_stories_get",
    "method": "GET",
    "path": "/stories",
    "tags": [],
    "hasRequestBody": false,
    "hasParameters": false,
    "responseCodes": [
      "200"
    ]
  },
  "generate_story_stories_generate_post": {
    "operationId": "generate_story_stories_generate_post",
    "method": "POST",
    "path": "/stories/generate",
    "tags": [],
    "hasRequestBody": true,
    "hasParameters": false,
    "responseCodes": [
      "200",
      "422"
    ]
  }
} as Record<string, ApiOperationMeta>;

export type ApiErrorEnvelope = {
  error: {
    code: string;
    message: string;
    retryable: boolean;
    request_id: string | null;
    details: Record<string, unknown>;
  };
};

export function buildApiUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, '')}${path}`;
}

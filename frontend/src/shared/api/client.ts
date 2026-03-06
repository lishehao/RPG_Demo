import type { ApiErrorEnvelope } from '@/shared/api/generated/backend-sdk';
import { useAuthStore } from '@/shared/store/authStore';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiClientError extends Error {
  code: string;
  retryable: boolean;
  requestId: string | null;
  statusCode: number;

  constructor(envelope: ApiErrorEnvelope, statusCode: number) {
    super(envelope.error.message);
    this.name = 'ApiClientError';
    this.code = envelope.error.code;
    this.retryable = envelope.error.retryable;
    this.requestId = envelope.error.request_id;
    this.statusCode = statusCode;
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
  skipAuth?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  headers.set('Content-Type', 'application/json');

  if (!options.skipAuth) {
    const token = useAuthStore.getState().token;
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!response.ok) {
    const payload = (await response.json()) as ApiErrorEnvelope;
    if (response.status === 401 && !options.skipAuth) {
      useAuthStore.getState().logout();
    }
    throw new ApiClientError(payload, response.status);
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
};

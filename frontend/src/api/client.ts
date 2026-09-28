/**
 * Axios instance and the unified error contract.
 *
 * Every backend error has the shape { error: { code, message, detail } }.
 * `toApiError` normalises anything else (network failure, HTML error page) into
 * the same shape so views never have to guess.
 */

import axios, { AxiosError } from 'axios'
import type { AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

import type { ApiErrorBody, ApiErrorEnvelope } from '@/types'

export const TOKEN_STORAGE_KEY = 'pd-rehab-token'

export class ApiError extends Error {
  code: string
  status: number | null
  detail: unknown

  constructor(body: ApiErrorBody, status: number | null = null) {
    super(body.message)
    this.name = 'ApiError'
    this.code = body.code
    this.status = status
    this.detail = body.detail ?? null
  }
}

/** Narrow an unknown thrown value into an ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  const axiosError = error as AxiosError<ApiErrorEnvelope>
  if (axiosError?.isAxiosError) {
    const status = axiosError.response?.status ?? null
    const envelope = axiosError.response?.data
    if (envelope && typeof envelope === 'object' && 'error' in envelope) {
      return new ApiError(envelope.error, status)
    }
    if (axiosError.code === 'ERR_NETWORK') {
      return new ApiError(
        {
          code: 'NETWORK_ERROR',
          message: '无法连接到后端服务，请确认后端已启动（默认 http://127.0.0.1:8000）。',
        },
        status,
      )
    }
    return new ApiError(
      { code: 'HTTP_ERROR', message: axiosError.message || '请求失败。' },
      status,
    )
  }

  return new ApiError({
    code: 'UNKNOWN_ERROR',
    message: error instanceof Error ? error.message : '发生未知错误。',
  })
}

export const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** Called when the session is no longer valid, so the app can route to /login. */
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorEnvelope>) => {
    const status = error.response?.status
    if (status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      onUnauthorized?.()
    }
    return Promise.reject(error)
  },
)

/** Show an error to the user using the backend's own message. */
export function notifyError(error: unknown, fallback?: string): ApiError {
  const apiError = toApiError(error)
  ElMessage.error(fallback && apiError.code === 'UNKNOWN_ERROR' ? fallback : apiError.message)
  return apiError
}

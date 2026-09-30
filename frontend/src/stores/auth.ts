/**
 * Authentication store. Token lives in localStorage; the user object is
 * refreshed from /auth/me on boot so a stale local copy cannot be trusted.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi } from '@/api'
import { TOKEN_STORAGE_KEY, toApiError } from '@/api/client'
import type { StaffUser } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_STORAGE_KEY))
  const user = ref<StaffUser | null>(null)
  const loading = ref(false)
  const initialised = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))
  const displayName = computed(() => user.value?.display_name ?? '')
  const roleLabel = computed(() => (user.value?.role === 'ADMIN' ? '管理员' : '医生'))
  /** Technical surfaces (model status, GPU, paths) are for administrators. */
  const isAdmin = computed(() => user.value?.role === 'ADMIN')

  function setToken(value: string | null) {
    token.value = value
    if (value) {
      localStorage.setItem(TOKEN_STORAGE_KEY, value)
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  }

  async function login(username: string, password: string): Promise<void> {
    loading.value = true
    try {
      const response = await authApi.login(username, password)
      setToken(response.access_token)
      user.value = response.user
      initialised.value = true
    } finally {
      loading.value = false
    }
  }

  /** Restore the session on app boot. Returns true when a valid user is present. */
  async function restore(): Promise<boolean> {
    if (!token.value) {
      initialised.value = true
      return false
    }
    try {
      user.value = await authApi.me()
      return true
    } catch (error) {
      // Token expired or revoked; drop it rather than looping on 401s.
      const apiError = toApiError(error)
      if (apiError.status === 401 || apiError.status === 403) {
        setToken(null)
      }
      user.value = null
      return false
    } finally {
      initialised.value = true
    }
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } catch {
      // Logging out locally must succeed even if the API call fails.
    }
    setToken(null)
    user.value = null
  }

  return {
    token,
    user,
    loading,
    initialised,
    isAuthenticated,
    displayName,
    roleLabel,
    isAdmin,
    login,
    logout,
    restore,
    setToken,
  }
})

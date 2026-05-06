import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AccountSummary, Role, TokenResponse, User } from '~/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  // F02 — multi-tenant : exposer Account et Role separement pour acces rapide
  // (sidebar, badge, middleware admin, etc.) sans avoir a deserialiser l'objet
  // user a chaque fois.
  const account = ref<AccountSummary | null>(null)
  const role = ref<Role | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)
  // F02 — helper computed pour le middleware admin et les routes protegees.
  const isAdmin = computed(() => role.value === 'ADMIN')

  function setTokens(tokens: TokenResponse) {
    accessToken.value = tokens.access_token
    if (tokens.refresh_token) {
      refreshToken.value = tokens.refresh_token
    }
    // Persister dans localStorage
    if (import.meta.client) {
      localStorage.setItem('access_token', tokens.access_token)
      if (tokens.refresh_token) {
        localStorage.setItem('refresh_token', tokens.refresh_token)
      }
    }
  }

  function setUser(userData: User) {
    user.value = userData
    // F02 — extraire role + account du payload backend pour avoir un acces
    // direct sans drill-down dans `user`.
    role.value = userData.role ?? null
    account.value = userData.account ?? null
  }

  function clearAuth() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    account.value = null
    role.value = null
    if (import.meta.client) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  }

  function loadFromStorage() {
    if (import.meta.client) {
      accessToken.value = localStorage.getItem('access_token')
      refreshToken.value = localStorage.getItem('refresh_token')
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    account,
    role,
    isAuthenticated,
    isAdmin,
    setTokens,
    setUser,
    clearAuth,
    loadFromStorage,
  }
})

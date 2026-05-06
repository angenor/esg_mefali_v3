import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AccountSummary, Role, TokenResponse, User } from '~/types'

// F02 — Cle localStorage utilisee pour persister l'objet User complet
// (incl. role + account). Necessaire pour eviter une fenetre de navigation
// pendant laquelle `auth.role` est null en attendant la resolution
// asynchrone de `/auth/me`, ce qui faisait rediriger les Admin vers
// /dashboard via le middleware `admin.ts`.
const USER_STORAGE_KEY = 'auth_user'

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
    // F02 — persister l'objet User complet pour que le role et l'account
    // soient disponibles synchroniquement au prochain mount (avant la
    // resolution de `/auth/me`). Sans cela, `admin.ts` lit `role === null`
    // au premier rendu et redirige les Admin vers `/dashboard`.
    if (import.meta.client) {
      try {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(userData))
      } catch {
        // localStorage indisponible (mode prive Safari, quota, etc.) :
        // tomber silencieusement vers le comportement degrade existant
        // (fetchMe rehydratera apres la navigation).
      }
    }
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
      localStorage.removeItem(USER_STORAGE_KEY)
    }
  }

  function loadFromStorage() {
    if (import.meta.client) {
      accessToken.value = localStorage.getItem('access_token')
      refreshToken.value = localStorage.getItem('refresh_token')
      // F02 — restaurer l'objet User (et donc role + account) si present.
      // En cas de payload corrompu, on purge la cle pour eviter une boucle.
      const rawUser = localStorage.getItem(USER_STORAGE_KEY)
      if (rawUser) {
        try {
          const parsed = JSON.parse(rawUser) as User
          user.value = parsed
          role.value = parsed.role ?? null
          account.value = parsed.account ?? null
        } catch {
          localStorage.removeItem(USER_STORAGE_KEY)
        }
      }
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

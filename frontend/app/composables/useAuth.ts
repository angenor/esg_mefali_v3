import type { TokenResponse, User } from '~/types'
import { useAuthStore } from '~/stores/auth'
import { useUiStore } from '~/stores/ui'

// ═════════════════════════════════════════════════════════════════════
// Module-level state (story 7.2 — single-flight refresh token)
// ═════════════════════════════════════════════════════════════════════
// refreshPromise est partage entre toutes les instances de useAuth pour
// eviter un « refresh storm » : N requetes paralleles qui recoivent 401
// simultanement partagent la meme Promise de refresh. Pattern module-level
// indispensable car useAuth() est re-instancie a chaque appel (composable).
let refreshPromise: Promise<boolean> | null = null

// Endpoints qui ne doivent pas declencher le cycle 401 → refresh → retry
// (sinon recursion infinie sur /auth/refresh, ou boucle sur /auth/login).
const AUTH_BYPASS_ENDPOINTS = [
  '/auth/login',
  '/auth/register',
  '/auth/refresh',
  '/auth/detect-country',
]

// Messages exacts (avec accents obligatoires — FR32 / NFR9).
const SESSION_EXPIRED_MESSAGE = 'Session expirée, veuillez vous reconnecter.'
const CHAT_SESSION_EXPIRED_MESSAGE = 'Votre session a expiré. Veuillez vous reconnecter.'

// Erreur enrichie avec le statut HTTP — permet aux composables metier de
// distinguer les reponses business 4xx (ex. 428 financing) des erreurs serveur.
export class ApiFetchError extends Error {
  status: number
  body: unknown
  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.name = 'ApiFetchError'
    this.status = status
    this.body = body
  }
}

// Sentinel class : signale une session expiree (refresh echoue OU retry 401 apres
// refresh reussi). Les composables metier detectent via `instanceof` — plus robuste
// qu'un `message.includes(...)` fragile a tout renommage/traduction.
export class SessionExpiredError extends Error {
  constructor(message: string = SESSION_EXPIRED_MESSAGE) {
    super(message)
    this.name = 'SessionExpiredError'
  }
}

// Single-flight du handleAuthFailure : evite les appels concurrents (N requetes
// paralleles qui echouent en meme temps → cancelTour/addSystemMessage/navigateTo
// ne s'executent qu'une seule fois).
let authFailurePromise: Promise<void> | null = null

export function useAuth() {
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const router = useRouter()

  const apiBase = config.public.apiBase

  async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    }
    if (authStore.accessToken) {
      headers['Authorization'] = `Bearer ${authStore.accessToken}`
    }

    const response = await fetch(`${apiBase}${url}`, {
      ...options,
      headers,
    })

    // Intercepteur 401 → refresh → retry (story 7.2 — AC1, AC3)
    const isAuthEndpoint = AUTH_BYPASS_ENDPOINTS.some((ep) => url.startsWith(ep))
    if (response.status === 401 && authStore.accessToken && !isAuthEndpoint) {
      // Single-flight : une seule POST /auth/refresh pour N requetes paralleles
      if (!refreshPromise) {
        refreshPromise = refresh().finally(() => {
          refreshPromise = null
        })
      }
      const ok = await refreshPromise
      if (!ok) {
        throw new SessionExpiredError()
      }

      // Rejouer la requete UNE seule fois avec le nouveau access_token
      const retryHeaders: Record<string, string> = {
        'Content-Type': 'application/json',
        ...((options.headers as Record<string, string>) || {}),
      }
      if (authStore.accessToken) {
        retryHeaders['Authorization'] = `Bearer ${authStore.accessToken}`
      }
      const retry = await fetch(`${apiBase}${url}`, {
        ...options,
        headers: retryHeaders,
      })
      // Retry 401 → traiter comme expiration de session (ex. token revoque /
      // compte banni entre refresh et retry). Sinon l'erreur se perdrait avec un
      // message serveur generique et handleAuthFailure ne serait jamais appele.
      if (retry.status === 401) {
        authStore.clearAuth()
        throw new SessionExpiredError()
      }
      if (!retry.ok) {
        const body = await retry.json().catch(() => ({ detail: 'Erreur inconnue' }))
        throw new ApiFetchError(
          extractDetailMessage(body, retry.status),
          retry.status,
          body,
        )
      }
      return retry.json() as Promise<T>
    }

    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: 'Erreur inconnue' }))
      throw new ApiFetchError(
        extractDetailMessage(body, response.status),
        response.status,
        body,
      )
    }

    return response.json() as Promise<T>
  }

  function extractDetailMessage(body: unknown, status: number): string {
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      if (detail && typeof detail === 'object' && 'message' in detail) {
        const message = (detail as { message: unknown }).message
        if (typeof message === 'string') return message
      }
    }
    return `Erreur ${status}`
  }

  // Variante Blob de apiFetch pour les endpoints retournant des PDF / binaires
  // (ex. fiche de preparation financement). Preserve le cycle 401 → refresh → retry.
  async function apiFetchBlob(url: string, options: RequestInit = {}): Promise<Blob> {
    const headers: Record<string, string> = {
      ...((options.headers as Record<string, string>) || {}),
    }
    if (authStore.accessToken) {
      headers['Authorization'] = `Bearer ${authStore.accessToken}`
    }

    const response = await fetch(`${apiBase}${url}`, { ...options, headers })

    const isAuthEndpoint = AUTH_BYPASS_ENDPOINTS.some((ep) => url.startsWith(ep))
    if (response.status === 401 && authStore.accessToken && !isAuthEndpoint) {
      if (!refreshPromise) {
        refreshPromise = refresh().finally(() => {
          refreshPromise = null
        })
      }
      const ok = await refreshPromise
      if (!ok) {
        throw new SessionExpiredError()
      }
      const retryHeaders: Record<string, string> = {
        ...((options.headers as Record<string, string>) || {}),
      }
      if (authStore.accessToken) {
        retryHeaders['Authorization'] = `Bearer ${authStore.accessToken}`
      }
      const retry = await fetch(`${apiBase}${url}`, { ...options, headers: retryHeaders })
      if (retry.status === 401) {
        authStore.clearAuth()
        throw new SessionExpiredError()
      }
      if (!retry.ok) {
        const body = await retry.json().catch(() => null)
        throw new ApiFetchError(
          extractDetailMessage(body, retry.status),
          retry.status,
          body,
        )
      }
      return retry.blob()
    }

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new ApiFetchError(
        extractDetailMessage(body, response.status),
        response.status,
        body,
      )
    }
    return response.blob()
  }

  async function register(data: {
    email: string
    password: string
    full_name: string
    company_name: string
    country?: string | null
    // F02 — token d'invitation team (rejoint un Account existant si fourni).
    invite_token?: string | null
  }): Promise<User> {
    return apiFetch<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async function detectCountry(): Promise<{
    detected_country: string | null
    supported_countries: string[]
  }> {
    return apiFetch('/auth/detect-country')
  }

  async function login(email: string, password: string): Promise<void> {
    const tokens = await apiFetch<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    authStore.setTokens(tokens)
    await fetchUser()
  }

  async function fetchUser(): Promise<void> {
    const user = await apiFetch<User>('/auth/me')
    authStore.setUser(user)
  }

  async function refresh(): Promise<boolean> {
    if (!authStore.refreshToken) return false

    try {
      const tokens = await apiFetch<TokenResponse>('/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: authStore.refreshToken }),
      })
      authStore.setTokens(tokens)
      return true
    } catch {
      authStore.clearAuth()
      return false
    }
  }

  // Story 7.2 — AC2 : cleanup parcours guide + redirection /login apres refresh echoue.
  // Imports dynamiques SSR-safe pour briser les cycles avec useGuidedTour/useChat.
  // Single-flight `authFailurePromise` (module-level) pour que N composables metier
  // qui recoivent simultanement une SessionExpiredError ne declenchent qu'UNE
  // execution de cancelTour/addSystemMessage/navigateTo.
  async function handleAuthFailure(): Promise<void> {
    if (authFailurePromise) return authFailurePromise

    authFailurePromise = (async () => {
      const uiStore = useUiStore()
      if (uiStore.guidedTourActive) {
        try {
          const { useGuidedTour } = await import('~/composables/useGuidedTour')
          useGuidedTour().cancelTour()
        } catch (err) {
          if (import.meta.dev) {
            console.warn('[handleAuthFailure] cancelTour cleanup failed', err)
          }
        }
        try {
          const { useChat } = await import('~/composables/useChat')
          useChat().addSystemMessage(CHAT_SESSION_EXPIRED_MESSAGE)
        } catch (err) {
          if (import.meta.dev) {
            console.warn('[handleAuthFailure] addSystemMessage failed', err)
          }
        }
      }
      // navigateTo est isomorphe Nuxt (safe SSR + client). En contexte client,
      // router.push serait equivalent mais navigateTo evite les edge cases SSR.
      await navigateTo('/login')
    })().finally(() => {
      authFailurePromise = null
    })

    return authFailurePromise
  }

  // F02 — logout cote serveur : revoque tous les refresh tokens via
  // POST /auth/logout puis vide le store local. Erreurs reseau silencieuses
  // (le user est deconnecte cote frontend dans tous les cas).
  async function logout(): Promise<void> {
    if (authStore.accessToken) {
      try {
        await apiFetch('/auth/logout', { method: 'POST' })
      } catch (err) {
        if (import.meta.dev) {
          console.warn('[logout] revocation serveur echouee', err)
        }
      }
    }
    authStore.clearAuth()
    await router.push('/login')
  }

  return {
    apiFetch,
    apiFetchBlob,
    register,
    detectCountry,
    login,
    fetchUser,
    refresh,
    logout,
    handleAuthFailure,
    isAuthenticated: authStore.isAuthenticated,
    // F02 — exposer isAdmin pour les middlewares et composants du back-office.
    isAdmin: authStore.isAdmin,
  }
}

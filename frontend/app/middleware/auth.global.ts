import { useAuthStore } from '~/stores/auth'

// F08 — Patterns de pages publiques accessibles sans authentification.
// /verify/{id} : page de vérification d'attestation (no-auth, scan QR fund officer).
// /legal/* : pages légales (mentions, conditions).
const PUBLIC_PATH_PATTERNS = [
  /^\/verify\/[^/]+\/?$/,
  /^\/legal(\/|$)/,
]

const PUBLIC_AUTH_PAGES = ['/login', '/register']

function isPublicPath(path: string): boolean {
  if (PUBLIC_AUTH_PAGES.includes(path)) return true
  return PUBLIC_PATH_PATTERNS.some((p) => p.test(path))
}

export default defineNuxtRouteMiddleware((to) => {
  const isPublicPage = isPublicPath(to.path)

  const authStore = useAuthStore()

  // Charger les tokens depuis localStorage au premier chargement
  if (import.meta.client && !authStore.accessToken) {
    authStore.loadFromStorage()
  }

  if (!isPublicPage && !authStore.isAuthenticated) {
    return navigateTo('/login')
  }

  // Rediriger les utilisateurs connectés qui tentent d'accéder au login/register
  // (mais pas les pages publiques /verify ou /legal — elles restent accessibles).
  if (
    PUBLIC_AUTH_PAGES.includes(to.path) &&
    authStore.isAuthenticated
  ) {
    return navigateTo('/')
  }
})

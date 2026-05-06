// F02 — Middleware Nuxt route-scope (NON global) :
// applique-le explicitement sur les pages admin via
// `definePageMeta({ middleware: 'admin' })`.
//
// Comportement :
//   - utilisateur non connecte    -> redirection /login
//   - utilisateur PME             -> redirection /dashboard
//   - utilisateur ADMIN           -> next() (acces autorise)
//
// On lit l'etat directement depuis le store auth pour ne pas declencher
// d'appel reseau supplementaire (le store est hydrate au boot par
// `loadFromStorage` + `/auth/me`).
import { useAuthStore } from '~/stores/auth'

export default defineNuxtRouteMiddleware(() => {
  const auth = useAuthStore()

  if (!auth.isAuthenticated) {
    return navigateTo('/login')
  }
  if (auth.role !== 'ADMIN') {
    return navigateTo('/dashboard')
  }
})

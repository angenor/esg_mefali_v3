import type { Page } from '@playwright/test'
import type { TestUser } from './users'

/**
 * Authentifie un utilisateur sans passer par le formulaire /login.
 *
 * Strategie adoptee : injection directe des tokens dans localStorage via
 * `page.addInitScript` AVANT tout `page.goto`. Le middleware global `auth.global.ts`
 * charge les tokens depuis localStorage au premier render (store.loadFromStorage)
 * et considere alors l'utilisateur authentifie.
 *
 * Pourquoi pas un login UI reel ?
 * - Rapide (<100 ms) vs ~2 s pour un login UI avec redirections + fetchUser()
 * - Aucun JWT reel requis — tous les endpoints auth sont mockes (cf mock-backend.ts)
 * - Deterministe — aucune depedance aux animations du formulaire ni au rate-limiting
 *
 * Important : `installMockBackend` DOIT avoir ete appele avant `loginAs` pour que
 * la route `GET /api/auth/me` renvoie l'utilisateur — sans quoi le dashboard
 * affichera des erreurs 404.
 *
 * F02 — Persistance role + account synchrone :
 * Inject aussi la cle `auth_user` (objet User serialise) attendue par
 * `app/stores/auth.ts::loadFromStorage()`. Sans cela, `auth.role` reste a
 * `null` au premier rendu et le middleware `admin.ts` redirige les Admin
 * vers `/dashboard` avant que `/auth/me` ne se resolve.
 */
export async function loginAs(page: Page, user: TestUser): Promise<void> {
  // Construire l'objet User attendu par le store (sans les champs de tokens
  // qui sont propres a la fixture). On copie explicitement tous les champs
  // de `User` (cf app/types/index.ts) pour eviter de fuiter `fakeAccessToken`
  // ou `fakeRefreshToken` dans `auth_user`.
  const authUser = {
    id: user.id,
    email: user.email,
    full_name: user.full_name,
    company_name: user.company_name,
    role: user.role,
    account: user.account ?? null,
    created_at: user.created_at,
    updated_at: user.updated_at,
  }

  await page.addInitScript(
    ({ accessToken, refreshToken, authUser: authUserPayload }) => {
      // ExecuteInPageContext : s'execute avant tout script de l'app.
      // Reset complet du storage pour garantir l'isolation entre tests (workers=1).
      window.localStorage.clear()
      window.localStorage.setItem('access_token', accessToken)
      window.localStorage.setItem('refresh_token', refreshToken)
      // F02 — persister l'objet User pour hydratation synchrone du role
      // et de l'account au premier render (cf store auth.loadFromStorage).
      window.localStorage.setItem('auth_user', JSON.stringify(authUserPayload))
    },
    {
      accessToken: user.fakeAccessToken,
      refreshToken: user.fakeRefreshToken,
      authUser,
    },
  )
}

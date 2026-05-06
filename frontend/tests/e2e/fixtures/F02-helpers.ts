/**
 * F02 — Helpers Playwright pour le multi-tenant + roles.
 *
 * Strategie : mock total des endpoints backend, comme les fixtures
 * existantes (mock-backend.ts pour 8.1 / 8.2). Aucun appel reseau reel,
 * tests deterministes en <2 s par scenario.
 *
 * Pattern adopte :
 *  - chaque "compte" (PME ou Admin) est materialise par un objet TestF02User
 *    qui porte fakeAccessToken/fakeRefreshToken pour `loginAs()`
 *  - les routes /api/auth/me, /api/account/users, /api/account/invite,
 *    /api/admin/health sont mockees per-test via `installF02MockBackend`
 *  - le helper `extractInviteTokenFromLogs` lit un magasin in-memory
 *    alimente par le mock backend (POST /api/account/invite genere un
 *    token deterministe stocke dans l'objet `state`)
 */
import type { Page, Route } from '@playwright/test'
import type {
  AccountInvitation,
  AccountSummary,
  AccountUsersResponse,
  Role,
  User,
} from '../../../app/types'

export interface TestF02User extends User {
  fakeAccessToken: string
  fakeRefreshToken: string
}

// ── Comptes de test ────────────────────────────────────────────────────

export const ACCOUNT_PME_A: AccountSummary = {
  id: 'acc-pme-a',
  name: 'PME Alpha SARL',
  is_active: true,
  plan: 'free',
}

export const ACCOUNT_PME_B: AccountSummary = {
  id: 'acc-pme-b',
  name: 'PME Beta SARL',
  is_active: true,
  plan: 'free',
}

export const ALICE: TestF02User = {
  id: 'user-alice-001',
  email: 'alice@pme-a.com',
  full_name: 'Alice Diallo',
  company_name: ACCOUNT_PME_A.name,
  role: 'PME',
  account: ACCOUNT_PME_A,
  created_at: '2026-01-10T08:00:00Z',
  fakeAccessToken: 'fake-access-alice',
  fakeRefreshToken: 'fake-refresh-alice',
}

export const BOB: TestF02User = {
  id: 'user-bob-001',
  email: 'bob@pme-b.com',
  full_name: 'Bob Niang',
  company_name: ACCOUNT_PME_B.name,
  role: 'PME',
  account: ACCOUNT_PME_B,
  created_at: '2026-01-10T08:30:00Z',
  fakeAccessToken: 'fake-access-bob',
  fakeRefreshToken: 'fake-refresh-bob',
}

export const ADMIN_USER: TestF02User = {
  id: 'user-admin-001',
  email: 'admin@esg-mefali.com',
  full_name: 'Admin Principal',
  company_name: 'ESG Mefali',
  role: 'ADMIN',
  account: null,
  created_at: '2026-01-01T08:00:00Z',
  fakeAccessToken: 'fake-access-admin',
  fakeRefreshToken: 'fake-refresh-admin',
}

// Carole rejoint l'Account d'Alice via une invitation.
export const CAROLE_INVITED: TestF02User = {
  id: 'user-carole-001',
  email: 'carole@pme-a.com',
  full_name: 'Carole Sow',
  company_name: ACCOUNT_PME_A.name,
  role: 'PME',
  account: ACCOUNT_PME_A,
  created_at: '2026-04-15T10:00:00Z',
  fakeAccessToken: 'fake-access-carole',
  fakeRefreshToken: 'fake-refresh-carole',
}

// Etat in-memory partage entre les routes mockees (par test).
export interface F02MockState {
  members: Record<string, TestF02User>
  pendingInvitations: AccountInvitation[]
  // Token "live" envoye dans le mail (LoggingEmailDelivery) — extractible
  // via extractInviteTokenFromMockState pour les scenarios complets.
  lastInviteToken: string | null
  // Conversations par user_id (US1 isolation)
  conversationsByUser: Record<string, Array<{ id: string; title: string }>>
}

export function createInitialState(): F02MockState {
  return {
    members: {
      [ALICE.id]: ALICE,
      [BOB.id]: BOB,
    },
    pendingInvitations: [],
    lastInviteToken: null,
    conversationsByUser: {},
  }
}

// ── Helpers HTTP ──────────────────────────────────────────────────────

function jsonResponse(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

function tokenFor(user: TestF02User) {
  return {
    access_token: user.fakeAccessToken,
    refresh_token: user.fakeRefreshToken,
    token_type: 'bearer',
    expires_in: 86400,
  }
}

function extractTokenFromAuth(headers: Record<string, string>): string | null {
  const auth = headers['authorization'] ?? headers['Authorization']
  if (!auth) return null
  const match = auth.match(/^Bearer\s+(.+)$/i)
  return match ? match[1] : null
}

function userByToken(state: F02MockState, token: string | null): TestF02User | null {
  if (!token) return null
  const candidates: TestF02User[] = [ALICE, BOB, ADMIN_USER, CAROLE_INVITED]
  return candidates.find((u) => u.fakeAccessToken === token) ?? null
}

// ── Mock backend installation ────────────────────────────────────────

export interface F02MockOptions {
  /** Utilisateur "courant" (celui qui repond au /auth/me du test). */
  currentUser?: TestF02User
  /** Etat partage entre routes (lazy si absent). */
  state?: F02MockState
}

/**
 * Installe les routes mock pour les scenarios F02. Doit etre appele
 * APRES `loginAs()` (qui injecte les tokens dans localStorage) et AVANT
 * `page.goto()`.
 */
export async function installF02MockBackend(
  page: Page,
  options: F02MockOptions = {},
): Promise<F02MockState> {
  const state = options.state ?? createInitialState()
  const currentUser = options.currentUser ?? ALICE

  // GET /api/auth/me — retourne le user courant (deduit du Bearer token)
  await page.route('**/api/auth/me', (route) => {
    const headers = route.request().headers()
    const token = extractTokenFromAuth(headers)
    const user = userByToken(state, token) ?? currentUser
    if (!user) {
      return jsonResponse(route, { detail: 'Unauthorized' }, 401)
    }
    return jsonResponse(route, user)
  })

  // GET /api/auth/detect-country — mock minimaliste
  await page.route('**/api/auth/detect-country', (route) =>
    jsonResponse(route, {
      detected_country: 'SN',
      supported_countries: ['SN', 'CI', 'ML', 'BF', 'TG', 'BJ'],
    }),
  )

  // POST /api/auth/login — accepte n'importe quel mdp et renvoie tokens
  await page.route('**/api/auth/login', async (route) => {
    const body = await route.request().postDataJSON().catch(() => ({}))
    const email = body?.email as string | undefined
    const allUsers: TestF02User[] = [ALICE, BOB, ADMIN_USER, CAROLE_INVITED]
    const user = allUsers.find((u) => u.email === email)
    if (!user) {
      return jsonResponse(route, { detail: 'Identifiants invalides' }, 401)
    }
    return jsonResponse(route, tokenFor(user))
  })

  // POST /api/auth/refresh — rotate
  await page.route('**/api/auth/refresh', (route) =>
    jsonResponse(route, tokenFor(currentUser)),
  )

  // POST /api/auth/logout — revoque (mock no-op + 204)
  await page.route('**/api/auth/logout', (route) =>
    route.fulfill({ status: 204, body: '' }),
  )

  // POST /api/auth/register — enregistre via invitation ou creation
  await page.route('**/api/auth/register', async (route) => {
    const body = await route.request().postDataJSON().catch(() => ({}))
    const inviteToken = body?.invite_token as string | undefined
    const email = body?.email as string | undefined
    if (inviteToken && state.lastInviteToken === inviteToken) {
      // L'utilisateur invite rejoint l'Account d'Alice (PME-A par defaut).
      const newUser: TestF02User = {
        ...CAROLE_INVITED,
        email: email ?? CAROLE_INVITED.email,
      }
      state.members[newUser.id] = newUser
      // Marquer l'invitation comme accepted
      state.pendingInvitations = state.pendingInvitations.filter(
        (inv) => inv.email !== email,
      )
      return jsonResponse(route, newUser, 201)
    }
    // Inscription standard (nouvel Account)
    const newAccount: AccountSummary = {
      id: 'acc-new-' + Date.now(),
      name: (body?.company_name as string) ?? 'Nouvelle entreprise',
      is_active: true,
      plan: 'free',
    }
    const newUser: TestF02User = {
      id: 'user-new-' + Date.now(),
      email: email ?? 'new@example.com',
      full_name: (body?.full_name as string) ?? 'Nouveau',
      company_name: newAccount.name,
      role: 'PME',
      account: newAccount,
      created_at: new Date().toISOString(),
      fakeAccessToken: 'fake-access-' + Date.now(),
      fakeRefreshToken: 'fake-refresh-' + Date.now(),
    }
    return jsonResponse(route, newUser, 201)
  })

  // GET /api/account/users — liste des membres + invitations pending
  await page.route('**/api/account/users', (route) => {
    const response: AccountUsersResponse = {
      members: Object.values(state.members)
        .filter((u) => u.account?.id === currentUser.account?.id)
        .map((u) => ({
          id: u.id,
          email: u.email,
          full_name: u.full_name,
          role: u.role ?? 'PME',
          is_active: true,
          joined_at: u.created_at,
        })),
      pending_invitations: state.pendingInvitations,
    }
    return jsonResponse(route, response)
  })

  // POST /api/account/invite — cree une invitation et stocke le token
  await page.route('**/api/account/invite', async (route) => {
    const body = await route.request().postDataJSON().catch(() => ({}))
    const email = (body?.email as string) ?? 'invite@example.com'
    const token = 'mock-invite-token-' + Date.now()
    state.lastInviteToken = token
    const invitation: AccountInvitation = {
      id: 'inv-' + Date.now(),
      email,
      status: 'pending',
      expires_at: new Date(
        Date.now() + 7 * 24 * 60 * 60 * 1000,
      ).toISOString(),
      invited_by: { id: currentUser.id, full_name: currentUser.full_name },
      created_at: new Date().toISOString(),
    }
    state.pendingInvitations.push(invitation)
    return jsonResponse(route, invitation, 201)
  })

  // DELETE /api/account/users/:id — soft delete
  await page.route('**/api/account/users/*', async (route) => {
    if (route.request().method() === 'DELETE') {
      const url = new URL(route.request().url())
      const segments = url.pathname.split('/')
      const userId = segments[segments.length - 1]
      delete state.members[userId]
      return route.fulfill({ status: 204, body: '' })
    }
    return route.continue()
  })

  // GET /api/admin/health — admin only (mock 403 si role != ADMIN)
  await page.route('**/api/admin/health', (route) => {
    const headers = route.request().headers()
    const token = extractTokenFromAuth(headers)
    const user = userByToken(state, token) ?? currentUser
    if (user.role !== 'ADMIN') {
      return jsonResponse(route, { detail: 'Acces reserve aux Admin' }, 403)
    }
    return jsonResponse(route, {
      status: 'ok',
      role: 'ADMIN',
      service: 'esg-mefali-backend',
    })
  })

  // GET /api/conversations — isolation US1 (chacun voit ses propres conv.)
  await page.route('**/api/chat/conversations', (route) => {
    const headers = route.request().headers()
    const token = extractTokenFromAuth(headers)
    const user = userByToken(state, token) ?? currentUser
    const list = state.conversationsByUser[user.id] ?? []
    return jsonResponse(route, list)
  })

  return state
}

/**
 * Recupere le dernier token d'invitation envoye par le mock backend
 * (simule la lecture des logs LoggingEmailDelivery cote serveur).
 */
export function extractInviteTokenFromMockState(
  state: F02MockState,
): string | null {
  return state.lastInviteToken
}

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

/**
 * F02 — Tests store auth.ts (US2 + US3).
 *
 * Couvre les nouveaux champs `account` et `role`, le getter `isAdmin`,
 * la propagation depuis setUser, le clearAuth qui purge tout et la
 * persistance du User dans localStorage (loadFromStorage hydrate role +
 * account de maniere synchrone pour eviter la fenetre ou le middleware
 * admin redirige a tort vers /dashboard).
 */
describe('useAuthStore (F02 multi-tenant)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Reset complet de localStorage entre chaque test pour eviter les
    // fuites d'etat cross-tests (jsdom partage le meme objet window).
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.clear()
    }
  })

  it('initialise account=null et role=null', async () => {
    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    expect(auth.account).toBeNull()
    expect(auth.role).toBeNull()
    expect(auth.isAdmin).toBe(false)
  })

  it('setUser propage role et account depuis le payload User', async () => {
    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.setUser({
      id: 'u1',
      email: 'admin@test.com',
      full_name: 'Admin',
      company_name: 'ESG',
      role: 'ADMIN',
      account: null,
      created_at: '2026-01-01',
    })

    expect(auth.role).toBe('ADMIN')
    expect(auth.account).toBeNull()
    expect(auth.isAdmin).toBe(true)
  })

  it('setUser hydrate account pour un utilisateur PME', async () => {
    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.setUser({
      id: 'u1',
      email: 'pme@test.com',
      full_name: 'PME',
      company_name: 'PME Co',
      role: 'PME',
      account: { id: 'a1', name: 'PME Co', is_active: true, plan: 'free' },
      created_at: '2026-01-01',
    })

    expect(auth.role).toBe('PME')
    expect(auth.isAdmin).toBe(false)
    expect(auth.account?.id).toBe('a1')
    expect(auth.account?.name).toBe('PME Co')
  })

  it('clearAuth purge user, tokens, account et role', async () => {
    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.setTokens({
      access_token: 'tok',
      refresh_token: 'ref',
      token_type: 'bearer',
      expires_in: 86400,
    })
    auth.setUser({
      id: 'u1',
      email: 'a@b.c',
      full_name: 'A',
      company_name: 'C',
      role: 'PME',
      account: { id: 'a1', name: 'C', is_active: true, plan: 'free' },
      created_at: '2026-01-01',
    })

    auth.clearAuth()

    expect(auth.user).toBeNull()
    expect(auth.accessToken).toBeNull()
    expect(auth.refreshToken).toBeNull()
    expect(auth.account).toBeNull()
    expect(auth.role).toBeNull()
    expect(auth.isAdmin).toBe(false)
  })

  it('setUser persiste le User complet dans localStorage (auth_user)', async () => {
    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.setUser({
      id: 'u1',
      email: 'admin@test.com',
      full_name: 'Admin',
      company_name: 'ESG',
      role: 'ADMIN',
      account: null,
      created_at: '2026-01-01',
    })

    const raw = window.localStorage.getItem('auth_user')
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw as string)
    expect(parsed.role).toBe('ADMIN')
    expect(parsed.email).toBe('admin@test.com')
  })

  it('loadFromStorage hydrate role et account synchroniquement (Admin)', async () => {
    // Pre-seed localStorage avec un Admin avant le mount du store
    window.localStorage.setItem('access_token', 'admin-token')
    window.localStorage.setItem(
      'auth_user',
      JSON.stringify({
        id: 'u1',
        email: 'admin@test.com',
        full_name: 'Admin',
        company_name: 'ESG',
        role: 'ADMIN',
        account: null,
        created_at: '2026-01-01',
      }),
    )

    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.loadFromStorage()

    expect(auth.accessToken).toBe('admin-token')
    expect(auth.role).toBe('ADMIN')
    expect(auth.isAdmin).toBe(true)
    expect(auth.user?.email).toBe('admin@test.com')
  })

  it('loadFromStorage hydrate role et account synchroniquement (PME)', async () => {
    window.localStorage.setItem('access_token', 'pme-token')
    window.localStorage.setItem(
      'auth_user',
      JSON.stringify({
        id: 'u2',
        email: 'pme@test.com',
        full_name: 'PME',
        company_name: 'PME Co',
        role: 'PME',
        account: { id: 'a1', name: 'PME Co', is_active: true, plan: 'free' },
        created_at: '2026-01-01',
      }),
    )

    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.loadFromStorage()

    expect(auth.role).toBe('PME')
    expect(auth.isAdmin).toBe(false)
    expect(auth.account?.id).toBe('a1')
  })

  it("loadFromStorage tolere un payload User corrompu et purge la cle", async () => {
    window.localStorage.setItem('access_token', 'tok')
    window.localStorage.setItem('auth_user', '{not-json')

    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.loadFromStorage()

    expect(auth.role).toBeNull()
    expect(auth.user).toBeNull()
    expect(window.localStorage.getItem('auth_user')).toBeNull()
  })

  it('clearAuth retire la cle auth_user du localStorage', async () => {
    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.setUser({
      id: 'u1',
      email: 'a@b.c',
      full_name: 'A',
      company_name: 'C',
      role: 'PME',
      account: null,
      created_at: '2026-01-01',
    })
    expect(window.localStorage.getItem('auth_user')).not.toBeNull()

    auth.clearAuth()

    expect(window.localStorage.getItem('auth_user')).toBeNull()
  })
})

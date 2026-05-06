import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

/**
 * F02 — Tests store auth.ts (US2 + US3).
 *
 * Couvre les nouveaux champs `account` et `role`, le getter `isAdmin`,
 * la propagation depuis setUser et le clearAuth qui purge tout.
 */
describe('useAuthStore (F02 multi-tenant)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Stub localStorage pour les tests Vitest (pas d'ssr ici)
    if (typeof window === 'undefined') {
      // pas de window — meta.client = false, le store skip localStorage
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
})

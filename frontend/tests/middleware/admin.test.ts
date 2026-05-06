import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock des auto-imports Nuxt
const mockNavigateTo = vi.fn()
;(globalThis as any).navigateTo = mockNavigateTo
;(globalThis as any).defineNuxtRouteMiddleware = (fn: Function) => fn

describe('middleware admin (F02 — US2)', () => {
  let middleware: () => unknown

  beforeAll(async () => {
    const mod = await import('~/middleware/admin')
    middleware = mod.default as () => unknown
  })

  beforeEach(() => {
    mockNavigateTo.mockClear()
    setActivePinia(createPinia())
  })

  it("redirige vers /login si l'utilisateur n'est pas authentifie", async () => {
    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.clearAuth() // s'assurer qu'on est deconnecte

    middleware()
    expect(mockNavigateTo).toHaveBeenCalledWith('/login')
  })

  it('redirige un utilisateur PME vers /dashboard', async () => {
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
      email: 'pme@test.com',
      full_name: 'PME',
      company_name: 'PME Co',
      role: 'PME',
      account: { id: 'a1', name: 'PME Co', is_active: true, plan: 'free' },
      created_at: '2026-01-01',
    })

    middleware()
    expect(mockNavigateTo).toHaveBeenCalledWith('/dashboard')
  })

  it('laisse passer un utilisateur ADMIN', async () => {
    const { useAuthStore } = await import('~/stores/auth')
    const auth = useAuthStore()
    auth.setTokens({
      access_token: 'tok',
      refresh_token: 'ref',
      token_type: 'bearer',
      expires_in: 86400,
    })
    auth.setUser({
      id: 'admin1',
      email: 'admin@test.com',
      full_name: 'Admin',
      company_name: 'ESG',
      role: 'ADMIN',
      account: null,
      created_at: '2026-01-01',
    })

    const result = middleware()
    expect(mockNavigateTo).not.toHaveBeenCalled()
    expect(result).toBeUndefined()
  })
})

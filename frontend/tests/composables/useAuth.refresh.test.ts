import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ═════════════════════════════════════════════════════════════════════
// Story 7.2 — Tests intercepteur JWT 401 → refresh → retry (AC1/3/2/6)
// ═════════════════════════════════════════════════════════════════════

// ── Mocks stores ──
const mockAuthStore = {
  accessToken: 'access-initial' as string | null,
  refreshToken: 'refresh-token' as string | null,
  setTokens: vi.fn((tokens: { access_token: string; refresh_token?: string }) => {
    mockAuthStore.accessToken = tokens.access_token
    if (tokens.refresh_token) mockAuthStore.refreshToken = tokens.refresh_token
  }),
  clearAuth: vi.fn(() => {
    mockAuthStore.accessToken = null
    mockAuthStore.refreshToken = null
  }),
  setUser: vi.fn(),
  isAuthenticated: true,
}
vi.mock('~/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

const mockUiStore = {
  guidedTourActive: false,
}
vi.mock('~/stores/ui', () => ({
  useUiStore: () => mockUiStore,
}))

// ── Mocks useGuidedTour / useChat (imports dynamiques dans handleAuthFailure) ──
const mockCancelTour = vi.fn()
vi.mock('~/composables/useGuidedTour', () => ({
  useGuidedTour: () => ({
    cancelTour: mockCancelTour,
  }),
}))

const mockAddSystemMessage = vi.fn()
vi.mock('~/composables/useChat', () => ({
  useChat: () => ({
    addSystemMessage: mockAddSystemMessage,
  }),
}))

// ── Mock useRouter (auto-import Nuxt, utilise par logout()) ──
const mockRouterPush = vi.fn()
vi.stubGlobal('useRouter', () => ({
  push: mockRouterPush,
}))

// ── Mock navigateTo (auto-import Nuxt, utilise par handleAuthFailure) ──
const mockNavigateTo = vi.fn(() => Promise.resolve())
vi.stubGlobal('navigateTo', mockNavigateTo)

// ── Mock import.meta.dev (no-op console.warn en prod) ──
// @ts-expect-error - import.meta.dev is set by Vite/Nuxt at build time
import.meta.dev = false

// ── Mock useRuntimeConfig ──
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://localhost:8000/api' },
}))

// ── Fetch mock ──
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response
}

async function importUseAuth() {
  const mod = await import('~/composables/useAuth')
  return mod
}

describe('useAuth — intercepteur 401 → refresh → retry (story 7.2)', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockCancelTour.mockClear()
    mockAddSystemMessage.mockClear()
    mockRouterPush.mockClear()
    mockNavigateTo.mockClear()
    mockAuthStore.accessToken = 'access-initial'
    mockAuthStore.refreshToken = 'refresh-token'
    mockAuthStore.setTokens.mockClear()
    mockAuthStore.clearAuth.mockClear()
    mockUiStore.guidedTourActive = false
  })

  afterEach(() => {
    vi.resetModules()
  })

  // ═════════════════════════════════════════════════════════════════
  // Bloc 1 : Intercepteur 401 → refresh → retry (AC1)
  // ═════════════════════════════════════════════════════════════════

  describe('Bloc 1 — intercepteur 401', () => {
    it('test_apiFetch_returns_data_on_first_200_without_triggering_refresh', async () => {
      mockFetch.mockResolvedValueOnce(jsonResponse({ hello: 'world' }, 200))
      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      const data = await apiFetch<{ hello: string }>('/dashboard/summary')

      expect(data).toEqual({ hello: 'world' })
      expect(mockFetch).toHaveBeenCalledTimes(1)
      expect(mockAuthStore.setTokens).not.toHaveBeenCalled()
    })

    it('test_apiFetch_triggers_refresh_on_401_then_retries_with_new_token', async () => {
      mockFetch
        // 1er appel : /dashboard/summary → 401
        .mockResolvedValueOnce(jsonResponse({ detail: 'token expired' }, 401))
        // 2e appel : /auth/refresh → 200 nouveau token
        .mockResolvedValueOnce(
          jsonResponse(
            { access_token: 'access-renewed', token_type: 'bearer', expires_in: 3600 },
            200,
          ),
        )
        // 3e appel : retry /dashboard/summary → 200
        .mockResolvedValueOnce(jsonResponse({ ok: true }, 200))

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      const data = await apiFetch<{ ok: boolean }>('/dashboard/summary')

      expect(data).toEqual({ ok: true })
      expect(mockFetch).toHaveBeenCalledTimes(3)
      expect(mockAuthStore.setTokens).toHaveBeenCalledWith(
        expect.objectContaining({ access_token: 'access-renewed' }),
      )
      // Le retry doit utiliser le nouveau token
      const retryCall = mockFetch.mock.calls[2]
      expect(retryCall[1].headers.Authorization).toBe('Bearer access-renewed')
    })

    it('test_apiFetch_throws_session_expired_when_refresh_fails', async () => {
      mockFetch
        .mockResolvedValueOnce(jsonResponse({ detail: 'token expired' }, 401))
        // /auth/refresh echoue lui aussi
        .mockResolvedValueOnce(jsonResponse({ detail: 'Refresh token invalide ou expiré' }, 401))

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      await expect(apiFetch('/dashboard/summary')).rejects.toThrow(/Session expirée/)
      expect(mockAuthStore.clearAuth).toHaveBeenCalled()
    })

    it('test_apiFetch_does_not_retry_when_second_attempt_also_401', async () => {
      mockFetch
        .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
        .mockResolvedValueOnce(
          jsonResponse(
            { access_token: 'access-renewed', token_type: 'bearer', expires_in: 3600 },
            200,
          ),
        )
        // Retry lui aussi en 401 — apiFetch doit throw SessionExpiredError
        // (token revoque / compte banni entre refresh et retry) sans boucler.
        .mockResolvedValueOnce(jsonResponse({ detail: 'still bad' }, 401))

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      await expect(apiFetch('/dashboard/summary')).rejects.toThrow(/Session expirée/)
      expect(mockFetch).toHaveBeenCalledTimes(3)
      expect(mockAuthStore.clearAuth).toHaveBeenCalled()
    })

    it('test_apiFetch_bypasses_refresh_for_auth_endpoints', async () => {
      // 401 sur /auth/login → throw direct, aucun appel a /auth/refresh
      mockFetch.mockResolvedValueOnce(jsonResponse({ detail: 'Identifiants invalides' }, 401))

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      await expect(
        apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({}) }),
      ).rejects.toThrow(/Identifiants invalides/)
      expect(mockFetch).toHaveBeenCalledTimes(1)
    })

    it('test_apiFetch_bypasses_refresh_when_no_access_token', async () => {
      mockAuthStore.accessToken = null
      mockFetch.mockResolvedValueOnce(jsonResponse({ detail: 'unauthenticated' }, 401))

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      await expect(apiFetch('/dashboard/summary')).rejects.toThrow(/unauthenticated/)
      expect(mockFetch).toHaveBeenCalledTimes(1)
    })

    it('test_refresh_clears_auth_when_no_refresh_token', async () => {
      // [fix scintillement] Sans refresh_token, refresh() doit purger l'auth
      // (clearAuth) et retourner false SANS appel réseau. Sinon l'access_token
      // survit en localStorage → réhydraté par le middleware → boucle infinie.
      mockAuthStore.refreshToken = null
      const { useAuth } = await importUseAuth()
      const { refresh } = useAuth()

      const ok = await refresh()

      expect(ok).toBe(false)
      expect(mockAuthStore.clearAuth).toHaveBeenCalled()
      expect(mockFetch).not.toHaveBeenCalled()
    })
  })

  // ═════════════════════════════════════════════════════════════════
  // Bloc 2 : Single-flight refresh (AC3)
  // ═════════════════════════════════════════════════════════════════

  describe('Bloc 2 — single-flight refresh', () => {
    it('test_concurrent_401s_share_a_single_refresh_call', async () => {
      let refreshCalls = 0
      mockFetch.mockImplementation((input: string) => {
        if (input.includes('/auth/refresh')) {
          refreshCalls++
          return Promise.resolve(
            jsonResponse(
              { access_token: 'access-renewed', token_type: 'bearer', expires_in: 3600 },
              200,
            ),
          )
        }
        // Premier appel sur chaque endpoint metier → 401, les retry → 200
        return Promise.resolve(jsonResponse({ url: input }, 200))
      })
      // Forcer : tous les 1ers appels business retournent 401, tous les 2e → 200
      const seenFirst = new Set<string>()
      mockFetch.mockReset()
      mockFetch.mockImplementation((input: string) => {
        if (input.includes('/auth/refresh')) {
          refreshCalls++
          return Promise.resolve(
            jsonResponse(
              { access_token: 'access-renewed', token_type: 'bearer', expires_in: 3600 },
              200,
            ),
          )
        }
        if (!seenFirst.has(input)) {
          seenFirst.add(input)
          return Promise.resolve(jsonResponse({ detail: 'expired' }, 401))
        }
        return Promise.resolve(jsonResponse({ url: input }, 200))
      })

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      const results = await Promise.all([
        apiFetch<{ url: string }>('/dashboard/summary'),
        apiFetch<{ url: string }>('/esg/assessments'),
        apiFetch<{ url: string }>('/carbon/assessments'),
      ])

      expect(results).toHaveLength(3)
      expect(refreshCalls).toBe(1)
    })

    it('test_refreshPromise_reset_after_completion', async () => {
      let refreshCalls = 0
      // Compteur explicite par URL metier : le 1er appel de chaque URL renvoie 401,
      // le 2e (retry apres refresh) renvoie 200. Evite l'heuristique fragile sur
      // mock.calls qui inclut l'appel courant.
      const seenByUrl = new Map<string, number>()
      mockFetch.mockImplementation((input: string) => {
        if (input.includes('/auth/refresh')) {
          refreshCalls++
          return Promise.resolve(
            jsonResponse(
              { access_token: `renewed-${refreshCalls}`, token_type: 'bearer', expires_in: 3600 },
              200,
            ),
          )
        }
        const seen = seenByUrl.get(input) ?? 0
        seenByUrl.set(input, seen + 1)
        // Premier hit sur cette URL metier → 401, second (retry) → 200
        return Promise.resolve(
          seen === 0
            ? jsonResponse({ detail: 'expired' }, 401)
            : jsonResponse({ ok: true }, 200),
        )
      })

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      await apiFetch('/dashboard/summary')
      await apiFetch('/esg/assessments')

      // 2 cycles complets 401 → refresh → retry → chacun a declenche son propre
      // /auth/refresh (preuve que refreshPromise a bien ete reset entre les deux).
      expect(refreshCalls).toBe(2)
    })

    it('test_concurrent_refresh_all_fail_together_when_refresh_rejects', async () => {
      const seenFirst = new Set<string>()
      mockFetch.mockImplementation((input: string) => {
        if (input.includes('/auth/refresh')) {
          return Promise.resolve(jsonResponse({ detail: 'refresh expired' }, 401))
        }
        if (!seenFirst.has(input)) {
          seenFirst.add(input)
          return Promise.resolve(jsonResponse({ detail: 'expired' }, 401))
        }
        return Promise.resolve(jsonResponse({ ok: true }, 200))
      })

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()

      const results = await Promise.allSettled([
        apiFetch('/dashboard/summary'),
        apiFetch('/esg/assessments'),
        apiFetch('/carbon/assessments'),
      ])

      expect(results.every((r) => r.status === 'rejected')).toBe(true)
      results.forEach((r) => {
        if (r.status === 'rejected') {
          expect(String(r.reason.message)).toMatch(/Session expirée/)
        }
      })
    })
  })

  // ═════════════════════════════════════════════════════════════════
  // Bloc 3 : handleAuthFailure (AC2)
  // ═════════════════════════════════════════════════════════════════

  describe('Bloc 3 — handleAuthFailure', () => {
    it('test_handleAuthFailure_cancels_guided_tour_when_active', async () => {
      mockUiStore.guidedTourActive = true
      const { useAuth } = await importUseAuth()
      const { handleAuthFailure } = useAuth()

      await handleAuthFailure()

      expect(mockCancelTour).toHaveBeenCalled()
      expect(mockAddSystemMessage).toHaveBeenCalledWith(
        'Votre session a expiré. Veuillez vous reconnecter.',
      )
      expect(mockNavigateTo).toHaveBeenCalledWith('/login')
    })

    it('test_handleAuthFailure_skips_chat_message_when_no_guided_tour', async () => {
      mockUiStore.guidedTourActive = false
      const { useAuth } = await importUseAuth()
      const { handleAuthFailure } = useAuth()

      await handleAuthFailure()

      expect(mockCancelTour).not.toHaveBeenCalled()
      expect(mockAddSystemMessage).not.toHaveBeenCalled()
      expect(mockNavigateTo).toHaveBeenCalledWith('/login')
    })

    it('test_handleAuthFailure_is_idempotent_on_concurrent_calls', async () => {
      // N requetes paralleles qui echouent en session expiree ne doivent
      // declencher qu'UN cancelTour + UN addSystemMessage + UN navigateTo.
      mockUiStore.guidedTourActive = true
      const { useAuth } = await importUseAuth()
      const { handleAuthFailure } = useAuth()

      await Promise.all([handleAuthFailure(), handleAuthFailure(), handleAuthFailure()])

      expect(mockCancelTour).toHaveBeenCalledTimes(1)
      expect(mockAddSystemMessage).toHaveBeenCalledTimes(1)
      expect(mockNavigateTo).toHaveBeenCalledTimes(1)
    })

    it('test_handleAuthFailure_clears_auth_before_redirect', async () => {
      // [fix scintillement] handleAuthFailure DOIT purger le store + localStorage
      // (clearAuth) AVANT de naviguer vers /login. Sinon accessToken survit, le
      // middleware global voit isAuthenticated=true sur /login et redirige vers
      // '/', qui relance un apiFetch → 401 → boucle de redirection = scintillement.
      mockUiStore.guidedTourActive = false
      const { useAuth } = await importUseAuth()
      const { handleAuthFailure } = useAuth()

      await handleAuthFailure()

      expect(mockAuthStore.clearAuth).toHaveBeenCalled()
      expect(mockNavigateTo).toHaveBeenCalledWith('/login')
      // Au moment de la navigation, le token doit déjà être purgé.
      expect(mockAuthStore.accessToken).toBeNull()
    })
  })

  // ═════════════════════════════════════════════════════════════════
  // Bloc 4 : Scenarios integres guidage (AC5) + test AC4 (mono-page)
  // ═════════════════════════════════════════════════════════════════

  describe('Bloc 4 — scenarios guidage', () => {
    it('test_multi_page_tour_silent_refresh_during_navigation', async () => {
      mockUiStore.guidedTourActive = true
      mockFetch
        // Mount page /dashboard → 401
        .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
        // /auth/refresh → 200
        .mockResolvedValueOnce(
          jsonResponse(
            { access_token: 'access-renewed', token_type: 'bearer', expires_in: 3600 },
            200,
          ),
        )
        // Retry → 200
        .mockResolvedValueOnce(jsonResponse({ summary: 'ok' }, 200))

      const { useAuth } = await importUseAuth()
      const { apiFetch } = useAuth()
      const data = await apiFetch('/dashboard/summary')

      expect(data).toEqual({ summary: 'ok' })
      // Refresh silencieux : aucun message chat, pas d'annulation de tour
      expect(mockAddSystemMessage).not.toHaveBeenCalled()
      expect(mockCancelTour).not.toHaveBeenCalled()
    })

    it('test_multi_page_tour_cancelled_when_refresh_expires', async () => {
      mockUiStore.guidedTourActive = true
      mockFetch
        .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
        .mockResolvedValueOnce(jsonResponse({ detail: 'refresh expired' }, 401))

      const { useAuth } = await importUseAuth()
      const { apiFetch, handleAuthFailure } = useAuth()

      try {
        await apiFetch('/dashboard/summary')
      } catch (e) {
        expect((e as Error).message).toMatch(/Session expirée/)
        await handleAuthFailure()
      }

      expect(mockCancelTour).toHaveBeenCalled()
      expect(mockAddSystemMessage).toHaveBeenCalledWith(
        'Votre session a expiré. Veuillez vous reconnecter.',
      )
      expect(mockNavigateTo).toHaveBeenCalledWith('/login')
    })

    it('test_driverjs_mono_page_tour_survives_jwt_expiration_without_api_call', async () => {
      // Aucun appel API → aucun 401 → aucun refresh declenche.
      mockUiStore.guidedTourActive = true
      const { useAuth } = await importUseAuth()
      useAuth()

      // On simule : JWT expire (token invalidable cote serveur) mais le front
      // ne fait aucun fetch — la boucle Driver.js est purement DOM.
      expect(mockFetch).not.toHaveBeenCalled()
      expect(mockCancelTour).not.toHaveBeenCalled()
    })
  })
})

// ═════════════════════════════════════════════════════════════════════
// Bloc 5 : Migration composables metier (AC6)
// ═════════════════════════════════════════════════════════════════════

describe('Migration composables metier — delegation a apiFetch (story 7.2)', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockRouterPush.mockClear()
    mockNavigateTo.mockClear()
    mockCancelTour.mockClear()
    mockAddSystemMessage.mockClear()
    mockAuthStore.accessToken = 'access-initial'
    mockAuthStore.refreshToken = 'refresh-token'
    mockUiStore.guidedTourActive = false
  })

  afterEach(() => {
    vi.resetModules()
  })

  it('test_useDashboard_fetchSummary_delegates_to_apiFetch', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ company_id: 'abc', esg: null }, 200))
    vi.doMock('~/stores/dashboard', () => ({
      useDashboardStore: () => ({
        setLoading: vi.fn(),
        setError: vi.fn(),
        setSummary: vi.fn(),
      }),
    }))
    const { useDashboard } = await import('~/composables/useDashboard')
    const { fetchSummary } = useDashboard()
    const data = await fetchSummary()

    expect(data).toEqual({ company_id: 'abc', esg: null })
    expect(mockFetch).toHaveBeenCalledTimes(1)
    const call = mockFetch.mock.calls[0]
    expect(call[0]).toContain('/dashboard/summary')
    expect(call[1].headers.Authorization).toBe('Bearer access-initial')
  })

  it('test_useEsg_assessment_calls_go_through_apiFetch', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ data: [], total: 0, page: 1, limit: 10 }, 200),
    )
    vi.doMock('~/stores/esg', () => ({
      useEsgStore: () => ({
        setLoading: vi.fn(),
        setError: vi.fn(),
        setAssessments: vi.fn(),
      }),
    }))
    const { useEsg } = await import('~/composables/useEsg')
    const { fetchAssessments } = useEsg()
    await fetchAssessments()

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const call = mockFetch.mock.calls[0]
    expect(call[0]).toContain('/esg/assessments')
    expect(call[1].headers.Authorization).toBe('Bearer access-initial')
  })

  it('test_useCarbon_assessment_calls_go_through_apiFetch', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ items: [], total: 0, page: 1, limit: 10 }, 200))
    vi.doMock('~/stores/carbon', () => ({
      useCarbonStore: () => ({
        setLoading: vi.fn(),
        setError: vi.fn(),
        setAssessments: vi.fn(),
      }),
    }))
    const { useCarbon } = await import('~/composables/useCarbon')
    const { fetchAssessments } = useCarbon()
    await fetchAssessments()

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const call = mockFetch.mock.calls[0]
    expect(call[0]).toContain('/carbon/assessments')
    expect(call[1].headers.Authorization).toBe('Bearer access-initial')
  })

  it('test_useFinancing_matches_calls_go_through_apiFetch', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ items: [], total: 0 }, 200))
    vi.doMock('~/stores/financing', () => ({
      useFinancingStore: () => ({
        setLoading: vi.fn(),
        setError: vi.fn(),
        setMatches: vi.fn(),
      }),
    }))
    const { useFinancing } = await import('~/composables/useFinancing')
    const { fetchMatches } = useFinancing()
    await fetchMatches()

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const call = mockFetch.mock.calls[0]
    expect(call[0]).toContain('/financing/matches')
    expect(call[1].headers.Authorization).toBe('Bearer access-initial')
  })

  it('test_useDashboard_calls_handleAuthFailure_on_session_expired', async () => {
    mockUiStore.guidedTourActive = true
    mockFetch
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'refresh expired' }, 401))

    vi.doMock('~/stores/dashboard', () => ({
      useDashboardStore: () => ({
        setLoading: vi.fn(),
        setError: vi.fn(),
        setSummary: vi.fn(),
      }),
    }))
    const { useDashboard } = await import('~/composables/useDashboard')
    const { fetchSummary } = useDashboard()
    const result = await fetchSummary()

    expect(result).toBeNull()
    expect(mockNavigateTo).toHaveBeenCalledWith('/login')
    expect(mockCancelTour).toHaveBeenCalled()
    expect(mockAddSystemMessage).toHaveBeenCalledWith(
      'Votre session a expiré. Veuillez vous reconnecter.',
    )
  })
})

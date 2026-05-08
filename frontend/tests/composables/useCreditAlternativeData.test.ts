import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * F18 — Tests useCreditAlternativeData (Mobile Money + Public data + Methodology).
 */

const mockAuthStore = { accessToken: 'fake-jwt' }

vi.mock('~/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

// Stub Nuxt useRuntimeConfig
;(globalThis as Record<string, unknown>).useRuntimeConfig = () => ({
  public: { apiBase: 'http://test' },
})

const fetchMock = vi.fn()
;(globalThis as Record<string, unknown>).fetch = fetchMock

describe('useCreditAlternativeData', () => {
  beforeEach(() => {
    fetchMock.mockReset()
  })

  describe('getMethodology', () => {
    it('appelle /credit/methodology sans Bearer (endpoint public)', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({ version: '1.2', factors: [], total_weight: '0' }),
      })

      const { useCreditAlternativeData } = await import(
        '~/composables/useCreditAlternativeData'
      )
      const composable = useCreditAlternativeData()
      const result = await composable.getMethodology()

      expect(fetchMock).toHaveBeenCalledWith('http://test/credit/methodology')
      const args = fetchMock.mock.calls[0]
      expect(args[1]).toBeUndefined()
      expect(result.version).toBe('1.2')
    })
  })

  describe('uploadMobileMoney — consent gating', () => {
    it('lève ConsentRequiredError si 403 consent_required', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: () =>
          Promise.resolve({
            detail: {
              detail: 'Consentement Mobile Money requis',
              consent_type: 'mobile_money_analysis',
              settings_url: '/mes-donnees/consentements',
            },
          }),
      })

      const { useCreditAlternativeData, ConsentRequiredError } = await import(
        '~/composables/useCreditAlternativeData'
      )
      const composable = useCreditAlternativeData()
      const file = new File(['date,type,amount,counterparty\n'], 'test.csv', {
        type: 'text/csv',
      })

      await expect(composable.uploadMobileMoney(file, 'wave')).rejects.toThrow(
        ConsentRequiredError
      )
    })

    it('retourne MobileMoneyUploadResponse en cas de succès', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () =>
          Promise.resolve({
            import_id: 'i-1',
            imported_rows: 3,
            rejected_rows: 0,
            status: 'completed',
            error_summary: null,
            analysis: null,
          }),
      })

      const { useCreditAlternativeData } = await import(
        '~/composables/useCreditAlternativeData'
      )
      const composable = useCreditAlternativeData()
      const file = new File(['x'], 'test.csv', { type: 'text/csv' })

      const result = await composable.uploadMobileMoney(file, 'wave')
      expect(result.imported_rows).toBe(3)
      expect(result.status).toBe('completed')
    })
  })

  describe('listPublicData', () => {
    it('retourne un tableau vide si aucune source', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      })

      const { useCreditAlternativeData } = await import(
        '~/composables/useCreditAlternativeData'
      )
      const composable = useCreditAlternativeData()
      const result = await composable.listPublicData()
      expect(result).toEqual([])
    })
  })

  describe('deletePublicData', () => {
    it('soft-delete renvoie 204', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 204,
        json: () => Promise.resolve({}),
      })

      const { useCreditAlternativeData } = await import(
        '~/composables/useCreditAlternativeData'
      )
      const composable = useCreditAlternativeData()
      await expect(
        composable.deletePublicData('source-id-1')
      ).resolves.toBeUndefined()
    })
  })
})

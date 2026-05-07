/**
 * Tests du composable useAttestations (F08).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://test/api' },
}))

vi.mock('~/stores/auth', () => ({
  useAuthStore: () => ({
    accessToken: 'test-token',
  }),
}))

import { useAttestations } from '~/composables/useAttestations'

describe('useAttestations', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    global.fetch = vi.fn() as never
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('generateAttestation appelle POST /attestations', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', display_id: 'ATT-2026-00001' }),
    })
    const { generateAttestation } = useAttestations()
    const result = await generateAttestation('combined')
    expect(result?.display_id).toBe('ATT-2026-00001')
    expect(global.fetch).toHaveBeenCalledWith(
      'http://test/api/attestations',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ attestation_type: 'combined' }),
      }),
    )
  })

  it('listAttestations appelle GET /attestations', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: 'a' }, { id: 'b' }],
    })
    const { listAttestations } = useAttestations()
    const result = await listAttestations()
    expect(result).toHaveLength(2)
    expect(global.fetch).toHaveBeenCalledWith(
      'http://test/api/attestations',
      expect.objectContaining({}),
    )
  })

  it('revokeAttestation appelle POST /attestations/{id}/revoke', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', revoked_at: '2026-05-07' }),
    })
    const { revokeAttestation } = useAttestations()
    const result = await revokeAttestation('abc', 'Mise à jour profil')
    expect(result).toBeTruthy()
    expect(global.fetch).toHaveBeenCalledWith(
      'http://test/api/attestations/abc/revoke',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ reason: 'Mise à jour profil' }),
      }),
    )
  })

  it('verifyPublic appelle GET /public/verify/{id} sans Authorization', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'authentic' }),
    })
    const { verifyPublic } = useAttestations()
    const r = await verifyPublic('abc-123')
    expect(r?.status).toBe('authentic')
  })

  it('listAttestations retourne tableau vide en cas d\'erreur', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      json: async () => ({}),
    })
    const { listAttestations, error } = useAttestations()
    const result = await listAttestations()
    expect(result).toEqual([])
    expect(error.value).not.toBe('')
  })

  it('generateAttestation retourne null en cas d\'erreur', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'CreditScore manquant' }),
    })
    const { generateAttestation, error } = useAttestations()
    const r = await generateAttestation('combined')
    expect(r).toBeNull()
    expect(error.value).toBe('CreditScore manquant')
  })
})

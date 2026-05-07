import type { Page } from '@playwright/test'

/**
 * Helpers Playwright pour F08 Attestation Vérifiable Ed25519.
 *
 * Mocks backend pour :
 * - GET /api/public/verify/{id} (4 statuts)
 * - GET /api/attestations (liste PME)
 * - POST /api/attestations (génération)
 * - POST /api/attestations/{id}/revoke
 * - GET /api/attestations/{id}/download (PDF stub)
 */

export const SAMPLE_AUTHENTIC = {
  status: 'authentic' as const,
  verified_at: '2026-05-07T10:00:00Z',
  message: 'Attestation authentique et signée',
  attestation_id: '11111111-2222-3333-4444-555555555555',
  display_id: 'ATT-2026-00042',
  attestation_type: 'combined' as const,
  valid_from: '2026-05-07T00:00:00Z',
  valid_until: '2027-05-07T00:00:00Z',
  issued_at: '2026-05-07T00:00:00Z',
  scores: { combined: 73, solvability: 68, green_impact: 78 },
  referentials: [{ name: 'ESG Mefali', version: '1.0' }],
  pdf_hash_sha256: 'a'.repeat(64),
  public_key_id: 'v1',
}

export const SAMPLE_REVOKED = {
  ...SAMPLE_AUTHENTIC,
  status: 'revoked' as const,
  message: 'Cette attestation a été révoquée',
  revoked_at: '2026-06-01T10:00:00Z',
  revoked_reason: 'Mise à jour majeure du profil',
  revoked_by_role: 'pme' as const,
}

export const SAMPLE_EXPIRED = {
  ...SAMPLE_AUTHENTIC,
  status: 'expired' as const,
  message: 'Cette attestation a expiré',
  valid_until: '2025-05-07T00:00:00Z',
  expired_since: '2025-05-07T00:00:00Z',
}

export const SAMPLE_INVALID = {
  status: 'invalid' as const,
  verified_at: '2026-05-07T10:00:00Z',
  message: "Cet identifiant d'attestation n'existe pas ou la signature est invalide",
}

export async function mockAuthForAttestations(page: Page) {
  await page.addInitScript(() => {
    const fakeUser = {
      id: 'user-1',
      email: 'pme@test.fr',
      full_name: 'PME Test',
      role: 'PME',
      account_id: 'acc-1',
    }
    localStorage.setItem('access_token', 'fake-jwt')
    localStorage.setItem('refresh_token', 'fake-refresh')
    localStorage.setItem('user', JSON.stringify(fakeUser))
  })
}

export async function mockPublicVerify(page: Page, response: object) {
  await page.route('**/api/public/verify/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(response),
    })
  })
}

export async function mockAttestationsList(
  page: Page,
  attestations: Array<Record<string, unknown>>,
) {
  await page.route('**/api/attestations', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(attestations),
      })
    } else if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          ...SAMPLE_AUTHENTIC,
          id: SAMPLE_AUTHENTIC.attestation_id,
          payload: { scores: SAMPLE_AUTHENTIC.scores },
          referential_snapshot: SAMPLE_AUTHENTIC.referentials,
          revoked_at: null,
          revoked_reason: null,
          verification_url: 'https://esg-mefali.com/verify/11111111-2222-3333-4444-555555555555',
          created_at: '2026-05-07T00:00:00Z',
        }),
      })
    }
  })
}

export async function mockAttestationRevoke(page: Page) {
  await page.route('**/api/attestations/*/revoke', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...SAMPLE_AUTHENTIC,
        id: SAMPLE_AUTHENTIC.attestation_id,
        revoked_at: '2026-06-01T10:00:00Z',
        revoked_reason: 'Test révocation E2E',
        verification_url:
          'https://esg-mefali.com/verify/11111111-2222-3333-4444-555555555555',
        created_at: '2026-05-07T00:00:00Z',
      }),
    })
  })
}

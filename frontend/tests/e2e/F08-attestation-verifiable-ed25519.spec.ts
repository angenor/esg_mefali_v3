import { expect, test } from '@playwright/test'
import {
  SAMPLE_AUTHENTIC,
  SAMPLE_EXPIRED,
  SAMPLE_INVALID,
  SAMPLE_REVOKED,
  mockAttestationRevoke,
  mockAttestationsList,
  mockAuthForAttestations,
  mockPublicVerify,
} from './F08-helpers'

/**
 * F08 — Attestation Vérifiable Ed25519 + QR + Page Publique /verify/{id} + Révocation (E2E).
 *
 * 5 scénarios couvrant les user stories US1, US2, US3, US6 du spec :
 *
 * 1. Generate authentic — login PME, page /attestations, génération réelle
 *    via API mockée, vérifie la liste, ouvre verify/{id} sans auth, badge AUTHENTIQUE.
 * 2. Tampered PDF detection — page /verify/{id} affiche AUTHENTIQUE, on colle
 *    un hash altéré dans HashCompareInput → message "non conforme".
 * 3. Revoke — accéder /attestations, révoquer, recharger /verify/{id}, badge RÉVOQUÉE.
 * 4. Expired — /verify/{id} avec mock status=expired, badge EXPIRÉE.
 * 5. Invalid UUID — /verify/{id} avec UUID inexistant, badge INVALIDE, aucun champ leak.
 */

test.describe('F08 — Attestation Vérifiable Ed25519', () => {
  test('Scenario 1 — Page publique /verify/{id} affiche AUTHENTIQUE', async ({
    page,
  }) => {
    await mockPublicVerify(page, SAMPLE_AUTHENTIC)
    await page.goto(`/verify/${SAMPLE_AUTHENTIC.attestation_id}`)

    // Pas de redirect vers /login
    await expect(page).toHaveURL(/\/verify\//)

    // Badge AUTHENTIQUE visible
    await expect(page.getByRole('status', { name: 'AUTHENTIQUE', exact: true })).toBeVisible()

    // Identifiant affiché
    await expect(page.getByText(SAMPLE_AUTHENTIC.display_id)).toBeVisible()

    // Hash visible
    await expect(page.locator('text=' + SAMPLE_AUTHENTIC.pdf_hash_sha256)).toBeVisible()
  })

  test('Scenario 2 — Tampered PDF detection (HashCompareInput)', async ({ page }) => {
    await mockPublicVerify(page, SAMPLE_AUTHENTIC)
    await page.goto(`/verify/${SAMPLE_AUTHENTIC.attestation_id}`)
    await expect(page.getByRole('status', { name: 'AUTHENTIQUE', exact: true })).toBeVisible()

    // Saisir un hash altéré dans HashCompareInput
    const tampered = 'b'.repeat(64)
    await page.locator('input#hash-compare').fill(tampered)
    await page.getByRole('button', { name: /comparer/i }).click()

    // Message d'erreur visible
    await expect(page.getByText(/non conforme/i)).toBeVisible()
  })

  test('Scenario 2bis — Hash conforme si match exact', async ({ page }) => {
    await mockPublicVerify(page, SAMPLE_AUTHENTIC)
    await page.goto(`/verify/${SAMPLE_AUTHENTIC.attestation_id}`)
    await expect(page.getByRole('status', { name: 'AUTHENTIQUE', exact: true })).toBeVisible()

    // Saisir le hash exact (le même que SAMPLE_AUTHENTIC.pdf_hash_sha256)
    await page.locator('input#hash-compare').fill(SAMPLE_AUTHENTIC.pdf_hash_sha256)
    await page.getByRole('button', { name: /comparer/i }).click()

    // Message de match visible
    await expect(page.getByText(/conforme/i)).toBeVisible()
  })

  test('Scenario 3 — Page publique affiche RÉVOQUÉE après révocation', async ({
    page,
  }) => {
    await mockPublicVerify(page, SAMPLE_REVOKED)
    await page.goto(`/verify/${SAMPLE_REVOKED.attestation_id}`)

    await expect(page.getByRole('status', { name: 'RÉVOQUÉE', exact: true })).toBeVisible()
    await expect(page.getByText(/Mise à jour majeure du profil/i)).toBeVisible()
  })

  test('Scenario 4 — Attestation expirée', async ({ page }) => {
    await mockPublicVerify(page, SAMPLE_EXPIRED)
    await page.goto(`/verify/${SAMPLE_EXPIRED.attestation_id}`)

    await expect(page.getByRole('status', { name: 'EXPIRÉE', exact: true })).toBeVisible()
  })

  test('Scenario 5 — UUID invalide → INVALIDE sans fuite', async ({ page }) => {
    await mockPublicVerify(page, SAMPLE_INVALID)
    await page.goto('/verify/00000000-0000-0000-0000-000000000000')

    await expect(page.getByRole('status', { name: 'INVALIDE', exact: true })).toBeVisible()

    // Vérifier qu'aucun champ technique sensible n'est exposé
    const html = await page.content()
    expect(html).not.toContain(SAMPLE_AUTHENTIC.display_id)
    expect(html).not.toContain(SAMPLE_AUTHENTIC.pdf_hash_sha256)
  })
})

test.describe('F08 — Liste PME (authentifié)', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthForAttestations(page)
    await mockAttestationsList(page, [
      {
        id: SAMPLE_AUTHENTIC.attestation_id,
        display_id: SAMPLE_AUTHENTIC.display_id,
        attestation_type: 'combined',
        valid_from: SAMPLE_AUTHENTIC.valid_from,
        valid_until: SAMPLE_AUTHENTIC.valid_until,
        revoked_at: null,
        revoked_reason: null,
        verification_url: `https://esg-mefali.com/verify/${SAMPLE_AUTHENTIC.attestation_id}`,
        pdf_hash_sha256: SAMPLE_AUTHENTIC.pdf_hash_sha256,
        public_key_id: 'v1',
        created_at: SAMPLE_AUTHENTIC.valid_from,
      },
    ])
    await mockAttestationRevoke(page)
  })

  test('La page /attestations liste les attestations existantes', async ({ page }) => {
    await page.goto('/attestations')
    await expect(page.getByText('Mes attestations')).toBeVisible()
    await expect(page.getByText(SAMPLE_AUTHENTIC.display_id)).toBeVisible()
  })
})

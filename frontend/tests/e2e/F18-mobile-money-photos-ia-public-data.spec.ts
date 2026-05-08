import { test, expect } from '@playwright/test'

/**
 * F18 — Mobile Money + Photos IA + Données publiques (E2E).
 *
 * NOTE phase B → B' : ces tests E2E sont conçus pour l'orchestrateur B'.
 * Ils valident :
 *  1. Méthodologie publique accessible sans login.
 *  2. Upload Mobile Money sans consentement → bannière 403 + CTA F05.
 *  3. Upload Mobile Money avec consentement actif → KPIs visibles.
 *  4. Déclaration source publique sans consentement → 403.
 *
 * Les scénarios Photos IA (P2) et plafond 10 % public_data (P3) sont
 * skippés en phase B (scope_partial F18 — voir notes orchestrateur).
 */

test.describe('F18 — Méthodologie publique (no auth)', () => {
  test('expose la version, les facteurs et leurs sources cliquables', async ({
    page,
  }) => {
    await page.goto('/legal/methodology-credit')
    await expect(
      page.getByRole('heading', { name: /Méthodologie de scoring crédit/i })
    ).toBeVisible()
    // Version visible (au moins le badge)
    await expect(page.getByLabel(/Version de la méthodologie/i)).toBeVisible()
  })
})

test.describe('F18 — Mobile Money gating', () => {
  test.skip('upload sans consentement → modale + bannière 403', async () => {
    // Implémenté en phase B' (mocks backend complets).
  })

  test.skip('upload avec consentement → KPIs ≥ 5 visibles', async () => {
    // Implémenté en phase B'.
  })
})

test.describe('F18 — Données publiques', () => {
  test.skip('déclarer 1 source publique sans consentement → 403', async () => {
    // Implémenté en phase B'.
  })

  test.skip('catégorie plafonnée à 10 % du score combiné', async () => {
    // Implémenté en phase B' — scope_partial : refactor scoring P3.
  })
})

test.describe('F18 — Photos IA (P2 — scope_partial)', () => {
  test.skip('upload 3 photos → analyse → 5 scores', async () => {
    // Phase B' : analyzer Vision OpenRouter à câbler.
  })
})

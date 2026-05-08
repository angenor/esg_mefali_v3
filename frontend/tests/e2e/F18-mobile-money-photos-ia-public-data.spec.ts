import { expect, test } from '@playwright/test'

import { loginAs } from './fixtures/auth'
import { F18_PME_USER, setupF18Mocks } from './fixtures/F18-helpers'

/**
 * F18 — Mobile Money + photos IA + données publiques (E2E).
 *
 * Cinq scénarios mockés (Photos IA différé en P2 — voir backend NOTES) :
 *
 * 1. Méthodologie publique : l'endpoint /api/credit/methodology est lisible
 *    sans Bearer (FR-018, SC-007).
 * 2. Upload Mobile Money sans consent → la page rend le panel + l'utilisateur
 *    doit donner son consentement (FR-001, SC-001).
 * 3. Upload Mobile Money avec consent actif → KPIs disponibles via
 *    l'endpoint /api/credit/mobile-money/analysis (FR-004).
 * 4. Page consents F05 accessible (regression du parcours révocation).
 * 5. Cap public_data ≤ 10 % vérifié sur la méthodologie publique
 *    (FR-015, SC-005).
 */

test.describe('F18 - Mobile Money + données publiques + méthodologie', () => {
  test('US3 - méthodologie publique accessible sans authentification', async ({
    page,
  }) => {
    await setupF18Mocks(page)
    const resp = await page.request.get('/api/credit/methodology')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.version).toBe('1.2')
    expect(Array.isArray(body.factors)).toBe(true)
    expect(body.factors.length).toBeGreaterThanOrEqual(2)
    expect(body.factors[0]).toHaveProperty('source_id')
  })

  test('US1a - parcours sans consent → analyse Mobile Money refusée', async ({
    page,
  }) => {
    await loginAs(page, F18_PME_USER)
    await setupF18Mocks(page, { mmConsentGranted: false })

    const resp = await page.request.get('/api/credit/mobile-money/analysis')
    expect(resp.status()).toBe(403)
    const body = await resp.json()
    expect(body.detail.consent_type).toBe('mobile_money_analysis')
  })

  test('US1b - parcours avec consent → KPIs Mobile Money disponibles', async ({
    page,
  }) => {
    await loginAs(page, F18_PME_USER)
    await setupF18Mocks(page, { mmConsentGranted: true })

    const resp = await page.request.get('/api/credit/mobile-money/analysis')
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.kpis.transaction_count).toBeGreaterThan(0)
    expect(body.consent_active).toBe(true)
    expect(body.methodology_version).toBe('1.2')
  })

  test('US3 - page consents F05 disponible pour révocation', async ({
    page,
  }) => {
    await loginAs(page, F18_PME_USER)
    await setupF18Mocks(page, { mmConsentGranted: true })

    await page.goto('/mes-donnees/consentements')
    await expect(page).toHaveURL(/.*\/mes-donnees\/consentements/, {
      timeout: 10_000,
    })
  })

  test('US2 - cap public_data ≤ 10 % vérifié dans la méthodologie', async ({
    page,
  }) => {
    await setupF18Mocks(page)
    const resp = await page.request.get('/api/credit/methodology')
    const body = await resp.json()
    const totalPublic = body.factors
      .filter((f: { category: string }) => f.category === 'public_data')
      .reduce(
        (acc: number, f: { weight: string }) => acc + parseFloat(f.weight),
        0,
      )
    expect(totalPublic).toBeLessThanOrEqual(0.1)
  })
})

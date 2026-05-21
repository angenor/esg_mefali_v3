import { test, expect } from '@playwright/test'

/**
 * F25 — Catalogue admin — Test E2E d'accès (US1).
 *
 * Vérifie que :
 *  - un compte ADMIN authentifié peut ouvrir /admin/catalog et voit les 4 onglets,
 *  - un compte PME est redirigé vers /dashboard (middleware admin.ts).
 *
 * Les fixtures backend (mock ou réel) sont injectées via les helpers F02
 * pour rester aligné sur les autres specs.
 */

test.describe('F25 — Accès /admin/catalog', () => {
  test('ADMIN voit les 4 onglets', async ({ page }) => {
    // Stub léger : route les appels API critiques vers du JSON pré-construit.
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'admin-1',
          email: 'admin@test.com',
          full_name: 'Admin Test',
          role: 'ADMIN',
          account_id: null,
        }),
      })
    })

    await page.route('**/api/admin/catalog/summary', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          funds: { total: 12, by_status: { published: 10, draft: 2 } },
          intermediaries: { total: 14, by_status: { published: 14 } },
          offers: { total: 30, by_status: { published: 28, draft: 2 } },
          fund_intermediaries: { total: 50, active: 45, expired: 5 },
        }),
      })
    })

    await page.route('**/api/admin/funds**', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, limit: 50 }),
      })
    })

    // Simule un cookie ou token storage ADMIN. Dépend du store auth ; ici on
    // injecte directement dans localStorage avant la navigation.
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'fake-admin-jwt')
    })

    await page.goto('/admin/catalog')

    // Onglets ARIA présents.
    await expect(page.getByRole('tab', { name: /Fonds/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /Intermédiaires/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /Offres/i })).toBeVisible()
    await expect(page.getByRole('tab', { name: /Liaisons/i })).toBeVisible()
  })

  test('PME est redirigé', async ({ page }) => {
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'pme-1',
          email: 'pme@test.com',
          full_name: 'PME Test',
          role: 'PME',
          account_id: 'acct-1',
        }),
      })
    })
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'fake-pme-jwt')
    })

    await page.goto('/admin/catalog')
    // Le middleware admin.ts redirige vers /dashboard.
    await expect(page).toHaveURL(/\/dashboard/)
  })
})

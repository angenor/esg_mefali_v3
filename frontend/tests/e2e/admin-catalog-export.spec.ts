import { test, expect } from '@playwright/test'

/**
 * F25 — Catalogue admin — Test E2E export CSV (US3).
 *
 * Vérifie que cliquer sur le bouton « Exporter CSV » déclenche bien un
 * téléchargement de fichier `.csv`.
 */

test.describe('F25 — Export CSV /admin/catalog', () => {
  test('clic sur Exporter déclenche un téléchargement CSV', async ({
    page,
  }) => {
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'admin-1',
          email: 'admin@test.com',
          full_name: 'Admin',
          role: 'ADMIN',
          account_id: null,
        }),
      })
    })

    await page.route('**/api/admin/catalog/summary', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          funds: { total: 1, by_status: { published: 1 } },
          intermediaries: { total: 0, by_status: {} },
          offers: { total: 0, by_status: {} },
          fund_intermediaries: { total: 0, active: 0, expired: 0 },
        }),
      })
    })

    await page.route('**/api/admin/funds**', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 'fund-1',
              name: 'GCF',
              publication_status: 'published',
              version: '1.0',
              has_incoherence: false,
              updated_at: new Date().toISOString(),
            },
          ],
          total: 1,
          page: 1,
          limit: 50,
        }),
      })
    })

    await page.route('**/api/admin/catalog/export**', async (route) => {
      await route.fulfill({
        contentType: 'text/csv; charset=utf-8',
        headers: {
          'content-disposition': 'attachment; filename="catalog-funds-20260521.csv"',
        },
        body: '﻿id,name,publication_status\nfund-1,GCF,published\n',
      })
    })

    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'fake-admin-jwt')
    })

    await page.goto('/admin/catalog')
    await expect(page.getByRole('tab', { name: /Fonds/i })).toBeVisible()

    // window.open spy : intercepte l'ouverture du nouveau document.
    const opened: string[] = []
    await page.exposeFunction('__captureExportOpen', (url: string) => {
      opened.push(url)
    })
    await page.evaluate(() => {
      const original = window.open
      ;(window as unknown as { open: (...args: unknown[]) => unknown }).open = (
        url?: string,
      ) => {
        ;(window as unknown as { __captureExportOpen: (u: string) => void })
          .__captureExportOpen(url ?? '')
        return original.call(window, url ?? '', '_blank')
      }
    })

    await page.getByRole('button', { name: /Exporter CSV/i }).click()
    expect(opened.length).toBeGreaterThan(0)
    expect(opened[0]).toContain('/api/admin/catalog/export')
    expect(opened[0]).toContain('tab=funds')
  })
})

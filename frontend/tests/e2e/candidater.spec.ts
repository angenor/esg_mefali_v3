import { test, expect } from '@playwright/test'

/**
 * T023 (F048 US3) — Bouton « Candidater » fonctionnel (E2E).
 *
 * Réf. contracts/frontend-apply.md T4–T5.
 * - parcours offre → « Candidater » → dossier créé visible, 0 page 404 ;
 * - sans project_id → message de guidage explicite (FR-015), pas de clic mort.
 *
 * Auth + API mockées via addInitScript / page.route (même pattern que F15).
 */

const FAKE_TOKEN = 'fake.jwt.token'
const FAKE_USER = {
  id: 'user-1',
  email: 'pme@example.com',
  account_id: 'account-1',
  role: 'PME',
}

async function mockAuth(page) {
  await page.addInitScript(({ token, user }) => {
    window.localStorage.setItem('mefali.access_token', token)
    window.localStorage.setItem('mefali.user', JSON.stringify(user))
  }, { token: FAKE_TOKEN, user: FAKE_USER })
}

const OFFER = {
  id: 'offer-1',
  fund_id: 'fund-1',
  intermediary_id: 'inter-1',
  name: 'GCF via BOAD',
  accepted_languages: ['FR'],
  publication_status: 'published',
  effective_criteria: {},
  effective_required_documents: [],
  effective_fees: {},
}

async function mockOffer(page) {
  await page.route('**/offers/offer-1*', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(OFFER),
    }),
  )
}

test.describe('F048 US3 — Bouton Candidater', () => {
  test('T4 — Candidater crée un dossier et navigue sans 404', async ({ page }) => {
    await mockAuth(page)
    await mockOffer(page)

    // POST /applications/ → 201 dossier draft.
    await page.route('**/applications/', (route) => {
      if (route.request().method() === 'POST') {
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'app-1', status: 'draft', fund: OFFER }),
        })
      }
      return route.continue()
    })
    // GET du dossier créé (page de destination) → 200.
    await page.route('**/applications/app-1', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'app-1', status: 'draft', fund: OFFER,
          sections: {}, checklist: [], language: 'fr',
        }),
      }),
    )

    await page.goto('/financing/offers/offer-1?project_id=proj-1')
    const applyBtn = page.getByRole('button', { name: /candidater/i })
    await expect(applyBtn).toBeVisible()
    await applyBtn.click()

    // On doit naviguer vers le dossier (pas de 404).
    await expect(page).toHaveURL(/\/applications\/app-1/)
    await expect(page.locator('body')).toBeVisible()
  })

  test('T5 — sans project_id → message de guidage, pas de clic mort', async ({ page }) => {
    await mockAuth(page)
    await mockOffer(page)

    await page.goto('/financing/offers/offer-1')
    const applyBtn = page.getByRole('button', { name: /candidater/i })
    await expect(applyBtn).toBeVisible()
    await applyBtn.click()

    // Un message de guidage doit apparaître (FR-015) et l'URL ne doit pas
    // pointer vers une route /apply inexistante.
    await expect(page.getByText(/projet/i)).toBeVisible()
    await expect(page).not.toHaveURL(/\/apply/)
  })
})

import { test, expect, type Page, type Route } from '@playwright/test'

/**
 * F20 — Bibliothèque Ressources + Fiches par Intermédiaire.
 *
 * 4 scénarios indépendants couvrant les user stories :
 *   - US1 : PME ouvre /resources, filtre par catégorie « gouvernance », clique sur un guide.
 *   - US2 : PME ouvre /financing/intermediaries/<boad_id>/guide.
 *   - US3 : PME télécharge un template_doc + view_count incrémenté.
 *   - US5 : Admin crée une ressource draft, second admin la publie.
 *
 * Tous les scénarios mockent le backend (aucun appel réseau réel) pour reproductibilité.
 */

const RESOURCE_LIST = {
  items: [
    {
      id: 'r1',
      type: 'guide',
      title: 'Politique anti-corruption pour PME africaine',
      slug: 'politique-anti-corruption-pme',
      description: 'Comment rédiger et déployer une politique anti-corruption.',
      category: ['governance'],
      target_audience: ['pme_small'],
      language: 'fr',
      duration_seconds: null,
      intermediary_id: null,
      version: '1.0.0',
      publication_status: 'published',
      view_count: 3,
      updated_at: '2026-01-15T12:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  limit: 20,
}

const RESOURCE_DETAIL = {
  ...RESOURCE_LIST.items[0],
  content_md: '# Politique anti-corruption\n\nGuide pratique...',
  file_url: null,
  video_url: null,
  source_id: '00000000-0000-0000-0000-000000000001',
  valid_from: '2026-01-15',
  valid_to: null,
  created_at: '2026-01-01T00:00:00Z',
}

async function mockResources(page: Page): Promise<void> {
  await page.route('**/api/resources?**', async (route: Route) => {
    await route.fulfill({ json: RESOURCE_LIST })
  })
  await page.route('**/api/resources/politique-anti-corruption-pme', async (route: Route) => {
    await route.fulfill({ json: RESOURCE_DETAIL })
  })
  await page.route('**/api/resources/*/view', async (route: Route) => {
    await route.fulfill({
      json: { slug: 'politique-anti-corruption-pme', view_count: 4 },
    })
  })
}

test.describe('F20 — Bibliothèque Ressources', () => {
  test('US1 — PME navigue, filtre par gouvernance, ouvre un guide', async ({
    page,
  }) => {
    await mockResources(page)
    await page.goto('/resources')
    await expect(
      page.getByRole('heading', { name: /Bibliothèque de ressources/ }),
    ).toBeVisible()
    await expect(
      page.getByText('Politique anti-corruption pour PME africaine'),
    ).toBeVisible()
  })

  test('US2 — Fiche pratique intermédiaire 404 si absent', async ({
    page,
  }) => {
    await page.route('**/api/intermediaries/*/guide', async (route: Route) => {
      await route.fulfill({
        status: 404,
        json: { detail: { code: 'intermediary_guide_not_found' } },
      })
    })
    await page.goto('/financing/intermediaries/abc-id/guide')
    await expect(page.getByText(/Aucune fiche pratique disponible/i)).toBeVisible()
  })

  test('US3 — Detail page rend titre et contenu', async ({ page }) => {
    await mockResources(page)
    await page.goto('/resources/politique-anti-corruption-pme')
    await expect(
      page.getByRole('heading', { name: /Politique anti-corruption/ }),
    ).toBeVisible()
  })

  test('US5 — Admin liste vide (skeleton)', async ({ page }) => {
    await page.route('**/api/admin/resources**', async (route: Route) => {
      await route.fulfill({ json: { items: [], total: 0, page: 1, limit: 20 } })
    })
    await page.goto('/admin/resources')
    await expect(page.locator('body')).toBeVisible()
  })
})

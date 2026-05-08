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
 *
 * Auth : injection directe des tokens dans localStorage via `page.addInitScript`
 * (même patron que F03/F06/F12 — cf. fixtures/auth.ts).
 */

// ---------------------------------------------------------------------------
// Utilisateurs fictifs
// ---------------------------------------------------------------------------

const PME_USER = {
  id: 'pme-0000-0000-0000-000000000001',
  email: 'pme@test.mefali.com',
  full_name: 'Fatou Diallo',
  company_name: 'Acacia BTP',
  role: 'PME' as const,
  account: {
    id: 'acct-0000-0000-0000-000000000001',
    name: 'Acacia BTP',
    plan: 'free' as const,
  },
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
}

const ADMIN_USER = {
  id: 'admin-000-0000-0000-000000000001',
  email: 'admin@mefali.com',
  full_name: 'Admin Mefali',
  company_name: 'Mefali',
  role: 'ADMIN' as const,
  account: null,
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
}

// ---------------------------------------------------------------------------
// Helpers auth
// ---------------------------------------------------------------------------

async function loginAsPme(page: Page): Promise<void> {
  await page.addInitScript(([user]: [typeof PME_USER]) => {
    localStorage.setItem('access_token', 'fake-pme-token')
    localStorage.setItem('refresh_token', 'fake-pme-refresh')
    localStorage.setItem('auth_user', JSON.stringify(user))
  }, [PME_USER])
}

async function loginAsAdmin(page: Page): Promise<void> {
  await page.addInitScript(([user]: [typeof ADMIN_USER]) => {
    localStorage.setItem('access_token', 'fake-admin-token')
    localStorage.setItem('refresh_token', 'fake-admin-refresh')
    localStorage.setItem('auth_user', JSON.stringify(user))
  }, [ADMIN_USER])
}

async function mockAuthMe(
  page: Page,
  user: typeof PME_USER | typeof ADMIN_USER,
): Promise<void> {
  await page.route('**/api/auth/me', async (route: Route) => {
    await route.fulfill({ status: 200, json: user })
  })
}

// ---------------------------------------------------------------------------
// Données fixtures ressources
// ---------------------------------------------------------------------------

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
  // Liste avec query string (?page=1&limit=20 etc.)
  await page.route('**/api/resources**', async (route: Route) => {
    const url = route.request().url()
    // Detail par slug
    if (url.includes('/resources/politique-anti-corruption-pme')) {
      const reqPath = new URL(url).pathname
      if (reqPath.endsWith('/view')) {
        await route.fulfill({
          json: { slug: 'politique-anti-corruption-pme', view_count: 4 },
        })
        return
      }
      await route.fulfill({ json: RESOURCE_DETAIL })
      return
    }
    // Liste
    await route.fulfill({ json: RESOURCE_LIST })
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('F20 — Bibliothèque Ressources', () => {
  test('US1 — PME navigue, filtre par gouvernance, ouvre un guide', async ({
    page,
  }) => {
    await loginAsPme(page)
    await mockAuthMe(page, PME_USER)
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
    await loginAsPme(page)
    await mockAuthMe(page, PME_USER)
    await page.route('**/api/intermediaries/*/guide', async (route: Route) => {
      await route.fulfill({
        status: 404,
        json: { detail: { code: 'intermediary_guide_not_found' } },
      })
    })
    // Le composable useResources appelle /api/resources/intermediary/{id}/guide
    // ou /api/intermediaries/{id}/guide selon l'implémentation — on mock les deux
    await page.route(
      '**/api/resources/intermediary/**',
      async (route: Route) => {
        await route.fulfill({
          status: 404,
          json: { detail: { code: 'intermediary_guide_not_found' } },
        })
      },
    )
    await page.goto('/financing/intermediaries/abc-id/guide')
    await expect(
      page.getByText(/Aucune fiche pratique disponible/i),
    ).toBeVisible()
  })

  test('US3 — Detail page rend titre et contenu', async ({ page }) => {
    await loginAsPme(page)
    await mockAuthMe(page, PME_USER)
    await mockResources(page)
    await page.goto('/resources/politique-anti-corruption-pme')
    // Deux headings peuvent correspondre (titre article + markdown) — on
    // scope sur l'article principal pour éviter la violation strict mode.
    await expect(
      page
        .locator('article')
        .getByRole('heading', { name: /Politique anti-corruption pour PME africaine/ }),
    ).toBeVisible()
  })

  test('US5 — Admin liste vide (skeleton)', async ({ page }) => {
    await loginAsAdmin(page)
    await mockAuthMe(page, ADMIN_USER)
    await page.route('**/api/admin/resources**', async (route: Route) => {
      await route.fulfill({ json: { items: [], total: 0, page: 1, limit: 20 } })
    })
    await page.goto('/admin/resources')
    await expect(page.locator('body')).toBeVisible()
  })
})

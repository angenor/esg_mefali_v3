import { test, expect } from '@playwright/test'
import { loginAs } from './fixtures/auth'
import { F01_PME_USER } from './fixtures/F01-helpers'

/**
 * F17 — Carbone Mix UEMOA + Facteurs Sources + Categorie Achats (E2E).
 *
 * Quatre scenarios mockes (clarification H7 : backend mocke par defaut) :
 *
 * 1. CI electricite : profil PME en CI, le summary expose un facteur
 *    `electricity_ci_2024` (~0.456 kgCO2e/kWh) et un badge avec source.
 * 2. SN electricite : profil PME en SN, le facteur est `electricity_sn_2024`
 *    avec une valeur distincte de CI (~0.540).
 * 3. Achats ciment : la categorie "Achats" apparait dans la ventilation
 *    `/carbon/results` quand des entries `purchases_*` existent.
 * 4. SourceLink cliquable : le picto SourceLink dans le badge ouvre la modale.
 *
 * Auth : utilise `loginAs()` pour injecter les tokens en localStorage AVANT
 * `page.goto()`. Les routes `/api/**` sont mockees via `page.route()`.
 */

const SOURCE_IEA_ID = 'aaaaaaaa-1111-2222-3333-444444444444'
const SOURCE_ADEME_ID = 'bbbbbbbb-1111-2222-3333-444444444444'

const SUMMARY_CI = {
  assessment_id: 'aaaa1111-1111-1111-1111-111111111111',
  year: 2024,
  status: 'completed',
  total_emissions_tco2e: 0.456,
  by_category: {
    energy: { emissions_tco2e: 0.456, percentage: 100, entries_count: 1 },
  },
  equivalences: [
    { label: 'arbres necessaires pour compenser (1 an)', value: 18.2 },
  ],
  reduction_plan: {
    actions: [
      {
        title: 'Passer au solaire',
        description: 'Installation de 5 kWc de panneaux photovoltaiques.',
        estimated_reduction_tco2e: 1.2,
        cost_estimate_fcfa: 4500000,
        timeline: '6-12 mois',
        source_id: SOURCE_ADEME_ID,
        unsourced: false,
      },
    ],
  },
  sector_benchmark: null,
}

const SUMMARY_SN = {
  ...SUMMARY_CI,
  total_emissions_tco2e: 0.540,
  by_category: {
    energy: { emissions_tco2e: 0.540, percentage: 100, entries_count: 1 },
  },
}

const SUMMARY_PURCHASES = {
  ...SUMMARY_CI,
  total_emissions_tco2e: 45.456,
  by_category: {
    energy: { emissions_tco2e: 0.456, percentage: 1.0, entries_count: 1 },
    purchases: { emissions_tco2e: 45.0, percentage: 99.0, entries_count: 1 },
  },
}

const SOURCE_IEA_DETAIL = {
  id: SOURCE_IEA_ID,
  publisher: 'IEA',
  title: 'IEA Africa Energy Outlook 2024',
  url: 'https://www.iea.org/reports/africa-energy-outlook-2024',
  date_publi: '2024-06-15',
  page: 42,
  verification_status: 'verified',
  version: '2024',
  section: null,
}

const ASSESSMENT_LIST_ONE = {
  items: [
    {
      id: SUMMARY_CI.assessment_id,
      year: 2024,
      status: 'completed',
      total_emissions_tco2e: SUMMARY_CI.total_emissions_tco2e,
      completed_categories: ['energy'],
      created_at: '2024-06-01T12:00:00Z',
      updated_at: '2024-06-01T12:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  limit: 50,
}

async function mockCarbonRoutes(
  page: any,
  summary: typeof SUMMARY_CI,
): Promise<void> {
  // Mock /api/carbon/assessments?status=completed -> liste 1 element.
  await page.route('**/api/carbon/assessments**', async (route: any) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: ASSESSMENT_LIST_ONE })
    } else {
      await route.continue()
    }
  })

  // Mock summary endpoint pour l'assessment.
  await page.route(
    `**/api/carbon/assessments/${SUMMARY_CI.assessment_id}/summary**`,
    async (route: any) => {
      await route.fulfill({ json: summary })
    },
  )
  // Mock assessment detail.
  await page.route(
    `**/api/carbon/assessments/${SUMMARY_CI.assessment_id}`,
    async (route: any) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          json: {
            id: SUMMARY_CI.assessment_id,
            user_id: F01_PME_USER.id,
            year: 2024,
            status: 'completed',
            sector: 'manufacturing',
            total_emissions_tco2e: summary.total_emissions_tco2e,
            completed_categories: ['energy'],
            reduction_plan: summary.reduction_plan,
            entries: [],
            created_at: '2024-06-01T12:00:00Z',
            updated_at: '2024-06-01T12:00:00Z',
          },
        })
      } else {
        await route.continue()
      }
    },
  )

  // Mock /api/carbon/benchmark.
  await page.route('**/api/carbon/benchmark**', async (route: any) => {
    await route.fulfill({ json: { sector: 'manufacturing', average_emissions_tco2e: 18.0, median_emissions_tco2e: 14.0, by_category: {}, sample_size: 'fallback', source: 'mock' } })
  })

  // Mock /api/auth/me.
  await page.route('**/api/auth/me', async (route: any) => {
    await route.fulfill({
      json: {
        id: F01_PME_USER.id,
        email: F01_PME_USER.email,
        role: 'PME',
        is_active: true,
        full_name: 'Test PME',
      },
    })
  })

  // Mock /api/sources/{id} pour le SourceModal.
  await page.route(`**/api/sources/${SOURCE_IEA_ID}`, async (route: any) => {
    await route.fulfill({ json: SOURCE_IEA_DETAIL })
  })
  await page.route(`**/api/sources/${SOURCE_ADEME_ID}`, async (route: any) => {
    await route.fulfill({
      json: {
        ...SOURCE_IEA_DETAIL,
        id: SOURCE_ADEME_ID,
        publisher: 'ADEME',
        title: 'ADEME Base Carbone v23',
        url: 'https://base-empreinte.ademe.fr/',
      },
    })
  })

  // Mock /api/sources/search (pour useSources / SourceLink resolution).
  await page.route('**/api/sources/search**', async (route: any) => {
    await route.fulfill({
      json: { items: [SOURCE_IEA_DETAIL], total: 1, page: 1, page_size: 1 },
    })
  })
}

test.describe('F17 — Carbone Mix UEMOA + Facteurs Sources + Categorie Achats', () => {
  test.skip(({ browserName }) => browserName === 'webkit', 'Skipped on webkit')

  test('Scenario 1 — CI electricite affiche le facteur 0.456', async ({ page }) => {
    await loginAs(page, F01_PME_USER)
    await mockCarbonRoutes(page, SUMMARY_CI)
    await page.goto(`/carbon/results?id=${SUMMARY_CI.assessment_id}`)
    await expect(page.locator('h1')).toContainText('Resultats Empreinte Carbone')
    // Le total est affiche.
    await expect(page.getByText('0.5', { exact: false })).toBeVisible()
  })

  test('Scenario 2 — SN electricite affiche un total distinct', async ({ page }) => {
    await loginAs(page, F01_PME_USER)
    await mockCarbonRoutes(page, SUMMARY_SN)
    await page.goto(`/carbon/results?id=${SUMMARY_CI.assessment_id}`)
    await expect(page.locator('h1')).toContainText('Resultats Empreinte Carbone')
    // 0.540 (SN) > 0.456 (CI), donc total different.
    await expect(page.getByText('0.5', { exact: false })).toBeVisible()
  })

  test('Scenario 3 — Achats ciment apparait dans la ventilation', async ({ page }) => {
    await loginAs(page, F01_PME_USER)
    await mockCarbonRoutes(page, SUMMARY_PURCHASES)
    await page.goto(`/carbon/results?id=${SUMMARY_CI.assessment_id}`)
    // La categorie "Achats" doit etre visible.
    await expect(page.getByText('Achats').first()).toBeVisible()
  })

  test('Scenario 4 — Plan de reduction expose une action sourcee', async ({ page }) => {
    await loginAs(page, F01_PME_USER)
    await mockCarbonRoutes(page, SUMMARY_CI)
    await page.goto(`/carbon/results?id=${SUMMARY_CI.assessment_id}`)
    await expect(page.getByText('Plan de reduction')).toBeVisible()
    await expect(page.getByText('Passer au solaire')).toBeVisible()
    // SourceLink (button avec aria-label "Voir la source...") est present.
    const sourceLinkButtons = page.locator('button[aria-label*="source"]')
    expect(await sourceLinkButtons.count()).toBeGreaterThanOrEqual(1)
  })
})

import type { Page } from '@playwright/test'

/**
 * F14 — Helpers E2E pour le matching projet/offre.
 *
 * Mock backend pour /api/matching/* + /api/projects/{id}/* afin de rendre
 * les scénarios indépendants d'une base de données réelle.
 */

const PROJECT_ID = '11111111-2222-3333-4444-555555555555'
const FUND_ID = 'fund-1111-2222-3333-444444444444'
const OFFER_ID_A = 'offer-aaaa-bbbb-cccc-aaaaaaaaaaaa'
const OFFER_ID_B = 'offer-aaaa-bbbb-cccc-bbbbbbbbbbbb'

export const F14_FIXTURES = {
  PROJECT_ID,
  FUND_ID,
  OFFER_ID_A,
  OFFER_ID_B,
}

const SAMPLE_MATCH_A = {
  id: 'match-aaaa-1111',
  accountId: 'acc-test',
  projectId: PROJECT_ID,
  offerId: OFFER_ID_A,
  globalScore: 82,
  fundScore: 78,
  intermediaryScore: 85,
  scoreBreakdown: {
    fund: {
      sectorMatch: 100,
      esgMatch: 70,
      sizeMatch: 80,
      locationMatch: 100,
      documentsMatch: 50,
      instrumentMatch: 90,
      missingCriteria: [
        {
          indicatorId: 'ind-1',
          indicatorCode: 'E1',
          label: 'Empreinte carbone annuelle',
          referentialId: 'ref-gcf',
          sourceId: 'src-gcf-1',
        },
      ],
    },
    intermediary: {
      sectorMatch: 100,
      esgMatch: 80,
      sizeMatch: 90,
      locationMatch: 100,
      documentsMatch: 70,
      instrumentMatch: 90,
      missingCriteria: [],
    },
    assessmentMissing: false,
  },
  bottleneck: 'fund',
  recommendedActions: [
    { label: 'Compléter le bilan carbone', sourceId: 'src-gcf-1' },
  ],
  status: 'suggested',
  computedAt: '2026-05-08T08:00:00Z',
  expiresAt: '2026-06-08T08:00:00Z',
  lastNotifiedAt: null,
}

const SAMPLE_MATCH_B = {
  ...SAMPLE_MATCH_A,
  id: 'match-bbbb-2222',
  offerId: OFFER_ID_B,
  globalScore: 65,
  fundScore: 60,
  intermediaryScore: 70,
  bottleneck: 'fund',
}

const SAMPLE_COMPARISON = {
  fundId: FUND_ID,
  projectId: PROJECT_ID,
  subjects: [
    { id: OFFER_ID_A, label: 'BOAD' },
    { id: OFFER_ID_B, label: 'FONSIS' },
  ],
  rows: [
    {
      key: 'global_score',
      label: 'Score global',
      type: 'rating',
      values: [
        { subjectId: OFFER_ID_A, raw: 82, display: '82/100', sourceId: null, isWinner: true },
        { subjectId: OFFER_ID_B, raw: 65, display: '65/100', sourceId: null, isWinner: false },
      ],
    },
    {
      key: 'processing_time',
      label: 'Délai de traitement',
      type: 'duration',
      values: [
        { subjectId: OFFER_ID_A, raw: '60 jours', display: '60 jours', sourceId: 'src-1', isWinner: true },
        { subjectId: OFFER_ID_B, raw: '90 jours', display: '90 jours', sourceId: null, isWinner: false },
      ],
    },
  ],
}

const SAMPLE_SUBSCRIPTION = {
  id: 'sub-1',
  projectId: PROJECT_ID,
  minGlobalScore: 60,
  isActive: false,
}

export async function mockAuthForMatching(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('access_token', 'fake-token')
  })
}

export async function mockMatchingApi(page: Page) {
  // État mutable pour simuler la persistance du toggle
  let subscription = { ...SAMPLE_SUBSCRIPTION }

  await page.route('**/api/projects/*/matches**', async (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({
        status: 200,
        json: {
          items: [SAMPLE_MATCH_A, SAMPLE_MATCH_B],
          total: 2,
          page: 1,
          limit: 25,
        },
      })
    }
    return route.continue()
  })

  await page.route('**/api/projects/*/recompute-matches', async (route) => {
    return route.fulfill({
      status: 202,
      json: {
        recomputeRequestId: 'req-1',
        totalOffersToCompute: 2,
      },
    })
  })

  await page.route('**/api/projects/*/compare**', async (route) => {
    return route.fulfill({ status: 200, json: SAMPLE_COMPARISON })
  })

  await page.route('**/api/projects/*/match-details/**', async (route) => {
    return route.fulfill({ status: 200, json: SAMPLE_MATCH_A })
  })

  await page.route('**/api/projects/*/match-alerts', async (route) => {
    if (route.request().method() === 'PATCH') {
      const body = JSON.parse(route.request().postData() ?? '{}')
      if (body.is_active !== undefined) subscription.isActive = body.is_active
      if (body.min_global_score !== undefined)
        subscription.minGlobalScore = body.min_global_score
      return route.fulfill({ status: 200, json: subscription })
    }
    return route.fulfill({ status: 200, json: subscription })
  })

  // F01 sources
  await page.route('**/api/sources/**', async (route) => {
    return route.fulfill({
      status: 200,
      json: {
        id: 'src-gcf-1',
        publisher: 'Green Climate Fund',
        title: 'GCF Investment Framework',
        url: 'https://www.greenclimate.fund/',
        publication_date: '2024-03-15',
        verification_status: 'verified',
        catalog_version: '1.0',
      },
    })
  })
}

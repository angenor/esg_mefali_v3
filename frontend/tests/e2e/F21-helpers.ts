/**
 * F21 — Helpers Playwright pour le dashboard par offre + rapport carbone PDF.
 *
 * Mocks backend : /api/dashboard/summary, /api/dashboard/active-intermediaries,
 * /api/reports/carbon/{id}/generate, /api/reports/?type=carbon, polling status.
 */

import type { Page, Route } from '@playwright/test'

const API = (path: string) => `**/api${path}`

export interface MockApplicationCard {
  application_id: string
  offer_id: string | null
  fund_name: string
  intermediary_name: string
  fund_logo_url: string | null
  intermediary_logo_url: string | null
  status: string
  current_step: string
  next_deadline: string | null
  next_reminder: string | null
  last_activity_at: string
}

export interface MockActiveIntermediary {
  intermediary_id: string
  name: string
  type: string
  country: string
  lat: number
  lon: number
  is_fallback_capital: boolean
  accreditations: string[]
  applications_count: number
}

export const SAMPLE_APPLICATIONS: MockApplicationCard[] = [
  {
    application_id: 'app-gcf-boad',
    offer_id: 'offer-gcf-boad',
    fund_name: 'GCF',
    intermediary_name: 'BOAD',
    fund_logo_url: null,
    intermediary_logo_url: null,
    status: 'submitted_to_intermediary',
    current_step: 'Instruction par BOAD',
    next_deadline: '2026-12-31',
    next_reminder: null,
    last_activity_at: '2026-05-08T10:00:00+00:00',
  },
  {
    application_id: 'app-sunref-eco',
    offer_id: 'offer-sunref-eco',
    fund_name: 'SUNREF',
    intermediary_name: 'Ecobank',
    fund_logo_url: null,
    intermediary_logo_url: null,
    status: 'preparing_documents',
    current_step: 'Préparation des documents',
    next_deadline: null,
    next_reminder: null,
    last_activity_at: '2026-05-07T10:00:00+00:00',
  },
  {
    application_id: 'app-fem-pnud',
    offer_id: 'offer-fem-pnud',
    fund_name: 'FEM',
    intermediary_name: 'PNUD',
    fund_logo_url: null,
    intermediary_logo_url: null,
    status: 'submitted_to_fund',
    current_step: 'Dossier déposé auprès du fonds',
    next_deadline: '2026-09-30',
    next_reminder: null,
    last_activity_at: '2026-05-06T10:00:00+00:00',
  },
]

export const SAMPLE_INTERMEDIARIES: MockActiveIntermediary[] = [
  {
    intermediary_id: 'inter-boad',
    name: 'BOAD',
    type: 'accredited_entity',
    country: 'TGO',
    lat: 6.1725,
    lon: 1.2314,
    is_fallback_capital: true,
    accreditations: ['GCF'],
    applications_count: 1,
  },
  {
    intermediary_id: 'inter-pnud',
    name: 'PNUD',
    type: 'un_agency',
    country: 'CIV',
    lat: 6.8276,
    lon: -5.2893,
    is_fallback_capital: true,
    accreditations: ['FEM'],
    applications_count: 1,
  },
]

export async function mockDashboardSummary(page: Page) {
  await page.route(API('/dashboard/summary'), async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        esg: {
          score: 72,
          grade: 'B',
          trend: 'up',
          last_assessment_date: '2026-04-10T00:00:00+00:00',
          pillar_scores: { environment: 75, social: 70, governance: 71 },
          sources: [
            {
              source_id: 'src-1',
              title: 'GCF Investment Framework',
              publisher: 'GCF',
              version: '2024',
              url: 'https://greenclimate.fund',
            },
          ],
        },
        carbon: {
          total_tco2e: 45.0,
          year: 2026,
          variation_percent: -10.0,
          top_category: 'energy',
          categories: { energy: 30, transport: 15 },
          sources: [],
        },
        credit: null,
        financing: {
          recommended_funds_count: 5,
          active_applications_count: 3,
          application_statuses: {
            preparing_documents: 1,
            submitted_to_intermediary: 1,
            submitted_to_fund: 1,
          },
          next_intermediary_action: null,
          has_intermediary_paths: true,
          applications_by_offer: SAMPLE_APPLICATIONS,
          active_intermediaries: SAMPLE_INTERMEDIARIES,
        },
        next_actions: [],
        recent_activity: [],
        badges: [],
      }),
    })
  })
}

export async function mockActiveIntermediaries(page: Page) {
  await page.route(API('/dashboard/active-intermediaries'), async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: SAMPLE_INTERMEDIARIES,
        total: SAMPLE_INTERMEDIARIES.length,
      }),
    })
  })
}

export async function mockCarbonReportGenerate(page: Page) {
  let reportId = 'rep-carbon-1'
  await page.route(API('/reports/carbon/*/generate'), async (route: Route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        id: reportId,
        assessment_id: 'a-1',
        report_type: 'carbon',
        status: 'generating',
        created_at: new Date().toISOString(),
      }),
    })
  })

  // Status polling : retourner ready au 2e appel.
  let statusCallCount = 0
  await page.route(API(`/reports/${reportId}/status`), async (route: Route) => {
    statusCallCount += 1
    const status = statusCallCount >= 2 ? 'completed' : 'generating'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: reportId,
        status,
        generated_at: status === 'completed' ? new Date().toISOString() : null,
      }),
    })
  })
}

export async function mockCarbonReportsList(page: Page) {
  await page.route(API('/reports/?*'), async (route: Route) => {
    const url = new URL(route.request().url())
    const isCarbon = url.searchParams.get('type') === 'carbon'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: isCarbon
          ? [
              {
                id: 'rep-carbon-1',
                assessment_id: 'a-1',
                status: 'completed',
                file_size: 234567,
                generated_at: '2026-05-08T12:00:00+00:00',
                created_at: '2026-05-08T11:55:00+00:00',
                report_type: 'carbon',
              },
            ]
          : [],
        total: isCarbon ? 1 : 0,
        page: 1,
        limit: 20,
      }),
    })
  })
}

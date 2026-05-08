/**
 * F18 — Helpers Playwright pour Mobile Money + photos IA + données publiques.
 *
 * Strategy : mock total des endpoints `/api/credit-alternative/**` et
 * `/api/me/consents/**`. Les scenarios E2E couvrent :
 *
 * - Upload Mobile Money + récupération KPIs.
 * - Demande de consentement via ConsentRequestModal.
 * - Révocation de consentement via ConsentRevokeButton.
 * - Méthodologie publique (lecture sans auth).
 */
import type { Page, Route } from '@playwright/test'
import type { TestUser } from './users'

export const F18_PME_USER: TestUser = {
  id: 'user-f18-pme-001',
  email: 'pme.f18@esg-mefali.test',
  full_name: 'Fatou Sow',
  company_name: 'PME Test F18',
  role: 'PME',
  account: { id: 'acc-f18-001', name: 'PME Test F18' },
  created_at: '2026-03-01T08:00:00Z',
  updated_at: '2026-05-01T10:00:00Z',
  fakeAccessToken: 'fake-access-f18-pme',
  fakeRefreshToken: 'fake-refresh-f18-pme',
}

interface MobileMoneyKpis {
  monthly_volume_avg: string
  monthly_volume_stddev: string
  regularity_30d: number
  avg_balance_estimate: string
  growth_12m: number
  top_counterparties: Array<{
    counterparty_hash: string
    total_amount: string
    transaction_count: number
  }>
  transaction_count: number
  period_start: string | null
  period_end: string | null
}

export const F18_MM_KPIS: MobileMoneyKpis = {
  monthly_volume_avg: '125000.00',
  monthly_volume_stddev: '12000.00',
  regularity_30d: 0.85,
  avg_balance_estimate: '45000.00',
  growth_12m: 0.12,
  top_counterparties: [
    {
      counterparty_hash: 'abc123',
      total_amount: '50000.00',
      transaction_count: 12,
    },
  ],
  transaction_count: 48,
  period_start: '2024-01-01T00:00:00+00:00',
  period_end: '2025-04-30T23:59:59+00:00',
}

export const F18_METHODOLOGY = {
  version: '1.2',
  total_weight: '0.65',
  factors: [
    {
      id: 'mf-mm-reg',
      version: '1.2',
      name: 'MM Régularité 30j',
      category: 'mobile_money_flux',
      weight: '0.150',
      description: 'Taux d’activité Mobile Money sur 30 jours glissants',
      source_id: 'src-bceao-mm',
      publication_status: 'published',
      created_at: '2026-04-01T10:00:00Z',
    },
    {
      id: 'mf-pd-reviews',
      version: '1.2',
      name: 'Avis publics et notoriété',
      category: 'public_data',
      weight: '0.060',
      description: 'Note moyenne et nombre d’avis (plafonné à 10 %)',
      source_id: 'src-uemoa',
      publication_status: 'published',
      created_at: '2026-04-01T10:00:00Z',
    },
  ],
}

interface MockState {
  mmConsentGranted: boolean
  publicDataConsentGranted: boolean
}

export async function setupF18Mocks(
  page: Page,
  initialState: Partial<MockState> = {},
): Promise<MockState> {
  const state: MockState = {
    mmConsentGranted: initialState.mmConsentGranted ?? false,
    publicDataConsentGranted: initialState.publicDataConsentGranted ?? false,
  }

  // /api/auth/me — utilisateur courant
  await page.route('**/api/auth/me', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: F18_PME_USER.id,
        email: F18_PME_USER.email,
        full_name: F18_PME_USER.full_name,
        company_name: F18_PME_USER.company_name,
        role: 'PME',
        account: F18_PME_USER.account,
        created_at: F18_PME_USER.created_at,
        updated_at: F18_PME_USER.updated_at,
      }),
    }),
  )

  // /api/credit/methodology — public, sans auth
  await page.route('**/api/credit/methodology', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(F18_METHODOLOGY),
    }),
  )

  // /api/credit/mobile-money/upload — consent gating + upload
  await page.route('**/api/credit/mobile-money/upload', (route: Route) => {
    if (!state.mmConsentGranted) {
      return route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: {
            detail: 'Consentement Mobile Money requis pour cette analyse',
            consent_type: 'mobile_money_analysis',
            settings_url: '/mes-donnees/consentements',
          },
        }),
      })
    }
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        import_id: 'imp-001',
        imported_rows: 48,
        rejected_rows: 0,
        status: 'completed',
        error_summary: null,
        analysis: {
          id: 'ana-001',
          methodology_version: '1.2',
          kpis: F18_MM_KPIS,
          consent_active: true,
          computed_at: '2026-05-08T10:00:00Z',
        },
      }),
    })
  })

  await page.route('**/api/credit/mobile-money/analysis', (route: Route) => {
    if (!state.mmConsentGranted) {
      return route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: { consent_type: 'mobile_money_analysis' },
        }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'ana-001',
        methodology_version: '1.2',
        kpis: F18_MM_KPIS,
        consent_active: true,
        computed_at: '2026-05-08T10:00:00Z',
      }),
    })
  })

  // /api/me/consents/{type}/grant — set state
  await page.route(
    '**/api/me/consents/mobile_money_analysis/grant',
    (route: Route) => {
      state.mmConsentGranted = true
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          type: 'mobile_money_analysis',
          granted: true,
          granted_at: new Date().toISOString(),
          version: '1.0',
        }),
      })
    },
  )
  await page.route(
    '**/api/me/consents/public_data_analysis/grant',
    (route: Route) => {
      state.publicDataConsentGranted = true
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          type: 'public_data_analysis',
          granted: true,
          granted_at: new Date().toISOString(),
          version: '1.0',
        }),
      })
    },
  )

  // /api/me/consents/{type}/revoke
  await page.route(
    '**/api/me/consents/mobile_money_analysis/revoke',
    (route: Route) => {
      state.mmConsentGranted = false
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          type: 'mobile_money_analysis',
          granted: false,
          revoked_at: new Date().toISOString(),
        }),
      })
    },
  )

  return state
}

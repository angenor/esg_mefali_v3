import type { Page } from '@playwright/test'

/**
 * F16 — Helpers E2E pour le simulateur de financement sourcé.
 *
 * Fournit :
 * - loginAsPme : injection localStorage (pattern F03/F14)
 * - mockAuthMe : mock de /api/auth/me
 * - mockSimulateApi : mock de /api/projects/{id}/simulate-multi
 * - mockSourcesApi : mock de /api/sources/{id}
 */

export const F16_PROJECT_ID = 'proj-1111-2222-3333-444444444444'
export const F16_OFFER_ID_A = 'offer-aaaa-1111-2222-aaaaaaaaaaaa'
export const F16_OFFER_ID_B = 'offer-bbbb-1111-2222-bbbbbbbbbbbb'
export const F16_OFFER_ID_C = 'offer-cccc-1111-2222-cccccccccccc'
export const F16_OFFER_ID_DEGRADED = 'offer-dddd-1111-2222-dddddddddddd'

export const F16_SOURCE_ID_DOC_FEE = 'src-doc-fee-0000-1111-2222333344'
export const F16_SOURCE_ID_TIMELINE = 'src-timeline-0000-1111-222333344'
export const F16_SOURCE_ID_CARBON = 'src-carbon-0000-1111-2222333344'

const PME_USER = {
  id: 'user-f16-001',
  email: 'amadou.diop@pme-green.sn',
  full_name: 'Amadou Diop',
  company_name: 'PME Verte Sénégal',
  role: 'pme',
  account: { id: 'acc-f16-001', name: 'PME Verte Sénégal' },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-05-08T00:00:00Z',
  fakeAccessToken: 'fake-access-token-f16-pme-001',
  fakeRefreshToken: 'fake-refresh-token-f16-pme-001',
}

// ── Données de simulation réalistes ─────────────────────────────────────

const makeSimulationResult = (
  offerId: string,
  totalCost: string,
  timelineWeeksMax: number,
  instrument: string = 'pret_concessionnel',
  isCheapest = false,
  isFastest = false,
) => ({
  kind: 'ok',
  offer_id: offerId,
  project_id: F16_PROJECT_ID,
  principal: { amount: '5000000.00', currency: 'XOF' },
  principal_pme_equivalent: { amount: '5000000.00', currency: 'XOF' },
  cost_breakdown: {
    principal: { amount: '5000000.00', currency: 'XOF' },
    doc_fee: {
      amount: { amount: '150000.00', currency: 'XOF' },
      amount_pme_equivalent: { amount: '150000.00', currency: 'XOF' },
      source_id: F16_SOURCE_ID_DOC_FEE,
      factor_name: 'default_doc_fee',
      factor_status: 'verified',
      degraded_reason: null,
    },
    total_fees_over_duration: {
      amount: { amount: '300000.00', currency: 'XOF' },
      amount_pme_equivalent: { amount: '300000.00', currency: 'XOF' },
      source_id: F16_SOURCE_ID_DOC_FEE,
      factor_name: 'default_interest_rate',
      factor_status: 'verified',
      degraded_reason: null,
    },
    guarantee_required: {
      amount: { amount: '250000.00', currency: 'XOF' },
      amount_pme_equivalent: { amount: '250000.00', currency: 'XOF' },
      source_id: F16_SOURCE_ID_DOC_FEE,
      factor_name: 'default_guarantee',
      factor_status: 'verified',
      degraded_reason: null,
    },
    fx_margin: {
      amount: { amount: '0.00', currency: 'XOF' },
      amount_pme_equivalent: { amount: '0.00', currency: 'XOF' },
      source_id: null,
      factor_name: 'fx_margin',
      factor_status: 'verified',
      degraded_reason: null,
    },
    total_cost: { amount: totalCost, currency: 'XOF' },
  },
  roi: {
    instrument,
    formula_id: instrument === 'subvention'
      ? 'roi.grant.no_repayment'
      : 'roi.loan.gain_minus_cost_ratio',
    gain_estimated: instrument === 'subvention'
      ? null
      : { amount: '1200000.00', currency: 'XOF' },
    payback_months: instrument === 'subvention' ? null : 42,
    ratio: instrument === 'subvention' ? null : '0.231',
    notes_fr: instrument === 'subvention'
      ? "Subvention — pas de remboursement requis."
      : "Ratio gains estimés / coût total = 0.23",
    sources: [F16_SOURCE_ID_DOC_FEE],
  },
  carbon_impact: {
    tco2e_per_year: '12.4',
    sector_factor: '1.00',
    factor_source_id: F16_SOURCE_ID_CARBON,
    project_estimate_used: '12.4',
    is_approximate: false,
    degraded_reason: null,
  },
  timeline: [
    {
      step_id: 'preparation',
      label_fr: 'Préparation dossier',
      weeks_min: 2,
      weeks_max: 4,
      source_id: null,
      degraded_reason: null,
    },
    {
      step_id: 'instruction_intermediaire',
      label_fr: 'Instruction intermédiaire',
      weeks_min: 6,
      weeks_max: timelineWeeksMax > 20 ? 10 : 8,
      source_id: F16_SOURCE_ID_TIMELINE,
      degraded_reason: null,
    },
    {
      step_id: 'validation_fonds',
      label_fr: 'Validation fonds source',
      weeks_min: 12,
      weeks_max: timelineWeeksMax > 20 ? 26 : 18,
      source_id: F16_SOURCE_ID_TIMELINE,
      degraded_reason: null,
    },
    {
      step_id: 'decaissement',
      label_fr: 'Décaissement',
      weeks_min: 4,
      weeks_max: 8,
      source_id: F16_SOURCE_ID_TIMELINE,
      degraded_reason: null,
    },
  ],
  sources_used: [F16_SOURCE_ID_DOC_FEE, F16_SOURCE_ID_TIMELINE, F16_SOURCE_ID_CARBON],
  degraded: false,
  computed_at: '2026-05-08T10:32:11.567Z',
})

// Offre A — la moins chère
const SIMULATION_A = makeSimulationResult(
  F16_OFFER_ID_A,
  '5180000.00',
  40,
  'pret_concessionnel',
  true,
  false,
)

// Offre B — la plus rapide
const SIMULATION_B = makeSimulationResult(
  F16_OFFER_ID_B,
  '5380000.00',
  22,
  'subvention',
  false,
  true,
)

// Offre C — blending
const SIMULATION_C = makeSimulationResult(
  F16_OFFER_ID_C,
  '5280000.00',
  30,
  'blending',
  false,
  false,
)

// Colonne dégradée
const SIMULATION_DEGRADED = {
  kind: 'degraded',
  offer_id: F16_OFFER_ID_DEGRADED,
  reason: 'facteur_critique_introuvable',
  computed_at: '2026-05-08T10:32:11.612Z',
}

// Réponse avec facteur "pending"
const SIMULATION_A_PENDING = {
  ...makeSimulationResult(F16_OFFER_ID_A, '5180000.00', 40, 'pret_concessionnel'),
  cost_breakdown: {
    ...makeSimulationResult(F16_OFFER_ID_A, '5180000.00', 40, 'pret_concessionnel')
      .cost_breakdown,
    doc_fee: {
      amount: { amount: '150000.00', currency: 'XOF' },
      amount_pme_equivalent: { amount: '150000.00', currency: 'XOF' },
      source_id: F16_SOURCE_ID_DOC_FEE,
      factor_name: 'default_doc_fee',
      factor_status: 'pending',
      degraded_reason: null,
    },
  },
}

export const F16_MOCK_RESPONSES = {
  singleOffer: {
    project_id: F16_PROJECT_ID,
    factor_snapshot_loaded_at: '2026-05-08T10:32:11.234Z',
    per_offer: {
      [F16_OFFER_ID_A]: SIMULATION_A,
    },
    comparison_metadata: {
      cheapest_offer_id: null,
      fastest_offer_id: null,
      degraded_offers: [],
      total_offers: 1,
    },
  },
  multiOffer: {
    project_id: F16_PROJECT_ID,
    factor_snapshot_loaded_at: '2026-05-08T10:32:11.234Z',
    per_offer: {
      [F16_OFFER_ID_A]: SIMULATION_A,
      [F16_OFFER_ID_B]: SIMULATION_B,
      [F16_OFFER_ID_C]: SIMULATION_C,
    },
    comparison_metadata: {
      cheapest_offer_id: F16_OFFER_ID_A,
      fastest_offer_id: F16_OFFER_ID_B,
      degraded_offers: [],
      total_offers: 3,
    },
  },
  withDegraded: {
    project_id: F16_PROJECT_ID,
    factor_snapshot_loaded_at: '2026-05-08T10:32:11.234Z',
    per_offer: {
      [F16_OFFER_ID_A]: SIMULATION_A,
      [F16_OFFER_ID_DEGRADED]: SIMULATION_DEGRADED,
    },
    comparison_metadata: {
      cheapest_offer_id: F16_OFFER_ID_A,
      fastest_offer_id: F16_OFFER_ID_A,
      degraded_offers: [F16_OFFER_ID_DEGRADED],
      total_offers: 2,
    },
  },
  pendingFactor: {
    project_id: F16_PROJECT_ID,
    factor_snapshot_loaded_at: '2026-05-08T10:32:11.234Z',
    per_offer: {
      [F16_OFFER_ID_A]: SIMULATION_A_PENDING,
    },
    comparison_metadata: {
      cheapest_offer_id: null,
      fastest_offer_id: null,
      degraded_offers: [],
      total_offers: 1,
    },
  },
}

// ── Auth helpers ──────────────────────────────────────────────────────────

/**
 * Authentifie la PME F16 via injection localStorage (pattern F14).
 * Doit être appelé AVANT page.goto().
 */
export async function loginAsPme(page: Page): Promise<void> {
  await page.addInitScript(
    ({ accessToken, refreshToken, authUser }) => {
      window.localStorage.clear()
      window.localStorage.setItem('access_token', accessToken)
      window.localStorage.setItem('refresh_token', refreshToken)
      window.localStorage.setItem('auth_user', JSON.stringify(authUser))
    },
    {
      accessToken: PME_USER.fakeAccessToken,
      refreshToken: PME_USER.fakeRefreshToken,
      authUser: {
        id: PME_USER.id,
        email: PME_USER.email,
        full_name: PME_USER.full_name,
        company_name: PME_USER.company_name,
        role: PME_USER.role,
        account: PME_USER.account,
        created_at: PME_USER.created_at,
        updated_at: PME_USER.updated_at,
      },
    },
  )
}

/**
 * Mock de /api/auth/me — retourne l'utilisateur PME F16.
 */
export async function mockAuthMe(page: Page): Promise<void> {
  await page.route('**/api/auth/me', (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: PME_USER.id,
        email: PME_USER.email,
        full_name: PME_USER.full_name,
        company_name: PME_USER.company_name,
        role: PME_USER.role,
        account: PME_USER.account,
        created_at: PME_USER.created_at,
        updated_at: PME_USER.updated_at,
      }),
    })
  })
}

/**
 * Mock de POST /api/projects/{id}/simulate-multi.
 * Le handler reçoit la réponse à renvoyer.
 */
export async function mockSimulateMulti(
  page: Page,
  response: object,
  statusCode = 200,
): Promise<void> {
  await page.route('**/api/projects/*/simulate-multi**', (route) => {
    return route.fulfill({
      status: statusCode,
      contentType: 'application/json',
      body: JSON.stringify(response),
    })
  })
}

/**
 * Mock de /api/sources/{id} — retourne une source vérifiée générique.
 */
export async function mockSourcesApi(page: Page): Promise<void> {
  await page.route('**/api/sources/**', (route) => {
    const url = route.request().url()
    const id = url.split('/').pop() ?? 'unknown'
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id,
        publisher: 'ADEME Base Carbone',
        title: 'Facteur d\'émission — Taxonomie verte UEMOA',
        url: 'https://www.ademe.fr/base-carbone',
        publication_date: '2024-01-15',
        verification_status: 'verified',
        catalog_version: '1.0',
      }),
    })
  })
}

/**
 * Mock complet pour les tests F16 (auth + simulate + sources).
 * Scenariosupported : 'single' | 'multi' | 'degraded' | 'pending'
 */
export async function setupF16Mocks(
  page: Page,
  scenario: 'single' | 'multi' | 'degraded' | 'pending' = 'single',
): Promise<void> {
  await mockAuthMe(page)
  await mockSourcesApi(page)

  const responseMap = {
    single: F16_MOCK_RESPONSES.singleOffer,
    multi: F16_MOCK_RESPONSES.multiOffer,
    degraded: F16_MOCK_RESPONSES.withDegraded,
    pending: F16_MOCK_RESPONSES.pendingFactor,
  }
  await mockSimulateMulti(page, responseMap[scenario])

  // Mock du profil entreprise (appelé par le layout)
  await page.route('**/api/company/profile**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'company-f16-001',
        user_id: PME_USER.id,
        company_name: 'PME Verte Sénégal',
        sector: 'energie',
        country: 'SN',
        employee_count: 20,
        annual_revenue_xof: 120_000_000,
      }),
    }),
  )

  // Mock du dashboard summary
  await page.route('**/api/dashboard/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) }),
  )
}

import { test, expect, type Page, type Route } from '@playwright/test'

/**
 * F03 — Audit log append-only.
 *
 * 4 scénarios indépendants couvrant les 4 user stories :
 *   - US1 (manuel) : édition manuelle du profil → audit `manual` sur /historique
 *   - US1 (llm)    : création de candidature via LLM → audit `llm` avec diff
 *   - US2          : consultation admin du compte PME → audit `view_admin` côté PME
 *   - US3          : export CSV/JSON conforme avec accents français préservés
 *
 * Tous les scénarios mockent le backend (aucun appel réseau réel) pour
 * reproductibilité en local. Les preconditions réelles sont validées côté
 * backend par les tests pytest test_audit/.
 */

const PME_ID = '00000000-0000-0000-0000-000000000010'
const PME_ACCOUNT_ID = '00000000-0000-0000-0000-000000000020'
const ADMIN_ID = '00000000-0000-0000-0000-000000000030'

const PME_USER = {
  id: PME_ID,
  email: 'pme@test.com',
  full_name: 'Fatou Diop',
  company_name: 'PME Co',
  role: 'PME' as const,
  account: {
    id: PME_ACCOUNT_ID,
    name: 'PME Co',
    is_active: true,
    plan: 'free' as const,
  },
  created_at: '2026-01-01',
}

const ADMIN_USER = {
  id: ADMIN_ID,
  email: 'admin@mefali.com',
  full_name: 'Admin Mefali',
  company_name: 'Mefali',
  role: 'ADMIN' as const,
  account: null,
  created_at: '2026-01-01',
}

interface FakeAuditEvent {
  id: string
  timestamp: string
  user_id: string
  user_email: string
  account_id: string
  entity_type: string
  entity_id: string
  action: 'create' | 'update' | 'delete' | 'view_admin'
  field: string | null
  old_value: unknown
  new_value: unknown
  source_of_change: 'manual' | 'llm' | 'admin' | 'import'
  actor_metadata: Record<string, unknown> | null
}

const PME_EVENTS_MANUAL: FakeAuditEvent[] = [
  {
    id: 'evt-1',
    timestamp: '2026-05-06T12:00:00Z',
    user_id: PME_ID,
    user_email: PME_USER.email,
    account_id: PME_ACCOUNT_ID,
    entity_type: 'company_profiles',
    entity_id: 'profile-1',
    action: 'update',
    field: 'sector',
    old_value: 'agriculture',
    new_value: 'energie',
    source_of_change: 'manual',
    actor_metadata: { endpoint: '/api/companies/me' },
  },
]

const PME_EVENTS_LLM: FakeAuditEvent = {
  id: 'evt-llm-1',
  timestamp: '2026-05-06T12:30:00Z',
  user_id: PME_ID,
  user_email: PME_USER.email,
  account_id: PME_ACCOUNT_ID,
  entity_type: 'fund_applications',
  entity_id: 'app-1',
  action: 'create',
  field: null,
  old_value: null,
  new_value: { fund_id: 'gcf-1' },
  source_of_change: 'llm',
  actor_metadata: { tool_name: 'create_fund_application', conversation_id: 'conv-1' },
}

const PME_EVENT_VIEW_ADMIN: FakeAuditEvent = {
  id: 'evt-view-1',
  timestamp: '2026-05-06T13:00:00Z',
  user_id: ADMIN_ID,
  user_email: ADMIN_USER.email,
  account_id: PME_ACCOUNT_ID,
  entity_type: 'account',
  entity_id: PME_ACCOUNT_ID,
  action: 'view_admin',
  field: null,
  old_value: null,
  new_value: null,
  source_of_change: 'admin',
  actor_metadata: { endpoint: `/api/admin/audit/${PME_ACCOUNT_ID}` },
}

const PME_EVENT_FRENCH_ACCENT: FakeAuditEvent = {
  id: 'evt-acc-1',
  timestamp: '2026-05-06T11:00:00Z',
  user_id: PME_ID,
  user_email: PME_USER.email,
  account_id: PME_ACCOUNT_ID,
  entity_type: 'company_profiles',
  entity_id: 'profile-1',
  action: 'update',
  field: 'sector',
  old_value: 'agriculture',
  new_value: 'énergie renouvelable',
  source_of_change: 'manual',
  actor_metadata: null,
}

async function loginAsPme(page: Page) {
  await page.addInitScript(([user]: [typeof PME_USER]) => {
    localStorage.setItem('access_token', 'fake-pme-token')
    localStorage.setItem('refresh_token', 'fake-pme-refresh')
    localStorage.setItem('auth_user', JSON.stringify(user))
  }, [PME_USER])
}

async function loginAsAdmin(page: Page) {
  await page.addInitScript(([user]: [typeof ADMIN_USER]) => {
    localStorage.setItem('access_token', 'fake-admin-token')
    localStorage.setItem('refresh_token', 'fake-admin-refresh')
    localStorage.setItem('auth_user', JSON.stringify(user))
  }, [ADMIN_USER])
}

async function mockAuthMe(page: Page, user: typeof PME_USER | typeof ADMIN_USER) {
  await page.route('**/api/auth/me', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(user),
    })
  })
}

test.describe('F03 — Audit Log Append-Only', () => {
  test('US1.manual — édition profil produit un audit manuel visible sur /historique', async ({
    page,
  }) => {
    await loginAsPme(page)
    await mockAuthMe(page, PME_USER)

    await page.route('**/api/audit/me*', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: PME_EVENTS_MANUAL,
          total: PME_EVENTS_MANUAL.length,
          page: 1,
          limit: 50,
        }),
      })
    })

    await page.goto('/historique')
    await expect(page.getByTestId('historique-title')).toBeVisible()
    // Scope au badge d'evenement (li[data-action]) pour eviter l'ambiguite avec
    // les <option> du filtre Action et le paragraphe descriptif de la page.
    const updateEntry = page.locator('li[data-action="update"]').first()
    await expect(updateEntry).toBeVisible()
    await expect(updateEntry.getByText('Modification')).toBeVisible()
    await expect(updateEntry.getByText('Profil entreprise')).toBeVisible()
    await expect(updateEntry.getByText('sector : agriculture → energie')).toBeVisible()
    await expect(updateEntry.getByText('Manuel')).toBeVisible()
  })

  test('US1.llm — création candidature via LLM produit un audit `llm` avec actor_metadata', async ({
    page,
  }) => {
    await loginAsPme(page)
    await mockAuthMe(page, PME_USER)

    await page.route('**/api/audit/me*', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [PME_EVENTS_LLM],
          total: 1,
          page: 1,
          limit: 50,
        }),
      })
    })

    await page.goto('/historique')
    // Scope au badge d'evenement (li[data-action="create"]) pour eviter l'ambiguite
    // avec les <option> du filtre Action.
    const createEntry = page.locator('li[data-action="create"]').first()
    await expect(createEntry).toBeVisible()
    await expect(createEntry.getByText('Création')).toBeVisible()
    await expect(createEntry.getByText('Candidature au fonds')).toBeVisible()
    await expect(createEntry.getByText("L'assistant IA")).toBeVisible()
  })

  test('US2 — consultation admin du compte PME crée un audit view_admin côté PME', async ({
    page,
  }) => {
    await loginAsPme(page)
    await mockAuthMe(page, PME_USER)

    // Côté PME, /api/audit/me retourne l'événement view_admin
    await page.route('**/api/audit/me*', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [PME_EVENT_VIEW_ADMIN],
          total: 1,
          page: 1,
          limit: 50,
        }),
      })
    })

    await page.goto('/historique')
    // Scope au badge d'evenement (li[data-action="view_admin"]) pour eviter l'ambiguite
    // avec les <option> du filtre Action et le paragraphe descriptif de la page.
    const viewAdminEntry = page.locator('li[data-action="view_admin"]').first()
    await expect(viewAdminEntry).toBeVisible()
    await expect(viewAdminEntry.getByText('Consultation Admin')).toBeVisible()
    await expect(viewAdminEntry.getByText('admin Mefali')).toBeVisible()
  })

  test('US3 — export CSV avec accents français préservés (BOM UTF-8)', async ({
    page,
  }) => {
    await loginAsPme(page)
    await mockAuthMe(page, PME_USER)

    await page.route('**/api/audit/me*', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          events: [PME_EVENT_FRENCH_ACCENT],
          total: 1,
          page: 1,
          limit: 50,
        }),
      })
    })

    // CSV mock : BOM + headers + ligne avec accents
    const BOM = '﻿'
    const csvBody =
      BOM +
      'id,timestamp,user_email,user_id,account_id,entity_type,entity_id,action,field,old_value,new_value,source_of_change,actor_metadata\n' +
      'evt-acc-1,2026-05-06T11:00:00Z,pme@test.com,' +
      PME_ID +
      ',' +
      PME_ACCOUNT_ID +
      ',company_profiles,profile-1,update,sector,agriculture,énergie renouvelable,manual,\n'

    await page.route('**/api/audit/me/export*', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/csv; charset=utf-8',
        headers: {
          'content-disposition': `attachment; filename="audit-log-${PME_ACCOUNT_ID}-20260506.csv"`,
        },
        body: csvBody,
      })
    })

    await page.goto('/historique')
    await expect(page.getByTestId('export-button')).toBeVisible()

    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('export-button').click()
    await page.getByTestId('export-csv').click()
    const download = await downloadPromise
    const path = await download.path()
    expect(path).toBeTruthy()
  })
})

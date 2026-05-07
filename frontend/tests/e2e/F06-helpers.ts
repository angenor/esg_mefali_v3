import type { Page } from '@playwright/test'

/**
 * F06 — Helpers E2E pour les projets verts.
 *
 * Mock backend complet pour les endpoints `/api/projects/*` afin de rendre
 * les scénarios indépendants d'une base de données réelle.
 */

export interface MockProject {
  id: string
  account_id: string
  name: string
  description: string | null
  objective_env: string[]
  maturity: string | null
  status: string
  target_amount: { amount: string; currency: string } | null
  duration_months: number | null
  financing_structure: string | null
  expected_impact_tco2e: string | null
  expected_jobs_created: number | null
  expected_beneficiaries: number | null
  expected_hectares_restored: string | null
  expected_other_impacts: Record<string, unknown> | null
  location_country: string | null
  location_region: string | null
  auto_generated: boolean
  created_at: string
  updated_at: string
  project_documents: unknown[]
  applications_count: number
}

export const SAMPLE_PROJECT: MockProject = {
  id: '11111111-1111-1111-1111-111111111111',
  account_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  name: 'Panneaux solaires usine principale',
  description: 'Installation 50 kWc',
  objective_env: ['renewable_energy', 'mitigation'],
  maturity: 'pilot',
  status: 'draft',
  target_amount: { amount: '50000000', currency: 'XOF' },
  duration_months: 12,
  financing_structure: 'subvention',
  expected_impact_tco2e: '120.0000',
  expected_jobs_created: 5,
  expected_beneficiaries: 100,
  expected_hectares_restored: null,
  expected_other_impacts: null,
  location_country: 'CI',
  location_region: 'Abidjan',
  auto_generated: false,
  created_at: '2026-05-07T10:00:00Z',
  updated_at: '2026-05-07T10:00:00Z',
  project_documents: [],
  applications_count: 0,
}

export async function mockProjectsApi(page: Page) {
  let createdProjects: MockProject[] = []

  await page.route('**/api/projects**', async (route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()

    // POST /api/projects
    if (method === 'POST' && url.pathname.endsWith('/api/projects')) {
      const body = JSON.parse(route.request().postData() || '{}')
      const newProject: MockProject = {
        ...SAMPLE_PROJECT,
        id: `00000000-0000-0000-0000-${Date.now().toString().padStart(12, '0')}`,
        name: body.name,
        description: body.description ?? null,
        objective_env: body.objective_env ?? [],
        maturity: body.maturity ?? null,
        status: body.status ?? 'draft',
        target_amount: body.target_amount ?? null,
        expected_impact_tco2e: body.expected_impact_tco2e ?? null,
        expected_jobs_created: body.expected_jobs_created ?? null,
        location_country: body.location_country ?? null,
        location_region: body.location_region ?? null,
        auto_generated: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        project_documents: [],
        applications_count: 0,
      }
      createdProjects = [newProject, ...createdProjects]
      return route.fulfill({ status: 201, json: newProject })
    }

    // GET /api/projects (liste)
    if (method === 'GET' && url.pathname.endsWith('/api/projects')) {
      return route.fulfill({
        status: 200,
        json: {
          items: createdProjects,
          total: createdProjects.length,
          page: 1,
          limit: 25,
        },
      })
    }

    // GET /api/projects/{id}
    if (method === 'GET' && url.pathname.match(/\/api\/projects\/[^/]+$/)) {
      const id = url.pathname.split('/').pop()
      const found = createdProjects.find((p) => p.id === id) || SAMPLE_PROJECT
      return route.fulfill({ status: 200, json: found })
    }

    // POST /api/projects/{id}/duplicate
    if (
      method === 'POST' &&
      url.pathname.match(/\/api\/projects\/[^/]+\/duplicate$/)
    ) {
      const id = url.pathname.split('/')[url.pathname.split('/').length - 2]
      const source = createdProjects.find((p) => p.id === id) || SAMPLE_PROJECT
      const body = JSON.parse(route.request().postData() || '{}')
      const dup: MockProject = {
        ...source,
        id: `dup-${Date.now()}`,
        name: body.new_name || `${source.name} (copie)`,
        status: 'draft',
        auto_generated: false,
        project_documents: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      createdProjects = [dup, ...createdProjects]
      return route.fulfill({ status: 201, json: dup })
    }

    // PATCH /api/projects/{id}
    if (method === 'PATCH' && url.pathname.match(/\/api\/projects\/[^/]+$/)) {
      const id = url.pathname.split('/').pop()
      const idx = createdProjects.findIndex((p) => p.id === id)
      if (idx >= 0) {
        const body = JSON.parse(route.request().postData() || '{}')
        const updated = { ...createdProjects[idx], ...body }
        createdProjects[idx] = updated
        return route.fulfill({ status: 200, json: updated })
      }
      return route.fulfill({ status: 404, json: { detail: 'Not found' } })
    }

    // DELETE /api/projects/{id}
    if (method === 'DELETE' && url.pathname.match(/\/api\/projects\/[^/]+$/)) {
      const id = url.pathname.split('/').pop()
      const force = url.searchParams.get('force') === 'true'
      // Simulation : ce projet de test a 1 application active
      if (id === 'with-active-app' && !force) {
        return route.fulfill({
          status: 409,
          json: {
            detail: {
              ok: false,
              blocked_by: [
                {
                  application_id: 'app-1',
                  fund_name: 'Green Climate Fund',
                  status: 'submitted_to_fund',
                },
              ],
              hint: 'force=true pour confirmer',
            },
          },
        })
      }
      return route.fulfill({
        status: 200,
        json: { ok: true, blocked_by: [], hint: null },
      })
    }

    // GET /api/projects/{id}/applications
    if (
      method === 'GET' &&
      url.pathname.match(/\/api\/projects\/[^/]+\/applications$/)
    ) {
      return route.fulfill({ status: 200, json: [] })
    }

    return route.continue()
  })
}

export async function mockAuthForProjects(page: Page) {
  // Mock simple : injecter un token JWT factice
  await page.addInitScript(() => {
    window.localStorage.setItem('access_token', 'fake-token')
  })
}

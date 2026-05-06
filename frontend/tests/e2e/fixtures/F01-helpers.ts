/**
 * F01 — Helpers Playwright pour les tests du sourcage et catalogue Source.
 *
 * Strategie : mock total des endpoints backend `/api/sources*`, identique
 * au pattern adopte par F02-helpers.ts (aucune dependance Postgres / migrations).
 * Les tests E2E F01 valident le rendu UI et les parcours utilisateur, pas
 * la requete SQL ; cette derniere est couverte par les tests pytest backend.
 *
 * Pattern d'usage dans une spec :
 *
 *   import { loginAs } from './fixtures/auth'
 *   import { setupF01Mocks, F01_SOURCES } from './fixtures/F01-helpers'
 *
 *   await loginAs(page, F01_PME_USER)        // tokens dans localStorage
 *   await setupF01Mocks(page)                // route /api/sources*
 *   await page.goto('/sources')              // /sources auth-protege
 */
import type { Page, Route } from '@playwright/test'
import type { TestUser } from './users'
import type { Source, SourceListItem, PaginatedSources } from '../../../app/types/source'

// ── Utilisateur PME generique pour les parcours F01 ────────────────────
//
// On reutilise le shape `TestUser` (cf users.ts) attendu par `loginAs()`.
// Ce compte ne fait PAS partie d'un Account multi-tenant (champ `account`
// volontairement omis) : F01 ne testant pas l'isolation, c'est suffisant.
export const F01_PME_USER: TestUser = {
  id: 'user-f01-pme-001',
  email: 'pme.f01@esg-mefali.test',
  full_name: 'Aminata Diop',
  company_name: 'PME Test F01',
  created_at: '2026-02-01T08:00:00Z',
  updated_at: '2026-04-15T10:00:00Z',
  fakeAccessToken: 'fake-access-f01-pme',
  fakeRefreshToken: 'fake-refresh-f01-pme',
}

// ── Fixtures de sources ────────────────────────────────────────────────
//
// 5 sources representatives couvrant les editeurs majeurs visibles dans
// le filtre du catalogue (ADEME, IPCC, IEA, UEMOA, BCEAO). Toutes au
// statut `verified` car l'UI filtre les autres.

export const F01_SOURCES: Source[] = [
  {
    id: 'src-ademe-bc-v23',
    url: 'https://base-empreinte.ademe.fr/donnees/jeu-donnees/base-carbone',
    title: 'ADEME Base Carbone v23',
    publisher: 'ADEME',
    version: 'v23',
    date_publi: '2024-01-15',
    page: 87,
    section: 'Mix electrique',
    captured_at: '2026-04-01T10:00:00Z',
    captured_by: 'system',
    verified_by: 'admin',
    verification_status: 'verified',
    verified_at: '2026-04-01T10:30:00Z',
    outdated_reason: null,
    created_by_user_id: 'system',
    created_at: '2026-04-01T10:00:00Z',
    updated_at: '2026-04-01T10:30:00Z',
  },
  {
    id: 'src-ipcc-ar6',
    url: 'https://www.ipcc.ch/report/ar6/wg3/',
    title: 'IPCC AR6 Working Group III',
    publisher: 'IPCC',
    version: 'AR6',
    date_publi: '2022-04-04',
    page: 12,
    section: 'Chapter 7 — Agriculture',
    captured_at: '2026-03-15T09:00:00Z',
    captured_by: 'system',
    verified_by: 'admin',
    verification_status: 'verified',
    verified_at: '2026-03-15T09:30:00Z',
    outdated_reason: null,
    created_by_user_id: 'system',
    created_at: '2026-03-15T09:00:00Z',
    updated_at: '2026-03-15T09:30:00Z',
  },
  {
    id: 'src-iea-weo-2024',
    url: 'https://www.iea.org/reports/world-energy-outlook-2024',
    title: 'IEA World Energy Outlook 2024',
    publisher: 'IEA',
    version: '2024',
    date_publi: '2024-10-16',
    page: null,
    section: 'Africa Energy Outlook',
    captured_at: '2026-02-20T11:00:00Z',
    captured_by: 'system',
    verified_by: 'admin',
    verification_status: 'verified',
    verified_at: '2026-02-20T11:30:00Z',
    outdated_reason: null,
    created_by_user_id: 'system',
    created_at: '2026-02-20T11:00:00Z',
    updated_at: '2026-02-20T11:30:00Z',
  },
  {
    id: 'src-uemoa-taxonomie',
    url: 'https://www.uemoa.int/fr/taxonomie-verte-uemoa',
    title: 'Taxonomie verte UEMOA',
    publisher: 'UEMOA',
    version: '2023.1',
    date_publi: '2023-11-30',
    page: 45,
    section: 'Criteres de durabilite',
    captured_at: '2026-01-10T08:00:00Z',
    captured_by: 'system',
    verified_by: 'admin',
    verification_status: 'verified',
    verified_at: '2026-01-10T08:30:00Z',
    outdated_reason: null,
    created_by_user_id: 'system',
    created_at: '2026-01-10T08:00:00Z',
    updated_at: '2026-01-10T08:30:00Z',
  },
  {
    id: 'src-bceao-rapport-2024',
    url: 'https://www.bceao.int/fr/publications/rapport-finance-durable-2024',
    title: 'BCEAO Rapport finance durable 2024',
    publisher: 'BCEAO',
    version: '2024',
    date_publi: '2024-06-30',
    page: null,
    section: null,
    captured_at: '2026-03-05T14:00:00Z',
    captured_by: 'system',
    verified_by: 'admin',
    verification_status: 'verified',
    verified_at: '2026-03-05T14:30:00Z',
    outdated_reason: null,
    created_by_user_id: 'system',
    created_at: '2026-03-05T14:00:00Z',
    updated_at: '2026-03-05T14:30:00Z',
  },
]

// ── Helpers HTTP ───────────────────────────────────────────────────────

function jsonResponse(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

function toListItem(source: Source): SourceListItem {
  return {
    id: source.id,
    url: source.url,
    title: source.title,
    publisher: source.publisher,
    version: source.version,
    date_publi: source.date_publi,
    page: source.page,
    section: source.section,
    verification_status: source.verification_status,
  }
}

// ── Mock backend installation ──────────────────────────────────────────

export interface F01MockOptions {
  /** Liste de sources servies par les routes mock (defaut : F01_SOURCES). */
  sources?: Source[]
}

/**
 * Installe les routes mock pour les scenarios F01. A appeler APRES
 * `loginAs()` (qui injecte les tokens dans localStorage) et AVANT
 * `page.goto()`.
 *
 * Routes mockees :
 *  - GET /api/sources           → PaginatedSources (filtre `verified` only)
 *  - GET /api/sources/:id       → Source (404 si non trouvee)
 *  - GET /api/auth/me           → user PME minimal (evite 404 cote auth store)
 */
export async function setupF01Mocks(
  page: Page,
  options: F01MockOptions = {},
): Promise<void> {
  const sources = options.sources ?? F01_SOURCES

  // GET /api/auth/me — minimal, evite que le store auth tombe en erreur 404
  // au premier render. Pas besoin du Bearer token (loginAs a deja injecte
  // l'objet `auth_user` complet dans localStorage).
  await page.route('**/api/auth/me', (route) => {
    return jsonResponse(route, F01_PME_USER)
  })

  // GET /api/sources?... — liste paginee, filtre par publisher / search
  await page.route('**/api/sources', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.continue()
    }
    const url = new URL(route.request().url())
    const publisher = url.searchParams.get('publisher') ?? ''
    const search = (url.searchParams.get('search') ?? '').toLowerCase()
    const page_param = Number(url.searchParams.get('page') ?? 1)
    const page_size = Number(url.searchParams.get('page_size') ?? 20)

    const filtered = sources
      .filter((s) => s.verification_status === 'verified')
      .filter((s) => (publisher ? s.publisher === publisher : true))
      .filter((s) => {
        if (!search) return true
        const haystack = `${s.title} ${s.publisher} ${s.section ?? ''}`.toLowerCase()
        return haystack.includes(search)
      })

    const start = (page_param - 1) * page_size
    const slice = filtered.slice(start, start + page_size)

    const response: PaginatedSources = {
      items: slice.map(toListItem),
      total: filtered.length,
      page: page_param,
      page_size,
    }
    return jsonResponse(route, response)
  })

  // GET /api/sources/:id — detail (404 si introuvable)
  await page.route('**/api/sources/*', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.continue()
    }
    const url = new URL(route.request().url())
    const segments = url.pathname.split('/')
    const id = segments[segments.length - 1]
    const source = sources.find((s) => s.id === id)
    if (!source) {
      return jsonResponse(route, { detail: 'Source introuvable' }, 404)
    }
    return jsonResponse(route, source)
  })
}

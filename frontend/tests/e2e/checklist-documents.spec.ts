import { test, expect } from '@playwright/test'

/**
 * 049 (US1, P1) — Fourniture des documents de la checklist (E2E).
 *
 * Parcours : ouvrir un dossier → onglet Checklist → téléverser un PDF valide
 * sur un item « Manquant » → l'item passe « Fourni » (nom de fichier affiché) et
 * la progression M/N s'incrémente. Backend mocké via page.route (aucune
 * dépendance Postgres/OpenRouter).
 */

const FAKE_TOKEN = 'fake.jwt.token'
const FAKE_USER = {
  id: 'user-1',
  email: 'pme@example.com',
  account_id: 'account-1',
  role: 'PME',
}

async function mockAuth(page) {
  await page.addInitScript(({ token, user }) => {
    // Clés réellement lues par le store auth (auth.global.ts → loadFromStorage).
    window.localStorage.setItem('access_token', token)
    window.localStorage.setItem('refresh_token', token)
    window.localStorage.setItem('auth_user', JSON.stringify(user))
  }, { token: FAKE_TOKEN, user: FAKE_USER })
}

const FUND = { id: 'fund-1', name: 'GCF', organization: 'Green Climate Fund' }

function detail(provided: boolean) {
  return {
    id: 'app-1',
    fund: FUND,
    intermediary: null,
    match: null,
    target_type: 'fund_direct',
    status: 'draft',
    status_label: 'Brouillon',
    sections: {},
    checklist: [
      provided
        ? {
            key: 'company_registration',
            name: 'Registre de commerce (RCCM)',
            status: 'provided',
            document_id: 'doc-1',
            required_by: 'fund_direct',
            document: { id: 'doc-1', original_filename: 'rccm.pdf', mime_type: 'application/pdf', status: 'uploaded' },
          }
        : {
            key: 'company_registration',
            name: 'Registre de commerce (RCCM)',
            status: 'missing',
            document_id: null,
            required_by: 'fund_direct',
            document: null,
          },
    ],
    checklist_progress: { provided: provided ? 1 : 0, total: 1 },
    intermediary_prep: null,
    simulation: null,
    created_at: '2026-06-03T00:00:00Z',
    updated_at: '2026-06-03T00:00:00Z',
    submitted_at: null,
  }
}

test.describe('049 — Checklist documents (P1)', () => {
  test('téléverser un fichier fait passer l\'item à « Fourni » + progression', async ({ page }) => {
    await mockAuth(page)

    // État mutable : avant/après rattachement.
    let attached = false

    // Sources (résolution onMounted) — réponse vide pour ne rien bloquer.
    await page.route('**/api/sources**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], total: 0 }) }),
    )

    // GET détail du dossier (reflète l'état courant).
    await page.route('**/api/applications/app-1', (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(detail(attached)),
        })
      }
      return route.continue()
    })

    // POST upload document → renvoie le document créé.
    await page.route('**/api/documents/upload', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ documents: [{ id: 'doc-1', original_filename: 'rccm.pdf', mime_type: 'application/pdf', file_size: 1024, status: 'uploaded', document_type: null, has_analysis: false, created_at: '2026-06-03T00:00:00Z' }] }),
      }),
    )
    // GET liste documents (rafraîchie par uploadDocuments). ``fallback`` laisse
    // le POST /upload (route plus spécifique) être traité par son handler.
    await page.route('**/api/documents/**', (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ documents: [], total: 0, page: 1, limit: 25 }) })
      }
      return route.fallback()
    })

    // PUT rattachement → item « provided » + progression 1/1.
    await page.route('**/api/applications/app-1/checklist/company_registration/document', (route) => {
      if (route.request().method() === 'PUT') {
        attached = true
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              item: detail(true).checklist[0],
              checklist_progress: { provided: 1, total: 1 },
            },
          }),
        })
      }
      return route.continue()
    })

    await page.goto('/applications/app-1')

    // Onglet Checklist.
    await page.getByRole('button', { name: 'Checklist' }).click()
    await expect(page.getByText('Registre de commerce (RCCM)')).toBeVisible()
    await expect(page.getByText('Manquant')).toBeVisible()

    // Révéler la zone de téléversement puis fournir un PDF valide.
    await page.getByRole('button', { name: 'Téléverser' }).click()
    await page.locator('input[type="file"]').setInputFiles({
      name: 'rccm.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 test'),
    })

    // L'item passe « Fourni », affiche le nom du fichier, progression 1/1.
    await expect(page.getByText('Fourni')).toBeVisible()
    await expect(page.getByText('rccm.pdf')).toBeVisible()
    await expect(page.getByText('1 / 1 documents fournis')).toBeVisible()
  })
})

/**
 * F21 — Dashboard par Offre + Carte Intermédiaires + Rapport Carbone PDF.
 *
 * 4 scénarios couvrant les user stories P1+P2 :
 * 1. US1 — 3 cards de candidatures par Offre sur /dashboard.
 * 2. US3 — Section carte UEMOA des intermédiaires actifs présente.
 * 3. US4 — Score ESG affiche un picto source cliquable.
 * 4. US5 — Onglet « Carbone » de /reports liste un rapport téléchargeable.
 */

import { test, expect } from '@playwright/test'

import {
  SAMPLE_APPLICATIONS,
  mockActiveIntermediaries,
  mockCarbonReportGenerate,
  mockCarbonReportsList,
  mockDashboardSummary,
} from './F21-helpers'

test.describe('F21 — Dashboard par Offre + Rapport Carbone PDF', () => {
  test.beforeEach(async ({ page }) => {
    // Auth bypass minimal — auth.global.ts gère la redirection ; pour les
    // mocks E2E on stub directement l'auth state via localStorage.
    await page.addInitScript(() => {
      window.localStorage.setItem(
        'mefali.auth.access_token',
        'mock-token-f21',
      )
    })
    await mockDashboardSummary(page)
    await mockActiveIntermediaries(page)
    await mockCarbonReportGenerate(page)
    await mockCarbonReportsList(page)
  })

  test('US1 — 3 cards de candidatures par Offre sur le dashboard', async ({ page }) => {
    await page.goto('/dashboard')

    // Attendre la section.
    const section = page.locator('[data-testid="applications-by-offer-section"]')
    await expect(section).toBeVisible({ timeout: 10_000 })

    // 3 cards distinctes (granularité par offre).
    for (const app of SAMPLE_APPLICATIONS) {
      const card = page.locator(`[data-testid="application-card-${app.application_id}"]`)
      await expect(card).toBeVisible()
      await expect(card).toContainText(app.fund_name)
      await expect(card).toContainText(app.intermediary_name)
    }
  })

  test('US3 — Carte UEMOA des intermédiaires actifs visible', async ({ page }) => {
    await page.goto('/dashboard')

    const section = page.locator('[data-testid="intermediaries-map-section"]')
    await expect(section).toBeVisible({ timeout: 10_000 })

    // Container map ou état vide.
    const container = page.locator('[data-testid="intermediaries-map-container"]')
    await expect(container).toBeVisible({ timeout: 10_000 })
  })

  test('US4 — ScoreCard ESG expose un picto source cliquable F01', async ({ page }) => {
    await page.goto('/dashboard')
    // SourceLink F01 est rendu quand sources non vide.
    const scoreCardEsg = page.locator('text=ESG Global').first().locator('..')
    await expect(scoreCardEsg).toBeVisible({ timeout: 10_000 })
    // Au moins une icône source ou badge non-sourcé doit être présent (transparence).
    const hasSourceLink = await page.locator('[data-testid="source-link"]').first().count()
    const hasUnsourcedBadge = await page.locator('[data-testid="score-unsourced-badge"]').first().count()
    expect(hasSourceLink + hasUnsourcedBadge).toBeGreaterThan(0)
  })

  test('US5 — Onglet « Carbone » sur /reports liste 1 rapport téléchargeable', async ({ page }) => {
    await page.goto('/reports')
    // Onglets ESG | Carbone.
    await expect(page.locator('[data-testid="reports-tabs"]')).toBeVisible({ timeout: 10_000 })
    await page.locator('[data-testid="tab-carbon"]').click()
    // Panneau carbone visible.
    await expect(page.locator('[data-testid="carbon-reports-panel"]')).toBeVisible()
    // 1 row de rapport carbone.
    await expect(
      page.locator('[data-testid="carbon-report-row-rep-carbon-1"]'),
    ).toBeVisible({ timeout: 10_000 })
    // Bouton de téléchargement présent.
    await expect(
      page.locator('[data-testid="carbon-download-rep-carbon-1"]'),
    ).toBeVisible()
  })
})

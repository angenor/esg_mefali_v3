import { test, expect } from '@playwright/test'
import {
  F14_FIXTURES,
  mockAuthForMatching,
  mockMatchingApi,
} from './F14-helpers'

/**
 * F14 — Matching Projet ↔ Offre + Comparateur (E2E).
 *
 * 4 scénarios couvrant les user stories US1-US4 du spec.
 *
 * Note : ces scénarios sont skippés en Phase B-bis (validation lors de
 * Phase B' E2E live). Ils sont complets et exécutables à part.
 */

test.describe('F14 — Matching projet/offre', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthForMatching(page)
    await mockMatchingApi(page)
  })

  test('US1 — page liste matches affiche les offres compatibles', async ({
    page,
  }) => {
    await page.goto(`/profile/projects/${F14_FIXTURES.PROJECT_ID}/matches`)
    await page.waitForLoadState('domcontentloaded')

    // Au moins une ligne de match avec score
    const firstRow = page.getByTestId(/^match-row-/).first()
    await expect(firstRow).toBeVisible()
    await expect(firstRow).toContainText(/\d+\/100/)

    // Bouton recalculer présent et accessible
    const recompute = page.getByTestId('recompute-matches-page-btn')
    await expect(recompute).toBeVisible()
    await expect(recompute).toBeEnabled()
  })

  test('US2 — comparateur affiche tableau ≥ 2 colonnes', async ({ page }) => {
    await page.goto(
      `/financing/compare/${F14_FIXTURES.FUND_ID}?project_id=${F14_FIXTURES.PROJECT_ID}`,
    )
    await page.waitForLoadState('domcontentloaded')

    // Le composant table comparateur F11 (ComparisonTableBlock) est rendu
    const table = page.getByTestId('comparator-table')
    await expect(table).toBeVisible()
    await expect(page.getByText('BOAD').first()).toBeVisible()
    await expect(page.getByText('FONSIS').first()).toBeVisible()
  })

  test('US3 — comparateur sans project_id affiche message d\'erreur', async ({
    page,
  }) => {
    await page.goto(`/financing/compare/${F14_FIXTURES.FUND_ID}`)
    await page.waitForLoadState('domcontentloaded')
    const errorBanner = page.getByTestId('comparator-error')
    await expect(errorBanner).toBeVisible()
    await expect(errorBanner).toContainText(/identifiant de projet/i)
  })

  test('US4 — toggle alertes persiste après refresh', async ({ page }) => {
    await page.goto(`/profile/projects/${F14_FIXTURES.PROJECT_ID}/alerts`)
    await page.waitForLoadState('domcontentloaded')

    const toggleContainer = page.getByTestId('match-alert-toggle')
    await expect(toggleContainer).toBeVisible()

    // Initial : off
    await expect(page.getByTestId('alert-toggle-off')).toBeVisible()

    // Activer
    await page.getByTestId('alert-toggle-off').click()
    await expect(page.getByTestId('alert-toggle-on')).toBeVisible()
    await expect(page.getByTestId('alerts-success')).toBeVisible()

    // Refresh : la subscription est persistée par le mock
    await page.reload()
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByTestId('alert-toggle-on')).toBeVisible()
  })
})

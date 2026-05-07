import { test, expect } from '@playwright/test'

/**
 * F11 — Tools de Visualisation Typés (KPICard, MatchCard, Map, ComparisonTable).
 *
 * 4 scénarios couvrant les 4 user stories P1/P2 :
 *
 * 1. **Scénario A — KPICard pour empreinte carbone (US1)** :
 *    Préparer un bilan carbone 2026 finalisé (45 tCO2e) + bilan 2024 (51 tCO2e).
 *    Envoyer "résume mon empreinte carbone 2026" → attendre l'event SSE
 *    visualization_block (block_type=show_kpi_card). Vérifier qu'une .kpi-card-block
 *    est visible avec titre, valeur "45", delta vert (down + delta_is_good=true),
 *    picto Source cliquable. Click sur picto → modale source visible.
 *    Click sur drilldown → URL contient "/carbon/results".
 *
 * 2. **Scénario B — 3 MatchCards cliquables (US2)** :
 *    Préparer 1 projet test + 3 offres compatibles (data-tagged "GCF/BOAD/AFD").
 *    Envoyer "quelles offres me correspondent ?". Attendre 3 events
 *    visualization_block (block_type=show_match_card). Vérifier 3 .match-card-block
 *    visibles, logo (ou placeholder), score circulaire, badges instruments.
 *    Click sur "Explorer" 1ère carte → URL contient "/financing/offers/" et
 *    "?project_id=".
 *
 * 3. **Scénario C — ComparisonTable avec highlight winner (US3)** :
 *    Préparer 3 offres GCF (BOAD/UNDP/AFD). Envoyer "compare-les" → attendre
 *    event visualization_block (block_type=show_comparison_table). Vérifier
 *    1 .comparison-table-block visible, 3 colonnes sujets, ≥ 2 rows critères,
 *    au moins 1 cellule a la classe .winner. Resize viewport à 600 px →
 *    fold en cartes verticales (tableau hidden, cartes mobile visibles).
 *
 * 4. **Scénario D — Map UEMOA avec markers + overlay (US4)** :
 *    Préparer projet à Bouaké (lat 7.6906, lon -5.0307) + intermédiaire
 *    BOAD à Lomé (lat 6.1319, lon 1.2228). Envoyer "où sont mes interlocuteurs
 *    en UEMOA ?" → attendre event visualization_block (block_type=show_map)
 *    après lazy-load Leaflet. Vérifier 1 .map-block visible, 2 .leaflet-marker-icon
 *    présents, path GeoJSON UEMOA visible (.leaflet-overlay-pane svg path),
 *    click sur 1 marker → popup visible avec label.
 *    Toggle dark mode → tile URL contient "cartocdn.com/dark_all".
 *
 * Note : ces tests s'appuient sur des fixtures Playwright dans
 * tests/e2e/helpers/F11-fixtures.ts (à compléter avec les helpers existants).
 * Si les fixtures ne sont pas disponibles, les scénarios sont skippés.
 * Les tests E2E ne sont PAS exécutés par cette phase B : ils sont validés
 * en phase C (E2E Playwright) après merge du backend + frontend.
 */

test.describe('F11 - Tools de visualisation typés', () => {
  test.skip(({ browserName }) => browserName !== 'chromium', 'E2E phase C uniquement')

  test.beforeEach(async ({ page }) => {
    // TODO(phase C) : login utilisateur PME + navigation vers /chat
    await page.goto('/')
  })

  // Scénario A — KPICard pour empreinte carbone
  test('Scénario A — KPICard empreinte carbone rendu inline (US1)', async ({ page }) => {
    // TODO(phase C) : préparer un bilan carbone 2026 finalisé (45 tCO2e) + bilan 2024 (51 tCO2e)
    // via API REST de seeding ou helper backend.

    // Envoyer le message
    // await page.locator('[data-test="chat-input"]').fill('Résume mon empreinte carbone 2026.')
    // await page.locator('[data-test="chat-send"]').click()

    // Attendre l'event SSE visualization_block
    // const kpiCard = page.locator('.kpi-card-block').first()
    // await expect(kpiCard).toBeVisible({ timeout: 30_000 })

    // Assertions sur le contenu
    // await expect(kpiCard).toContainText('Empreinte carbone 2026')
    // await expect(kpiCard).toContainText('45')

    // Delta : couleur verte (text-emerald-* ou text-green-*)
    // const deltaEl = kpiCard.locator('[class*="text-emerald"], [class*="text-green"]')
    // await expect(deltaEl).toBeVisible()

    // Picto Source : visible et cliquable
    // const sourceBtn = kpiCard.locator('button[aria-label*="source"]')
    // await expect(sourceBtn).toBeVisible()
    // await sourceBtn.click()
    // await expect(page.locator('[role="dialog"]')).toBeVisible()
    // await page.keyboard.press('Escape')

    // Drilldown : click sur la card → /carbon/results
    // await kpiCard.click()
    // await expect(page).toHaveURL(/\/carbon\/results/)

    test.skip(true, 'Implémentation phase C — fixtures + LLM réel requis')
  })

  // Scénario B — 3 MatchCards cliquables
  test('Scénario B — 3 MatchCards proposées avec drill-down (US2)', async ({ page }) => {
    // TODO(phase C) : préparer 1 projet test + 3 offres compatibles via API seed.

    // Envoyer le message
    // await page.locator('[data-test="chat-input"]').fill('Quelles offres me correspondent ?')
    // await page.locator('[data-test="chat-send"]').click()

    // Attendre 3 .match-card-block
    // const cards = page.locator('.match-card-block')
    // await expect(cards).toHaveCount(3, { timeout: 30_000 })

    // Vérifier score circulaire
    // for (let i = 0; i < 3; i++) {
    //   const card = cards.nth(i)
    //   await expect(card.locator('svg')).toBeVisible()
    //   await expect(card.locator('[data-test="match-card-cta"]')).toBeVisible()
    // }

    // Click sur "Explorer" de la 1ère carte
    // await cards.nth(0).locator('[data-test="match-card-cta"]').click()
    // await expect(page).toHaveURL(/\/financing\/offers\//)
    // await expect(page).toHaveURL(/project_id=/)

    test.skip(true, 'Implémentation phase C — fixtures + LLM réel requis')
  })

  // Scénario C — ComparisonTable avec highlight winner
  test('Scénario C — ComparisonTable 3 offres avec highlight winner par row (US3)', async ({ page }) => {
    // TODO(phase C) : préparer 3 offres GCF (BOAD/UNDP/AFD) via API seed.

    // Envoyer le message
    // await page.locator('[data-test="chat-input"]').fill('Compare GCF via BOAD vs GCF via UNDP vs GCF via AFD.')
    // await page.locator('[data-test="chat-send"]').click()

    // Attendre la table
    // const table = page.locator('.comparison-table-block').first()
    // await expect(table).toBeVisible({ timeout: 30_000 })

    // 3 colonnes sujets + ≥ 2 rows
    // const headers = table.locator('thead th[scope="col"]')
    // await expect(headers).toHaveCount(4) // 1 critère + 3 sujets

    // Au moins 1 cellule winner
    // const winnerCell = table.locator('td.winner, td[data-winner="true"]').first()
    // await expect(winnerCell).toBeVisible()

    // Resize viewport à 600 px → fold en cartes
    // await page.setViewportSize({ width: 600, height: 800 })
    // await expect(table.locator('table')).toBeHidden()
    // await expect(table.locator('dl').first()).toBeVisible()

    test.skip(true, 'Implémentation phase C — fixtures + LLM réel requis')
  })

  // Scénario D — Map UEMOA avec markers + overlay
  test('Scénario D — Map UEMOA avec markers projet + intermédiaire et overlay (US4)', async ({ page }) => {
    // TODO(phase C) : préparer projet Bouaké (lat 7.6906, lon -5.0307)
    // + intermédiaire BOAD Lomé (lat 6.1319, lon 1.2228) via API seed.

    // Envoyer le message
    // await page.locator('[data-test="chat-input"]').fill('Où sont mes interlocuteurs en UEMOA ?')
    // await page.locator('[data-test="chat-send"]').click()

    // Attendre lazy-load Leaflet + map rendue
    // const map = page.locator('.map-block').first()
    // await expect(map).toBeVisible({ timeout: 30_000 })

    // 2 markers visibles
    // const markers = map.locator('.leaflet-marker-icon')
    // await expect(markers).toHaveCount(2)

    // Path GeoJSON UEMOA
    // const overlay = map.locator('.leaflet-overlay-pane svg path').first()
    // await expect(overlay).toBeVisible()

    // Click sur 1 marker → popup
    // await markers.nth(0).click()
    // await expect(map.locator('.leaflet-popup-content')).toBeVisible()

    // Toggle dark mode
    // await page.evaluate(() => {
    //   document.documentElement.classList.add('dark')
    // })
    // const tile = map.locator('.leaflet-tile')
    // const tileSrc = await tile.first().getAttribute('src')
    // expect(tileSrc).toContain('cartocdn.com')

    test.skip(true, 'Implémentation phase C — fixtures + LLM réel requis')
  })
})

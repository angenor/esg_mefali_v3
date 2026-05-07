/**
 * F23 — E2E Skills admin (T056).
 *
 * Couvre :
 *  - Admin crée une skill (en draft).
 *  - Tentative de publication avec golden_examples insuffisants → erreur affichée.
 *  - Édition d'une skill draft → in-place update.
 *
 * Ces scénarios nécessitent un environnement avec :
 *  - Backend en route (/api/admin/skills/* opérationnels).
 *  - Un compte admin valide (variables d'env E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD).
 */

import { test, expect } from '@playwright/test'

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD

test.describe('F23 - Admin Skills', () => {
  test.skip(
    !ADMIN_EMAIL || !ADMIN_PASSWORD,
    'Variables E2E_ADMIN_EMAIL et E2E_ADMIN_PASSWORD requises',
  )

  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="email"]', ADMIN_EMAIL!)
    await page.fill('input[type="password"]', ADMIN_PASSWORD!)
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard')
  })

  test('admin liste les skills depuis /admin/skills', async ({ page }) => {
    await page.goto('/admin/skills')
    await expect(page.getByRole('heading', { name: /Skills/i })).toBeVisible()
  })

  test('admin crée une skill draft', async ({ page }) => {
    await page.goto('/admin/skills/new')
    await expect(page.getByRole('heading', { name: /Nouvelle skill/i })).toBeVisible()

    // Onglet Identité.
    await page.fill('input[placeholder*="skill_"]', `skill_e2e_${Date.now()}`)

    // Onglet Prompt.
    await page.click('button:has-text("Prompt expert")')
    await page.fill(
      'textarea',
      'Tu es un expert ESG ouest-africain. Aide les PME à structurer un diagnostic clair sur 30 critères.',
    )

    // Onglet Procédure.
    await page.click('button:has-text("Procédure")')
    await page.fill(
      'textarea',
      '1) Demander le secteur. 2) Calculer score. 3) Restituer recommandations.',
    )

    // Onglet Tools.
    await page.click('button:has-text("Tools")')
    await page.fill('input[placeholder*="update_company_profile"]', 'update_company_profile')
    await page.click('button:has-text("Ajouter")')

    // Soumission.
    await page.click('button[type="submit"]')

    await expect(page).toHaveURL(/\/admin\/skills\/[a-f0-9-]+/, { timeout: 10000 })
  })

  test('publier sans 5 golden_examples affiche une erreur', async ({ page }) => {
    await page.goto('/admin/skills')
    // Cherche un skill draft existant, sinon skip.
    const draftRow = page.locator('tr', { hasText: 'draft' }).first()
    const count = await draftRow.count()
    test.skip(count === 0, 'Aucune skill draft disponible pour ce test')

    page.on('dialog', (d) => d.accept()) // Auto-accept confirm dialog
    await draftRow.getByRole('button', { name: /Publier/i }).click()
    // Attendre l'alerte d'erreur (insufficient_golden_examples ou gate_failed).
    await page.waitForEvent('dialog')
  })
})

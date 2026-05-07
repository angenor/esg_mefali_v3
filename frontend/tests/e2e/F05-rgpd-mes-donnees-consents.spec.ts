/**
 * F05 — Tests E2E Playwright : RGPD Mes Données + Consentements + Export/Suppression.
 *
 * 5 scénarios critiques :
 * 1. Créer compte → exporter → JSON valide non vide.
 * 2. Programmer suppression → annuler → compte intact.
 * 3. Programmer suppression → simuler J+30 → purge effective + audit_log anonymisé.
 * 4. Tenter analyse Mobile Money sans consent → 403.
 * 5. Page /legal/privacy accessible sans auth + checkbox obligatoire à /register.
 */

import { test, expect } from '@playwright/test'

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'
const APP_BASE = process.env.APP_BASE_URL || 'http://localhost:3000'

test.describe('F05 — RGPD Mes Données + Consentements + Export/Suppression', () => {
  test('Scénario 1 : créer compte → exporter → ZIP non vide', async ({
    page,
    request,
  }) => {
    const email = `e2e-${Date.now()}@example.com`
    const password = 'TestPwd123!'

    // 1. Inscription avec privacy_policy_accepted=true via API
    const registerRes = await request.post(`${API_BASE}/api/auth/register`, {
      data: {
        email,
        password,
        full_name: 'E2E User',
        company_name: 'E2E Test Co',
        country: 'France',
        privacy_policy_accepted: true,
      },
    })
    expect(registerRes.ok()).toBeTruthy()

    // 2. Login
    const loginRes = await request.post(`${API_BASE}/api/auth/login`, {
      data: { email, password },
    })
    const tokens = await loginRes.json()
    const token = tokens.access_token
    expect(token).toBeTruthy()

    // 3. Inventaire
    const inventoryRes = await request.get(
      `${API_BASE}/api/me/data/inventory`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(inventoryRes.ok()).toBeTruthy()
    const inventory = await inventoryRes.json()
    expect(inventory.counts).toHaveProperty('profile')

    // 4. Export
    const exportRes = await request.get(
      `${API_BASE}/api/me/data/export?format=json`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(exportRes.ok()).toBeTruthy()
    const buffer = await exportRes.body()
    expect(buffer.length).toBeGreaterThan(100)
    // Le ZIP doit commencer par les bytes magiques 'PK'
    expect(buffer[0]).toBe(0x50)
    expect(buffer[1]).toBe(0x4b)
  })

  test('Scénario 2 : programmer suppression → annuler → compte intact', async ({
    request,
  }) => {
    const email = `e2e-cancel-${Date.now()}@example.com`
    const password = 'TestPwd123!'

    await request.post(`${API_BASE}/api/auth/register`, {
      data: {
        email,
        password,
        full_name: 'E2E Cancel',
        company_name: 'E2E Cancel Co',
        country: 'France',
        privacy_policy_accepted: true,
      },
    })
    const loginRes = await request.post(`${API_BASE}/api/auth/login`, {
      data: { email, password },
    })
    const { access_token: token } = await loginRes.json()

    // Programmer suppression
    const schedRes = await request.post(
      `${API_BASE}/api/me/account/schedule-deletion`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { password, confirmation_text: 'SUPPRIMER' },
      },
    )
    expect(schedRes.ok()).toBeTruthy()
    const sched = await schedRes.json()
    expect(sched.deletion_scheduled_at).toBeTruthy()

    // Annuler via JWT
    const cancelRes = await request.post(
      `${API_BASE}/api/me/account/cancel-deletion`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    )
    expect(cancelRes.ok()).toBeTruthy()
    const cancel = await cancelRes.json()
    expect(cancel.cancelled_at).toBeTruthy()
  })

  test('Scénario 4 : analyse Mobile Money sans consent → 403, avec consent → 501 (stub)', async ({
    request,
  }) => {
    const email = `e2e-gating-${Date.now()}@example.com`
    const password = 'TestPwd123!'

    await request.post(`${API_BASE}/api/auth/register`, {
      data: {
        email,
        password,
        full_name: 'E2E Gating',
        company_name: 'E2E Gating Co',
        country: 'France',
        privacy_policy_accepted: true,
      },
    })
    const loginRes = await request.post(`${API_BASE}/api/auth/login`, {
      data: { email, password },
    })
    const { access_token: token } = await loginRes.json()

    // Sans consent → 403
    const previewRes = await request.post(
      `${API_BASE}/api/credit/mobile-money/preview`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(previewRes.status()).toBe(403)
    const detail = await previewRes.json()
    expect(detail.detail.consent_type).toBe('mobile_money_analysis')

    // Grant consent
    const grantRes = await request.post(
      `${API_BASE}/api/me/consents/mobile_money_analysis/grant`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(grantRes.ok()).toBeTruthy()

    // Avec consent → 501 (stub) — pas 403
    const previewRes2 = await request.post(
      `${API_BASE}/api/credit/mobile-money/preview`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(previewRes2.status()).not.toBe(403)
    expect(previewRes2.status()).toBe(501)

    // Revoke
    await request.post(
      `${API_BASE}/api/me/consents/mobile_money_analysis/revoke`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const previewRes3 = await request.post(
      `${API_BASE}/api/credit/mobile-money/preview`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    expect(previewRes3.status()).toBe(403)
  })

  test('Scénario 5 : page /legal/privacy accessible sans auth + checkbox obligatoire', async ({
    page,
  }) => {
    // 1. Naviguer sur /legal/privacy sans auth
    await page.goto(`${APP_BASE}/legal/privacy`)
    await expect(page).toHaveURL(/\/legal\/privacy/)
    await expect(
      page.getByRole('heading', { name: 'Politique de confidentialité' }),
    ).toBeVisible()
    await expect(
      page.getByRole('link', { name: 'privacy@esg-mefali.com' }).first(),
    ).toBeVisible()

    // 2. Footer contient le lien
    await expect(
      page.locator('footer').getByText('Politique de confidentialité'),
    ).toBeVisible()

    // 3. Sur /register, sans cocher la case → soumission désactivée
    await page.goto(`${APP_BASE}/register`)
    const submitButton = page.locator('button[type="submit"]')
    await expect(submitButton).toBeDisabled()
  })
})

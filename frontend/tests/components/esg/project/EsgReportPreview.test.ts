/**
 * T054 [US3] — Tests EsgReportPreview : 7 sections affichées, bouton désactivé
 * tant que non finalisé, et état chargement bien rendu.
 */

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import EsgReportPreview from '~/components/esg/project/EsgReportPreview.vue'

describe('EsgReportPreview (F047 US3)', () => {
  it('liste les 7 sections du rapport ESIA-light', () => {
    const wrapper = mount(EsgReportPreview, {
      props: {
        projectId: 'proj-1',
        assessmentId: 'asst-1',
        isFinalized: true,
      },
    })
    const items = wrapper.findAll('[data-testid="esia-sections-outline"] li')
    expect(items.length).toBe(7)
    expect(items[0].text()).toContain('Résumé exécutif')
    expect(items[2].text()).toContain('Diagnostic')
    expect(items[6].text()).toContain('Indicateurs de suivi')
  })

  it('désactive le bouton tant que isFinalized=false', () => {
    const wrapper = mount(EsgReportPreview, {
      props: {
        projectId: 'p',
        assessmentId: 'a',
        isFinalized: false,
      },
    })
    const btn = wrapper.find('[data-testid="esia-generate-button"]')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('title')).toContain('finaliser')
  })

  it('active le bouton quand isFinalized=true', () => {
    const wrapper = mount(EsgReportPreview, {
      props: {
        projectId: 'p',
        assessmentId: 'a',
        isFinalized: true,
      },
    })
    const btn = wrapper.find('[data-testid="esia-generate-button"]')
    expect(btn.attributes('disabled')).toBeUndefined()
    expect(btn.text()).toContain('Générer le rapport ESIA')
  })

  it("annonce '30 secondes' dans le titre du bouton pour les utilisateurs", () => {
    const wrapper = mount(EsgReportPreview, {
      props: {
        projectId: 'p',
        assessmentId: 'a',
        isFinalized: true,
      },
    })
    const btn = wrapper.find('[data-testid="esia-generate-button"]')
    expect(btn.attributes('title')).toMatch(/30\s*s/i)
  })
})

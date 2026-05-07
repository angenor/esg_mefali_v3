import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MissingCriteriaList from '~/components/esg/MissingCriteriaList.vue'
import type { MissingCriterion } from '~/types/esg'

function makeCriterion(code: string, suggestion: string | null = null): MissingCriterion {
  return {
    indicator_id: `i-${code}`,
    indicator_code: code,
    reason: 'non_renseigne',
    source_id: `s-${code}`,
    suggestion,
  }
}

describe('MissingCriteriaList', () => {
  it('renders the list of missing criteria', () => {
    const criteria = [makeCriterion('PS6'), makeCriterion('PS7')]
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria, referentialName: 'IFC PS' },
    })
    expect(wrapper.text()).toContain('PS6')
    expect(wrapper.text()).toContain('PS7')
    expect(wrapper.text()).toContain('Critères manquants (2)')
  })

  it('shows empty state when no criteria', () => {
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria: [], referentialName: 'Mefali' },
    })
    expect(wrapper.text()).toContain('Aucun critère manquant')
    expect(wrapper.text()).toContain('Mefali')
  })

  it('opens detail modal on click', async () => {
    const criteria = [makeCriterion('PS6', 'Renseigner PS6 — Biodiversité')]
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria, referentialName: 'IFC PS' },
    })
    const btn = wrapper.find('button[aria-label*="PS6"]')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    // La modale doit afficher la suggestion
    expect(wrapper.text()).toContain('Renseigner PS6')
  })

  it('shows source info in modal when source_id is set', async () => {
    const criteria = [{ ...makeCriterion('PS6'), source_id: 'src-abc-123' }]
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria, referentialName: 'IFC PS' },
    })
    const btn = wrapper.find('button[aria-label*="PS6"]')
    await btn.trigger('click')
    expect(wrapper.text()).toContain('Source officielle')
    expect(wrapper.text()).toContain('src-abc-123')
  })

  it('translates reason labels in French', () => {
    const criteria = [
      { ...makeCriterion('A1'), reason: 'invalide' as const },
      { ...makeCriterion('A2'), reason: 'hors_scope' as const },
    ]
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria, referentialName: 'Test' },
    })
    expect(wrapper.text()).toContain('Donnée invalide')
    expect(wrapper.text()).toContain('Hors scope')
  })

  it('applies dark mode classes', () => {
    const wrapper = mount(MissingCriteriaList, {
      props: { criteria: [makeCriterion('A1')], referentialName: 'Test' },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-card')
    expect(html).toContain('dark:text-surface-dark-text')
  })
})

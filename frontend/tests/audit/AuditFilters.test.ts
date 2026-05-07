import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

import AuditFilters from '~/components/audit/AuditFilters.vue'

describe('AuditFilters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('rend les selects (entité, source, action) en français', () => {
    const w = mount(AuditFilters, {
      props: { modelValue: { page: 1, limit: 50, order: 'desc' as const } },
    })
    expect(w.text()).toContain('Entité')
    expect(w.text()).toContain('Source')
    expect(w.text()).toContain('Action')
    expect(w.text()).toContain('Profil entreprise')
    expect(w.text()).toContain('Assistant IA')
    expect(w.text()).toContain('Création')
  })

  it('emit update:modelValue quand on change un filtre', async () => {
    const w = mount(AuditFilters, {
      props: { modelValue: { page: 1, limit: 50, order: 'desc' as const } },
    })
    const firstSelect = w.findAll('select')[0]
    await firstSelect.setValue('company_profiles')

    const events = w.emitted('update:modelValue')
    expect(events).toBeTruthy()
    const last = events![events!.length - 1][0] as Record<string, unknown>
    expect(last.entity_type).toBe('company_profiles')
    // page reset à 1 lors d'un changement de filtre
    expect(last.page).toBe(1)
  })

  it('Réinitialiser remet tous les filtres à null', async () => {
    const w = mount(AuditFilters, {
      props: {
        modelValue: {
          page: 1,
          limit: 50,
          order: 'desc' as const,
          entity_type: 'company_profiles',
          source_of_change: 'llm' as const,
        },
      },
    })
    await w.find('button').trigger('click')

    const events = w.emitted('update:modelValue')
    expect(events).toBeTruthy()
    const last = events![events!.length - 1][0] as Record<string, unknown>
    expect(last.entity_type).toBeNull()
    expect(last.source_of_change).toBeNull()
  })
})

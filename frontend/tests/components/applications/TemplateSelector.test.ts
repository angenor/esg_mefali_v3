import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import TemplateSelector from '~/components/applications/TemplateSelector.vue'
import type { TemplateRead } from '~/types/template'

function makeTemplate(overrides: Partial<TemplateRead> = {}): TemplateRead {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    name: 'Template fallback subvention (FR)',
    offer_id: null,
    instrument_type: 'subvention',
    language: 'fr',
    sections: [
      {
        key: 'intro',
        title: 'Introduction',
        instructions: 'x',
        target_length: 200,
        required: true,
      },
    ],
    required_documents: [],
    tone: 'formel',
    vocabulary_hints: null,
    anti_patterns: null,
    skill_id: '22222222-2222-2222-2222-222222222222',
    source_id: '33333333-3333-3333-3333-333333333333',
    version: '1.0',
    valid_from: '2026-01-01',
    valid_to: null,
    superseded_by: null,
    status: 'published',
    captured_by: '44444444-4444-4444-4444-444444444444',
    verified_by: '55555555-5555-5555-5555-555555555555',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('TemplateSelector', () => {
  it('renders template name and metadata', () => {
    const tmpl = makeTemplate()
    const wrapper = mount(TemplateSelector, {
      props: { modelValue: null, templates: [tmpl] },
    })
    expect(wrapper.text()).toContain('Template fallback subvention')
    expect(wrapper.text()).toContain('Subvention')
    expect(wrapper.text()).toContain('Français')
    expect(wrapper.text()).toContain('v1.0')
    expect(wrapper.text()).toContain('1 sections')
  })

  it('emits update:modelValue when a template is selected', async () => {
    const tmpl = makeTemplate()
    const wrapper = mount(TemplateSelector, {
      props: { modelValue: null, templates: [tmpl] },
    })
    await wrapper.find('input[type="radio"]').setValue(true)
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([tmpl.id])
  })

  it('shows empty state with admin-request CTA', async () => {
    const wrapper = mount(TemplateSelector, {
      props: { modelValue: null, templates: [] },
    })
    expect(wrapper.text()).toContain('Aucun modèle publié')
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('request-template')).toBeTruthy()
  })

  it('shows error state when error prop is set', () => {
    const wrapper = mount(TemplateSelector, {
      props: {
        modelValue: null,
        templates: [],
        error: 'Erreur réseau',
      },
    })
    expect(wrapper.text()).toContain('Erreur réseau')
  })

  it('shows loading state', () => {
    const wrapper = mount(TemplateSelector, {
      props: { modelValue: null, templates: [], loading: true },
    })
    expect(wrapper.text()).toContain('Chargement')
  })

  it('uses ARIA radiogroup role', () => {
    const tmpl = makeTemplate()
    const wrapper = mount(TemplateSelector, {
      props: { modelValue: null, templates: [tmpl] },
    })
    expect(wrapper.find('[role="radiogroup"]').exists()).toBe(true)
    expect(wrapper.find('[role="region"]').exists()).toBe(true)
  })
})

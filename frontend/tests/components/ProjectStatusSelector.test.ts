import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectStatusSelector from '~/components/projects/ProjectStatusSelector.vue'

describe('ProjectStatusSelector (F06)', () => {
  it('affiche le label du statut courant', () => {
    const wrapper = mount(ProjectStatusSelector, {
      props: { modelValue: 'draft' },
    })
    expect(wrapper.text()).toContain('Brouillon')
  })

  it('a role combobox + aria-expanded false initial', () => {
    const wrapper = mount(ProjectStatusSelector, {
      props: { modelValue: 'draft' },
    })
    const button = wrapper.find('button[role="combobox"]')
    expect(button.exists()).toBe(true)
    expect(button.attributes('aria-expanded')).toBe('false')
    expect(button.attributes('aria-haspopup')).toBe('listbox')
  })

  it('ouvre la liste au clic', async () => {
    const wrapper = mount(ProjectStatusSelector, {
      props: { modelValue: 'draft' },
    })
    await wrapper.find('button[role="combobox"]').trigger('click')
    const listbox = wrapper.find('ul[role="listbox"]')
    expect(listbox.exists()).toBe(true)
    expect(wrapper.find('button[role="combobox"]').attributes('aria-expanded')).toBe(
      'true',
    )
  })

  it('emit update:modelValue à la sélection', async () => {
    const wrapper = mount(ProjectStatusSelector, {
      props: { modelValue: 'draft' },
    })
    await wrapper.find('button[role="combobox"]').trigger('click')
    const options = wrapper.findAll('li[role="option"]')
    const fundedOption = options.find((o) => o.text() === 'Financé')
    expect(fundedOption).toBeDefined()
    await fundedOption!.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual(['funded'])
  })

  it('liste 6 options par défaut', async () => {
    const wrapper = mount(ProjectStatusSelector, {
      props: { modelValue: 'draft' },
    })
    await wrapper.find('button[role="combobox"]').trigger('click')
    expect(wrapper.findAll('li[role="option"]').length).toBe(6)
  })

  it('libellés français', async () => {
    const wrapper = mount(ProjectStatusSelector, {
      props: { modelValue: 'draft' },
    })
    await wrapper.find('button[role="combobox"]').trigger('click')
    const text = wrapper.text()
    expect(text).toContain('Brouillon')
    expect(text).toContain('En recherche de financement')
    expect(text).toContain('Financé')
    expect(text).toContain('En exécution')
    expect(text).toContain('Annulé')
  })

  it('classes dark: présentes', () => {
    const wrapper = mount(ProjectStatusSelector, {
      props: { modelValue: 'draft' },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-input')
    expect(html).toContain('dark:text-surface-dark-text')
    expect(html).toContain('dark:border-dark-border')
  })

  it('disabled attribute respecté', () => {
    const wrapper = mount(ProjectStatusSelector, {
      props: { modelValue: 'draft', disabled: true },
    })
    expect(
      wrapper.find('button[role="combobox"]').attributes('disabled'),
    ).toBeDefined()
  })
})

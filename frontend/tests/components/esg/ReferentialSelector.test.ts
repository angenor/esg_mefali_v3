import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ReferentialSelector from '~/components/esg/ReferentialSelector.vue'

describe('ReferentialSelector', () => {
  const options = [
    { code: 'mefali', name: 'ESG Mefali', version: '1.0' },
    { code: 'ifc_ps', name: 'IFC Performance Standards 2012', version: '1.0' },
  ]

  it('renders all options', () => {
    const wrapper = mount(ReferentialSelector, {
      props: { options, modelValue: 'mefali' },
    })
    const optionEls = wrapper.findAll('option')
    expect(optionEls).toHaveLength(2)
    expect(optionEls[0]?.text()).toContain('ESG Mefali')
    expect(optionEls[1]?.text()).toContain('IFC')
  })

  it('emits update:modelValue when selecting another option', async () => {
    const wrapper = mount(ReferentialSelector, {
      props: { options, modelValue: 'mefali' },
    })
    const select = wrapper.find('select')
    await select.setValue('ifc_ps')
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted![0]).toEqual(['ifc_ps'])
  })

  it('is disabled when disabled=true', () => {
    const wrapper = mount(ReferentialSelector, {
      props: { options, modelValue: 'mefali', disabled: true },
    })
    const select = wrapper.find('select')
    expect(select.attributes('disabled')).toBeDefined()
  })

  it('has ARIA role listbox on select and option role', () => {
    const wrapper = mount(ReferentialSelector, {
      props: { options, modelValue: 'mefali' },
    })
    const select = wrapper.find('select')
    expect(select.attributes('role')).toBe('listbox')
    const opt = wrapper.find('option')
    expect(opt.attributes('role')).toBe('option')
  })

  it('applies dark mode classes', () => {
    const wrapper = mount(ReferentialSelector, {
      props: { options, modelValue: 'mefali' },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-input')
    expect(html).toContain('dark:text-surface-dark-text')
  })
})

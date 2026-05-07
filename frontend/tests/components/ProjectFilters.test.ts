import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectFilters from '~/components/projects/ProjectFilters.vue'
import type { ProjectFilters as Filters } from '~/types/project'

describe('ProjectFilters (F06)', () => {
  it('role search présent', () => {
    const wrapper = mount(ProjectFilters, {
      props: { modelValue: { page: 1, limit: 25 } as Filters },
    })
    expect(wrapper.find('[role="search"]').exists()).toBe(true)
  })

  it('emit update:modelValue au changement de status', async () => {
    const wrapper = mount(ProjectFilters, {
      props: { modelValue: { page: 1, limit: 25 } as Filters },
    })
    const select = wrapper.find('#filter-status')
    await select.setValue('seeking_funding')
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect(events![0][0]).toMatchObject({ status: 'seeking_funding' })
  })

  it('reset effacé filtres', async () => {
    const wrapper = mount(ProjectFilters, {
      props: {
        modelValue: { status: 'draft', page: 1, limit: 25 } as Filters,
      },
    })
    const buttons = wrapper.findAll('button')
    const resetBtn = buttons.find((b) => b.text() === 'Réinitialiser')
    expect(resetBtn).toBeDefined()
    await resetBtn!.trigger('click')
    const events = wrapper.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect(events![events!.length - 1][0]).toMatchObject({
      page: 1,
      limit: 25,
    })
  })

  it('classes dark: présentes', () => {
    const wrapper = mount(ProjectFilters, {
      props: { modelValue: { page: 1, limit: 25 } as Filters },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-card')
    expect(html).toContain('dark:border-dark-border')
  })
})

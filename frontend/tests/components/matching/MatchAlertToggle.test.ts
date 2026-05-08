import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MatchAlertToggle from '~/components/matching/MatchAlertToggle.vue'

describe('MatchAlertToggle (F14)', () => {
  it('rend le switch désactivé quand subscription null', () => {
    const wrapper = mount(MatchAlertToggle, {
      props: { subscription: null },
    })
    const sw = wrapper.find('button[role="switch"]')
    expect(sw.attributes('aria-checked')).toBe('false')
    expect(wrapper.attributes('data-testid')).toBe('match-alert-toggle')
  })

  it('rend le switch activé quand subscription active', () => {
    const wrapper = mount(MatchAlertToggle, {
      props: {
        subscription: {
          id: 's-1',
          projectId: 'p-1',
          minGlobalScore: 60,
          isActive: true,
        },
      },
    })
    const sw = wrapper.find('button[role="switch"]')
    expect(sw.attributes('aria-checked')).toBe('true')
  })

  it('émet toggle au clic', async () => {
    const wrapper = mount(MatchAlertToggle, {
      props: {
        subscription: {
          id: 's-1',
          projectId: 'p-1',
          minGlobalScore: 60,
          isActive: false,
        },
      },
    })
    await wrapper.find('button[role="switch"]').trigger('click')
    expect(wrapper.emitted('toggle')).toBeTruthy()
    expect(wrapper.emitted('toggle')?.[0]?.[0]).toBe(true)
  })

  it('affiche le slider de seuil quand actif', () => {
    const wrapper = mount(MatchAlertToggle, {
      props: {
        subscription: {
          id: 's-1',
          projectId: 'p-1',
          minGlobalScore: 75,
          isActive: true,
        },
      },
    })
    expect(wrapper.find('input[type="range"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('75')
  })

  it('émet update-threshold au change du slider', async () => {
    const wrapper = mount(MatchAlertToggle, {
      props: {
        subscription: {
          id: 's-1',
          projectId: 'p-1',
          minGlobalScore: 60,
          isActive: true,
        },
      },
    })
    const input = wrapper.find('input[type="range"]')
    await input.setValue('80')
    await input.trigger('change')
    expect(wrapper.emitted('update-threshold')).toBeTruthy()
    expect(wrapper.emitted('update-threshold')?.[0]?.[0]).toBe(80)
  })

  it('aria-label change selon état', () => {
    const wrapper = mount(MatchAlertToggle, {
      props: {
        subscription: {
          id: 's-1',
          projectId: 'p-1',
          minGlobalScore: 60,
          isActive: true,
        },
      },
    })
    const aria = wrapper.find('button[role="switch"]').attributes('aria-label') ?? ''
    expect(aria).toContain('désactiver')
  })

  it('disabled quand loading', () => {
    const wrapper = mount(MatchAlertToggle, {
      props: { subscription: null, loading: true },
    })
    const sw = wrapper.find('button[role="switch"]')
    expect(sw.attributes('disabled')).toBeDefined()
  })

  it('expose dark mode', () => {
    const wrapper = mount(MatchAlertToggle, {
      props: { subscription: null },
    })
    expect(wrapper.html()).toMatch(/dark:/)
  })
})

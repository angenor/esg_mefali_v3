import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SourceLink from '~/components/sources/SourceLink.vue'

/**
 * F01 — Tests SourceLink.vue (picto cliquable inline).
 */
describe('SourceLink', () => {
  it('rend le bouton si sourceId est fourni', () => {
    const wrapper = mount(SourceLink, { props: { sourceId: 'abc-123' } })
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it("ne rend rien si sourceId est null", () => {
    const wrapper = mount(SourceLink, { props: { sourceId: null } })
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it("emet 'open' au clic avec l'identifiant", async () => {
    const wrapper = mount(SourceLink, { props: { sourceId: 'abc-123' } })
    await wrapper.find('button').trigger('click')
    const events = wrapper.emitted('open')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['abc-123'])
  })

  it('utilise un aria-label par defaut explicite', () => {
    const wrapper = mount(SourceLink, { props: { sourceId: 'abc' } })
    const btn = wrapper.find('button')
    expect(btn.attributes('aria-label')).toContain('source')
  })

  it("respecte un aria-label personnalise", () => {
    const wrapper = mount(SourceLink, {
      props: { sourceId: 'abc', ariaLabel: 'Voir source ADEME' },
    })
    expect(wrapper.find('button').attributes('aria-label')).toBe('Voir source ADEME')
  })

  it("utilise dark: classes Tailwind", () => {
    const wrapper = mount(SourceLink, { props: { sourceId: 'abc' } })
    const cls = wrapper.find('button').classes().join(' ')
    expect(cls).toContain('dark:text-gray-400')
    expect(cls).toContain('dark:hover:text-blue-400')
  })
})

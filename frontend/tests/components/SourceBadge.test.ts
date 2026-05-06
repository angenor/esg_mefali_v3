import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SourceBadge from '~/components/sources/SourceBadge.vue'

/**
 * F01 — Tests SourceBadge.vue (statut visuel d'une source).
 */
describe('SourceBadge', () => {
  it('affiche "Verifiee" pour le statut verified', () => {
    const wrapper = mount(SourceBadge, { props: { status: 'verified' } })
    expect(wrapper.text()).toContain('Verifiee')
  })

  it('affiche "En attente" pour le statut pending', () => {
    const wrapper = mount(SourceBadge, { props: { status: 'pending' } })
    expect(wrapper.text()).toContain('En attente')
  })

  it('affiche "Obsolete" pour le statut outdated', () => {
    const wrapper = mount(SourceBadge, { props: { status: 'outdated' } })
    expect(wrapper.text()).toContain('Obsolete')
  })

  it('affiche la raison pour le statut outdated', () => {
    const wrapper = mount(SourceBadge, {
      props: { status: 'outdated', reason: 'Nouvelle version 2025' },
    })
    expect(wrapper.text()).toContain('Nouvelle version 2025')
  })

  it('utilise une couleur verte pour verified (light + dark)', () => {
    const wrapper = mount(SourceBadge, { props: { status: 'verified' } })
    const cls = wrapper.find('span').classes().join(' ')
    expect(cls).toContain('bg-green-100')
    expect(cls).toContain('dark:bg-green-900/30')
  })

  it('utilise une couleur orange pour pending (light + dark)', () => {
    const wrapper = mount(SourceBadge, { props: { status: 'pending' } })
    const cls = wrapper.find('span').classes().join(' ')
    expect(cls).toContain('bg-orange-100')
    expect(cls).toContain('dark:bg-orange-900/30')
  })

  it('utilise une couleur rouge pour outdated (light + dark)', () => {
    const wrapper = mount(SourceBadge, { props: { status: 'outdated' } })
    const cls = wrapper.find('span').classes().join(' ')
    expect(cls).toContain('bg-red-100')
    expect(cls).toContain('dark:bg-red-900/30')
  })

  it('le pictogramme circulaire est marque aria-hidden', () => {
    const wrapper = mount(SourceBadge, { props: { status: 'verified' } })
    const dot = wrapper.findAll('span > span').at(0)
    expect(dot?.attributes('aria-hidden')).toBe('true')
  })
})

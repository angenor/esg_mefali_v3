/**
 * F25 — Tests du composant `SuccessorBanner.vue`.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SuccessorBanner from '~/components/admin/catalog/SuccessorBanner.vue'

describe('SuccessorBanner (F25)', () => {
  it('rendu vide si successorId null et brokenChain=false', () => {
    const wrapper = mount(SuccessorBanner, {
      props: { successorId: null, basePath: '/admin/catalog/funds' },
      global: {
        stubs: { NuxtLink: { template: '<a><slot /></a>' } },
      },
    })
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('rendu actif avec successorId et NuxtLink vers basePath/id', () => {
    const wrapper = mount(SuccessorBanner, {
      props: {
        successorId: 'fund-v2',
        basePath: '/admin/catalog/funds',
        ctaLabel: 'Voir le fonds successeur',
        currentVersion: '1.0',
      },
      global: {
        stubs: { NuxtLink: { template: '<a :data-to="$attrs.to"><slot /></a>' } },
      },
    })
    const link = wrapper.find('a')
    expect(link.exists()).toBe(true)
    expect(link.attributes('data-to')).toBe('/admin/catalog/funds/fund-v2')
    expect(wrapper.text()).toContain('Version 1.0')
  })

  it('affiche un message "chaîne rompue" si brokenChain=true', () => {
    const wrapper = mount(SuccessorBanner, {
      props: {
        successorId: 'lost-id',
        basePath: '/admin/catalog/funds',
        brokenChain: true,
      },
      global: {
        stubs: { NuxtLink: { template: '<a><slot /></a>' } },
      },
    })
    expect(wrapper.text()).toContain('Chaîne rompue')
    // Pas de bouton CTA quand la chaîne est rompue.
    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('classes amber + dark mode présentes', () => {
    const wrapper = mount(SuccessorBanner, {
      props: { successorId: 'a', basePath: '/admin/catalog/funds' },
      global: {
        stubs: { NuxtLink: { template: '<a><slot /></a>' } },
      },
    })
    const html = wrapper.html()
    expect(html).toContain('border-amber-300')
    expect(html).toContain('dark:border-amber-700')
  })
})

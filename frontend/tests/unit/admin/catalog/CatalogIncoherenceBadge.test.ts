/**
 * F25 — Tests du composant `CatalogIncoherenceBadge.vue`.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CatalogIncoherenceBadge from '~/components/admin/catalog/CatalogIncoherenceBadge.vue'

describe('CatalogIncoherenceBadge (F25)', () => {
  it('affiche le badge avec aria-label par défaut', () => {
    const wrapper = mount(CatalogIncoherenceBadge)
    expect(wrapper.attributes('aria-label')).toBe('Incohérence détectée')
    expect(wrapper.attributes('title')).toContain('incohérence')
  })

  it('accepte un tooltip personnalisé', () => {
    const wrapper = mount(CatalogIncoherenceBadge, {
      props: { tooltip: 'Publié sans source F01' },
    })
    expect(wrapper.attributes('title')).toBe('Publié sans source F01')
  })

  it('classes amber + dark mode présentes', () => {
    const wrapper = mount(CatalogIncoherenceBadge)
    const html = wrapper.html()
    expect(html).toContain('bg-amber-100')
    expect(html).toContain('dark:bg-amber-900/40')
  })
})

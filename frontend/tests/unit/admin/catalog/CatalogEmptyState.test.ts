/**
 * F25 — Tests du composant `CatalogEmptyState.vue`.
 * Couvre les 2 modes ("empty" et "no-match"), l'émission de `reset` et
 * l'inclusion de la query dans le message d'erreur.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CatalogEmptyState from '~/components/admin/catalog/CatalogEmptyState.vue'

describe('CatalogEmptyState (F25)', () => {
  it('mode empty : affiche le message "Aucun élément enregistré"', () => {
    const wrapper = mount(CatalogEmptyState, { props: { mode: 'empty', label: 'fonds' } })
    expect(wrapper.text()).toContain('Aucun')
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
    // Pas de bouton "Réinitialiser" en mode empty.
    expect(wrapper.findAll('button').length).toBe(0)
  })

  it('mode no-match : affiche le bouton Réinitialiser', async () => {
    const wrapper = mount(CatalogEmptyState, {
      props: { mode: 'no-match', query: 'GCF' },
    })
    expect(wrapper.text()).toContain('Aucun résultat')
    expect(wrapper.text()).toContain('GCF')
    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    expect(wrapper.emitted('reset')).toBeTruthy()
  })

  it('classes dark mode présentes', () => {
    const wrapper = mount(CatalogEmptyState, { props: { mode: 'empty' } })
    expect(wrapper.html()).toContain('dark:bg-dark-card')
  })

  it('mode no-match sans query : message générique', () => {
    const wrapper = mount(CatalogEmptyState, {
      props: { mode: 'no-match', query: null },
    })
    expect(wrapper.text()).toContain('Aucun résultat ne correspond aux filtres')
  })
})

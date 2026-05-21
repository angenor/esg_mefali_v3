/**
 * F25 — Tests du composant `CatalogToolbar.vue`.
 * Couvre l'émission des événements (search, publication-status, status,
 * sort, export, reset) et la sensibilité à l'onglet courant (le filtre
 * statut publication est masqué pour `fund_intermediaries`).
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CatalogToolbar from '~/components/admin/catalog/CatalogToolbar.vue'

describe('CatalogToolbar (F25)', () => {
  const defaultProps = {
    tab: 'funds' as const,
    query: '',
    publicationStatus: null,
    status: 'all' as const,
    sort: 'updated_at_desc',
    total: 5,
    filteredCount: 5,
  }

  it('input recherche émet update:query', async () => {
    const wrapper = mount(CatalogToolbar, { props: defaultProps })
    const input = wrapper.find('input[type="search"]')
    await input.setValue('GCF')
    expect(wrapper.emitted('update:query')).toBeTruthy()
    expect(wrapper.emitted('update:query')![0][0]).toBe('GCF')
  })

  it('select statut émet update:publicationStatus avec la bonne valeur', async () => {
    const wrapper = mount(CatalogToolbar, { props: defaultProps })
    const select = wrapper.find('select[aria-label="Filtre statut de publication"]')
    expect(select.exists()).toBe(true)
    await (select.element as HTMLSelectElement).dispatchEvent(new Event('change'))
    await select.setValue('draft')
    const evts = wrapper.emitted('update:publicationStatus')
    expect(evts).toBeTruthy()
    expect(evts!.at(-1)![0]).toBe('draft')
  })

  it("masque le filtre statut publication sur l'onglet liaisons", () => {
    const wrapper = mount(CatalogToolbar, {
      props: { ...defaultProps, tab: 'fund_intermediaries' },
    })
    expect(
      wrapper.find('select[aria-label="Filtre statut de publication"]').exists(),
    ).toBe(false)
    expect(
      wrapper.find('select[aria-label="Filtre état d\'accréditation"]').exists(),
    ).toBe(true)
  })

  it('select tri émet update:sort', async () => {
    const wrapper = mount(CatalogToolbar, { props: defaultProps })
    const sortSelect = wrapper.find('select[aria-label="Tri"]')
    await sortSelect.setValue('version_desc')
    const evts = wrapper.emitted('update:sort')
    expect(evts).toBeTruthy()
    expect(evts!.at(-1)![0]).toBe('version_desc')
  })

  it('bouton Réinitialiser émet reset', async () => {
    const wrapper = mount(CatalogToolbar, { props: defaultProps })
    const buttons = wrapper.findAll('button')
    const resetBtn = buttons.find((b) => b.text().includes('Réinitialiser'))
    expect(resetBtn).toBeDefined()
    await resetBtn!.trigger('click')
    expect(wrapper.emitted('reset')).toBeTruthy()
  })

  it('bouton Exporter CSV émet export', async () => {
    const wrapper = mount(CatalogToolbar, { props: defaultProps })
    const buttons = wrapper.findAll('button')
    const exportBtn = buttons.find((b) => b.text().includes('Exporter'))
    expect(exportBtn).toBeDefined()
    await exportBtn!.trigger('click')
    expect(wrapper.emitted('export')).toBeTruthy()
  })

  it('classes dark mode présentes', () => {
    const wrapper = mount(CatalogToolbar, { props: defaultProps })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-card')
    expect(html).toContain('dark:border-dark-border')
  })
})

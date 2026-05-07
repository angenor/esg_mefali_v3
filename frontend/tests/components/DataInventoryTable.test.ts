import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import DataInventoryTable from '~/components/DataInventoryTable.vue'
import type {
  InventoryCounts,
  InventoryLastModified,
} from '~/composables/useDataPrivacy'

const COUNTS: InventoryCounts = {
  profile: 1,
  projects: 3,
  applications: 5,
  esg_assessments: 2,
  carbon_assessments: 1,
  credit_scores: 1,
  documents: 12,
  conversations: 8,
  messages: 142,
  attestations: 1,
  consents: 7,
}

const LAST_MODIFIED: InventoryLastModified = {
  profile: '2026-04-22T10:14:33Z',
  projects: '2026-05-01T08:22:11Z',
  applications: null,
  esg_assessments: null,
  carbon_assessments: null,
  credit_scores: null,
  documents: null,
  conversations: null,
  messages: null,
  attestations: null,
  consents: null,
}

describe('DataInventoryTable', () => {
  it('rend les 11 catégories', () => {
    const wrapper = mount(DataInventoryTable, {
      props: { counts: COUNTS, lastModified: LAST_MODIFIED },
    })
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(11)
  })

  it('affiche les compteurs', () => {
    const wrapper = mount(DataInventoryTable, {
      props: { counts: COUNTS, lastModified: LAST_MODIFIED },
    })
    expect(wrapper.text()).toContain('142') // messages
    expect(wrapper.text()).toContain('12') // documents
    expect(wrapper.text()).toContain('Profil entreprise')
  })

  it('affiche — pour les dates absentes', () => {
    const wrapper = mount(DataInventoryTable, {
      props: { counts: COUNTS, lastModified: LAST_MODIFIED },
    })
    expect(wrapper.text()).toContain('—')
  })

  it('a le bon role et aria-label', () => {
    const wrapper = mount(DataInventoryTable, {
      props: { counts: COUNTS, lastModified: LAST_MODIFIED },
    })
    const region = wrapper.find('[role="region"]')
    expect(region.exists()).toBe(true)
    expect(region.attributes('aria-label')).toBe('Inventaire de mes données')
  })

  it('contient les classes dark mode', () => {
    const wrapper = mount(DataInventoryTable, {
      props: { counts: COUNTS, lastModified: LAST_MODIFIED },
    })
    expect(wrapper.html()).toContain('dark:bg-dark-card')
    expect(wrapper.html()).toContain('dark:divide-dark-border')
  })
})

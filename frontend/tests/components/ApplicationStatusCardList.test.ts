import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ApplicationStatusCardList from '~/components/dashboard/ApplicationStatusCardList.vue'
import type { ApplicationCard } from '~/types/dashboard'

function makeCard(id: string): ApplicationCard {
  return {
    application_id: id,
    offer_id: null,
    fund_name: `Fund-${id}`,
    intermediary_name: 'Accès direct',
    fund_logo_url: null,
    intermediary_logo_url: null,
    status: 'preparing_documents',
    current_step: 'Préparation des documents',
    next_deadline: null,
    next_reminder: null,
    last_activity_at: '2026-05-08T00:00:00+00:00',
  }
}

describe('ApplicationStatusCardList (F21 US1)', () => {
  it('affiche état vide quand aucune card', () => {
    const w = mount(ApplicationStatusCardList, {
      props: { cards: [], totalActive: 0 },
      global: { stubs: ['NuxtLink', 'ApplicationStatusCard'] },
    })
    expect(w.find('[data-testid="applications-empty-state"]').exists()).toBe(true)
    expect(w.text()).toContain("Vous n'avez pas encore de candidature")
  })

  it('rend chaque card', () => {
    const w = mount(ApplicationStatusCardList, {
      props: {
        cards: [makeCard('a'), makeCard('b'), makeCard('c')],
        totalActive: 3,
      },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.findAll('[data-testid^="application-card-"]').length).toBe(3)
  })

  it('affiche lien « Voir toutes » quand totalActive > cards.length', () => {
    const w = mount(ApplicationStatusCardList, {
      props: {
        cards: [makeCard('a'), makeCard('b'), makeCard('c'), makeCard('d'), makeCard('e')],
        totalActive: 8,
      },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.find('[data-testid="applications-see-all-link"]').exists()).toBe(true)
  })

  it('expose le compteur', () => {
    const w = mount(ApplicationStatusCardList, {
      props: { cards: [makeCard('a')], totalActive: 1 },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.find('[data-testid="applications-counter"]').text()).toContain('1 active')
  })
})

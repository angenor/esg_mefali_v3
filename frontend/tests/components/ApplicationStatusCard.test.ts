import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ApplicationStatusCard from '~/components/dashboard/ApplicationStatusCard.vue'
import type { ApplicationCard } from '~/types/dashboard'

function makeCard(overrides: Partial<ApplicationCard> = {}): ApplicationCard {
  return {
    application_id: 'aaaa-1111',
    offer_id: 'offer-1',
    fund_name: 'GCF',
    intermediary_name: 'BOAD',
    fund_logo_url: null,
    intermediary_logo_url: null,
    status: 'submitted_to_intermediary',
    current_step: 'Instruction par BOAD',
    next_deadline: '2026-12-31',
    next_reminder: null,
    last_activity_at: '2026-05-08T00:00:00+00:00',
    ...overrides,
  }
}

describe('ApplicationStatusCard (F21 US1)', () => {
  it('rend nom du fonds et de l\'intermédiaire', () => {
    const w = mount(ApplicationStatusCard, {
      props: { card: makeCard() },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.text()).toContain('GCF')
    expect(w.text()).toContain('BOAD')
  })

  it('affiche libellé d\'étape FR', () => {
    const w = mount(ApplicationStatusCard, {
      props: { card: makeCard({ current_step: 'Instruction par BOAD' }) },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.text()).toContain('Instruction par BOAD')
  })

  it('formate la deadline en DD/MM/YYYY', () => {
    const w = mount(ApplicationStatusCard, {
      props: { card: makeCard({ next_deadline: '2026-12-31' }) },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.text()).toContain('31/12/2026')
  })

  it('affiche « Aucune échéance » quand deadline=null', () => {
    const w = mount(ApplicationStatusCard, {
      props: { card: makeCard({ next_deadline: null }) },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.text()).toContain('Aucune échéance')
  })

  it('expose les data-testid pour Playwright', () => {
    const w = mount(ApplicationStatusCard, {
      props: { card: makeCard() },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.find('[data-testid="application-status-badge"]').exists()).toBe(true)
    expect(w.find('[data-testid="application-deadline"]').exists()).toBe(true)
    expect(w.find('[data-testid="application-detail-link"]').exists()).toBe(true)
  })

  it('le lien détail pointe vers /applications/{id}', () => {
    const w = mount(ApplicationStatusCard, {
      props: { card: makeCard({ application_id: 'app-42' }) },
      global: { stubs: { NuxtLink: { template: '<a :href="to"><slot /></a>', props: ['to'] } } },
    })
    expect(w.html()).toContain('/applications/app-42')
  })

  it('classes dark mode présentes', () => {
    const w = mount(ApplicationStatusCard, {
      props: { card: makeCard() },
      global: { stubs: ['NuxtLink'] },
    })
    expect(w.html()).toContain('dark:bg-dark-card')
    expect(w.html()).toContain('dark:border-dark-border')
  })
})

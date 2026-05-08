import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import SimulationDetailedCard from '~/components/financing/SimulationDetailedCard.vue'
import type { SimulationResult } from '~/types/simulator'

function makeResult(overrides: Partial<SimulationResult> = {}): SimulationResult {
  const baseSource = '00000000-0000-0000-0000-000000000001'
  return {
    offer_id: 'offer-1234567890',
    project_id: 'project-1',
    principal: { amount: '5000000.00', currency: 'XOF' },
    principal_pme_equivalent: null,
    cost_breakdown: {
      principal: { amount: '5000000.00', currency: 'XOF' },
      doc_fee: {
        amount: { amount: '50000.00', currency: 'XOF' },
        amount_pme_equivalent: null,
        source_id: baseSource,
        factor_name: 'default_doc_fee_rate',
        factor_status: 'verified',
        degraded_reason: null,
      },
      total_fees_over_duration: {
        amount: { amount: '500000.00', currency: 'XOF' },
        amount_pme_equivalent: null,
        source_id: baseSource,
        factor_name: 'default_loan_rate',
        factor_status: 'verified',
        degraded_reason: null,
      },
      guarantee_required: {
        amount: { amount: '500000.00', currency: 'XOF' },
        amount_pme_equivalent: null,
        source_id: baseSource,
        factor_name: 'default_guarantee_rate',
        factor_status: 'verified',
        degraded_reason: null,
      },
      fx_margin: {
        amount: { amount: '0', currency: 'XOF' },
        amount_pme_equivalent: null,
        source_id: null,
        factor_name: 'default_fx_margin_rate',
        factor_status: null,
        degraded_reason: null,
      },
      total_cost: { amount: '5550000.00', currency: 'XOF' },
    },
    roi: {
      instrument: 'pret_concessionnel',
      formula_id: 'roi.loan.gain_minus_cost_ratio',
      gain_estimated: { amount: '750000.00', currency: 'XOF' },
      payback_months: 60,
      ratio: '0.135',
      notes_fr: 'Ratio gains estimés / coût total.',
      sources: [baseSource],
    },
    carbon_impact: {
      tco2e_per_year: '12.4',
      sector_factor: '1.0',
      factor_source_id: baseSource,
      project_estimate_used: '12.4',
      is_approximate: false,
      degraded_reason: null,
    },
    timeline: [
      {
        step_id: 'preparation',
        label_fr: 'Préparation du dossier',
        weeks_min: null,
        weeks_max: null,
        source_id: null,
        degraded_reason: 'effort_pme_non_facteur_catalogue',
      },
      {
        step_id: 'instruction_intermediaire',
        label_fr: "Instruction par l'intermédiaire",
        weeks_min: 4,
        weeks_max: 8,
        source_id: baseSource,
        degraded_reason: null,
      },
      {
        step_id: 'validation_fonds',
        label_fr: 'Validation par le fonds',
        weeks_min: 12,
        weeks_max: 24,
        source_id: baseSource,
        degraded_reason: null,
      },
      {
        step_id: 'decaissement',
        label_fr: 'Décaissement des fonds',
        weeks_min: 2,
        weeks_max: 4,
        source_id: baseSource,
        degraded_reason: null,
      },
    ],
    sources_used: [baseSource],
    degraded: false,
    computed_at: '2026-05-08T00:00:00Z',
    kind: 'ok',
    ...overrides,
  } as SimulationResult
}

describe('SimulationDetailedCard (F16)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('rend les sections principales', () => {
    const wrapper = mount(SimulationDetailedCard, {
      props: { result: makeResult() },
    })
    expect(wrapper.text()).toContain('Simulation')
    expect(wrapper.text()).toContain('Coût total')
    expect(wrapper.text()).toContain("Retour sur investissement")
    expect(wrapper.text()).toContain('Impact carbone')
    expect(wrapper.text()).toContain('Timeline')
  })

  it('affiche le badge "Moins chère" quand isCheapest=true', () => {
    const wrapper = mount(SimulationDetailedCard, {
      props: { result: makeResult(), isCheapest: true },
    })
    expect(wrapper.text()).toContain('Moins chère')
  })

  it('affiche le badge "Plus rapide" quand isFastest=true', () => {
    const wrapper = mount(SimulationDetailedCard, {
      props: { result: makeResult(), isFastest: true },
    })
    expect(wrapper.text()).toContain('Plus rapide')
  })

  it('affiche un badge pending quand factor_status=pending', () => {
    const result = makeResult()
    result.cost_breakdown.doc_fee.factor_status = 'pending'
    const wrapper = mount(SimulationDetailedCard, {
      props: { result },
    })
    expect(wrapper.text()).toContain('en attente de vérification')
  })

  it('affiche "Délai non disponible" si une étape est dégradée', () => {
    const result = makeResult()
    result.timeline[1] = {
      ...result.timeline[1],
      weeks_min: null,
      weeks_max: null,
      degraded_reason: 'delai_intermediaire_non_renseigne',
    }
    const wrapper = mount(SimulationDetailedCard, {
      props: { result },
    })
    expect(wrapper.text()).toContain('Délai non disponible')
  })

  it('affiche "Impact non estimé" si tco2e_per_year est null', () => {
    const result = makeResult()
    result.carbon_impact.tco2e_per_year = null
    result.carbon_impact.degraded_reason = 'aucune_estimation_projet'
    const wrapper = mount(SimulationDetailedCard, {
      props: { result },
    })
    expect(wrapper.text()).toContain('Impact non estimé')
  })

  it('mappe instrument pret_concessionnel → libellé FR', () => {
    const wrapper = mount(SimulationDetailedCard, {
      props: { result: makeResult() },
    })
    expect(wrapper.text()).toContain('Prêt concessionnel')
  })

  it("émet 'open-source' au clic sur SourceLink", async () => {
    const wrapper = mount(SimulationDetailedCard, {
      props: { result: makeResult() },
    })
    const sourceButtons = wrapper.findAll('button[aria-label*="source"]')
    expect(sourceButtons.length).toBeGreaterThan(0)
    await sourceButtons[0].trigger('click')
    expect(wrapper.emitted('open-source')).toBeDefined()
  })
})

import { beforeEach } from 'vitest'

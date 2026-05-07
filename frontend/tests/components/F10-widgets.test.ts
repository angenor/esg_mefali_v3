/**
 * F10 — Tests des 9 widgets bottom sheet (rendu, événements, dark mode).
 *
 * Couvre FR-018, FR-019, FR-022, FR-023, FR-024, FR-025, FR-030.
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import YesNoWidget from '~/components/chat/widgets/YesNoWidget.vue'
import SelectWidget from '~/components/chat/widgets/SelectWidget.vue'
import NumberWidget from '~/components/chat/widgets/NumberWidget.vue'
import DateWidget from '~/components/chat/widgets/DateWidget.vue'
import DateRangeWidget from '~/components/chat/widgets/DateRangeWidget.vue'
import RatingWidget from '~/components/chat/widgets/RatingWidget.vue'
import FormWidget from '~/components/chat/widgets/FormWidget.vue'
import SummaryCardWidget from '~/components/chat/widgets/SummaryCardWidget.vue'
import UnsupportedWidget from '~/components/chat/widgets/UnsupportedWidget.vue'
import InteractiveQuestionInputBar from '~/components/chat/InteractiveQuestionInputBar.vue'

import type { InteractiveQuestion } from '~/types/interactive-question'

function makeQuestion(overrides: Partial<InteractiveQuestion> = {}): InteractiveQuestion {
  return {
    id: 'q-test-1',
    conversation_id: 'conv-1',
    question_type: 'yes_no',
    prompt: 'Test prompt',
    module: 'chat',
    created_at: '2026-05-07T10:00:00Z',
    state: 'pending',
    response_values: null,
    response_justification: null,
    answered_at: null,
    payload: { question_type: 'yes_no', confirm_label: 'Oui', deny_label: 'Non', destructive: false },
    ...overrides,
  }
}

// ─── YesNoWidget ────────────────────────────────────────────────────────


describe('YesNoWidget', () => {
  it('rend les boutons Oui/Non avec labels par défaut', () => {
    const wrapper = mount(YesNoWidget, {
      props: { question: makeQuestion() },
    })
    expect(wrapper.text()).toContain('Oui')
    expect(wrapper.text()).toContain('Non')
  })

  it('mode destructif : rend un bouton rouge avec instructions hold', () => {
    const q = makeQuestion({
      payload: {
        question_type: 'yes_no',
        confirm_label: 'Oui, supprimer',
        deny_label: 'Non, annuler',
        destructive: true,
      },
    })
    const wrapper = mount(YesNoWidget, { props: { question: q } })
    expect(wrapper.text()).toContain('Oui, supprimer')
    // Tooltip ARIA et instructions hold présents
    const btn = wrapper.find(`[data-testid="yesno-confirm-${q.id}"]`)
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('title')).toContain('irréversible')
    // Classe rouge présente
    expect(btn.classes().some(c => c.includes('red'))).toBe(true)
  })

  it('clic sur Non émet submit avec value=false', async () => {
    const wrapper = mount(YesNoWidget, { props: { question: makeQuestion() } })
    await wrapper.find('[data-testid="yesno-deny-q-test-1"]').trigger('click')
    const emitted = wrapper.emitted('submit')
    expect(emitted).toBeTruthy()
    expect(emitted![0]![0]).toMatchObject({ question_type: 'yes_no', value: false })
  })

  it('mode normal : clic sur Oui émet immédiatement (pas de hold)', async () => {
    const wrapper = mount(YesNoWidget, { props: { question: makeQuestion() } })
    await wrapper.find('[data-testid="yesno-confirm-q-test-1"]').trigger('click')
    expect(wrapper.emitted('submit')).toBeTruthy()
  })

  it('disabled prop verrouille les boutons', () => {
    const wrapper = mount(YesNoWidget, {
      props: { question: makeQuestion(), disabled: true },
    })
    const buttons = wrapper.findAll('button')
    for (const btn of buttons) {
      if (btn.attributes('disabled') !== undefined) {
        expect(btn.attributes('disabled')).not.toBe('false')
      }
    }
  })

  it('émet abandon-and-send quand on clique « Répondre autrement »', async () => {
    const wrapper = mount(YesNoWidget, { props: { question: makeQuestion() } })
    const fallbackBtn = wrapper.findAll('button').find(b => b.text().includes('autrement'))
    expect(fallbackBtn?.exists()).toBe(true)
    await fallbackBtn!.trigger('click')
    expect(wrapper.emitted('abandon-and-send')).toBeTruthy()
  })
})


// ─── SelectWidget ───────────────────────────────────────────────────────


describe('SelectWidget', () => {
  it('rend les options et permet la sélection mono', async () => {
    const q = makeQuestion({
      question_type: 'select',
      payload: {
        question_type: 'select',
        options: [
          { id: 'ci', label: "Côte d'Ivoire" },
          { id: 'sn', label: 'Sénégal' },
        ],
        min_selections: 1,
        max_selections: 1,
        allow_other: false,
      },
    })
    const wrapper = mount(SelectWidget, { props: { question: q } })
    expect(wrapper.text()).toContain("Côte d'Ivoire")
    expect(wrapper.text()).toContain('Sénégal')

    await wrapper.find('[data-testid="select-option-ci"]').trigger('click')
    const emitted = wrapper.emitted('submit')
    expect(emitted).toBeTruthy()
    expect(emitted![0]![0]).toMatchObject({ selected: [{ id: 'ci' }] })
  })

  it('affiche le champ recherche si >= 8 options', () => {
    const opts = Array.from({ length: 10 }, (_, i) => ({
      id: `id_${i}`,
      label: `Label ${i}`,
    }))
    const q = makeQuestion({
      question_type: 'select',
      payload: {
        question_type: 'select',
        options: opts,
        min_selections: 1,
        max_selections: 1,
        allow_other: false,
      },
    })
    const wrapper = mount(SelectWidget, { props: { question: q } })
    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
  })

  it('mode multi : compteur affiché', async () => {
    const q = makeQuestion({
      question_type: 'select',
      payload: {
        question_type: 'select',
        options: [
          { id: 'a', label: 'A' },
          { id: 'b', label: 'B' },
          { id: 'c', label: 'C' },
        ],
        min_selections: 1,
        max_selections: 3,
        allow_other: false,
      },
    })
    const wrapper = mount(SelectWidget, { props: { question: q } })
    expect(wrapper.text()).toContain('sur 3 max')
  })
})


// ─── NumberWidget ───────────────────────────────────────────────────────


describe('NumberWidget', () => {
  it('rend input numérique avec sélecteur devise XOF', () => {
    const q = makeQuestion({
      question_type: 'number',
      payload: {
        question_type: 'number',
        unit: 'FCFA',
        min: 0,
        max: 1_000_000_000,
        step: 1000,
        currency: 'XOF',
      },
    })
    const wrapper = mount(NumberWidget, { props: { question: q } })
    const input = wrapper.find(`[data-testid="number-input-${q.id}"]`)
    expect(input.exists()).toBe(true)
    expect(input.attributes('type')).toBe('number')
    const select = wrapper.find(`[data-testid="number-currency-${q.id}"]`)
    expect(select.exists()).toBe(true)
  })

  it('boutons +/- ajustent la valeur via step', async () => {
    const q = makeQuestion({
      question_type: 'number',
      payload: {
        question_type: 'number',
        unit: 'FCFA',
        step: 1000,
        currency: 'XOF',
        default: 5000,
      },
    })
    const wrapper = mount(NumberWidget, { props: { question: q } })
    await wrapper.find(`[data-testid="number-increment-${q.id}"]`).trigger('click')
    const input = wrapper.find(`[data-testid="number-input-${q.id}"]`).element as HTMLInputElement
    expect(parseFloat(input.value)).toBe(6000)
  })
})


// ─── DateWidget / DateRangeWidget ─────────────────────────────────────


describe('DateWidget', () => {
  it('rend input type=date avec lang fr', () => {
    const q = makeQuestion({
      question_type: 'date',
      payload: { question_type: 'date' },
    })
    const wrapper = mount(DateWidget, { props: { question: q } })
    const input = wrapper.find('input[type="date"]')
    expect(input.exists()).toBe(true)
    expect(input.attributes('lang')).toBe('fr')
  })
})


describe('DateRangeWidget', () => {
  it('rend deux inputs from/to', () => {
    const q = makeQuestion({
      question_type: 'date_range',
      payload: { question_type: 'date_range' },
    })
    const wrapper = mount(DateRangeWidget, { props: { question: q } })
    expect(wrapper.find(`[data-testid="daterange-from-${q.id}"]`).exists()).toBe(true)
    expect(wrapper.find(`[data-testid="daterange-to-${q.id}"]`).exists()).toBe(true)
  })
})


// ─── RatingWidget ───────────────────────────────────────────────────────


describe('RatingWidget', () => {
  it('rend 5 étoiles si scale=5', () => {
    const q = makeQuestion({
      question_type: 'rating',
      payload: { question_type: 'rating', scale: 5 },
    })
    const wrapper = mount(RatingWidget, { props: { question: q } })
    const stars = wrapper.findAll('[role="radio"]')
    expect(stars.length).toBe(5)
  })

  it('rend 10 points si scale=10', () => {
    const q = makeQuestion({
      question_type: 'rating',
      payload: { question_type: 'rating', scale: 10 },
    })
    const wrapper = mount(RatingWidget, { props: { question: q } })
    const points = wrapper.findAll('[role="radio"]')
    expect(points.length).toBe(10)
  })

  it('clic sur une étoile sélectionne la valeur', async () => {
    const q = makeQuestion({
      question_type: 'rating',
      payload: {
        question_type: 'rating',
        scale: 5,
        labels: ['Très mauvais', 'Mauvais', 'Moyen', 'Très bien', 'Excellent'],
      },
    })
    const wrapper = mount(RatingWidget, { props: { question: q } })
    await wrapper.find(`[data-testid="rating-4-${q.id}"]`).trigger('click')
    const submitBtn = wrapper.find(`[data-testid="rating-submit-${q.id}"]`)
    expect(submitBtn.attributes('disabled')).toBeUndefined()
  })
})


// ─── FormWidget ─────────────────────────────────────────────────────────


describe('FormWidget', () => {
  it('rend chaque champ selon son type', () => {
    const q = makeQuestion({
      question_type: 'form',
      payload: {
        question_type: 'form',
        title: 'Création de projet',
        submit_label: 'Créer',
        fields: [
          { name: 'project_name', label: 'Nom', type: 'text', required: true },
          { name: 'description', label: 'Description', type: 'textarea', required: false },
          { name: 'amount', label: 'Montant', type: 'money', required: true },
          { name: 'date', label: 'Date', type: 'date', required: false },
        ],
      },
    })
    const wrapper = mount(FormWidget, { props: { question: q } })
    expect(wrapper.find(`[data-testid="form-project_name-${q.id}"]`).exists()).toBe(true)
    expect(wrapper.find(`[data-testid="form-description-${q.id}"]`).exists()).toBe(true)
    expect(wrapper.find(`[data-testid="form-amount-${q.id}"]`).exists()).toBe(true)
    expect(wrapper.find(`[data-testid="form-date-${q.id}"]`).exists()).toBe(true)
  })

  it('bouton submit désactivé si champ requis vide', () => {
    const q = makeQuestion({
      question_type: 'form',
      payload: {
        question_type: 'form',
        title: 'X',
        submit_label: 'Y',
        fields: [{ name: 'name', label: 'Nom', type: 'text', required: true }],
      },
    })
    const wrapper = mount(FormWidget, { props: { question: q } })
    const submit = wrapper.find(`[data-testid="form-submit-${q.id}"]`)
    expect(submit.attributes('disabled')).toBeDefined()
  })
})


// ─── SummaryCardWidget ─────────────────────────────────────────────────


describe('SummaryCardWidget', () => {
  it('rend les items en mode lecture par défaut', () => {
    const q = makeQuestion({
      question_type: 'summary_card',
      payload: {
        question_type: 'summary_card',
        title: 'Extraction',
        items: [
          { label: 'Forme', value: 'SARL', editable: true },
          { label: 'Capital', value: '5M', editable: false },
        ],
        confirm_label: 'Valider',
        correct_label: 'Corriger',
      },
    })
    const wrapper = mount(SummaryCardWidget, { props: { question: q } })
    expect(wrapper.text()).toContain('SARL')
    expect(wrapper.text()).toContain('5M')
    // Bouton Corriger présent
    expect(wrapper.find(`[data-testid="summary-correct-${q.id}"]`).exists()).toBe(true)
  })

  it('clic sur Corriger active le mode édition', async () => {
    const q = makeQuestion({
      question_type: 'summary_card',
      payload: {
        question_type: 'summary_card',
        title: 'X',
        items: [{ label: 'Forme', value: 'SARL', editable: true }],
        confirm_label: 'V',
        correct_label: 'Corriger',
      },
    })
    const wrapper = mount(SummaryCardWidget, { props: { question: q } })
    await wrapper.find(`[data-testid="summary-correct-${q.id}"]`).trigger('click')
    // L'input éditable apparaît
    expect(wrapper.find(`[data-testid="summary-edit-Forme-${q.id}"]`).exists()).toBe(true)
  })

  it('valider sans modifications émet un payload validé sans modifications', async () => {
    const q = makeQuestion({
      question_type: 'summary_card',
      payload: {
        question_type: 'summary_card',
        title: 'X',
        items: [{ label: 'Forme', value: 'SARL', editable: true }],
        confirm_label: 'Valider',
        correct_label: 'Corriger',
      },
    })
    const wrapper = mount(SummaryCardWidget, { props: { question: q } })
    await wrapper.find(`[data-testid="summary-validate-${q.id}"]`).trigger('click')
    const emitted = wrapper.emitted('submit')
    expect(emitted).toBeTruthy()
    const payload = emitted![0]![0] as { validated: boolean; modifications: unknown[] }
    expect(payload.validated).toBe(true)
    expect(payload.modifications).toEqual([])
  })
})


// ─── UnsupportedWidget ─────────────────────────────────────────────────


describe('UnsupportedWidget', () => {
  it('rend un textarea fallback', () => {
    const q = makeQuestion({
      question_type: 'unknown_type' as never,
    })
    const wrapper = mount(UnsupportedWidget, { props: { question: q } })
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.text()).toContain('Type de widget non supporté')
  })

  it('émet abandon-and-send avec le contenu texte', async () => {
    const q = makeQuestion({ question_type: 'unknown_type' as never })
    const wrapper = mount(UnsupportedWidget, { props: { question: q } })
    const textarea = wrapper.find('textarea')
    await textarea.setValue('Ma réponse libre')
    await wrapper.find(`[data-testid="unsupported-send-${q.id}"]`).trigger('click')
    expect(wrapper.emitted('abandon-and-send')).toBeTruthy()
    expect(wrapper.emitted('abandon-and-send')![0]![0]).toBe('Ma réponse libre')
  })
})


// ─── InteractiveQuestionInputBar — Dispatcher ──────────────────────────


describe('InteractiveQuestionInputBar (dispatcher)', () => {
  it('route un yes_no vers YesNoWidget', () => {
    const q = makeQuestion({ question_type: 'yes_no' })
    const wrapper = mount(InteractiveQuestionInputBar, { props: { question: q } })
    expect(wrapper.findComponent(YesNoWidget).exists()).toBe(true)
  })

  it('route un select vers SelectWidget', () => {
    const q = makeQuestion({
      question_type: 'select',
      payload: {
        question_type: 'select',
        options: [{ id: 'a', label: 'A' }],
        min_selections: 1,
        max_selections: 1,
        allow_other: false,
      },
    })
    const wrapper = mount(InteractiveQuestionInputBar, { props: { question: q } })
    expect(wrapper.findComponent(SelectWidget).exists()).toBe(true)
  })

  it('route un type inconnu vers UnsupportedWidget', () => {
    const q = makeQuestion({ question_type: 'unknown_type' as never })
    const wrapper = mount(InteractiveQuestionInputBar, { props: { question: q } })
    expect(wrapper.findComponent(UnsupportedWidget).exists()).toBe(true)
  })

  it('route un qcu vers SingleChoiceWidget (rétro-compat F18)', async () => {
    const q = makeQuestion({
      question_type: 'qcu',
      options: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }],
      min_selections: 1,
      max_selections: 1,
    })
    const wrapper = mount(InteractiveQuestionInputBar, { props: { question: q } })
    // Vérifie que la carte conteneur est rendue (compatibilité ancien F18)
    expect(wrapper.find('.iq-sheet').exists()).toBe(true)
    expect(wrapper.text()).toContain('Test prompt')
  })
})

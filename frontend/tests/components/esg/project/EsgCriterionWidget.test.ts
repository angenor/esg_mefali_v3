/**
 * T024 [US1] — Composant EsgCriterionWidget : rendu qcu, validation XOR
 * source/unsourced, émission de l'événement save avec payload conforme.
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import EsgCriterionWidget from '~/components/esg/project/EsgCriterionWidget.vue'

describe('EsgCriterionWidget (F047 US1)', () => {
  const baseCriterion = {
    id: 'crit-1',
    code: 'PS1-1',
    label: 'Identification des risques E&S',
    is_required: true,
  }

  it('affiche le badge Requis pour un critère obligatoire', () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: { criterion: baseCriterion },
    })
    expect(wrapper.text()).toContain('Requis')
    expect(wrapper.text()).toContain('PS1-1')
    expect(wrapper.text()).toContain('Identification des risques E&S')
  })

  it("affiche les 3 options qcu (oui / partiel / non)", () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: { criterion: baseCriterion },
    })
    const radios = wrapper.findAll('input[type="radio"]')
    expect(radios).toHaveLength(3)
    const labels = wrapper.findAll('fieldset label').map((l) => l.text())
    expect(labels[0]).toMatch(/Oui/)
    expect(labels[1]).toMatch(/Partiellement/)
    expect(labels[2]).toMatch(/Non/)
  })

  it("désactive le bouton tant qu'aucun choix n'est sélectionné", () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: { criterion: baseCriterion },
    })
    const btn = wrapper.find('button')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it("affiche un message d'alerte si XOR violé (source ET unsourced)", async () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: {
        criterion: baseCriterion,
        initial: { source_id: 'src-1', unsourced: false },
      },
    })
    // Choix d'une réponse
    await wrapper.findAll('input[type="radio"]')[0].setValue()
    // Activer le bouton (source uniquement → OK)
    expect(wrapper.find('button').attributes('disabled')).toBeUndefined()
  })

  it('émet save avec le payload conforme quand source_id est fourni', async () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: {
        criterion: baseCriterion,
        initial: { source_id: 'src-1', unsourced: false },
      },
    })
    await wrapper.findAll('input[type="radio"]')[0].setValue()
    await wrapper.find('button').trigger('click')
    const emits = wrapper.emitted('save')
    expect(emits).toBeTruthy()
    const payload = (emits as unknown as Array<Array<unknown>>)[0][0] as Record<string, unknown>
    expect(payload.criterion_id).toBe('crit-1')
    expect(payload.response_type).toBe('qcu')
    expect(payload.source_id).toBe('src-1')
    expect(payload.unsourced).toBe(false)
    expect(payload.response_value).toEqual({ choice: 'yes' })
  })

  it('émet save avec unsourced=true quand l\'utilisateur coche la case', async () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: {
        criterion: baseCriterion,
        initial: { unsourced: true },
      },
    })
    await wrapper.findAll('input[type="radio"]')[1].setValue()
    await wrapper.find('button').trigger('click')
    const payload = (wrapper.emitted('save') as unknown as Array<Array<Record<string, unknown>>>)[0][0]
    expect(payload.unsourced).toBe(true)
    expect(payload.source_id).toBeNull()
    expect(payload.response_value).toEqual({ choice: 'partial' })
  })

  it("désactive l'input source si unsourced=true (XOR côté UI)", async () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: {
        criterion: baseCriterion,
        initial: { unsourced: true },
      },
    })
    const sourceInput = wrapper.find('input[type="text"]')
    expect(sourceInput.attributes('disabled')).toBeDefined()
  })

  it("propage le mode disabled (lecture seule, évaluation finalisée)", () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: { criterion: baseCriterion, disabled: true },
    })
    // Les radios sont à l'intérieur d'un <fieldset :disabled="disabled"> qui
    // les désactive en cascade. On vérifie donc le fieldset, l'input source
    // et le bouton, plutôt que chaque radio individuellement.
    expect(wrapper.find('fieldset').attributes('disabled')).toBeDefined()
    expect(wrapper.find('input[type="text"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('input[type="checkbox"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  it('respecte le contrat ARIA (aria-labelledby + role alert)', async () => {
    const wrapper = mount(EsgCriterionWidget, {
      props: { criterion: baseCriterion },
    })
    const section = wrapper.find('section')
    expect(section.attributes('aria-labelledby')).toBe('crit-crit-1')
    // Sans choix ET ni source ni unsourced ; on coche les deux pour invalider XOR
    await wrapper.findAll('input[type="radio"]')[2].setValue()
    // ni source ni unsourced → XOR invalide → alerte visible
    const alert = wrapper.find('[role="alert"]')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toMatch(/source.*non sourcée/i)
  })
})

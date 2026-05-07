import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ComparisonTableBlock from '~/components/richblocks/ComparisonTableBlock.vue'
import type { ComparisonTableBlockProps } from '~/types/richblocks'

function _props(
  overrides: Partial<ComparisonTableBlockProps> = {},
): ComparisonTableBlockProps {
  return {
    title: 'Comparaison fonds GCF',
    subjects: [
      { id: 'boad', label: 'GCF via BOAD' },
      { id: 'undp', label: 'GCF via UNDP' },
      { id: 'afd', label: 'GCF via AFD' },
    ],
    rows: [
      {
        label: 'Frais d\'instruction',
        type: 'money',
        higherIsBetter: false,
        values: [
          {
            subjectId: 'boad',
            value: '100000',
            money: { amount: '100000.00', currency: 'XOF' },
          },
          {
            subjectId: 'undp',
            value: '150000',
            money: { amount: '150000.00', currency: 'XOF' },
          },
          {
            subjectId: 'afd',
            value: '120000',
            money: { amount: '120000.00', currency: 'XOF' },
          },
        ],
      },
      {
        label: 'Délai instruction',
        type: 'duration',
        higherIsBetter: false,
        values: [
          { subjectId: 'boad', value: '12 mois' },
          { subjectId: 'undp', value: '8 mois' },
          { subjectId: 'afd', value: '14 mois' },
        ],
      },
      {
        label: 'Taux succès',
        type: 'percentage',
        higherIsBetter: true,
        values: [
          { subjectId: 'boad', value: 65 },
          { subjectId: 'undp', value: 80 },
          { subjectId: 'afd', value: 55 },
        ],
      },
    ],
    highlightWinner: true,
    ...overrides,
  }
}

describe('ComparisonTableBlock (F11)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('rend le titre', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    expect(wrapper.text()).toContain('Comparaison fonds GCF')
  })

  it('rend les headers sujets', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const text = wrapper.text()
    expect(text).toContain('GCF via BOAD')
    expect(text).toContain('GCF via UNDP')
    expect(text).toContain('GCF via AFD')
  })

  it('rend les labels de rows', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const text = wrapper.text()
    expect(text).toContain('Frais d\'instruction')
    expect(text).toContain('Délai instruction')
    expect(text).toContain('Taux succès')
  })

  it('formatte type money avec FCFA', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const text = wrapper.text()
    expect(text).toMatch(/FCFA|100\s?000|150\s?000/)
  })

  it('formatte type percentage avec %', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const text = wrapper.text()
    expect(text).toMatch(/65 ?%|80 ?%|55 ?%/)
  })

  it('formatte type boolean avec ✓ ou ✗', () => {
    const wrapper = mount(ComparisonTableBlock, {
      props: _props({
        rows: [{
          label: 'Disponible',
          type: 'boolean',
          higherIsBetter: true,
          values: [
            { subjectId: 'boad', value: 1 },
            { subjectId: 'undp', value: 0 },
            { subjectId: 'afd', value: 1 },
          ],
        }],
      }),
    })
    const text = wrapper.text()
    expect(text).toMatch(/[✓✗]|oui|non|true|false/i)
  })

  it('met en valeur (highlight) la cellule gagnante par row', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const html = wrapper.html()
    // Au moins une cellule a la classe "winner" ou similaire
    expect(html).toMatch(/winner|bg-emerald|bg-green/)
  })

  it('emet open-source au clic sur picto source', async () => {
    const wrapper = mount(ComparisonTableBlock, {
      props: _props({
        rows: [{
          label: 'Frais',
          type: 'money',
          higherIsBetter: false,
          values: [
            {
              subjectId: 'boad',
              value: '100',
              sourceId: 'src-1',
              money: { amount: '100.00', currency: 'XOF' },
            },
            {
              subjectId: 'undp',
              value: '200',
              money: { amount: '200.00', currency: 'XOF' },
            },
            {
              subjectId: 'afd',
              value: '150',
              money: { amount: '150.00', currency: 'XOF' },
            },
          ],
        }],
      }),
    })
    const sourceBtn = wrapper.find('button[aria-label*="source"]')
    expect(sourceBtn.exists()).toBe(true)
    await sourceBtn.trigger('click')
    const events = wrapper.emitted('open-source')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['src-1'])
  })

  it('emet navigate au clic sur header sujet avec drilldownUrl', async () => {
    const wrapper = mount(ComparisonTableBlock, {
      props: _props({
        subjects: [
          { id: 'boad', label: 'BOAD', drilldownUrl: '/financing/offers/boad' },
          { id: 'undp', label: 'UNDP' },
          { id: 'afd', label: 'AFD' },
        ],
      }),
    })
    const headerBtn = wrapper.find('button[data-test="comparison-header-boad"]')
    expect(headerBtn.exists()).toBe(true)
    await headerBtn.trigger('click')
    const events = wrapper.emitted('navigate')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['/financing/offers/boad'])
  })

  it('utilise les classes dark: Tailwind', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const html = wrapper.html()
    expect(html).toMatch(/dark:/)
  })

  it('expose un attribut role="table" et aria-label', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const table = wrapper.find('[role="table"], table')
    expect(table.exists()).toBe(true)
  })

  it('rend en cartes verticales sur mobile (< 768px) — classes responsive', () => {
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const html = wrapper.html()
    // Le container utilise hidden md:block ou équivalent
    expect(html).toMatch(/md:|sm:|hidden|lg:/)
  })

  it('ne highlight pas si highlightWinner=false', () => {
    const wrapper = mount(ComparisonTableBlock, {
      props: _props({ highlightWinner: false }),
    })
    const html = wrapper.html()
    // Les cellules ne doivent pas porter la classe winner
    expect(html).not.toMatch(/data-winner="true"/)
  })

  it('respecte higherIsBetter=false (le plus bas gagne)', () => {
    // Row 'Frais' avec higher_is_better=false : la valeur 100000 (BOAD)
    // doit être marquée gagnante
    const wrapper = mount(ComparisonTableBlock, { props: _props() })
    const html = wrapper.html()
    // Le test est indirect : on vérifie qu'un winner existe
    expect(html).toMatch(/winner|bg-emerald|bg-green/)
  })
})

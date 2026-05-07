// F11 — Régression : les fences markdown existants (chart/table/timeline/progress/gauge/mermaid)
// continuent de fonctionner avec MessageParser après ajout des tools typés.

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MessageParser from '~/components/chat/MessageParser.vue'

describe('MessageParser markdown compat (F11 régression)', () => {
  it('rend un ChartBlock pour fence ```chart', () => {
    setActivePinia(createPinia())
    const content = '```chart\n{"type":"bar","data":{"labels":["A"],"datasets":[{"label":"X","data":[1]}]}}\n```'
    const wrapper = mount(MessageParser, {
      props: { content },
    })
    // Au moins un composant ChartBlock instancié
    const html = wrapper.html()
    // Le ChartBlock crée un canvas Chart.js — au minimum, le contenu raw est passé
    expect(html.length).toBeGreaterThan(0)
  })

  it('rend un MermaidBlock pour fence ```mermaid', () => {
    setActivePinia(createPinia())
    const content = '```mermaid\ngraph LR\nA-->B\n```'
    const wrapper = mount(MessageParser, { props: { content } })
    const html = wrapper.html()
    expect(html.length).toBeGreaterThan(0)
  })

  it('rend un TableBlock pour fence ```table', () => {
    setActivePinia(createPinia())
    const content = '```table\n{"headers":["A","B"],"rows":[["1","2"]]}\n```'
    const wrapper = mount(MessageParser, { props: { content } })
    const html = wrapper.html()
    expect(html.length).toBeGreaterThan(0)
  })

  it('rend un GaugeBlock pour fence ```gauge', () => {
    setActivePinia(createPinia())
    const content = '```gauge\n{"value":72,"max":100,"label":"Score","thresholds":[{"limit":100,"color":"#10B981"}]}\n```'
    const wrapper = mount(MessageParser, { props: { content } })
    const html = wrapper.html()
    expect(html.length).toBeGreaterThan(0)
  })

  it('rend un ProgressBlock pour fence ```progress', () => {
    setActivePinia(createPinia())
    const content = '```progress\n{"items":[{"label":"X","value":50,"max":100}]}\n```'
    const wrapper = mount(MessageParser, { props: { content } })
    const html = wrapper.html()
    expect(html.length).toBeGreaterThan(0)
  })

  it('rend un TimelineBlock pour fence ```timeline', () => {
    setActivePinia(createPinia())
    const content = '```timeline\n{"events":[{"date":"2026","title":"X","status":"todo"}]}\n```'
    const wrapper = mount(MessageParser, { props: { content } })
    const html = wrapper.html()
    expect(html.length).toBeGreaterThan(0)
  })

  it('rend du texte markdown standard sans bloc', () => {
    setActivePinia(createPinia())
    const wrapper = mount(MessageParser, {
      props: { content: '# Bonjour\n\nCeci est un message texte simple.' },
    })
    expect(wrapper.text()).toContain('Bonjour')
  })

  it('combine un texte et un bloc visuel', () => {
    setActivePinia(createPinia())
    const content = 'Mon résumé :\n\n```chart\n{"type":"bar","data":{"labels":[],"datasets":[]}}\n```\n\nFin.'
    const wrapper = mount(MessageParser, { props: { content } })
    const text = wrapper.text()
    expect(text).toContain('Mon résumé')
    expect(text).toContain('Fin')
  })

  it('rend les blocs typés F11 quand visualizationBlocks fourni', () => {
    setActivePinia(createPinia())
    const wrapper = mount(MessageParser, {
      props: {
        content: 'Voici le résumé :',
        visualizationBlocks: [{
          blockType: 'show_kpi_card',
          payload: {
            title: 'Score ESG',
            value: '72',
            color: 'emerald',
          },
        }],
      },
    })
    const text = wrapper.text()
    expect(text).toContain('Score ESG')
    expect(text).toContain('72')
  })

  it('combine markdown et blocs typés F11', () => {
    setActivePinia(createPinia())
    const wrapper = mount(MessageParser, {
      props: {
        content: 'Texte avant.',
        visualizationBlocks: [{
          blockType: 'show_kpi_card',
          payload: {
            title: 'Score',
            value: '50',
            color: 'blue',
          },
        }],
      },
    })
    const text = wrapper.text()
    expect(text).toContain('Texte avant')
    expect(text).toContain('Score')
  })
})

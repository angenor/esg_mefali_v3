import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ToolCallIndicator from '~/components/chat/ToolCallIndicator.vue'

/**
 * F12 — Tests ToolCallIndicator.vue (case `recall_history` ajoute).
 */
describe('ToolCallIndicator', () => {
  describe('Mapping libelles tools', () => {
    it('affiche le libelle francais pour `recall_history` (F12)', () => {
      const wrapper = mount(ToolCallIndicator, {
        props: { toolName: 'recall_history' },
      })
      expect(wrapper.text()).toContain("Recherche dans l'historique de conversation...")
    })

    it('affiche un libelle generique pour un tool inconnu', () => {
      const wrapper = mount(ToolCallIndicator, {
        props: { toolName: 'unknown_tool_xyz' },
      })
      expect(wrapper.text()).toContain('Execution de unknown_tool_xyz...')
    })

    it('affiche le libelle pour create_esg_assessment', () => {
      const wrapper = mount(ToolCallIndicator, {
        props: { toolName: 'create_esg_assessment' },
      })
      expect(wrapper.text()).toContain("Creation de l'evaluation ESG...")
    })
  })

  describe('Dark mode', () => {
    it('inclut les classes dark: pour le fond et le texte', () => {
      const wrapper = mount(ToolCallIndicator, {
        props: { toolName: 'recall_history' },
      })
      const html = wrapper.html()
      expect(html).toContain('dark:bg-blue-900/20')
      expect(html).toContain('dark:text-blue-300')
      expect(html).toContain('dark:border-blue-800')
    })
  })

  describe('Spinner accessibilite', () => {
    it('le spinner SVG est present', () => {
      const wrapper = mount(ToolCallIndicator, {
        props: { toolName: 'recall_history' },
      })
      const svg = wrapper.find('svg')
      expect(svg.exists()).toBe(true)
      expect(svg.classes()).toContain('animate-spin')
    })
  })
})

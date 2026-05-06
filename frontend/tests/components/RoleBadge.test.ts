import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RoleBadge from '~/components/ui/RoleBadge.vue'

/**
 * F02 — Tests RoleBadge.vue (US2 visualisation roles).
 */
describe('RoleBadge', () => {
  describe('Variante ADMIN', () => {
    it('affiche le label "Administrateur" pour role=ADMIN', () => {
      const wrapper = mount(RoleBadge, { props: { role: 'ADMIN' } })
      expect(wrapper.text()).toContain('Administrateur')
    })

    it('utilise les classes Tailwind rouge pour ADMIN (light + dark)', () => {
      const wrapper = mount(RoleBadge, { props: { role: 'ADMIN' } })
      const span = wrapper.find('span').element as HTMLElement
      const classes = span.className
      expect(classes).toContain('bg-red-700')
      expect(classes).toContain('dark:bg-red-900')
    })
  })

  describe('Variante PME', () => {
    it('affiche le label "PME" pour role=PME', () => {
      const wrapper = mount(RoleBadge, { props: { role: 'PME' } })
      expect(wrapper.text()).toContain('PME')
    })

    it('utilise les classes Tailwind emerald pour PME (light + dark)', () => {
      const wrapper = mount(RoleBadge, { props: { role: 'PME' } })
      const span = wrapper.find('span').element as HTMLElement
      const classes = span.className
      expect(classes).toContain('bg-emerald-100')
      expect(classes).toContain('dark:bg-emerald-900')
      expect(classes).toContain('text-emerald-700')
    })
  })

  describe('Tailles', () => {
    it('size=sm utilise les classes "text-xs"', () => {
      const wrapper = mount(RoleBadge, {
        props: { role: 'PME', size: 'sm' },
      })
      const span = wrapper.find('span').element as HTMLElement
      expect(span.className).toContain('text-xs')
    })

    it('size=md utilise les classes "text-sm"', () => {
      const wrapper = mount(RoleBadge, {
        props: { role: 'ADMIN', size: 'md' },
      })
      const span = wrapper.find('span').element as HTMLElement
      expect(span.className).toContain('text-sm')
    })
  })

  describe('Accessibilite', () => {
    it("l'icone est marque aria-hidden", () => {
      const wrapper = mount(RoleBadge, { props: { role: 'PME' } })
      const iconSpan = wrapper.findAll('span > span').at(0)
      expect(iconSpan?.attributes('aria-hidden')).toBe('true')
    })
  })
})

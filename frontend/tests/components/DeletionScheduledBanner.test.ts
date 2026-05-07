import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import DeletionScheduledBanner from '~/components/DeletionScheduledBanner.vue'

describe('DeletionScheduledBanner', () => {
  it('affiche la date programmée formattée en français', () => {
    const wrapper = mount(DeletionScheduledBanner, {
      props: { scheduledAt: '2026-06-06T10:00:00Z' },
    })
    expect(wrapper.text()).toContain('6 juin 2026')
    expect(wrapper.text()).toContain('Suppression programmée')
  })

  it('a le bon role=alert', () => {
    const wrapper = mount(DeletionScheduledBanner, {
      props: { scheduledAt: '2026-06-06T10:00:00Z' },
    })
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  })

  it('émet @cancel au clic sur le bouton', async () => {
    const wrapper = mount(DeletionScheduledBanner, {
      props: { scheduledAt: '2026-06-06T10:00:00Z' },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
  })

  it('désactive le bouton quand loading=true', () => {
    const wrapper = mount(DeletionScheduledBanner, {
      props: { scheduledAt: '2026-06-06T10:00:00Z', loading: true },
    })
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  it('contient les classes dark mode', () => {
    const wrapper = mount(DeletionScheduledBanner, {
      props: { scheduledAt: '2026-06-06T10:00:00Z' },
    })
    expect(wrapper.html()).toContain('dark:bg-orange-900/30')
  })
})

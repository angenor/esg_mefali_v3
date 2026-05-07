import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import AttestationStatusBadge from '~/components/attestations/AttestationStatusBadge.vue'

describe('AttestationStatusBadge', () => {
  it('rend le label AUTHENTIQUE pour status=authentic', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'authentic' },
    })
    expect(wrapper.text()).toContain('AUTHENTIQUE')
  })

  it('rend le label RÉVOQUÉE pour status=revoked', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'revoked' },
    })
    expect(wrapper.text()).toContain('RÉVOQUÉE')
  })

  it('rend le label EXPIRÉE pour status=expired', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'expired' },
    })
    expect(wrapper.text()).toContain('EXPIRÉE')
  })

  it('rend le label INVALIDE pour status=invalid', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'invalid' },
    })
    expect(wrapper.text()).toContain('INVALIDE')
  })

  it('attribue role=status et aria-live=polite (accessibilité)', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'authentic' },
    })
    const span = wrapper.find('span')
    expect(span.attributes('role')).toBe('status')
    expect(span.attributes('aria-live')).toBe('polite')
  })

  it('applique les classes vert pour authentic', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'authentic' },
    })
    expect(wrapper.classes().some((c) => c.includes('emerald'))).toBe(true)
  })

  it('applique les classes rouge pour revoked', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'revoked' },
    })
    expect(wrapper.classes().some((c) => c.includes('rose'))).toBe(true)
  })

  it('applique les classes orange pour expired', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'expired' },
    })
    expect(wrapper.classes().some((c) => c.includes('amber'))).toBe(true)
  })

  it('respecte la prop size sm/md/lg', () => {
    const sm = mount(AttestationStatusBadge, { props: { status: 'authentic', size: 'sm' } })
    const lg = mount(AttestationStatusBadge, { props: { status: 'authentic', size: 'lg' } })
    expect(sm.classes().some((c) => c.includes('text-[10px]'))).toBe(true)
    expect(lg.classes().some((c) => c.includes('text-base'))).toBe(true)
  })

  it('inclut les variantes dark: dans les classes', () => {
    const wrapper = mount(AttestationStatusBadge, {
      props: { status: 'authentic' },
    })
    const allClasses = wrapper.classes().join(' ')
    expect(allClasses).toMatch(/dark:/)
  })
})

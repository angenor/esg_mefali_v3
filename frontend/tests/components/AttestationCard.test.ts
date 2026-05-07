import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import AttestationCard from '~/components/attestations/AttestationCard.vue'
import type { AttestationSummary } from '~/types/attestation'

function makeAttestation(overrides: Partial<AttestationSummary> = {}): AttestationSummary {
  return {
    id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
    display_id: 'ATT-2026-00042',
    attestation_type: 'combined',
    valid_from: '2026-01-01T00:00:00+00:00',
    valid_until: '2027-01-01T00:00:00+00:00',
    revoked_at: null,
    revoked_reason: null,
    verification_url: 'https://esg-mefali.com/verify/aaaaaaaa',
    pdf_hash_sha256: 'a'.repeat(64),
    public_key_id: 'v1',
    created_at: '2026-01-01T00:00:00+00:00',
    ...overrides,
  }
}

describe('AttestationCard', () => {
  it('rend display_id, type et boutons standards (authentic)', () => {
    const wrapper = mount(AttestationCard, {
      props: { attestation: makeAttestation() },
      global: {
        stubs: ['NuxtLink'],
      },
    })
    expect(wrapper.text()).toContain('ATT-2026-00042')
    expect(wrapper.text()).toContain('Combinée')
    expect(wrapper.text()).toContain('Télécharger PDF')
    expect(wrapper.text()).toContain('Copier URL')
    expect(wrapper.text()).toContain('Révoquer')
  })

  it("n'affiche pas le bouton Révoquer si attestation déjà révoquée", () => {
    const wrapper = mount(AttestationCard, {
      props: {
        attestation: makeAttestation({
          revoked_at: '2026-02-01T00:00:00+00:00',
          revoked_reason: 'Mise à jour',
        }),
      },
    })
    expect(wrapper.text()).not.toContain('Révoquer')
  })

  it('émet "revoke" avec id quand on clique', async () => {
    const wrapper = mount(AttestationCard, {
      props: { attestation: makeAttestation() },
    })
    const buttons = wrapper.findAll('button')
    const revokeBtn = buttons.find((b) => b.text() === 'Révoquer')!
    await revokeBtn.trigger('click')
    expect(wrapper.emitted('revoke')).toBeTruthy()
    expect((wrapper.emitted('revoke') as string[][])[0][0]).toBe(
      'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
    )
  })

  it('émet "download" avec id quand on clique sur Télécharger', async () => {
    const wrapper = mount(AttestationCard, {
      props: { attestation: makeAttestation() },
    })
    const dlBtn = wrapper.findAll('button').find((b) => b.text() === 'Télécharger PDF')!
    await dlBtn.trigger('click')
    expect(wrapper.emitted('download')).toBeTruthy()
  })

  it('émet "copy-url" quand on clique sur Copier URL', async () => {
    const wrapper = mount(AttestationCard, {
      props: { attestation: makeAttestation() },
    })
    const copyBtn = wrapper.findAll('button').find((b) => b.text().includes('Copier URL'))!
    await copyBtn.trigger('click')
    expect(wrapper.emitted('copy-url')).toBeTruthy()
    expect((wrapper.emitted('copy-url') as string[][])[0][0]).toBe(
      'https://esg-mefali.com/verify/aaaaaaaa',
    )
  })

  it('affiche un badge expire bientôt si <30 jours', () => {
    const future = new Date()
    future.setDate(future.getDate() + 15)
    const wrapper = mount(AttestationCard, {
      props: {
        attestation: makeAttestation({
          valid_until: future.toISOString(),
        }),
      },
    })
    expect(wrapper.text()).toContain('Expire bientôt')
    expect(wrapper.text()).toContain('Renouveler')
  })

  it('intègre les classes dark: pour le dark mode', () => {
    const wrapper = mount(AttestationCard, {
      props: { attestation: makeAttestation() },
    })
    const html = wrapper.html()
    expect(html).toMatch(/dark:bg-dark-card/)
    expect(html).toMatch(/dark:border-dark-border/)
  })

  it('article a un role et aria-label', () => {
    const wrapper = mount(AttestationCard, {
      props: { attestation: makeAttestation() },
    })
    const article = wrapper.find('article')
    expect(article.attributes('role')).toBe('article')
    expect(article.attributes('aria-label')).toContain('ATT-2026-00042')
  })
})

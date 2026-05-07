import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

// Mock auto-import store
;(globalThis as any).useRuntimeConfig = () => ({ public: { apiBase: 'http://test' } })

import AuditLogEntry from '~/components/audit/AuditLogEntry.vue'
import type { AuditEvent } from '~/types/audit'

function makeEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: 'e1',
    timestamp: new Date().toISOString(),
    user_id: 'u1',
    user_email: 'u@x.com',
    account_id: 'acct1',
    entity_type: 'company_profiles',
    entity_id: 'ent1',
    action: 'update',
    field: 'sector',
    old_value: 'agriculture',
    new_value: 'energie',
    source_of_change: 'manual',
    actor_metadata: null,
    ...overrides,
  }
}

describe('AuditLogEntry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('affiche le libellé Modification pour action update', () => {
    const w = mount(AuditLogEntry, { props: { event: makeEvent() } })
    expect(w.text()).toContain('Modification')
    expect(w.text()).toContain('Profil entreprise')
  })

  it('affiche Création pour action create', () => {
    const w = mount(AuditLogEntry, { props: { event: makeEvent({ action: 'create' }) } })
    expect(w.text()).toContain('Création')
  })

  it('affiche Suppression pour action delete', () => {
    const w = mount(AuditLogEntry, { props: { event: makeEvent({ action: 'delete' }) } })
    expect(w.text()).toContain('Suppression')
  })

  it('affiche Consultation Admin pour view_admin', () => {
    const w = mount(AuditLogEntry, {
      props: {
        event: makeEvent({
          action: 'view_admin',
          source_of_change: 'admin',
          entity_type: 'account',
        }),
      },
    })
    expect(w.text()).toContain('Consultation Admin')
    expect(w.text()).toContain('admin Mefali')
  })

  it('affiche le diff field : old → new', () => {
    const w = mount(AuditLogEntry, { props: { event: makeEvent() } })
    expect(w.text()).toContain('sector')
    expect(w.text()).toContain('agriculture')
    expect(w.text()).toContain('energie')
  })

  it("L'assistant IA pour source llm", () => {
    const w = mount(AuditLogEntry, {
      props: { event: makeEvent({ source_of_change: 'llm' }) },
    })
    expect(w.text()).toContain("L'assistant IA")
  })

  it('classe dark mode appliquée', () => {
    const w = mount(AuditLogEntry, { props: { event: makeEvent() } })
    const html = w.html()
    expect(html).toContain('dark:')
  })

  it('utilise le marqueur tronqué dans le diff', () => {
    const w = mount(AuditLogEntry, {
      props: {
        event: makeEvent({
          old_value: { _truncated: true, _truncated_size: 12345, _preview: '...' } as unknown,
          new_value: 'short',
        }),
      },
    })
    expect(w.text()).toContain('tronquée')
  })
})

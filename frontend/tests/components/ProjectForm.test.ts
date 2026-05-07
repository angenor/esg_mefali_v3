import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectForm from '~/components/projects/ProjectForm.vue'
import ProjectStatusSelector from '~/components/projects/ProjectStatusSelector.vue'

const stubs = {
  ProjectStatusSelector,
}

describe('ProjectForm (F06)', () => {
  it('mode create : champs vides initial', () => {
    const wrapper = mount(ProjectForm, {
      props: { mode: 'create' },
      global: { stubs },
    })
    expect((wrapper.find('#project-name').element as HTMLInputElement).value).toBe('')
  })

  it('valide le nom requis', async () => {
    const wrapper = mount(ProjectForm, {
      props: { mode: 'create' },
      global: { stubs },
    })
    // Le bouton submit est disabled tant que name vide.
    const submitBtn = wrapper.find('button[type="submit"]')
    expect(submitBtn.attributes('disabled')).toBeDefined()
  })

  it('emit submit avec payload normalisé', async () => {
    const wrapper = mount(ProjectForm, {
      props: { mode: 'create' },
      global: { stubs },
    })
    await wrapper.find('#project-name').setValue('Mon projet')
    await wrapper.find('form').trigger('submit')
    const events = wrapper.emitted('submit')
    expect(events).toBeTruthy()
    expect(events![0][0]).toMatchObject({ name: 'Mon projet' })
  })

  it('mode duplicate : préremplit avec suffix copie', async () => {
    const wrapper = mount(ProjectForm, {
      props: {
        mode: 'duplicate',
        initialProject: {
          id: 'p-1',
          account_id: 'a-1',
          name: 'Source',
          description: null,
          objective_env: ['renewable_energy'],
          maturity: 'pilot',
          status: 'funded',
          target_amount: null,
          duration_months: null,
          financing_structure: null,
          expected_impact_tco2e: null,
          expected_jobs_created: null,
          expected_beneficiaries: null,
          expected_hectares_restored: null,
          expected_other_impacts: null,
          location_country: null,
          location_region: null,
          auto_generated: false,
          created_at: '2026-05-07T00:00:00Z',
          updated_at: '2026-05-07T00:00:00Z',
          project_documents: [],
          applications_count: 0,
        },
      },
      global: { stubs },
    })
    await wrapper.vm.$nextTick()
    expect(
      (wrapper.find('#project-name').element as HTMLInputElement).value,
    ).toBe('Source (copie)')
  })

  it('emit cancel', async () => {
    const wrapper = mount(ProjectForm, {
      props: { mode: 'create' },
      global: { stubs },
    })
    const buttons = wrapper.findAll('button')
    const cancelBtn = buttons.find((b) => b.text() === 'Annuler')
    expect(cancelBtn).toBeDefined()
    await cancelBtn!.trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
  })

  it('classes dark: présentes', () => {
    const wrapper = mount(ProjectForm, {
      props: { mode: 'create' },
      global: { stubs },
    })
    const html = wrapper.html()
    expect(html).toContain('dark:bg-dark-input')
    expect(html).toContain('dark:text-surface-dark-text')
  })

  it('checkbox objectif toggle', async () => {
    const wrapper = mount(ProjectForm, {
      props: { mode: 'create' },
      global: { stubs },
    })
    await wrapper.find('#project-name').setValue('Test')
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    await checkboxes[0].trigger('change')
    await wrapper.find('form').trigger('submit')
    const events = wrapper.emitted('submit')
    expect(events).toBeTruthy()
    const payload = events![0][0] as { objective_env?: string[] }
    expect(payload.objective_env?.length).toBeGreaterThan(0)
  })

  it('libellé bouton submit dépend du mode', () => {
    const wrapperCreate = mount(ProjectForm, {
      props: { mode: 'create' },
      global: { stubs },
    })
    expect(
      wrapperCreate.find('button[type="submit"]').text(),
    ).toContain('Créer')

    const wrapperEdit = mount(ProjectForm, {
      props: { mode: 'edit' },
      global: { stubs },
    })
    expect(wrapperEdit.find('button[type="submit"]').text()).toContain(
      'Enregistrer',
    )

    const wrapperDup = mount(ProjectForm, {
      props: { mode: 'duplicate' },
      global: { stubs },
    })
    expect(wrapperDup.find('button[type="submit"]').text()).toContain(
      'Dupliquer',
    )
  })
})

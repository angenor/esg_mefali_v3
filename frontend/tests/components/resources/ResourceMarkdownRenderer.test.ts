import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ResourceMarkdownRenderer from '~/components/resources/ResourceMarkdownRenderer.vue'

describe('ResourceMarkdownRenderer', () => {
  it('rend un titre H1 markdown', () => {
    const wrapper = mount(ResourceMarkdownRenderer, {
      props: { content: '# Titre principal' },
    })
    expect(wrapper.html()).toContain('<h1')
    expect(wrapper.text()).toContain('Titre principal')
  })

  it('rend une liste à puces', () => {
    const wrapper = mount(ResourceMarkdownRenderer, {
      props: { content: '- premier\n- deuxième' },
    })
    expect(wrapper.html()).toContain('<ul')
    expect(wrapper.text()).toContain('premier')
    expect(wrapper.text()).toContain('deuxième')
  })

  it('strip les balises script (anti-XSS)', () => {
    const wrapper = mount(ResourceMarkdownRenderer, {
      props: { content: '# Hi\n<script>alert(1)</script>' },
    })
    expect(wrapper.html()).not.toContain('<script')
  })

  it('strip les balises iframe (anti-XSS)', () => {
    const wrapper = mount(ResourceMarkdownRenderer, {
      props: { content: '<iframe src="evil"></iframe>texte' },
    })
    expect(wrapper.html()).not.toContain('<iframe')
  })

  it('rend les liens markdown vers http(s)', () => {
    const wrapper = mount(ResourceMarkdownRenderer, {
      props: { content: '[BCEAO](https://www.bceao.int/)' },
    })
    expect(wrapper.html()).toContain('href="https://www.bceao.int/"')
    expect(wrapper.text()).toContain('BCEAO')
  })

  it('gère content_md null sans crasher', () => {
    const wrapper = mount(ResourceMarkdownRenderer, {
      props: { content: null },
    })
    expect(wrapper.html()).toBeDefined()
  })
})

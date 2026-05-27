import { describe, it, expect } from 'vitest'
import { stripCodeFences } from '~/utils/stripCodeFences'

describe('stripCodeFences', () => {
  it('retire un bloc englobant ```html … ```', () => {
    expect(stripCodeFences('```html\n<p>Bonjour</p>\n```')).toBe('<p>Bonjour</p>')
  })

  it('retire un bloc englobant ``` … ``` sans langage', () => {
    expect(stripCodeFences('```\n<p>X</p>\n```')).toBe('<p>X</p>')
  })

  it('laisse intact un contenu déjà propre', () => {
    expect(stripCodeFences('<p>déjà propre</p>')).toBe('<p>déjà propre</p>')
  })

  it('retire une fence orpheline en ouverture', () => {
    expect(stripCodeFences('```html\n<p>ouverture</p>')).toBe('<p>ouverture</p>')
  })

  it('retire une fence orpheline en fermeture', () => {
    expect(stripCodeFences('<p>fermeture</p>\n```')).toBe('<p>fermeture</p>')
  })

  it('gère null / undefined / vide', () => {
    expect(stripCodeFences(null)).toBe('')
    expect(stripCodeFences(undefined)).toBe('')
    expect(stripCodeFences('')).toBe('')
  })

  it('est idempotent', () => {
    const once = stripCodeFences('```html\n<p>X</p>\n```')
    expect(stripCodeFences(once)).toBe(once)
  })

  it('préserve un bloc de code interne (non englobant)', () => {
    const content = '<p>code :</p>\n```python\nx = 1\n```\n<p>fin</p>'
    expect(stripCodeFences(content)).toBe(content)
  })
})

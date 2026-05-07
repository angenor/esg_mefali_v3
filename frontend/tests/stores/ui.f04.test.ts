import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useUiStore } from '~/stores/ui'

/**
 * F04 — Tests displayCurrencyMode dans le store ui.
 */
describe('useUiStore — displayCurrencyMode (F04)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })
  afterEach(() => {
    localStorage.clear()
  })

  it('initialise à "both" par défaut', () => {
    const store = useUiStore()
    expect(store.displayCurrencyMode).toBe('both')
  })

  it('setDisplayCurrencyMode("native") met à jour le store', () => {
    const store = useUiStore()
    store.setDisplayCurrencyMode('native')
    expect(store.displayCurrencyMode).toBe('native')
  })

  it('setDisplayCurrencyMode persiste dans localStorage', () => {
    const store = useUiStore()
    store.setDisplayCurrencyMode('pme')
    expect(localStorage.getItem('mefali.ui.displayCurrencyMode')).toBe('pme')
  })

  it('setDisplayCurrencyMode rejette les valeurs invalides', () => {
    const store = useUiStore()
    store.setDisplayCurrencyMode('both')
    // @ts-expect-error testing runtime guard
    store.setDisplayCurrencyMode('invalid')
    expect(store.displayCurrencyMode).toBe('both')
  })

  it('initDisplayCurrencyMode lit la valeur depuis localStorage', () => {
    localStorage.setItem('mefali.ui.displayCurrencyMode', 'native')
    const store = useUiStore()
    store.initDisplayCurrencyMode()
    expect(store.displayCurrencyMode).toBe('native')
  })

  it('initDisplayCurrencyMode ignore les valeurs invalides', () => {
    localStorage.setItem('mefali.ui.displayCurrencyMode', 'invalid-value')
    const store = useUiStore()
    store.initDisplayCurrencyMode()
    expect(store.displayCurrencyMode).toBe('both')
  })
})

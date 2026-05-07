import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCurrency } from '~/composables/useCurrency'
import type { Currency, Money } from '~/types/currency'

/**
 * F04 — Tests useCurrency composable (US2).
 */

const fetchMock = vi.fn()

vi.stubGlobal('$fetch', fetchMock)

beforeEach(() => {
  fetchMock.mockReset()
})
afterEach(() => {
  vi.clearAllMocks()
})

describe('useCurrency', () => {
  it('format() rend "1 000 FCFA"', () => {
    const { format } = useCurrency()
    const money: Money = { amount: '1000', currency: 'XOF' }
    const out = format(money)
    expect(out).toContain('FCFA')
    expect(out).toContain('1')
  })

  it('format() utilise séparateurs insécables pour milliers', () => {
    const { format } = useCurrency()
    const money: Money = { amount: '1000000', currency: 'XOF' }
    const out = format(money)
    expect(out).toMatch(/1[\s ]+000[\s ]+000/)
  })

  it('getPmeCurrency() retourne XOF par défaut', () => {
    const { getPmeCurrency } = useCurrency()
    expect(getPmeCurrency()).toBe<Currency>('XOF')
  })

  it('convert() retourne le money sans appeler $fetch si même devise', async () => {
    const { convert } = useCurrency()
    const money: Money = { amount: '500', currency: 'XOF' }
    const out = await convert(money, 'XOF')
    expect(out).toEqual(money)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('convert() délègue à POST /api/currency/convert', async () => {
    fetchMock.mockResolvedValueOnce({
      target: { amount: '1000.00', currency: 'EUR' },
    })
    const { convert } = useCurrency()
    const money: Money = { amount: '655957', currency: 'XOF' }
    const out = await convert(money, 'EUR')
    expect(out.currency).toBe('EUR')
    expect(out.amount).toBe('1000.00')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/currency/convert',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('getRate() retourne 1 quand base === quote', async () => {
    const { getRate } = useCurrency()
    const r = await getRate('XOF', 'XOF')
    expect(r).toBe(1)
  })
})

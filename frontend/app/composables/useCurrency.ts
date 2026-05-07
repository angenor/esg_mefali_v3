// F04 — Composable Vue pour la conversion et le formatage Money.

import {
  CURRENCY_SYMBOLS,
  type ConvertRequest,
  type ConvertResponse,
  type Currency,
  type Money,
  type RatesLatestResponse,
} from '~/types/currency'

const NBSP = ' ' // espace insécable fine (FR-061)
// Devise PME par défaut pour le MVP (UEMOA/CEDEAO).
const PME_CURRENCY: Currency = 'XOF'

function formatNumber(amount: string, currency: Currency): string {
  const num = Number.parseFloat(amount)
  if (!Number.isFinite(num)) return amount
  // JPY/USD/EUR/GBP affichés à 2 décimales ; XOF affiché en entier.
  const decimals = currency === 'XOF' || currency === 'JPY' ? 0 : 2
  const fixed = num.toFixed(decimals)
  // Séparateur de milliers : espace insécable.
  const [intPart, decPart] = fixed.split('.')
  const intWithSep = (intPart ?? '0').replace(
    /\B(?=(\d{3})+(?!\d))/g,
    NBSP,
  )
  return decPart ? `${intWithSep},${decPart}` : intWithSep
}

export function useCurrency() {
  /**
   * Formate un Money en string lisible : `1 000 000 FCFA`.
   */
  function format(money: Money): string {
    const symbol = CURRENCY_SYMBOLS[money.currency] ?? money.currency
    return `${formatNumber(money.amount, money.currency)}${NBSP}${symbol}`
  }

  /**
   * Devise PME par défaut (XOF pour le MVP, cf. clarif Q2).
   */
  function getPmeCurrency(): Currency {
    return PME_CURRENCY
  }

  /**
   * Convertit un Money via l'API backend POST /api/currency/convert.
   */
  async function convert(money: Money, target: Currency): Promise<Money> {
    if (money.currency === target) return money
    const body: ConvertRequest = {
      amount: money.amount,
      source_currency: money.currency,
      target_currency: target,
    }
    const resp = await $fetch<ConvertResponse>('/api/currency/convert', {
      method: 'POST',
      body,
    })
    return resp.target
  }

  /**
   * Récupère le taux courant pour une paire (base, quote).
   * Retourne 1 si base === quote, ou null si introuvable.
   */
  async function getRate(base: Currency, quote: Currency): Promise<number | null> {
    if (base === quote) return 1
    try {
      const data = await $fetch<RatesLatestResponse>('/api/currency/rates/latest')
      const direct = data.rates.find(
        (r) => r.base_currency === base && r.quote_currency === quote,
      )
      if (direct) return Number.parseFloat(direct.rate)
      const peg = data.peg_pairs.find(
        (p) => p.base_currency === base && p.quote_currency === quote,
      )
      if (peg) return Number.parseFloat(peg.rate)
      return null
    }
    catch {
      return null
    }
  }

  return {
    format,
    convert,
    getRate,
    getPmeCurrency,
  }
}

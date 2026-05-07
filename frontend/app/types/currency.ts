// F04 — Types TypeScript pour le module Currency / Money.

export type Currency = 'XOF' | 'EUR' | 'USD' | 'GBP' | 'JPY'

export const SUPPORTED_CURRENCIES: readonly Currency[] = [
  'XOF',
  'EUR',
  'USD',
  'GBP',
  'JPY',
] as const

/**
 * Représentation côté frontend d'un montant Money typé.
 * `amount` est un string décimal pour préserver la précision (cohérent
 * avec la sérialisation Pydantic du backend `model_dump(mode='json')`).
 */
export interface Money {
  amount: string
  currency: Currency
}

export interface ExchangeRate {
  base_currency: Currency
  quote_currency: Currency
  rate: string
  as_of: string
  source: string
  fetched_at: string
}

export interface PegPair {
  base_currency: Currency
  quote_currency: Currency
  rate: string
  formula: string
}

export interface RatesLatestResponse {
  rates: ExchangeRate[]
  peg_pairs: PegPair[]
}

export interface ConvertRequest {
  amount: string
  source_currency: Currency
  target_currency: Currency
  date?: string
}

export interface ConvertResponse {
  source: Money
  target: Money
  rate_used: string
  method: 'peg_fixed' | 'table' | 'pivot_usd'
  rate_date: string | null
}

export interface ReferentialDescriptor {
  id: string
  name: string
  version: string
  valid_from: string
}

/**
 * Symboles d'affichage des devises côté UI (FR-061).
 */
export const CURRENCY_SYMBOLS: Record<Currency, string> = {
  XOF: 'FCFA',
  EUR: '€',
  USD: '$',
  GBP: '£',
  JPY: '¥',
}

// Types des blocs visuels (Rich Blocks) pour le rendu dans le chat

import type { Money } from './currency'

// =====================================================================
// F11 — Énumérations partagées avec backend (snake_case → camelCase)
// =====================================================================

export type DeltaDirection = 'up' | 'down' | 'neutral'
export type KPIColor = 'emerald' | 'blue' | 'rose' | 'amber' | 'violet'
export type MarkerType = 'project' | 'intermediary' | 'fund_office' | 'company_hq'
export type ComparisonValueType =
  | 'text'
  | 'money'
  | 'duration'
  | 'percentage'
  | 'rating'
  | 'boolean'

// =====================================================================
// F11 — Props miroir des schémas Pydantic backend (camelCase)
// =====================================================================

export interface KPICardBlockProps {
  title: string
  value: string
  valueMoney?: Money | null
  delta?: number | null
  deltaLabel?: string | null
  deltaDirection?: DeltaDirection | null
  deltaIsGood?: boolean | null
  icon?: string | null
  color: KPIColor
  sourceId?: string | null
  drilldownUrl?: string | null
}

export interface MatchCardBlockProps {
  projectId: string
  offerId: string
  fundName: string
  fundLogoUrl?: string | null
  intermediaryName: string
  intermediaryLogoUrl?: string | null
  compatibilityScore: number
  compatibilityBreakdown?: Record<string, number> | null
  amountRange: string
  timeline: string
  instruments: string[]
  missingCriteriaCount: number
  ctaLabel: string
  drilldownUrl: string
}

export interface MapMarkerProps {
  lat: number
  lon: number
  label: string
  type: MarkerType
  icon?: string | null
  popupContent?: string | null
  drilldownUrl?: string | null
}

export interface MapBlockProps {
  title?: string | null
  center?: [number, number] | null
  zoom: number
  markers: MapMarkerProps[]
  showUemoaOverlay: boolean
}

export interface ComparisonValueProps {
  subjectId: string
  value: string | number
  money?: Money | null
  annotation?: string | null
  sourceId?: string | null
}

export interface ComparisonRowProps {
  label: string
  values: ComparisonValueProps[]
  type: ComparisonValueType
  higherIsBetter: boolean
}

export interface ComparisonSubjectProps {
  id: string
  label: string
  sublabel?: string | null
  drilldownUrl?: string | null
}

export interface ComparisonTableBlockProps {
  title: string
  subjects: ComparisonSubjectProps[]
  rows: ComparisonRowProps[]
  highlightWinner: boolean
}

// Mapping nom de tool → props (anti pattern hardcodé dans le parser).
export type TypedVisualizationToolName =
  | 'show_kpi_card'
  | 'show_match_card'
  | 'show_map'
  | 'show_comparison_table'

export const TYPED_VISUALIZATION_TOOLS: ReadonlySet<string> = new Set<string>([
  'show_kpi_card',
  'show_match_card',
  'show_map',
  'show_comparison_table',
])

// =====================================================================
// Types existants (rétro-compatibles)
// =====================================================================

export interface ChartBlockData {
  type: 'bar' | 'line' | 'pie' | 'doughnut' | 'radar' | 'polarArea'
  data: {
    labels: string[]
    datasets: Array<{
      label: string
      data: number[]
      backgroundColor?: string | string[]
      borderColor?: string | string[]
      [key: string]: unknown
    }>
  }
  options?: Record<string, unknown>
}

export interface TableBlockData {
  headers: string[]
  rows: Array<Array<string | number>>
  highlightColumn?: number
  sortable?: boolean
}

export interface GaugeBlockData {
  value: number
  max: number
  label: string
  thresholds: Array<{ limit: number; color: string }>
  unit?: string
}

export interface ProgressBlockData {
  items: Array<{
    label: string
    value: number
    max: number
    color?: string
  }>
}

export interface TimelineBlockData {
  events: Array<{
    date: string
    title: string
    status: 'done' | 'in_progress' | 'todo'
    description?: string
  }>
}

export type RichBlockType = 'chart' | 'mermaid' | 'table' | 'gauge' | 'progress' | 'timeline'

export interface ParsedSegment {
  type: 'text' | RichBlockType
  content: string
  isComplete: boolean
}

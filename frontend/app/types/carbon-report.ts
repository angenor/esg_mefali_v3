// F21 — Types TypeScript du rapport carbone PDF.

export type CarbonReportStatus =
  | 'pending'
  | 'generating'
  | 'ready'
  | 'completed' // alias legacy F06
  | 'failed'

export interface CarbonReportGenerateResponse {
  id: string
  assessment_id: string
  report_type: 'carbon'
  status: CarbonReportStatus
  created_at: string
}

export interface CarbonReportListItem {
  id: string
  assessment_id: string
  status: CarbonReportStatus
  file_size: number | null
  generated_at: string | null
  created_at: string
  download_url?: string | null
}

export interface CarbonReportListResponse {
  items: CarbonReportListItem[]
  total: number
  page: number
  limit: number
}

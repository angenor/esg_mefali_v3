// Types TypeScript partagés pour ESG Mefali

// F02 — Multi-tenant + Roles
export type Role = 'PME' | 'ADMIN'

export interface AccountSummary {
  id: string
  name: string
  is_active: boolean
  plan: 'free' | 'pro'
}

export interface AccountMember {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  joined_at: string
}

export interface AccountInvitationInviter {
  id: string
  full_name: string
}

export interface AccountInvitation {
  id: string
  email: string
  status: 'pending' | 'accepted' | 'expired' | 'revoked'
  expires_at: string
  invited_by: AccountInvitationInviter
  created_at: string
}

export interface AccountUsersResponse {
  members: AccountMember[]
  pending_invitations: AccountInvitation[]
}

export interface User {
  id: string
  email: string
  full_name: string
  company_name: string
  role?: Role
  account?: AccountSummary | null
  created_at: string
  updated_at?: string
}

export interface Conversation {
  id: string
  title: string
  current_module: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id?: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token?: string
  token_type: string
  expires_in: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
}

export interface ApiError {
  detail: string
}

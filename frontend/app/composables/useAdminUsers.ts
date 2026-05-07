// F09 — Composable admin /users (reset password, toggle active).
//
// Wrappe les endpoints `/api/admin/users/*` exposes par le back-office.
import { useAuth } from '~/composables/useAuth'

export interface ResetPasswordInitiateResponse {
  user_id: string
  email_sent: boolean
  expires_at: string
  backend: string
}

export interface ToggleActiveResponse {
  user_id: string
  is_active: boolean
}

export function useAdminUsers() {
  const { apiFetch } = useAuth()

  async function resetPassword(
    userId: string,
  ): Promise<ResetPasswordInitiateResponse> {
    return await apiFetch<ResetPasswordInitiateResponse>(
      `/admin/users/${userId}/reset-password`,
      { method: 'POST' },
    )
  }

  async function toggleActive(
    userId: string,
    reason: string,
  ): Promise<ToggleActiveResponse> {
    return await apiFetch<ToggleActiveResponse>(
      `/admin/users/${userId}/toggle-active`,
      {
        method: 'POST',
        body: { reason },
      },
    )
  }

  return { resetPassword, toggleActive }
}

import { ref, computed } from 'vue'
import type {
  AccountInvitation,
  AccountMember,
  AccountUsersResponse,
} from '~/types'
import { useAuth } from '~/composables/useAuth'

/**
 * Composable F02 — gestion d'equipe PME (multi-utilisateurs).
 *
 * Expose des actions pour inviter un collaborateur, lister les membres
 * de l'Account et retirer un membre. Les etats reactifs `members`,
 * `pendingInvitations`, `loading`, `error` sont consommes par
 * `pages/account/team.vue`.
 */
export function useAccountTeam() {
  const { apiFetch } = useAuth()

  const members = ref<AccountMember[]>([])
  const pendingInvitations = ref<AccountInvitation[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const hasPendingInvitations = computed(
    () => pendingInvitations.value.length > 0,
  )

  async function listTeam(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data = await apiFetch<AccountUsersResponse>('/account/users')
      members.value = data.members ?? []
      pendingInvitations.value = data.pending_invitations ?? []
    } catch (err: unknown) {
      error.value = extractError(err, 'Impossible de charger l\'equipe')
    } finally {
      loading.value = false
    }
  }

  async function inviteMember(email: string): Promise<AccountInvitation | null> {
    loading.value = true
    error.value = null
    try {
      const invitation = await apiFetch<AccountInvitation>(
        '/account/invite',
        {
          method: 'POST',
          body: JSON.stringify({ email }),
        },
      )
      // Refraichir la liste apres invitation reussie
      await listTeam()
      return invitation
    } catch (err: unknown) {
      error.value = extractError(err, 'Invitation echouee')
      return null
    } finally {
      loading.value = false
    }
  }

  async function removeMember(userId: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      await apiFetch(`/account/users/${userId}`, { method: 'DELETE' })
      await listTeam()
      return true
    } catch (err: unknown) {
      error.value = extractError(err, 'Suppression impossible')
      return false
    } finally {
      loading.value = false
    }
  }

  async function revokeInvitation(invitationId: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      await apiFetch(`/account/invitations/${invitationId}`, {
        method: 'DELETE',
      })
      await listTeam()
      return true
    } catch (err: unknown) {
      error.value = extractError(err, 'Revocation impossible')
      return false
    } finally {
      loading.value = false
    }
  }

  function extractError(err: unknown, fallback: string): string {
    if (err && typeof err === 'object' && 'message' in err) {
      const message = (err as { message: unknown }).message
      if (typeof message === 'string' && message.length > 0) return message
    }
    return fallback
  }

  return {
    members,
    pendingInvitations,
    hasPendingInvitations,
    loading,
    error,
    listTeam,
    inviteMember,
    removeMember,
    revokeInvitation,
  }
}

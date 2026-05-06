import { describe, it, expect, vi, beforeEach } from 'vitest'

/**
 * F02 — Tests useAccountTeam (US3 invitations).
 *
 * Strategie : mocker `useAuth().apiFetch` pour simuler les reponses backend.
 */

const mockApiFetch = vi.fn()

vi.mock('~/composables/useAuth', () => ({
  useAuth: () => ({
    apiFetch: mockApiFetch,
  }),
}))

describe('useAccountTeam', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  describe('listTeam', () => {
    it('charge les membres et invitations en cours', async () => {
      mockApiFetch.mockResolvedValueOnce({
        members: [
          {
            id: 'u1',
            email: 'a@test.com',
            full_name: 'Alice',
            role: 'PME',
            is_active: true,
            joined_at: '2026-01-01',
          },
        ],
        pending_invitations: [],
      })

      const { useAccountTeam } = await import('~/composables/useAccountTeam')
      const team = useAccountTeam()
      await team.listTeam()

      expect(mockApiFetch).toHaveBeenCalledWith('/account/users')
      expect(team.members.value).toHaveLength(1)
      expect(team.members.value[0].full_name).toBe('Alice')
      expect(team.error.value).toBeNull()
    })

    it("met a jour error si l'appel echoue", async () => {
      mockApiFetch.mockRejectedValueOnce(new Error('reseau down'))

      const { useAccountTeam } = await import('~/composables/useAccountTeam')
      const team = useAccountTeam()
      await team.listTeam()

      expect(team.error.value).toContain('reseau down')
    })
  })

  describe('inviteMember', () => {
    it('POST /account/invite et rafraichit la liste', async () => {
      // 1er appel : POST invite -> retourne invitation
      mockApiFetch.mockResolvedValueOnce({
        id: 'inv1',
        email: 'new@test.com',
        status: 'pending',
        expires_at: '2026-12-01',
        invited_by: { id: 'u1', full_name: 'Alice' },
        created_at: '2026-04-15',
      })
      // 2eme appel : GET users (refresh)
      mockApiFetch.mockResolvedValueOnce({
        members: [],
        pending_invitations: [
          {
            id: 'inv1',
            email: 'new@test.com',
            status: 'pending',
            expires_at: '2026-12-01',
            invited_by: { id: 'u1', full_name: 'Alice' },
            created_at: '2026-04-15',
          },
        ],
      })

      const { useAccountTeam } = await import('~/composables/useAccountTeam')
      const team = useAccountTeam()
      const result = await team.inviteMember('new@test.com')

      expect(result?.email).toBe('new@test.com')
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/account/invite',
        expect.objectContaining({ method: 'POST' }),
      )
      expect(team.pendingInvitations.value).toHaveLength(1)
    })

    it("retourne null et set error si l'invitation echoue", async () => {
      mockApiFetch.mockRejectedValueOnce(new Error('email deja invite'))

      const { useAccountTeam } = await import('~/composables/useAccountTeam')
      const team = useAccountTeam()
      const result = await team.inviteMember('dup@test.com')

      expect(result).toBeNull()
      expect(team.error.value).toContain('deja invite')
    })
  })

  describe('removeMember', () => {
    it('DELETE /account/users/:id et rafraichit', async () => {
      // 1er appel : DELETE
      mockApiFetch.mockResolvedValueOnce(undefined)
      // 2eme appel : GET users
      mockApiFetch.mockResolvedValueOnce({
        members: [],
        pending_invitations: [],
      })

      const { useAccountTeam } = await import('~/composables/useAccountTeam')
      const team = useAccountTeam()
      const ok = await team.removeMember('u-target')

      expect(ok).toBe(true)
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/account/users/u-target',
        expect.objectContaining({ method: 'DELETE' }),
      )
    })
  })
})

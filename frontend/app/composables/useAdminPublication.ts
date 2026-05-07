// F09 — Composable admin publication (publish gating).
//
// Tente de publier une entité catalogue. En cas d'erreur 400 avec
// `error: 'publish_gating'`, retourne la liste `blocking_sources`.
import { useAuth } from '~/composables/useAuth'

export type AdminEntityType =
  | 'fund'
  | 'intermediary'
  | 'offer'
  | 'referential'
  | 'indicator'
  | 'criterion'
  | 'emission_factor'
  | 'simulation_factor'

export interface PublishResponse {
  entity_type: string
  entity_id: string
  publication_status: string
  published_at: string | null
}

export interface PublishGatingError {
  error: 'publish_gating'
  message: string
  blocking_sources: string[]
}

const PLURAL_MAP: Record<AdminEntityType, string> = {
  fund: 'funds',
  intermediary: 'intermediaries',
  offer: 'offers',
  referential: 'referentials',
  indicator: 'indicators',
  criterion: 'criteria',
  emission_factor: 'emission-factors',
  simulation_factor: 'simulation-factors',
}

export function useAdminPublication() {
  const { apiFetch } = useAuth()

  async function publishEntity(
    entityType: AdminEntityType,
    entityId: string,
  ): Promise<PublishResponse> {
    const segment = PLURAL_MAP[entityType]
    return await apiFetch<PublishResponse>(
      `/admin/${segment}/${entityId}/publish`,
      { method: 'POST' },
    )
  }

  return { publishEntity }
}

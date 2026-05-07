// F11 — Sélection du tile layer Leaflet selon le thème (light/dark) du store ui.
// Light : OpenStreetMap standard (gratuit, OSM).
// Dark : CartoDB Dark Matter (gratuit, OSM-based, sans clé API).

import { computed, type ComputedRef } from 'vue'
import { useUiStore } from '~/stores/ui'

const OSM_LIGHT_TILE = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const OSM_LIGHT_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

const CARTODB_DARK_TILE =
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
const CARTODB_DARK_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'

export interface UseMapTilesReturn {
  tileUrl: ComputedRef<string>
  attribution: ComputedRef<string>
}

/**
 * Retourne le tile URL et l'attribution Leaflet adaptés au thème courant.
 * Réactif : recalculé automatiquement au toggle dark/light du store ui.
 */
export function useMapTiles(): UseMapTilesReturn {
  const ui = useUiStore()
  const tileUrl = computed(() =>
    ui.theme === 'dark' ? CARTODB_DARK_TILE : OSM_LIGHT_TILE,
  )
  const attribution = computed(() =>
    ui.theme === 'dark' ? CARTODB_DARK_ATTRIBUTION : OSM_LIGHT_ATTRIBUTION,
  )
  return { tileUrl, attribution }
}

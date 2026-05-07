<script setup lang="ts">
// F11 — MapBlock : carte Leaflet UEMOA avec markers SVG colorés et overlay GeoJSON.
// Lazy-load Leaflet en onMounted (Leaflet manipule window/document).
// Tile layer light/dark via composable useMapTiles.

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useMapTiles } from '~/composables/useMapTiles'
import type { MapBlockProps, MapMarkerProps, MarkerType } from '~/types/richblocks'

const props = defineProps<MapBlockProps>()

const emit = defineEmits<{
  navigate: [url: string]
}>()

const { tileUrl, attribution } = useMapTiles()

// Référence au container DOM
const mapContainer = ref<HTMLDivElement | null>(null)

// Référence à l'instance Leaflet
let mapInstance: any = null
let tileLayerInstance: any = null

// Centre régional UEMOA pour défaut
const UEMOA_CENTER: [number, number] = [12.0, -2.0]

// Couleurs SVG par type (FR-013)
const MARKER_COLORS: Record<MarkerType, string> = {
  project: '#10B981',         // emerald-500
  intermediary: '#3B82F6',    // blue-500
  fund_office: '#8B5CF6',     // violet-500
  company_hq: '#F59E0B',      // amber-500
}

const ariaLabel = computed(() => {
  const count = props.markers.length
  return `Carte géographique avec ${count} marqueur(s)`
})

// Construit un divIcon SVG simple coloré (heroicon-like dot).
function buildSvgIcon(L: any, type: MarkerType): any {
  const color = MARKER_COLORS[type] ?? '#10B981'
  const html = `
    <div style="
      display:flex;align-items:center;justify-content:center;
      width:28px;height:28px;border-radius:50%;
      background:${color};border:2px solid white;
      box-shadow:0 2px 4px rgba(0,0,0,0.2);
    ">
      <div style="width:8px;height:8px;background:white;border-radius:50%;"></div>
    </div>
  `
  return L.divIcon({
    html,
    className: '',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })
}

async function initMap() {
  if (!mapContainer.value) return
  // Lazy import : Leaflet manipule window/document.
  const L = (await import('leaflet')).default
  await import('leaflet/dist/leaflet.css')

  // Centre : props.center > markers bounds > UEMOA_CENTER
  const center: [number, number] = props.center ?? UEMOA_CENTER

  mapInstance = L.map(mapContainer.value).setView(center, props.zoom)

  // Tile layer (light/dark)
  tileLayerInstance = L.tileLayer(tileUrl.value, {
    attribution: attribution.value,
    maxZoom: 18,
  }).addTo(mapInstance)

  // Markers
  for (const marker of props.markers) {
    const icon = buildSvgIcon(L, marker.type as MarkerType)
    const m = L.marker([marker.lat, marker.lon], { icon }).addTo(mapInstance)
    if (marker.popupContent) {
      // Sanitisation XSS (FR-013)
      const safe = DOMPurify.sanitize(marker.popupContent)
      m.bindPopup(`<div class="leaflet-popup-content-clean">${safe}<br><strong>${escapeHtml(marker.label)}</strong></div>`)
    } else {
      m.bindPopup(`<strong>${escapeHtml(marker.label)}</strong>`)
    }
    if (marker.drilldownUrl) {
      const url = marker.drilldownUrl
      m.on('click', () => emit('navigate', url))
    }
  }

  // Si plusieurs markers, ajuster les bounds
  if (props.markers.length > 1 && !props.center) {
    const bounds = props.markers.map((mk) => [mk.lat, mk.lon] as [number, number])
    try {
      mapInstance.fitBounds(bounds, { padding: [20, 20] })
    } catch {
      // ignore
    }
  }

  // Overlay GeoJSON UEMOA (lazy fetch)
  if (props.showUemoaOverlay) {
    try {
      const res = await fetch('/_nuxt/assets/geo/uemoa-borders.geo.json')
      if (res.ok) {
        const geo = await res.json()
        L.geoJSON(geo, {
          style: {
            color: '#10B981',
            weight: 1,
            opacity: 0.6,
            fillColor: '#10B981',
            fillOpacity: 0.05,
          },
        }).addTo(mapInstance)
      }
    } catch {
      // Silently ignore GeoJSON loading errors (network, dev server path).
    }
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

onMounted(() => {
  void initMap()
})

onBeforeUnmount(() => {
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
    tileLayerInstance = null
  }
})

// Recalcul du tile layer si toggle dark/light
watch(tileUrl, (newUrl) => {
  if (mapInstance && tileLayerInstance) {
    // Re-créer le tile layer pour appliquer le dark mode
    void (async () => {
      const L = (await import('leaflet')).default
      tileLayerInstance.setUrl?.(newUrl)
    })()
  }
})
</script>

<template>
  <div
    data-test="map-block-root"
    role="region"
    :aria-label="ariaLabel"
    class="map-block my-3 rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card overflow-hidden"
  >
    <h3
      v-if="title"
      class="text-sm font-semibold text-gray-900 dark:text-surface-dark-text px-3 py-2 border-b border-gray-200 dark:border-dark-border"
    >
      {{ title }}
    </h3>
    <div
      ref="mapContainer"
      class="w-full h-72 sm:h-80 md:h-96 bg-gray-100 dark:bg-gray-900"
    />
    <p class="px-3 py-1 text-xs text-gray-500 dark:text-gray-400">
      {{ markers.length }} marqueur{{ markers.length > 1 ? 's' : '' }}
    </p>
  </div>
</template>

<style scoped>
.map-block :deep(.leaflet-container) {
  font-family: inherit;
}
.map-block :deep(.leaflet-popup-content-wrapper) {
  border-radius: 0.5rem;
}
</style>

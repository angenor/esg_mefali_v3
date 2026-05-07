import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import type { MapBlockProps } from '~/types/richblocks'

// Mock Leaflet : éviter d'instancier la lib réelle dans happy-dom
const mockMap = {
  setView: vi.fn(() => mockMap),
  remove: vi.fn(),
  fitBounds: vi.fn(() => mockMap),
}
const mockTileLayer = {
  addTo: vi.fn(() => mockTileLayer),
}
const mockMarker = {
  addTo: vi.fn(() => mockMarker),
  bindPopup: vi.fn(() => mockMarker),
  on: vi.fn(() => mockMarker),
}
const mockGeoJSON = {
  addTo: vi.fn(() => mockGeoJSON),
}
const mockDivIcon = vi.fn(() => ({}))

vi.mock('leaflet', () => ({
  default: {
    map: vi.fn(() => mockMap),
    tileLayer: vi.fn(() => mockTileLayer),
    marker: vi.fn(() => mockMarker),
    geoJSON: vi.fn(() => mockGeoJSON),
    divIcon: mockDivIcon,
    latLngBounds: vi.fn(() => ({})),
  },
}))

// Mock CSS import
vi.mock('leaflet/dist/leaflet.css', () => ({}))

// Mock fetch pour le geojson UEMOA
globalThis.fetch = vi.fn(() => Promise.resolve({
  ok: true,
  json: async () => ({
    type: 'FeatureCollection',
    features: [],
  }),
})) as typeof fetch

import MapBlock from '~/components/richblocks/MapBlock.vue'

function _props(overrides: Partial<MapBlockProps> = {}): MapBlockProps {
  return {
    title: 'Vos interlocuteurs UEMOA',
    zoom: 6,
    showUemoaOverlay: false,
    markers: [
      { lat: 7.6906, lon: -5.0307, label: 'Bouaké', type: 'project' },
      { lat: 6.1319, lon: 1.2228, label: 'Lomé BOAD', type: 'intermediary' },
    ],
    ...overrides,
  }
}

describe('MapBlock (F11)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('rend un container et le titre', async () => {
    const wrapper = mount(MapBlock, { props: _props() })
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('Vos interlocuteurs UEMOA')
  })

  it('appelle Leaflet en onMounted (pas au top-level)', async () => {
    const L = await import('leaflet')
    expect(L.default.map).not.toHaveBeenCalled()
    mount(MapBlock, { props: _props() })
    await flushPromises()
    expect(L.default.map).toHaveBeenCalled()
  })

  it('crée un marker par item dans markers', async () => {
    const L = await import('leaflet')
    mount(MapBlock, { props: _props() })
    await flushPromises()
    expect(L.default.marker).toHaveBeenCalledTimes(2)
  })

  it('charge le GeoJSON UEMOA si showUemoaOverlay=true', async () => {
    mount(MapBlock, { props: _props({ showUemoaOverlay: true }) })
    await flushPromises()
    expect(globalThis.fetch).toHaveBeenCalled()
  })

  it('ne charge pas le GeoJSON si showUemoaOverlay=false', async () => {
    mount(MapBlock, { props: _props({ showUemoaOverlay: false }) })
    await flushPromises()
    // Aucun appel fetch sur geo
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
    const geoCalls = calls.filter(([url]) => String(url).includes('geo'))
    expect(geoCalls.length).toBe(0)
  })

  it('appelle bindPopup si popupContent fourni', async () => {
    mount(MapBlock, {
      props: _props({
        markers: [{
          lat: 7.69,
          lon: -5.03,
          label: 'Test',
          type: 'project',
          popupContent: '<b>Bouaké</b>',
        }],
      }),
    })
    await flushPromises()
    expect(mockMarker.bindPopup).toHaveBeenCalled()
  })

  it('utilise les classes dark: Tailwind', async () => {
    const wrapper = mount(MapBlock, { props: _props() })
    await flushPromises()
    const html = wrapper.html()
    expect(html).toMatch(/dark:/)
  })

  it('expose un attribut role="region" et aria-label', async () => {
    const wrapper = mount(MapBlock, { props: _props() })
    await flushPromises()
    const root = wrapper.find('[data-test="map-block-root"]')
    expect(root.exists()).toBe(true)
    expect(root.attributes('aria-label')).toBeTruthy()
  })

  it('utilise tileLayer (light ou dark selon ui store)', async () => {
    const L = await import('leaflet')
    mount(MapBlock, { props: _props() })
    await flushPromises()
    expect(L.default.tileLayer).toHaveBeenCalled()
    const args = (L.default.tileLayer as ReturnType<typeof vi.fn>).mock.calls[0]
    // Premier argument = URL du tile
    const url = args?.[0] as string
    expect(typeof url).toBe('string')
  })

  it('respecte le zoom passé en props', async () => {
    const L = await import('leaflet')
    mount(MapBlock, { props: _props({ zoom: 10 }) })
    await flushPromises()
    expect(mockMap.setView).toHaveBeenCalled()
    const setViewArgs = mockMap.setView.mock.calls[0]
    expect(setViewArgs?.[1]).toBe(10)
  })

  it('utilise le centre fourni si présent', async () => {
    mount(MapBlock, { props: _props({ center: [12.0, -2.0] }) })
    await flushPromises()
    expect(mockMap.setView).toHaveBeenCalled()
    const setViewArgs = mockMap.setView.mock.calls[0]
    expect(setViewArgs?.[0]).toEqual([12.0, -2.0])
  })
})

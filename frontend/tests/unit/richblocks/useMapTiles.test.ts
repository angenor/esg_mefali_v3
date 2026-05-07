import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUiStore } from '~/stores/ui'
import { useMapTiles } from '~/composables/useMapTiles'

describe('useMapTiles (F11)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('retourne le tile OSM en mode light', () => {
    const ui = useUiStore()
    ui.theme = 'light'
    const { tileUrl, attribution } = useMapTiles()
    expect(tileUrl.value).toContain('openstreetmap.org')
    expect(attribution.value).toContain('OpenStreetMap')
  })

  it('retourne le tile CartoDB Dark Matter en mode dark', () => {
    const ui = useUiStore()
    ui.theme = 'dark'
    const { tileUrl, attribution } = useMapTiles()
    expect(tileUrl.value).toContain('cartocdn.com')
    expect(tileUrl.value).toContain('dark_all')
    // CartoDB respecte aussi l'attribution OSM (sources)
    expect(attribution.value).toContain('OpenStreetMap')
    expect(attribution.value).toContain('CARTO')
  })

  it('réagit au toggle theme (réactif)', async () => {
    const ui = useUiStore()
    ui.theme = 'light'
    const { tileUrl } = useMapTiles()
    const lightUrl = tileUrl.value
    ui.theme = 'dark'
    // Computed réactif → attendre le tick suivant
    await Promise.resolve()
    expect(tileUrl.value).not.toBe(lightUrl)
    expect(tileUrl.value).toContain('dark_all')
  })

  it('expose tileUrl et attribution comme ComputedRef', () => {
    const ui = useUiStore()
    ui.theme = 'light'
    const result = useMapTiles()
    expect(result).toHaveProperty('tileUrl')
    expect(result).toHaveProperty('attribution')
    // computed → .value accessible
    expect(typeof result.tileUrl.value).toBe('string')
    expect(typeof result.attribution.value).toBe('string')
  })
})

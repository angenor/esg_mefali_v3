import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// F2: Constantes partagees — referencees par le composant FloatingChatWidget
export const WIDGET_DEFAULT_WIDTH = 400
export const WIDGET_DEFAULT_HEIGHT = 600
export const WIDGET_MIN_WIDTH = 300
export const WIDGET_MIN_HEIGHT = 400
export const WIDGET_MARGIN = 100

const WIDGET_STORAGE_KEY = 'esg_mefali_widget_size'

// F04 — Préférence d'affichage de devise (Money typed).
const DISPLAY_CURRENCY_MODE_KEY = 'mefali.ui.displayCurrencyMode'
export type DisplayCurrencyMode = 'native' | 'pme' | 'both'
const DISPLAY_CURRENCY_MODE_VALUES: readonly DisplayCurrencyMode[] = ['native', 'pme', 'both']
const DEFAULT_DISPLAY_CURRENCY_MODE: DisplayCurrencyMode = 'both'

export const useUiStore = defineStore('ui', () => {
  const sidebarOpen = ref(true)
  const conversationDrawerOpen = ref(false)
  const chatWidgetOpen = ref(false)
  const chatWidgetMinimized = ref(false)
  const guidedTourActive = ref(false)
  const currentPage = ref<string>('/')
  const chatWidgetWidth = ref(WIDGET_DEFAULT_WIDTH)
  const chatWidgetHeight = ref(WIDGET_DEFAULT_HEIGHT)
  const theme = ref<'light' | 'dark'>('light')
  const prefersReducedMotion = ref(false)
  // F04 — préférence affichage de devise (native, pme, both).
  const displayCurrencyMode = ref<DisplayCurrencyMode>(DEFAULT_DISPLAY_CURRENCY_MODE)
  let _reducedMotionQuery: MediaQueryList | null = null
  let _reducedMotionHandler: ((e: MediaQueryListEvent) => void) | null = null

  function initTheme() {
    if (import.meta.client) {
      const saved = localStorage.getItem('esg-theme')
      if (saved === 'dark' || saved === 'light') {
        theme.value = saved
      } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        theme.value = 'dark'
      }
      applyTheme()
    }
  }

  function applyTheme() {
    if (import.meta.client) {
      document.documentElement.classList.toggle('dark', theme.value === 'dark')
    }
  }

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    if (import.meta.client) {
      localStorage.setItem('esg-theme', theme.value)
    }
    applyTheme()
  }

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function toggleConversationDrawer() {
    conversationDrawerOpen.value = !conversationDrawerOpen.value
  }

  function toggleChatWidget() {
    chatWidgetOpen.value = !chatWidgetOpen.value
  }

  function openChatWidget() {
    chatWidgetOpen.value = true
  }

  function closeChatWidget() {
    chatWidgetOpen.value = false
  }

  // F3: Validation — rejette les valeurs invalides (negatif, zero, NaN, non-fini)
  function isValidDimension(n: number): boolean {
    return Number.isFinite(n) && n > 0
  }

  function initWidgetSize() {
    if (import.meta.client) {
      try {
        const saved = localStorage.getItem(WIDGET_STORAGE_KEY)
        if (saved) {
          const parsed = JSON.parse(saved)
          if (
            typeof parsed === 'object' && parsed !== null
            && typeof parsed.width === 'number' && typeof parsed.height === 'number'
            && isValidDimension(parsed.width) && isValidDimension(parsed.height)
          ) {
            chatWidgetWidth.value = parsed.width
            chatWidgetHeight.value = parsed.height
          }
        }
      } catch {
        // Donnees invalides — garder les defauts
      }
    }
  }

  function setChatWidgetSize(width: number, height: number) {
    // F3: Validation des entrees — clamp aux bornes connues
    const w = isValidDimension(width) ? Math.max(width, WIDGET_MIN_WIDTH) : WIDGET_DEFAULT_WIDTH
    const h = isValidDimension(height) ? Math.max(height, WIDGET_MIN_HEIGHT) : WIDGET_DEFAULT_HEIGHT
    chatWidgetWidth.value = w
    chatWidgetHeight.value = h
    if (import.meta.client) {
      localStorage.setItem(WIDGET_STORAGE_KEY, JSON.stringify({ width: w, height: h }))
    }
  }

  function resetChatWidgetSize() {
    chatWidgetWidth.value = WIDGET_DEFAULT_WIDTH
    chatWidgetHeight.value = WIDGET_DEFAULT_HEIGHT
    if (import.meta.client) {
      localStorage.removeItem(WIDGET_STORAGE_KEY)
    }
  }

  function initReducedMotion() {
    if (import.meta.client) {
      // F2: guard contre les appels multiples (HMR, tests)
      destroyReducedMotion()
      _reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
      prefersReducedMotion.value = _reducedMotionQuery.matches
      _reducedMotionHandler = (e) => { prefersReducedMotion.value = e.matches }
      _reducedMotionQuery.addEventListener('change', _reducedMotionHandler)
    }
  }

  function destroyReducedMotion() {
    if (_reducedMotionQuery && _reducedMotionHandler) {
      _reducedMotionQuery.removeEventListener('change', _reducedMotionHandler)
      _reducedMotionHandler = null
      _reducedMotionQuery = null
    }
  }

  function setTheme(newTheme: 'light' | 'dark') {
    theme.value = newTheme
    if (import.meta.client) {
      localStorage.setItem('esg-theme', newTheme)
    }
    applyTheme()
  }

  // F04 — chargement / persistance du mode d'affichage devise.
  function initDisplayCurrencyMode() {
    if (import.meta.client) {
      const saved = localStorage.getItem(DISPLAY_CURRENCY_MODE_KEY)
      if (saved && DISPLAY_CURRENCY_MODE_VALUES.includes(saved as DisplayCurrencyMode)) {
        displayCurrencyMode.value = saved as DisplayCurrencyMode
      }
    }
  }

  function setDisplayCurrencyMode(mode: DisplayCurrencyMode): void {
    if (!DISPLAY_CURRENCY_MODE_VALUES.includes(mode)) {
      // Validation : ignore silencieusement les valeurs invalides
      return
    }
    displayCurrencyMode.value = mode
    if (import.meta.client) {
      localStorage.setItem(DISPLAY_CURRENCY_MODE_KEY, mode)
    }
  }

  return {
    sidebarOpen,
    conversationDrawerOpen,
    chatWidgetOpen,
    chatWidgetMinimized,
    guidedTourActive,
    currentPage,
    chatWidgetWidth,
    chatWidgetHeight,
    theme,
    prefersReducedMotion,
    displayCurrencyMode,
    initTheme,
    initReducedMotion,
    destroyReducedMotion,
    initWidgetSize,
    setChatWidgetSize,
    resetChatWidgetSize,
    toggleSidebar,
    toggleConversationDrawer,
    toggleChatWidget,
    openChatWidget,
    closeChatWidget,
    toggleTheme,
    setTheme,
    initDisplayCurrencyMode,
    setDisplayCurrencyMode,
  }
})

/**
 * F10 — Composable pour le pattern click-and-hold 2 secondes (actions destructives).
 *
 * Implémentation native (zéro dépendance) avec :
 * - listeners pointer events (pointerdown/pointerup/pointercancel)
 * - équivalent clavier (Entrée maintenue 2s, Escape pour annuler)
 * - respect de `prefers-reduced-motion: reduce` (compteur textuel à la place
 *   de l'animation)
 *
 * Usage dans un widget :
 * ```vue
 * const { isHolding, progress, holdInstructions, onPointerDown, onPointerUp,
 *         onPointerCancel, onKeyDown, onKeyUp } = useHoldToConfirm({
 *   durationMs: 2000,
 *   onConfirmed: () => emit('submit', payload),
 * })
 * ```
 */

import { computed, onBeforeUnmount, ref } from 'vue'

interface UseHoldToConfirmOptions {
  durationMs?: number
  onConfirmed: () => void
}

export function useHoldToConfirm(options: UseHoldToConfirmOptions): {
  isHolding: ReturnType<typeof ref<boolean>>
  progress: ReturnType<typeof ref<number>>
  prefersReducedMotion: ReturnType<typeof ref<boolean>>
  holdInstructions: ReturnType<typeof computed<string>>
  onPointerDown: (e: PointerEvent) => void
  onPointerUp: (e?: PointerEvent) => void
  onPointerCancel: (e?: PointerEvent) => void
  onKeyDown: (e: KeyboardEvent) => void
  onKeyUp: (e: KeyboardEvent) => void
} {
  const durationMs = options.durationMs ?? 2000
  const isHolding = ref(false)
  const progress = ref(0) // 0 → 1
  const prefersReducedMotion = ref(false)

  let rafId: number | null = null
  let startedAt: number | null = null
  let confirmTimer: ReturnType<typeof setTimeout> | null = null

  // Détection de prefers-reduced-motion (côté client uniquement)
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)')
    prefersReducedMotion.value = mql.matches
    const handler = (ev: MediaQueryListEvent) => {
      prefersReducedMotion.value = ev.matches
    }
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', handler)
      onBeforeUnmount(() => mql.removeEventListener('change', handler))
    }
  }

  const holdInstructions = computed(() => {
    if (!isHolding.value) {
      return prefersReducedMotion.value
        ? `Maintenez Entrée pendant ${Math.round(durationMs / 1000)} secondes pour confirmer.`
        : 'Maintenez le bouton pour confirmer.'
    }
    const remaining = Math.ceil((1 - progress.value) * (durationMs / 1000))
    return `Maintenez encore ${remaining} seconde${remaining > 1 ? 's' : ''}…`
  })

  function _tick(now: number): void {
    if (startedAt === null || !isHolding.value) return
    const elapsed = now - startedAt
    progress.value = Math.min(1, elapsed / durationMs)
    if (progress.value < 1) {
      rafId = requestAnimationFrame(_tick)
    }
  }

  function _start(): void {
    if (isHolding.value) return
    isHolding.value = true
    progress.value = 0
    startedAt = performance.now()

    if (!prefersReducedMotion.value) {
      rafId = requestAnimationFrame(_tick)
    } else {
      // En mode reduced-motion, on n'anime pas le ring mais on garde le timer.
      // Le compteur textuel est mis à jour via un setInterval pour le UX.
      const intervalId = setInterval(() => {
        if (!isHolding.value || startedAt === null) {
          clearInterval(intervalId)
          return
        }
        const elapsed = performance.now() - startedAt
        progress.value = Math.min(1, elapsed / durationMs)
        if (progress.value >= 1) clearInterval(intervalId)
      }, 250)
    }

    confirmTimer = setTimeout(() => {
      if (isHolding.value) {
        progress.value = 1
        try {
          options.onConfirmed()
        } finally {
          _reset()
        }
      }
    }, durationMs)
  }

  function _reset(): void {
    isHolding.value = false
    progress.value = 0
    startedAt = null
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (confirmTimer !== null) {
      clearTimeout(confirmTimer)
      confirmTimer = null
    }
  }

  function onPointerDown(_e: PointerEvent): void {
    _start()
  }
  function onPointerUp(_e?: PointerEvent): void {
    _reset()
  }
  function onPointerCancel(_e?: PointerEvent): void {
    _reset()
  }
  function onKeyDown(e: KeyboardEvent): void {
    // Entrée OU Espace (accessibilité clavier)
    if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) {
      e.preventDefault()
      _start()
    } else if (e.key === 'Escape') {
      _reset()
    }
  }
  function onKeyUp(e: KeyboardEvent): void {
    if (e.key === 'Enter' || e.key === ' ') {
      _reset()
    }
  }

  onBeforeUnmount(() => _reset())

  return {
    isHolding,
    progress,
    prefersReducedMotion,
    holdInstructions,
    onPointerDown,
    onPointerUp,
    onPointerCancel,
    onKeyDown,
    onKeyUp,
  }
}

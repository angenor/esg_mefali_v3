<script setup lang="ts">
/**
 * F18 — Modale demande de consentement (RGPD F05).
 *
 * Composant réutilisable affiché lorsqu'une fonctionnalité requiert un
 * consentement non encore accordé. Propose à l'utilisateur de :
 *  - lire la finalité du traitement,
 *  - accorder le consentement directement (action principale),
 *  - être redirigé vers la page /mes-donnees/consentements (action secondaire).
 *
 * Émissions :
 *  - ``confirm`` : l'utilisateur accepte d'accorder le consentement.
 *  - ``cancel``  : l'utilisateur ferme la modale sans action.
 */
import { computed } from 'vue'

interface Props {
  open: boolean
  consentType:
    | 'mobile_money_analysis'
    | 'photos_ia_analysis'
    | 'public_data_analysis'
  loading?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const labels: Record<Props['consentType'], { title: string; body: string }> = {
  mobile_money_analysis: {
    title: 'Analyse Mobile Money',
    body:
      "Pour calculer votre score crédit alternatif, nous avons besoin de votre " +
      "consentement pour analyser vos flux Mobile Money (Wave, Orange Money, " +
      "MTN, Moov). Vos données sont anonymisées (hash des contre-parties) et " +
      "vous pouvez révoquer ce consentement à tout moment.",
  },
  photos_ia_analysis: {
    title: 'Analyse IA des photos',
    body:
      "Pour enrichir votre profil, l'IA peut analyser des photos de votre " +
      "exploitation (équipements, espace, stocks). Les photos sont stockées " +
      "chiffrées et purgées 30 jours après révocation.",
  },
  public_data_analysis: {
    title: 'Analyse de données publiques',
    body:
      "Vous pouvez déclarer vos sources publiques (Google My Business, " +
      "Trustpilot, programmes verts) pour enrichir votre score. Cette " +
      "catégorie est plafonnée à 10 % du score combiné.",
  },
}

const meta = computed(() => labels[props.consentType])
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 dark:bg-black/60 px-4"
        role="dialog"
        :aria-labelledby="`consent-modal-title-${consentType}`"
        :aria-describedby="`consent-modal-body-${consentType}`"
        aria-modal="true"
        @click.self="emit('cancel')"
      >
        <div
          class="w-full max-w-md rounded-lg bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border shadow-xl p-6"
        >
          <h2
            :id="`consent-modal-title-${consentType}`"
            class="text-lg font-semibold text-surface-text dark:text-surface-dark-text"
          >
            {{ meta.title }} — consentement requis
          </h2>
          <p
            :id="`consent-modal-body-${consentType}`"
            class="mt-3 text-sm text-gray-700 dark:text-gray-300"
          >
            {{ meta.body }}
          </p>

          <div class="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <button
              type="button"
              class="px-4 py-2 rounded-md border border-gray-300 dark:border-dark-border text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover transition-colors"
              :disabled="loading"
              @click="emit('cancel')"
            >
              Annuler
            </button>
            <button
              type="button"
              class="px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50 transition-colors"
              :disabled="loading"
              @click="emit('confirm')"
            >
              {{ loading ? 'Enregistrement…' : "J'accorde mon consentement" }}
            </button>
          </div>

          <p class="mt-3 text-[11px] text-gray-500 dark:text-gray-400">
            Vous pouvez révoquer ce consentement à tout moment depuis
            <a
              href="/mes-donnees/consentements"
              class="text-emerald-700 dark:text-emerald-400 hover:underline"
            >
              /mes-donnees/consentements
            </a>.
          </p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

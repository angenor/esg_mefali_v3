<script setup lang="ts">
/**
 * F18 — Bouton de révocation d'un consentement (RGPD F05).
 *
 * Affiche un bouton avec une confirmation native (window.confirm) avant
 * d'émettre l'événement ``revoke``. La révocation effective est gérée par
 * le parent (qui appelle l'API ``/api/me/consents/{type}/revoke``).
 *
 * Avertit l'utilisateur que les données associées seront purgées sous 30
 * jours (FR-005, SC-008 F18).
 */
import { ref } from 'vue'

interface Props {
  consentType:
    | 'mobile_money_analysis'
    | 'photos_ia_analysis'
    | 'public_data_analysis'
  label?: string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  label: 'Révoquer ce consentement',
  loading: false,
})

const emit = defineEmits<{
  revoke: [consentType: Props['consentType']]
}>()

const showConfirm = ref(false)

function handleClick() {
  if (props.loading) return
  showConfirm.value = true
}

function confirmRevoke() {
  emit('revoke', props.consentType)
  showConfirm.value = false
}

function cancelRevoke() {
  showConfirm.value = false
}
</script>

<template>
  <div class="inline-block">
    <button
      type="button"
      class="px-3 py-1.5 rounded-md text-xs font-semibold text-red-700 dark:text-red-300 border border-red-300 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50 transition-colors"
      :disabled="loading"
      :aria-label="`${label} pour ${consentType}`"
      @click="handleClick"
    >
      {{ loading ? 'Révocation…' : label }}
    </button>

    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showConfirm"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 dark:bg-black/60 px-4"
          role="alertdialog"
          aria-labelledby="revoke-confirm-title"
          aria-modal="true"
          @click.self="cancelRevoke"
        >
          <div
            class="w-full max-w-md rounded-lg bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border shadow-xl p-6"
          >
            <h2
              id="revoke-confirm-title"
              class="text-lg font-semibold text-surface-text dark:text-surface-dark-text"
            >
              Confirmer la révocation
            </h2>
            <p class="mt-3 text-sm text-gray-700 dark:text-gray-300">
              Vous êtes sur le point de révoquer votre consentement
              <strong>{{ consentType }}</strong>. Les données associées seront
              marquées comme inutilisées et automatiquement purgées sous
              <strong>30 jours</strong>.
            </p>
            <p class="mt-2 text-xs text-gray-500 dark:text-gray-400">
              Vous pourrez ré-accorder ce consentement à tout moment, mais les
              données purgées ne pourront pas être restaurées.
            </p>
            <div
              class="mt-5 flex flex-col-reverse sm:flex-row sm:justify-end gap-2"
            >
              <button
                type="button"
                class="px-4 py-2 rounded-md border border-gray-300 dark:border-dark-border text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover transition-colors"
                @click="cancelRevoke"
              >
                Annuler
              </button>
              <button
                type="button"
                class="px-4 py-2 rounded-md bg-red-600 hover:bg-red-700 text-white transition-colors"
                @click="confirmRevoke"
              >
                Confirmer la révocation
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
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

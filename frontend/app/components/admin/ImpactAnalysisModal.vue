<script setup lang="ts">
// F09 PRIO 3 — Modal d'analyse d'impact avant suppression destructive.
//
// Affiche les entités dépendantes (groupées par type) avant de demander
// confirmation de la suppression. Utilisé pour les sources, référentiels,
// indicateurs, fonds, intermédiaires.
import { computed } from 'vue'

interface DependentGroup {
  label: string
  count: number
  items?: Array<{ id: string; label?: string }>
}

interface Props {
  open: boolean
  entityType: string
  entityId: string
  entityLabel?: string
  dependentGroups: DependentGroup[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  entityLabel: '',
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'force-delete'): void
}>()

const totalDeps = computed(() =>
  props.dependentGroups.reduce((acc, g) => acc + g.count, 0),
)

const hasDependents = computed(() => totalDeps.value > 0)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="`impact-modal-title-${entityId}`"
      data-testid="impact-analysis-modal"
      @click.self="emit('close')"
    >
      <div
        class="w-full max-w-lg rounded-2xl bg-white dark:bg-dark-card border border-gray-200 dark:border-dark-border p-6 shadow-2xl"
      >
        <h2
          :id="`impact-modal-title-${entityId}`"
          class="text-xl font-bold text-surface-text dark:text-surface-dark-text"
        >
          Analyse d'impact
        </h2>
        <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
          Suppression de
          <span class="font-medium text-surface-text dark:text-surface-dark-text">
            {{ entityLabel || `${entityType} ${entityId}` }}
          </span>
        </p>

        <div v-if="loading" class="mt-6 text-center text-gray-500 dark:text-gray-400">
          Calcul des dépendances…
        </div>

        <div v-else-if="!hasDependents" class="mt-6">
          <p class="rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 p-3 text-sm text-emerald-700 dark:text-emerald-300">
            Aucune entité dépendante. La suppression est sûre.
          </p>
        </div>

        <div v-else class="mt-4">
          <p
            class="rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 p-3 text-sm text-amber-800 dark:text-amber-300 mb-4"
          >
            {{ totalDeps }} entité(s) dépendante(s) trouvée(s). La
            suppression forcée propagera <code>valid_to=today</code> en
            cascade.
          </p>

          <ul class="space-y-2 text-sm">
            <li
              v-for="group in dependentGroups"
              :key="group.label"
              class="flex justify-between rounded-lg bg-gray-50 dark:bg-gray-800/40 px-3 py-2"
            >
              <span class="text-surface-text dark:text-surface-dark-text">
                {{ group.label }}
              </span>
              <span class="font-medium text-rose-600 dark:text-rose-400">
                {{ group.count }}
              </span>
            </li>
          </ul>
        </div>

        <div class="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            class="rounded-lg border border-gray-300 dark:border-dark-border px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-dark-hover"
            data-testid="impact-cancel"
            @click="emit('close')"
          >
            Annuler
          </button>
          <button
            v-if="hasDependents"
            type="button"
            class="rounded-lg bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 text-sm font-medium"
            data-testid="impact-force-delete"
            @click="emit('force-delete')"
          >
            Forcer la suppression
          </button>
          <button
            v-else
            type="button"
            class="rounded-lg bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 text-sm font-medium"
            data-testid="impact-confirm-delete"
            @click="emit('force-delete')"
          >
            Confirmer la suppression
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

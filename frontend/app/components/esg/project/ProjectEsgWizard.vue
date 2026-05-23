<script setup lang="ts">
/**
 * F047 — Orchestrateur multi-étapes : choix référentiel → critères → revue → finalisation.
 */
import { computed, onMounted, ref } from 'vue'
import EsgCriterionWidget from '~/components/esg/project/EsgCriterionWidget.vue'
import EsgReferentialPicker from '~/components/esg/project/EsgReferentialPicker.vue'
import EsgScoreDisplay from '~/components/esg/project/EsgScoreDisplay.vue'
import EsgTargetBadge from '~/components/esg/project/EsgTargetBadge.vue'
import { useProjectEsgStore } from '~/stores/projectEsg'
import type {
  EsgReferentialRef,
  ProjectEsgCriterionResponseSavePayload,
} from '~/types/projectEsg'

interface CriterionLike {
  id: string
  code: string
  label: string
  is_required: boolean
}

interface Props {
  projectId: string
  referentials: EsgReferentialRef[]
  // Liste plate des critères disponibles, fournie par la page parente
  // (en MVP on charge tous les critères de tous les référentiels et on filtre côté UI).
  criteriaByReferentialId: Record<string, CriterionLike[]>
}
const props = defineProps<Props>()

const store = useProjectEsgStore()
const step = ref<1 | 2 | 3>(1)
const selectedReferentialId = ref<string | null>(null)
const finalizing = ref(false)
const finalizeError = ref('')

const currentCriteria = computed<CriterionLike[]>(() => {
  if (!selectedReferentialId.value) return []
  return props.criteriaByReferentialId[selectedReferentialId.value] || []
})
const respondedIds = computed(
  () => new Set(store.currentAssessment?.responses.map((r) => r.criterion_id) ?? []),
)
const remainingRequired = computed(() =>
  currentCriteria.value.filter(
    (c) => c.is_required && !respondedIds.value.has(c.id),
  ),
)

onMounted(async () => {
  await store.loadList(props.projectId)
})

async function start() {
  if (!selectedReferentialId.value) return
  const a = await store.startAssessment(
    props.projectId,
    selectedReferentialId.value,
  )
  if (a) step.value = 2
}

async function onSave(payload: ProjectEsgCriterionResponseSavePayload) {
  await store.saveCriterion(props.projectId, payload)
}

async function onFinalize() {
  finalizing.value = true
  finalizeError.value = ''
  const result = await store.finalize(props.projectId)
  finalizing.value = false
  if (result) {
    step.value = 3
  } else {
    finalizeError.value = store.error || 'Échec de la finalisation'
  }
}

function resume(assessmentId: string) {
  store.loadDetail(props.projectId, assessmentId).then((d) => {
    if (d) {
      selectedReferentialId.value = d.referential_id
      step.value = d.state === 'finalized' ? 3 : 2
    }
  })
}
</script>

<template>
  <div class="space-y-6">
    <header class="flex items-center justify-between flex-wrap gap-2">
      <div class="flex items-center gap-2">
        <EsgTargetBadge target="project" />
        <h2 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text">
          Évaluation ESG du projet
        </h2>
      </div>
      <nav aria-label="Étapes" class="flex items-center gap-2 text-xs">
        <span
          v-for="(label, i) in ['Référentiel', 'Critères', 'Score']"
          :key="i"
          :class="[
            'px-2 py-0.5 rounded',
            step === i + 1
              ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200 font-semibold'
              : 'text-gray-500 dark:text-gray-500',
          ]"
        >
          {{ i + 1 }}. {{ label }}
        </span>
      </nav>
    </header>

    <!-- Liste évaluations existantes -->
    <section
      v-if="store.assessments.length"
      class="rounded-lg ring-1 ring-gray-200 dark:ring-dark-border bg-surface-bg dark:bg-surface-dark-bg p-3"
    >
      <h3 class="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
        Évaluations précédentes
      </h3>
      <ul class="space-y-1">
        <li
          v-for="a in store.assessments"
          :key="a.id"
          class="flex items-center justify-between text-sm text-surface-text dark:text-surface-dark-text"
        >
          <span>
            {{ a.state === 'finalized' ? `Score ${a.score}/100` : 'En cours' }}
            — {{ new Date(a.created_at).toLocaleDateString('fr-FR') }}
          </span>
          <button
            type="button"
            class="text-xs text-emerald-700 dark:text-emerald-400 hover:underline"
            @click="resume(a.id)"
          >
            Reprendre
          </button>
        </li>
      </ul>
    </section>

    <!-- Étape 1 : choix référentiel -->
    <section v-if="step === 1">
      <h3 class="text-sm font-medium text-surface-text dark:text-surface-dark-text mb-2">
        Contre quel référentiel souhaitez-vous évaluer ce projet ?
      </h3>
      <EsgReferentialPicker
        v-model="selectedReferentialId"
        :referentials="referentials"
        :disabled="store.loading"
      />
      <div class="mt-4 flex justify-end">
        <button
          type="button"
          :disabled="!selectedReferentialId || store.loading"
          class="px-4 py-2 text-sm font-semibold rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
          @click="start"
        >
          Démarrer l'évaluation
        </button>
      </div>
    </section>

    <!-- Étape 2 : critères -->
    <section v-else-if="step === 2 && store.currentAssessment">
      <div class="mb-4">
        <div class="flex items-center justify-between mb-1 text-xs text-gray-600 dark:text-gray-400">
          <span>Progression</span>
          <span>{{ store.progressPercent }}%</span>
        </div>
        <div class="h-2 rounded bg-gray-200 dark:bg-dark-hover overflow-hidden">
          <div
            class="h-full bg-emerald-500 transition-all"
            :style="{ width: `${store.progressPercent}%` }"
          />
        </div>
      </div>

      <div class="space-y-3">
        <EsgCriterionWidget
          v-for="crit in currentCriteria"
          :key="crit.id"
          :criterion="crit"
          @save="onSave"
        />
      </div>

      <div class="mt-6 flex items-center justify-between gap-3">
        <p v-if="remainingRequired.length" class="text-xs text-amber-700 dark:text-amber-400">
          {{ remainingRequired.length }} critère(s) obligatoire(s) restant(s)
        </p>
        <button
          type="button"
          :disabled="remainingRequired.length > 0 || finalizing"
          class="px-4 py-2 text-sm font-semibold rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
          @click="onFinalize"
        >
          {{ finalizing ? 'Finalisation…' : 'Finaliser l\'évaluation' }}
        </button>
      </div>
      <p v-if="finalizeError" role="alert" class="mt-2 text-xs text-red-600 dark:text-red-400">
        {{ finalizeError }}
      </p>
    </section>

    <!-- Étape 3 : score -->
    <section v-else-if="step === 3 && store.currentAssessment">
      <EsgScoreDisplay :assessment="store.currentAssessment" />
      <div class="mt-4 flex justify-end gap-2">
        <button
          type="button"
          class="px-4 py-2 text-sm font-medium rounded ring-1 ring-gray-300 dark:ring-dark-border text-surface-text dark:text-surface-dark-text hover:bg-gray-50 dark:hover:bg-dark-hover"
          @click="() => { store.reset(); step = 1; selectedReferentialId = null; }"
        >
          Nouvelle évaluation
        </button>
      </div>
    </section>
  </div>
</template>

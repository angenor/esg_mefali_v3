<script setup lang="ts">
// F23 — Bouton "Tester" + affichage SkillEvalReport.
import { ref } from 'vue'
import { useAdminSkills } from '~/composables/useAdminSkills'
import type { SkillEvalReport } from '~/types/skills'

const props = defineProps<{
  skillId: string
}>()

const { testSkill } = useAdminSkills()

const report = ref<SkillEvalReport | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function runTest() {
  loading.value = true
  error.value = null
  try {
    report.value = await testSkill(props.skillId)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="bg-white dark:bg-dark-card rounded-lg border border-gray-200 dark:border-dark-border p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold text-surface-text dark:text-surface-dark-text">
        Tester (sans publier)
      </h3>
      <button
        :disabled="loading"
        class="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm"
        @click="runTest"
      >
        {{ loading ? 'Test en cours...' : 'Lancer le test' }}
      </button>
    </div>
    <p v-if="error" class="text-red-600 dark:text-red-400 text-sm">{{ error }}</p>
    <div v-if="report" class="space-y-2">
      <div
        :class="[
          'inline-flex items-center gap-2 px-3 py-1 rounded font-medium',
          report.gate_passed
            ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200'
            : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200',
        ]"
      >
        <span>{{ report.gate_passed ? 'Gate passé' : 'Gate échoué' }}</span>
        <span class="text-sm font-normal">
          ({{ (report.success_rate * 100).toFixed(0) }}% / seuil {{ (report.threshold * 100).toFixed(0) }}%)
        </span>
      </div>
      <p class="text-sm text-gray-600 dark:text-gray-400">
        {{ report.passed }} / {{ report.total_cases }} cas passants ({{ report.duration_seconds.toFixed(1) }}s)
      </p>
      <div v-if="report.failed_cases.length > 0">
        <h4 class="font-medium text-surface-text dark:text-surface-dark-text mt-3 mb-1">
          Cas en échec
        </h4>
        <ul class="space-y-1 text-sm">
          <li
            v-for="fc in report.failed_cases"
            :key="fc.case_id"
            class="px-3 py-2 rounded bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200"
          >
            <p class="font-mono">{{ fc.case_id }}</p>
            <p class="text-xs">
              attendu : {{ Array.isArray(fc.expected_tool) ? fc.expected_tool.join(' / ') : fc.expected_tool }}
            </p>
            <p class="text-xs">obtenu : {{ fc.actual_tool ?? '(aucun)' }}</p>
            <p v-if="fc.error" class="text-xs italic">{{ fc.error }}</p>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

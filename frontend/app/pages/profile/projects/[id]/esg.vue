<script setup lang="ts">
/**
 * F047 — Page d'évaluation ESG-projet (US1).
 * URL : /profile/projects/[id]/esg
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import ProjectEsgWizard from '~/components/esg/project/ProjectEsgWizard.vue'
import EsgTargetBadge from '~/components/esg/project/EsgTargetBadge.vue'
import EsgReportPreview from '~/components/esg/project/EsgReportPreview.vue'
import { useProjectEsgStore } from '~/stores/projectEsg'
import type { EsgReferentialRef } from '~/types/projectEsg'

const route = useRoute()
const projectId = computed(() => String(route.params.id))

// F047 (US3) — État partagé pour activer l'aperçu rapport.
const projectEsgStore = useProjectEsgStore()
const currentAssessmentId = computed(() => projectEsgStore.currentAssessment?.id ?? null)
const isFinalized = computed(() => projectEsgStore.isFinalized)

// MVP — référentiels chargés via endpoint catalogue F13 (suppose le catalogue existant).
// En attendant l'endpoint dédié, on fournit des stubs alignés sur le seed 047.
const referentials = ref<EsgReferentialRef[]>([])
const criteriaByReferentialId = ref<Record<string, { id: string; code: string; label: string; is_required: boolean }[]>>(
  {},
)
const loading = ref(true)
const error = ref('')

async function loadCatalog() {
  const auth = (await import('~/stores/auth')).useAuthStore()
  const config = useRuntimeConfig()
  const headers = {
    'Content-Type': 'application/json',
    ...(auth.accessToken ? { Authorization: `Bearer ${auth.accessToken}` } : {}),
  }
  try {
    const res = await fetch(`${config.public.apiBase}/sources/referentials`, {
      headers,
    })
    if (res.ok) {
      const items = await res.json()
      referentials.value = (Array.isArray(items) ? items : []).map((r: any) => ({
        id: r.id,
        code: r.code,
        label: r.label,
        description: r.description,
      }))
    }
    // Charger les critères applicables au projet
    const cRes = await fetch(`${config.public.apiBase}/sources/criteria?applies_to_project=true`, {
      headers,
    })
    if (cRes.ok) {
      const crits = await cRes.json()
      const grouped: Record<string, any[]> = {}
      for (const c of crits) {
        if (!c.referential_id) continue
        const refId = c.referential_id as string
        const list = grouped[refId] ?? (grouped[refId] = [])
        list.push({
          id: c.id,
          code: c.code,
          label: c.label,
          is_required: c.is_required,
        })
      }
      criteriaByReferentialId.value = grouped
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur de chargement du catalogue'
  } finally {
    loading.value = false
  }
}

onMounted(loadCatalog)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-6">
    <NuxtLink
      :to="`/profile/projects/${projectId}`"
      class="text-xs text-gray-600 dark:text-gray-400 hover:underline mb-2 inline-block"
    >
      ← Retour à la fiche projet
    </NuxtLink>

    <div class="flex items-center gap-2 mb-1">
      <EsgTargetBadge target="project" />
    </div>
    <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text mb-4">
      Évaluation ESG du projet
    </h1>

    <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">
      Évaluez ce projet contre un référentiel reconnu par les bailleurs verts
      (IFC PS / GCF ESS / BOAD ESS) afin d'obtenir un score 0..100 sourcé et
      éligible au matching projet-centric.
    </p>

    <div v-if="loading" class="text-center py-12 text-gray-500">
      Chargement du catalogue ESG…
    </div>
    <div
      v-else-if="error"
      role="alert"
      class="p-3 rounded ring-1 ring-red-300 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-300 text-sm"
    >
      {{ error }}
    </div>
    <ProjectEsgWizard
      v-else
      :project-id="projectId"
      :referentials="referentials"
      :criteria-by-referential-id="criteriaByReferentialId"
    />

    <!-- F047 (US3) — Aperçu + bouton de génération PDF dès qu'une évaluation est finalisée. -->
    <div v-if="currentAssessmentId" class="mt-8">
      <EsgReportPreview
        :project-id="projectId"
        :assessment-id="currentAssessmentId"
        :is-finalized="isFinalized"
      />
    </div>
  </div>
</template>

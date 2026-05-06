<script setup lang="ts">
// F02 — Page de sante du systeme reservee aux Admin.
//
// Acces via middleware `admin` (F02) + layout `admin` (accent rouge).
// Le test E2E US2 verifie qu'un PME tentant d'acceder a /admin/health
// est redirige vers /dashboard.
import { onMounted, ref } from 'vue'
import { useAuth } from '~/composables/useAuth'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

interface HealthResponse {
  status: string
  role: string
  service: string
}

const { apiFetch } = useAuth()
const health = ref<HealthResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function fetchHealth() {
  loading.value = true
  error.value = null
  try {
    health.value = await apiFetch<HealthResponse>('/admin/health')
  } catch (err: unknown) {
    error.value =
      err && typeof err === 'object' && 'message' in err
        ? String((err as { message: unknown }).message)
        : 'Erreur reseau'
  } finally {
    loading.value = false
  }
}

onMounted(fetchHealth)
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h2
      class="text-2xl font-bold text-red-900 dark:text-red-100 mb-2"
    >
      Sante du systeme
    </h2>
    <p class="text-sm text-red-700 dark:text-red-300 mb-6">
      Verification rapide du back-office et des services critiques.
    </p>

    <div
      v-if="loading"
      class="rounded-lg border border-red-200 dark:border-red-800 bg-white dark:bg-red-950/30 p-6 shadow-sm"
    >
      <div class="flex items-center gap-3">
        <span
          class="inline-block h-3 w-3 rounded-full bg-red-400 animate-pulse"
          aria-hidden="true"
        />
        <span class="text-sm text-red-700 dark:text-red-300">
          Verification en cours...
        </span>
      </div>
    </div>

    <div
      v-else-if="error"
      class="rounded-lg border border-red-300 dark:border-red-700 bg-red-100 dark:bg-red-900/40 p-6"
    >
      <h3 class="text-sm font-semibold text-red-900 dark:text-red-100 mb-2">
        Echec du health check
      </h3>
      <p class="text-sm text-red-800 dark:text-red-200">{{ error }}</p>
      <button
        type="button"
        class="mt-3 inline-flex items-center gap-1 rounded-md bg-red-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-800 dark:bg-red-800 dark:hover:bg-red-700"
        @click="fetchHealth"
      >
        Reessayer
      </button>
    </div>

    <div
      v-else-if="health"
      class="rounded-lg border border-red-200 dark:border-red-800 bg-white dark:bg-red-950/30 p-6 shadow-sm"
    >
      <div class="flex items-center gap-3 mb-4">
        <span
          class="inline-block h-3 w-3 rounded-full bg-emerald-500"
          aria-hidden="true"
        />
        <span
          class="text-sm font-semibold text-emerald-700 dark:text-emerald-300"
        >
          Service operationnel
        </span>
      </div>
      <dl class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
        <div>
          <dt class="text-xs uppercase tracking-wide text-red-600 dark:text-red-300">
            Statut
          </dt>
          <dd class="mt-1 font-medium text-red-900 dark:text-red-100">
            {{ health.status }}
          </dd>
        </div>
        <div>
          <dt class="text-xs uppercase tracking-wide text-red-600 dark:text-red-300">
            Role detecte
          </dt>
          <dd class="mt-1 font-medium text-red-900 dark:text-red-100">
            {{ health.role }}
          </dd>
        </div>
        <div>
          <dt class="text-xs uppercase tracking-wide text-red-600 dark:text-red-300">
            Service
          </dt>
          <dd class="mt-1 font-medium text-red-900 dark:text-red-100">
            {{ health.service }}
          </dd>
        </div>
      </dl>
    </div>
  </div>
</template>

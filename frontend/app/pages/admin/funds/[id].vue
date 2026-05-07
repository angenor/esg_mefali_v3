<script setup lang="ts">
// F09 — Détail fund avec bouton publish.
import { onMounted, ref } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'
import PublishButton from '~/components/admin/PublishButton.vue'
import { useAuth } from '~/composables/useAuth'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const route = useRoute()
const { apiFetch } = useAuth()

interface AdminFund {
  id: string
  name: string
  publication_status: 'draft' | 'published'
  status: string
  fund_type?: string | null
}

const fund = ref<AdminFund | null>(null)
const error = ref('')
const blockingMsg = ref('')

async function load() {
  try {
    fund.value = await apiFetch<AdminFund>(`/admin/funds/${route.params.id}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  }
}

function onPublished() {
  if (fund.value) fund.value.publication_status = 'published'
  blockingMsg.value = ''
}

function onGated(payload: { message: string; blocking_sources: string[] }) {
  blockingMsg.value = `${payload.message} (${payload.blocking_sources.length} bloquantes)`
}

onMounted(load)
</script>

<template>
  <div class="px-6 py-8 max-w-3xl mx-auto">
    <div v-if="error" class="text-red-600">{{ error }}</div>
    <div v-else-if="fund">
      <div class="mb-6 flex items-center justify-between">
        <h1 class="text-2xl font-bold">{{ fund.name }}</h1>
        <StatusBadge :variant="fund.publication_status" />
      </div>

      <div
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6 space-y-2 mb-6"
      >
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Type : {{ fund.fund_type ?? '—' }}
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Statut métier : {{ fund.status }}
        </p>
      </div>

      <PublishButton
        v-if="fund.publication_status === 'draft'"
        entity-type="fund"
        :entity-id="fund.id"
        @published="onPublished"
        @gated="onGated"
      />

      <p
        v-if="blockingMsg"
        class="mt-2 text-sm text-yellow-700 dark:text-yellow-300"
      >
        {{ blockingMsg }}
      </p>
    </div>
  </div>
</template>

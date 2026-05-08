<script setup lang="ts">
// F09 PRIO 3 — Détail intermédiaire admin avec publish.
import { onMounted, ref } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'
import PublishButton from '~/components/admin/PublishButton.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const route = useRoute()
const { getEntity } = useAdminCatalog<AdminIntermediary>('intermediary')

interface AdminIntermediary {
  id: string
  name: string
  publication_status: 'draft' | 'published'
  country?: string | null
  type?: string | null
}

const entity = ref<AdminIntermediary | null>(null)
const error = ref('')
const blockingMsg = ref('')

async function load() {
  try {
    entity.value = await getEntity(route.params.id as string)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Erreur'
  }
}

function onPublished() {
  if (entity.value) entity.value.publication_status = 'published'
  blockingMsg.value = ''
}

function onGated(payload: { message: string; blocking_sources: string[] }) {
  blockingMsg.value = `${payload.message} (${payload.blocking_sources.length} bloquantes)`
}

onMounted(load)
</script>

<template>
  <div class="px-6 py-8 max-w-3xl mx-auto">
    <div v-if="error" class="text-red-600 dark:text-red-400">{{ error }}</div>
    <div v-else-if="entity">
      <header class="mb-6 flex items-center justify-between">
        <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
          {{ entity.name }}
        </h1>
        <StatusBadge :variant="entity.publication_status" />
      </header>

      <div
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6 space-y-2 mb-6"
      >
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Type : {{ entity.type ?? '—' }}
        </p>
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Pays : {{ entity.country ?? '—' }}
        </p>
      </div>

      <PublishButton
        v-if="entity.publication_status === 'draft'"
        entity-type="intermediary"
        :entity-id="entity.id"
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

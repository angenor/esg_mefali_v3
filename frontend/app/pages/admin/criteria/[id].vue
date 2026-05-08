<script setup lang="ts">
// F09 PRIO 3 — Détail critère admin.
import { onMounted, ref } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'
import PublishButton from '~/components/admin/PublishButton.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const route = useRoute()
const router = useRouter()
const { getEntity, deleteEntity } = useAdminCatalog<AdminCriterion>('criterion')

interface AdminCriterion {
  id: string
  code: string
  label: string
  expression: Record<string, unknown>
  source_id: string
  publication_status: 'draft' | 'published'
}

const entity = ref<AdminCriterion | null>(null)
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
}

function onGated(payload: { message: string; blocking_sources: string[] }) {
  blockingMsg.value = `${payload.message} (${payload.blocking_sources.length} bloquantes)`
}

async function onDelete() {
  if (!entity.value) return
  if (!confirm('Supprimer ce critère ?')) return
  await deleteEntity(entity.value.id)
  router.push('/admin/criteria')
}

onMounted(load)
</script>

<template>
  <div class="px-6 py-8 max-w-3xl mx-auto">
    <div v-if="error" class="text-red-600 dark:text-red-400">{{ error }}</div>
    <div v-else-if="entity">
      <header class="mb-6 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
            {{ entity.label }}
          </h1>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            <code>{{ entity.code }}</code>
          </p>
        </div>
        <StatusBadge :variant="entity.publication_status" />
      </header>

      <div
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6 mb-6"
      >
        <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">
          Expression logique
        </p>
        <pre
          class="overflow-x-auto rounded-lg bg-gray-50 dark:bg-gray-800 p-3 text-xs text-surface-text dark:text-surface-dark-text"
        >{{ JSON.stringify(entity.expression, null, 2) }}</pre>
      </div>

      <div class="flex items-center gap-3">
        <PublishButton
          v-if="entity.publication_status === 'draft'"
          entity-type="criterion"
          :entity-id="entity.id"
          @published="onPublished"
          @gated="onGated"
        />
        <button
          v-if="entity.publication_status === 'draft'"
          type="button"
          class="rounded-lg border border-rose-300 dark:border-rose-700 text-rose-700 dark:text-rose-300 px-4 py-2 text-sm hover:bg-rose-50 dark:hover:bg-rose-950/40"
          @click="onDelete"
        >
          Supprimer
        </button>
      </div>

      <p
        v-if="blockingMsg"
        class="mt-2 text-sm text-yellow-700 dark:text-yellow-300"
      >
        {{ blockingMsg }}
      </p>
    </div>
  </div>
</template>

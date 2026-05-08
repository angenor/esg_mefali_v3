<script setup lang="ts">
// F09 PRIO 3 — Détail indicateur admin.
import { onMounted, ref } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'
import PublishButton from '~/components/admin/PublishButton.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({
  middleware: 'admin',
  layout: 'admin',
})

const route = useRoute()
const router = useRouter()
const { getEntity, deleteEntity } = useAdminCatalog<AdminIndicator>('indicator')

interface AdminIndicator {
  id: string
  code: string
  pillar: string
  label: string
  description: string
  question: string
  source_id: string
  publication_status: 'draft' | 'published'
  version?: string | null
}

const entity = ref<AdminIndicator | null>(null)
const error = ref('')
const blockingMsg = ref('')
const showDelete = ref(false)
const deleting = ref(false)

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

async function onDelete() {
  if (!entity.value) return
  deleting.value = true
  try {
    await deleteEntity(entity.value.id)
    router.push('/admin/indicators')
  } finally {
    deleting.value = false
  }
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
            <code>{{ entity.code }}</code> · {{ entity.pillar }}
          </p>
        </div>
        <StatusBadge :variant="entity.publication_status" />
      </header>

      <div
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6 space-y-3 mb-6"
      >
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Description
          </p>
          <p class="mt-1 text-sm text-surface-text dark:text-surface-dark-text">
            {{ entity.description }}
          </p>
        </div>
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Question PME
          </p>
          <p class="mt-1 text-sm text-surface-text dark:text-surface-dark-text">
            {{ entity.question }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <PublishButton
          v-if="entity.publication_status === 'draft'"
          entity-type="indicator"
          :entity-id="entity.id"
          @published="onPublished"
          @gated="onGated"
        />
        <button
          v-if="entity.publication_status === 'draft'"
          type="button"
          class="rounded-lg border border-rose-300 dark:border-rose-700 text-rose-700 dark:text-rose-300 px-4 py-2 text-sm hover:bg-rose-50 dark:hover:bg-rose-950/40"
          @click="showDelete = true"
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

      <Teleport to="body">
        <div
          v-if="showDelete"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          @click.self="showDelete = false"
        >
          <div
            class="w-full max-w-md rounded-2xl bg-white dark:bg-dark-card p-6 shadow-2xl"
          >
            <h2 class="text-lg font-bold text-surface-text dark:text-surface-dark-text">
              Supprimer cet indicateur ?
            </h2>
            <div class="mt-6 flex justify-end gap-2">
              <button
                type="button"
                class="rounded-lg border border-gray-300 dark:border-dark-border px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-dark-hover"
                @click="showDelete = false"
              >
                Annuler
              </button>
              <button
                type="button"
                :disabled="deleting"
                class="rounded-lg bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 text-sm font-medium disabled:opacity-50"
                @click="onDelete"
              >
                {{ deleting ? 'Suppression…' : 'Confirmer' }}
              </button>
            </div>
          </div>
        </div>
      </Teleport>
    </div>
  </div>
</template>

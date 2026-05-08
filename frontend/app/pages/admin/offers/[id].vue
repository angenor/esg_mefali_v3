<script setup lang="ts">
// F09 PRIO 3 — Détail offre admin.
import { onMounted, ref } from 'vue'
import StatusBadge from '~/components/admin/badges/StatusBadge.vue'
import PublishButton from '~/components/admin/PublishButton.vue'
import { useAdminCatalog } from '~/composables/useAdminCatalog'

definePageMeta({ middleware: 'admin', layout: 'admin' })

const route = useRoute()
const router = useRouter()
const { getEntity, deleteEntity } = useAdminCatalog<AdminOffer>('offer')

interface AdminOffer {
  id: string
  fund_id: string
  intermediary_id: string
  publication_status: 'draft' | 'published'
  effective_criteria?: Record<string, unknown>
  created_at?: string
}

const entity = ref<AdminOffer | null>(null)
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
  if (!confirm('Supprimer cette offre ?')) return
  await deleteEntity(entity.value.id)
  router.push('/admin/offers')
}

onMounted(load)
</script>

<template>
  <div class="px-6 py-8 max-w-3xl mx-auto">
    <div v-if="error" class="text-red-600 dark:text-red-400">{{ error }}</div>
    <div v-else-if="entity">
      <header class="mb-6 flex items-center justify-between">
        <h1 class="text-2xl font-bold text-surface-text dark:text-surface-dark-text">
          Offre
        </h1>
        <StatusBadge :variant="entity.publication_status" />
      </header>

      <div
        class="bg-white dark:bg-dark-card rounded-xl border border-gray-200 dark:border-dark-border p-6 space-y-3 mb-6"
      >
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Fonds
          </p>
          <NuxtLink
            :to="`/admin/funds/${entity.fund_id}`"
            class="mt-1 inline-block text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            {{ entity.fund_id }}
          </NuxtLink>
        </div>
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Intermédiaire
          </p>
          <NuxtLink
            :to="`/admin/intermediaries/${entity.intermediary_id}`"
            class="mt-1 inline-block text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            {{ entity.intermediary_id }}
          </NuxtLink>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <PublishButton
          v-if="entity.publication_status === 'draft'"
          entity-type="offer"
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

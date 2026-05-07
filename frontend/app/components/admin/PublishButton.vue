<script setup lang="ts">
// F09 — Bouton "Publier" générique pour les pages admin catalogue.
//
// Tente la publication via le composable useAdminPublication. En cas
// d'erreur 400 publish_gating, affiche un message listant les sources
// bloquantes (toast à brancher selon le système de notifications).
import { ref } from 'vue'
import {
  useAdminPublication,
  type AdminEntityType,
} from '~/composables/useAdminPublication'

interface Props {
  entityType: AdminEntityType
  entityId: string
  disabled?: boolean
  disabledReason?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'published', payload: { publication_status: string }): void
  (
    e: 'gated',
    payload: { message: string; blocking_sources: string[] },
  ): void
  (e: 'error', payload: Error): void
}>()

const { publishEntity } = useAdminPublication()

const loading = ref(false)
const localError = ref('')

async function onClick() {
  if (props.disabled) return
  loading.value = true
  localError.value = ''
  try {
    const response = await publishEntity(props.entityType, props.entityId)
    emit('published', { publication_status: response.publication_status })
  } catch (e: unknown) {
    const data = (e as { data?: { detail?: unknown } }).data
    if (
      data?.detail &&
      typeof data.detail === 'object' &&
      (data.detail as { error?: string }).error === 'publish_gating'
    ) {
      const detail = data.detail as {
        message: string
        blocking_sources: string[]
      }
      localError.value = detail.message
      emit('gated', {
        message: detail.message,
        blocking_sources: detail.blocking_sources,
      })
    } else {
      localError.value = e instanceof Error ? e.message : 'Erreur'
      emit('error', e instanceof Error ? e : new Error(String(e)))
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="inline-flex flex-col items-start">
    <button
      type="button"
      :disabled="disabled || loading"
      :title="disabled ? disabledReason : ''"
      class="inline-flex items-center gap-2 rounded-lg bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-600 text-white font-medium px-4 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
      @click="onClick"
    >
      <span aria-hidden="true">{{ loading ? '⏳' : '✅' }}</span>
      <span>{{ loading ? 'Publication…' : 'Publier' }}</span>
    </button>
    <p
      v-if="localError"
      class="mt-2 text-xs text-red-600 dark:text-red-400"
      role="alert"
    >
      {{ localError }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useSources } from '~/composables/useSources'
import type { Source } from '~/types/source'
import SourceBadge from './SourceBadge.vue'

interface Props {
  sourceId: string | null
  visible: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
}>()

const { fetchSource, store } = useSources()
const source = ref<Source | null>(null)
const loading = ref(false)
const error = ref('')

watch(
  () => props.sourceId,
  async (id) => {
    if (id && props.visible) {
      await load(id)
    }
  },
  { immediate: true },
)

watch(
  () => props.visible,
  async (open) => {
    if (open && props.sourceId) {
      await load(props.sourceId)
    } else if (!open) {
      source.value = null
      error.value = ''
    }
  },
)

async function load(id: string) {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchSource(id)
    source.value = data
    if (!data) error.value = store.error || 'Source introuvable'
  } finally {
    loading.value = false
  }
}

function handleBackdropClick(event: MouseEvent) {
  if (event.target === event.currentTarget) {
    emit('close')
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.visible) {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

const formattedDate = computed(() => {
  if (!source.value?.date_publi) return ''
  try {
    return new Date(source.value.date_publi).toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return source.value.date_publi
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-modal-title"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
        @click="handleBackdropClick"
      >
        <div
          class="relative w-full max-w-2xl max-h-[90vh] bg-white dark:bg-dark-card rounded-2xl shadow-2xl overflow-auto p-6"
        >
          <button
            class="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-full text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-hover transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Fermer"
            @click="emit('close')"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="w-5 h-5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fill-rule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clip-rule="evenodd"
              />
            </svg>
          </button>

          <div v-if="loading" class="text-center text-gray-500 py-8">
            Chargement de la source...
          </div>

          <div v-else-if="error" class="text-center text-red-600 dark:text-red-400 py-8">
            {{ error }}
          </div>

          <div v-else-if="source" class="space-y-4">
            <div class="flex items-start justify-between gap-3">
              <h2
                id="source-modal-title"
                class="text-xl font-semibold text-surface-text dark:text-surface-dark-text pr-8"
              >
                {{ source.title }}
              </h2>
              <SourceBadge :status="source.verification_status" :reason="source.outdated_reason" />
            </div>

            <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <div>
                <dt class="text-gray-500 dark:text-gray-400 font-medium">Editeur</dt>
                <dd class="text-surface-text dark:text-surface-dark-text">
                  {{ source.publisher }}
                </dd>
              </div>
              <div>
                <dt class="text-gray-500 dark:text-gray-400 font-medium">Version</dt>
                <dd class="text-surface-text dark:text-surface-dark-text">
                  {{ source.version }}
                </dd>
              </div>
              <div>
                <dt class="text-gray-500 dark:text-gray-400 font-medium">Date de publication</dt>
                <dd class="text-surface-text dark:text-surface-dark-text">
                  {{ formattedDate }}
                </dd>
              </div>
              <div v-if="source.page">
                <dt class="text-gray-500 dark:text-gray-400 font-medium">Page</dt>
                <dd class="text-surface-text dark:text-surface-dark-text">
                  {{ source.page }}
                </dd>
              </div>
              <div v-if="source.section" class="sm:col-span-2">
                <dt class="text-gray-500 dark:text-gray-400 font-medium">Section</dt>
                <dd class="text-surface-text dark:text-surface-dark-text">
                  {{ source.section }}
                </dd>
              </div>
            </dl>

            <div class="pt-2">
              <a
                :href="source.url"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-dark-card"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="w-4 h-4"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                  <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                </svg>
                Ouvrir le document officiel
              </a>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

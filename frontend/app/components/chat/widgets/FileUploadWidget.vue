<script setup lang="ts">
/**
 * F10 — FileUploadWidget : drag-and-drop avec validation client + progress bar.
 *
 * Le serveur fait la validation MIME signature via python-magic (FR-025, SC-012).
 *
 * Réf : FR-018, FR-025, US8.
 */
import { computed, ref } from 'vue'
import type {
  FileUploadPayload,
  FileUploadResponse,
  InteractiveQuestion,
  UploadedDocument,
} from '~/types/interactive-question'
import { useAuthStore } from '~/stores/auth'

interface Props {
  question: InteractiveQuestion
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  (e: 'submit', payload: FileUploadResponse, displayText: string): void
  (e: 'abandon-and-send', content: string): void
}>()

const inputLocked = computed(() => props.loading || props.disabled)

const payload = computed<FileUploadPayload>(() => {
  const p = props.question.payload as FileUploadPayload | undefined
  return p ?? {
    question_type: 'file_upload',
    accept: ['.pdf'],
    max_size_mb: 10,
    multi: false,
  }
})

const dragActive = ref(false)
const errorMsg = ref('')
const progress = ref(0)
const isUploading = ref(false)
const uploaded = ref<UploadedDocument[]>([])

const acceptAttr = computed(() => payload.value.accept.join(','))
const maxBytes = computed(() => payload.value.max_size_mb * 1024 * 1024)

function _validateFile(file: File): string | null {
  // Extension whitelist
  const idx = file.name.lastIndexOf('.')
  const ext = idx >= 0 ? file.name.slice(idx).toLowerCase() : ''
  if (!payload.value.accept.includes(ext)) {
    return `Type non accepté. Extensions autorisées : ${payload.value.accept.join(', ')}`
  }
  if (file.size > maxBytes.value) {
    return `Fichier trop volumineux (max ${payload.value.max_size_mb} Mo)`
  }
  return null
}

async function _uploadFile(file: File): Promise<UploadedDocument | null> {
  errorMsg.value = ''
  const err = _validateFile(file)
  if (err) {
    errorMsg.value = err
    return null
  }

  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const apiBase = config.public.apiBase

  const formData = new FormData()
  formData.append('files', file)

  isUploading.value = true
  progress.value = 50 // approximation puisque fetch ne donne pas de progress natif simple
  try {
    const headers: Record<string, string> = {}
    if (authStore.accessToken) {
      headers.Authorization = `Bearer ${authStore.accessToken}`
    }
    const resp = await fetch(`${apiBase}/documents/upload`, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (resp.status === 415) {
      errorMsg.value = 'Type de fichier incohérent (signature MIME). Réessayez avec un autre fichier.'
      return null
    }
    if (!resp.ok) {
      errorMsg.value = `Erreur d'upload (${resp.status})`
      return null
    }
    const data = await resp.json()
    progress.value = 100
    const doc = data.documents?.[0]
    if (!doc) {
      errorMsg.value = 'Réponse serveur invalide'
      return null
    }
    return {
      document_id: doc.id,
      filename: doc.original_filename ?? file.name,
      size: doc.file_size ?? file.size,
      mime_type: doc.mime_type ?? file.type,
    }
  } catch {
    errorMsg.value = 'Erreur réseau lors de l\'upload'
    return null
  } finally {
    isUploading.value = false
  }
}

async function handleFiles(files: FileList | File[]) {
  if (inputLocked.value) return
  const arr = Array.from(files)
  for (const f of arr) {
    const result = await _uploadFile(f)
    if (result) {
      uploaded.value = [...uploaded.value, result]
      if (!payload.value.multi) break // mono → stop après le premier
    }
  }
  if (uploaded.value.length > 0) {
    _doSubmit()
  }
}

function onFileInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files) handleFiles(target.files)
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragActive.value = false
  if (e.dataTransfer?.files) handleFiles(e.dataTransfer.files)
}

function _doSubmit() {
  if (uploaded.value.length === 0) return
  const docs = uploaded.value
  let display: string
  if (docs.length === 1) {
    display = `✓ ${docs[0]!.filename} (uploaded)`
  } else {
    display = `✓ ${docs.map(d => d.filename).join(', ')} (${docs.length} fichiers uploaded)`
  }
  emit(
    'submit',
    { question_type: 'file_upload', documents: docs },
    display,
  )
}
</script>

<template>
  <div class="space-y-3">
    <div
      :class="[
        'rounded-2xl border-2 border-dashed p-6 text-center transition-all',
        dragActive
          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30'
          : 'border-gray-300 dark:border-dark-border bg-white dark:bg-dark-card',
        inputLocked && 'opacity-50',
      ]"
      role="region"
      :aria-busy="isUploading"
      @dragover.prevent="dragActive = true"
      @dragleave.prevent="dragActive = false"
      @drop="onDrop"
    >
      <p class="text-sm font-medium text-surface-text dark:text-surface-dark-text mb-2">
        Déposez votre fichier ici, ou
      </p>
      <label class="inline-block">
        <input
          type="file"
          :accept="acceptAttr"
          :multiple="payload.multi"
          :disabled="inputLocked"
          :data-testid="`file-input-${question.id}`"
          class="sr-only"
          @change="onFileInput"
        />
        <span class="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-semibold cursor-pointer hover:shadow-lg transition-all">
          Parcourir
        </span>
      </label>
      <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
        {{ payload.accept.join(', ') }} (max {{ payload.max_size_mb }} Mo)
      </p>
    </div>

    <!-- Progress bar -->
    <div
      v-if="isUploading"
      class="h-2 rounded-full bg-gray-200 dark:bg-dark-border overflow-hidden"
    >
      <div
        class="h-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all"
        :style="{ width: `${progress}%` }"
      ></div>
    </div>

    <!-- Documents uploadés -->
    <ul
      v-if="uploaded.length"
      class="space-y-1 text-sm"
    >
      <li
        v-for="doc in uploaded"
        :key="doc.document_id"
        class="flex items-center gap-2 text-indigo-700 dark:text-indigo-300"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <span>{{ doc.filename }}</span>
      </li>
    </ul>

    <!-- Erreur -->
    <p
      v-if="errorMsg"
      role="alert"
      class="text-xs text-red-600 dark:text-red-400 font-medium"
    >
      {{ errorMsg }}
    </p>

    <div class="flex items-center justify-end pt-1">
      <button
        type="button"
        :disabled="inputLocked"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium"
        @click="emit('abandon-and-send', '')"
      >
        Répondre autrement
      </button>
    </div>
  </div>
</template>

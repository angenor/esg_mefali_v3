<script setup lang="ts">
/**
 * 049 — Ligne d'item de checklist documentaire.
 *
 * Encapsule le cycle de vie d'un item (US1→US4) : téléverser un fichier
 * (réutilise ``DocumentUpload``), rattacher un document existant (``DocumentPicker``),
 * prévisualiser (``DocumentPreview``), remplacer ou détacher. Orchestre
 * ``useDocuments.uploadDocuments`` puis ``useApplications.attachDocument`` /
 * ``detachDocument`` et émet ``changed`` après chaque mutation réussie.
 */
import { computed, ref } from 'vue'
import DocumentUpload from '~/components/documents/DocumentUpload.vue'
import DocumentPicker from '~/components/documents/DocumentPicker.vue'
import DocumentPreview from '~/components/documents/DocumentPreview.vue'
import FullscreenModal from '~/components/ui/FullscreenModal.vue'
import { useApplications } from '~/composables/useApplications'
import { useDocuments } from '~/composables/useDocuments'
import type { ChecklistItem } from '~/stores/applications'

const props = defineProps<{ applicationId: string; item: ChecklistItem }>()
const emit = defineEmits<{ changed: [] }>()

const { attachDocument, detachDocument } = useApplications()
const { uploadDocuments } = useDocuments()

const busy = ref(false)
const errorMessage = ref('')
const showUpload = ref(false)
const replaceMode = ref(false)
const pickerVisible = ref(false)
const previewVisible = ref(false)

const isProvided = computed(() => props.item.status === 'provided')

function resetControls() {
  showUpload.value = false
  replaceMode.value = false
  pickerVisible.value = false
  errorMessage.value = ''
}

async function onUpload(files: File[]) {
  errorMessage.value = ''
  busy.value = true
  try {
    const documents = await uploadDocuments(files)
    if (!documents.length) {
      errorMessage.value = "Le téléversement a échoué. Vérifiez le fichier et réessayez."
      return
    }
    await doAttach(documents[0]!.id)
  } finally {
    busy.value = false
  }
}

async function onPickerSelect(documentId: string) {
  await doAttach(documentId)
}

async function doAttach(documentId: string) {
  const ok = await attachDocument(props.applicationId, props.item.key, documentId)
  if (ok) {
    resetControls()
    emit('changed')
  } else {
    errorMessage.value = "Le rattachement du document a échoué."
  }
}

async function onDetach() {
  errorMessage.value = ''
  busy.value = true
  try {
    const ok = await detachDocument(props.applicationId, props.item.key)
    if (ok) {
      resetControls()
      emit('changed')
    } else {
      errorMessage.value = "Le détachement a échoué."
    }
  } finally {
    busy.value = false
  }
}

function openPreview() {
  if (props.item.document) previewVisible.value = true
}
</script>

<template>
  <div class="py-3 border-b border-gray-100 dark:border-gray-800 last:border-0">
    <div class="flex items-center justify-between gap-3">
      <!-- Statut + libellé + nom de fichier -->
      <div class="flex items-center gap-3 min-w-0">
        <div
          :class="[
            'w-5 h-5 shrink-0 rounded-full flex items-center justify-center',
            isProvided
              ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-400'
              : 'bg-gray-100 text-gray-400 dark:bg-gray-700 dark:text-gray-500',
          ]"
        >
          <svg v-if="isProvided" class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
          <div v-else class="w-2 h-2 rounded-full bg-current" />
        </div>
        <div class="min-w-0">
          <span class="text-sm text-surface-text dark:text-surface-dark-text">{{ item.name }}</span>
          <p
            v-if="isProvided && item.document"
            class="text-xs text-gray-500 dark:text-gray-400 truncate"
            :title="item.document.original_filename"
          >
            {{ item.document.original_filename }}
          </p>
        </div>
      </div>

      <!-- Badge + actions -->
      <div class="flex items-center gap-2 shrink-0">
        <span
          :class="[
            'text-xs font-medium px-2 py-0.5 rounded-full',
            isProvided
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300'
              : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
          ]"
        >
          {{ isProvided ? 'Fourni' : 'Manquant' }}
        </span>

        <!-- Actions item manquant -->
        <template v-if="!isProvided">
          <button
            type="button"
            class="px-2.5 py-1 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
            :disabled="busy"
            @click="showUpload = !showUpload"
          >
            Téléverser
          </button>
          <button
            type="button"
            class="px-2.5 py-1 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
            :disabled="busy"
            @click="pickerVisible = true"
          >
            Choisir un existant
          </button>
        </template>

        <!-- Actions item fourni -->
        <template v-else>
          <button
            type="button"
            class="px-2.5 py-1 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            @click="openPreview"
          >
            Aperçu
          </button>
          <button
            type="button"
            class="px-2.5 py-1 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
            :disabled="busy"
            @click="replaceMode = !replaceMode"
          >
            Remplacer
          </button>
          <button
            type="button"
            class="px-2.5 py-1 text-xs bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/60 transition-colors disabled:opacity-50"
            :disabled="busy"
            @click="onDetach"
          >
            Détacher
          </button>
        </template>
      </div>
    </div>

    <!-- Contrôles de remplacement (item fourni) -->
    <div v-if="isProvided && replaceMode" class="flex items-center gap-2 mt-3">
      <button
        type="button"
        class="px-2.5 py-1 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
        :disabled="busy"
        @click="showUpload = !showUpload"
      >
        Téléverser un nouveau
      </button>
      <button
        type="button"
        class="px-2.5 py-1 text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
        :disabled="busy"
        @click="pickerVisible = true"
      >
        Choisir un existant
      </button>
    </div>

    <!-- Zone de téléversement (réutilise DocumentUpload + ses validations) -->
    <div v-if="showUpload" class="mt-3">
      <DocumentUpload :is-uploading="busy" @upload="onUpload" />
    </div>

    <!-- Message d'erreur -->
    <p v-if="errorMessage" class="mt-2 text-xs text-red-600 dark:text-red-400">
      {{ errorMessage }}
    </p>

    <!-- Sélecteur de document existant -->
    <DocumentPicker
      :visible="pickerVisible"
      @select="onPickerSelect"
      @close="pickerVisible = false"
    />

    <!-- Aperçu du document rattaché (DocumentPreview fournit sa propre croix) -->
    <FullscreenModal :visible="previewVisible" :show-close="false" @close="previewVisible = false">
      <DocumentPreview
        v-if="previewVisible && item.document"
        :document-id="item.document.id"
        :mime-type="item.document.mime_type"
        :filename="item.document.original_filename"
        @close="previewVisible = false"
      />
    </FullscreenModal>
  </div>
</template>

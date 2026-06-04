<script setup lang="ts">
import type { Document, DocumentType, DocumentStatus } from '~/types/documents'

const props = defineProps<{
  documents: Document[]
  isLoading?: boolean
  // 049 — masque l'action destructrice (corbeille + confirmation) lorsque la
  // liste sert de sélecteur (DocumentPicker), où seul @select a du sens.
  selectableOnly?: boolean
}>()

const emit = defineEmits<{
  select: [document: Document]
  delete: [id: string]
}>()

const filterType = ref<DocumentType | ''>('')
const filterStatus = ref<DocumentStatus | ''>('')

const typeLabels: Record<string, string> = {
  statuts_juridiques: 'Statuts juridiques',
  rapport_activite: 'Rapport d\'activite',
  facture: 'Facture',
  contrat: 'Contrat',
  politique_interne: 'Politique interne',
  bilan_financier: 'Bilan financier',
  autre: 'Autre',
}

const statusLabels: Record<DocumentStatus, string> = {
  uploaded: 'Uploade',
  processing: 'En cours',
  analyzed: 'Analyse',
  error: 'Erreur',
}

const statusColors: Record<DocumentStatus, string> = {
  uploaded: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  processing: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  analyzed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
}

const filteredDocuments = computed(() => {
  return props.documents.filter(doc => {
    if (filterType.value && doc.document_type !== filterType.value) return false
    if (filterStatus.value && doc.status !== filterStatus.value) return false
    return true
  })
})

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function getFileIcon(mimeType: string): string {
  if (mimeType === 'application/pdf') return 'pdf'
  if (mimeType.startsWith('image/')) return 'image'
  if (mimeType.includes('wordprocessing')) return 'word'
  if (mimeType.includes('spreadsheet')) return 'excel'
  return 'file'
}

const deleteConfirmId = ref<string | null>(null)

function confirmDelete(id: string) {
  deleteConfirmId.value = id
}

function executeDelete(id: string) {
  emit('delete', id)
  deleteConfirmId.value = null
}
</script>

<template>
  <div>
    <!-- Filtres -->
    <div class="flex gap-3 mb-4">
      <select
        v-model="filterType"
        class="text-sm border border-gray-300 dark:border-dark-border rounded-lg px-3 py-1.5 bg-white dark:bg-dark-input dark:text-surface-dark-text"
      >
        <option value="">Tous les types</option>
        <option v-for="(label, key) in typeLabels" :key="key" :value="key">
          {{ label }}
        </option>
      </select>

      <select
        v-model="filterStatus"
        class="text-sm border border-gray-300 dark:border-dark-border rounded-lg px-3 py-1.5 bg-white dark:bg-dark-input dark:text-surface-dark-text"
      >
        <option value="">Tous les statuts</option>
        <option v-for="(label, key) in statusLabels" :key="key" :value="key">
          {{ label }}
        </option>
      </select>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-8">
      <div class="w-8 h-8 border-3 border-brand-green border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Liste vide -->
    <div v-else-if="filteredDocuments.length === 0" class="text-center py-8 text-gray-500 dark:text-gray-400">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <p class="text-sm">Aucun document</p>
    </div>

    <!-- Liste -->
    <div v-else class="space-y-2">
      <div
        v-for="doc in filteredDocuments"
        :key="doc.id"
        class="flex items-center gap-3 p-3 rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-card hover:border-brand-green transition-colors cursor-pointer group"
        @click="emit('select', doc)"
      >
        <!-- Icone type fichier -->
        <div class="shrink-0 w-10 h-10 rounded-lg bg-gray-100 dark:bg-dark-hover flex items-center justify-center">
          <svg v-if="getFileIcon(doc.mime_type) === 'pdf'" xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-red-500" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" />
          </svg>
          <svg v-else-if="getFileIcon(doc.mime_type) === 'image'" xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-blue-500" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clip-rule="evenodd" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-gray-500" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" />
          </svg>
        </div>

        <!-- Infos -->
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-surface-text dark:text-surface-dark-text truncate">
            {{ doc.original_filename }}
          </p>
          <p class="text-xs text-gray-500 dark:text-gray-400">
            {{ formatFileSize(doc.file_size) }} — {{ formatDate(doc.created_at) }}
            <span v-if="doc.document_type" class="ml-1">— {{ typeLabels[doc.document_type] || doc.document_type }}</span>
          </p>
        </div>

        <!-- Badge statut -->
        <span
          class="shrink-0 text-xs font-medium px-2 py-0.5 rounded-full"
          :class="statusColors[doc.status]"
        >
          {{ statusLabels[doc.status] }}
        </span>

        <!-- Bouton supprimer (masqué en mode sélecteur) -->
        <button
          v-if="!selectableOnly"
          class="shrink-0 p-1.5 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
          @click.stop="confirmDelete(doc.id)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Confirmation suppression -->
    <Teleport to="body">
      <div
        v-if="deleteConfirmId"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        @click.self="deleteConfirmId = null"
      >
        <div class="bg-white dark:bg-dark-card rounded-xl p-6 max-w-sm mx-4 shadow-xl">
          <p class="text-sm text-surface-text dark:text-surface-dark-text mb-4">
            Supprimer ce document ? Cette action est irreversible.
          </p>
          <div class="flex gap-3 justify-end">
            <button
              class="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-hover rounded-lg"
              @click="deleteConfirmId = null"
            >
              Annuler
            </button>
            <button
              class="px-3 py-1.5 text-sm text-white bg-red-500 hover:bg-red-600 rounded-lg"
              @click="executeDelete(deleteConfirmId!)"
            >
              Supprimer
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

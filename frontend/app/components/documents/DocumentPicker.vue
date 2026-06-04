<script setup lang="ts">
/**
 * 049 (US2) — Sélecteur de document existant.
 *
 * Réutilise ``FullscreenModal`` + ``DocumentList`` + ``useDocuments``. Liste
 * TOUS les documents du compte (aucun filtrage par origine — FR-002a) et émet
 * l'``id`` du document choisi. État vide : message + invite au téléversement.
 */
import { computed, watch } from 'vue'
import FullscreenModal from '~/components/ui/FullscreenModal.vue'
import DocumentList from '~/components/documents/DocumentList.vue'
import { useDocuments } from '~/composables/useDocuments'
import type { Document } from '~/types/documents'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ select: [documentId: string]; close: [] }>()

const { store, fetchDocuments } = useDocuments()
const documents = computed<Document[]>(() => store.documents)

// Charger (ou rafraîchir) la liste à chaque ouverture. ``limit`` haut pour que
// TOUS les documents du compte soient sélectionnables (FR-002a/FR-003) : sans
// pagination dans le sélecteur, la limite par défaut (20) masquerait les
// documents au-delà de la 1re page.
watch(
  () => props.visible,
  (visible) => {
    if (visible) fetchDocuments({ limit: 200 })
  },
  { immediate: true },
)

function onSelect(document: Document) {
  emit('select', document.id)
  emit('close')
}
</script>

<template>
  <FullscreenModal :visible="visible" @close="emit('close')">
    <h3 class="text-lg font-semibold text-surface-text dark:text-surface-dark-text mb-4">
      Choisir un document existant
    </h3>

    <DocumentList
      v-if="documents.length > 0"
      :documents="documents"
      :is-loading="store.isLoading"
      selectable-only
      @select="onSelect"
    />

    <div
      v-else
      role="status"
      class="text-center py-10 text-gray-500 dark:text-gray-400"
    >
      <p class="mb-2">Aucun document disponible pour le moment.</p>
      <p class="text-sm">
        Téléversez un fichier depuis l'item de checklist pour commencer.
      </p>
    </div>
  </FullscreenModal>
</template>

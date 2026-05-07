<script setup lang="ts">
// F03 — Conteneur timeline verticale d'événements d'audit.
import type { AuditEvent } from '~/types/audit'
import AuditLogEntry from './AuditLogEntry.vue'

interface Props {
  events: AuditEvent[]
  loading?: boolean
}

defineProps<Props>()
</script>

<template>
  <div>
    <div
      v-if="loading"
      class="flex items-center justify-center py-12 text-sm text-gray-500 dark:text-gray-400"
    >
      Chargement...
    </div>

    <ol v-else-if="events.length > 0" role="list" class="flex flex-col gap-3">
      <AuditLogEntry v-for="event in events" :key="event.id" :event="event" />
    </ol>

    <div
      v-else
      class="rounded-lg border border-dashed border-gray-200 bg-white p-12 text-center dark:border-dark-border dark:bg-dark-card"
    >
      <p class="text-sm text-gray-500 dark:text-gray-400">
        Aucun événement d'audit pour les filtres sélectionnés.
      </p>
    </div>
  </div>
</template>

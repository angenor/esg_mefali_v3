<script setup lang="ts">
import type { Message } from '~/types'
import type { ProfileUpdateEvent } from '~/types/company'
import type {
  InteractiveQuestion,
  InteractiveQuestionAnswer,
} from '~/types/interactive-question'
import type { VisualizationBlock } from '~/composables/useChat'
import { useCompanyStore } from '~/stores/company'
import InteractiveQuestionHost from './InteractiveQuestionHost.vue'

const props = defineProps<{
  message: Message
  isStreaming?: boolean
  documentProgress?: {
    documentId: string
    filename: string
    status: 'uploaded' | 'extracting' | 'analyzing' | 'done' | 'error'
  } | null
  interactiveQuestion?: InteractiveQuestion | null
  // F11 — blocs de visualisation typés associés à ce message.
  visualizationBlocks?: VisualizationBlock[]
}>()

const emit = defineEmits<{
  (e: 'interactive-answer', payload: { questionId: string; answer: InteractiveQuestionAnswer }): void
  (e: 'interactive-abandoned', questionId: string): void
  (e: 'navigate', url: string): void
  (e: 'open-source', sourceId: string): void
}>()

function onNavigate(url: string) {
  emit('navigate', url)
}

function onOpenSource(sid: string) {
  emit('open-source', sid)
}

function onAnswer(payload: InteractiveQuestionAnswer) {
  if (props.interactiveQuestion) {
    emit('interactive-answer', { questionId: props.interactiveQuestion.id, answer: payload })
  }
}

function onAbandoned() {
  if (props.interactiveQuestion) {
    emit('interactive-abandoned', props.interactiveQuestion.id)
  }
}

const companyStore = useCompanyStore()
const isUser = computed(() => props.message.role === 'user')
const copied = ref(false)

// Notifications de profil associées à ce message
const profileUpdates = computed<ProfileUpdateEvent[]>(() => {
  if (isUser.value || props.isStreaming) return []
  return companyStore.recentUpdates
})

const docStatusLabels: Record<string, string> = {
  uploaded: 'Document recu',
  extracting: 'Extraction du texte...',
  analyzing: 'Analyse IA en cours...',
  done: 'Analyse terminee',
  error: 'Erreur d\'analyse',
}

const docStatusIcon = computed(() => {
  const status = props.documentProgress?.status
  if (!status) return ''
  if (status === 'done') return 'check'
  if (status === 'error') return 'error'
  return 'loading'
})

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // Fallback silencieux
  }
}
</script>

<template>
  <div>
    <div
      class="flex gap-3 px-4 py-3"
      :class="isUser ? 'justify-end' : 'justify-start'"
    >
      <!-- Avatar assistant -->
      <div
        v-if="!isUser"
        class="shrink-0 w-8 h-8 rounded-full bg-brand-green flex items-center justify-center text-white text-sm font-bold mt-1"
      >
        IA
      </div>

      <!-- Bulle de message -->
      <div
        class="rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
        :class="[
          isUser
            ? 'bg-brand-green text-white rounded-br-md max-w-[75%] whitespace-pre-wrap'
            : 'bg-gray-100 dark:bg-dark-hover text-surface-text dark:text-surface-dark-text rounded-bl-md max-w-[85%]',
        ]"
      >
        <!-- Messages utilisateur : texte brut -->
        <template v-if="isUser">
          {{ message.content }}
        </template>

        <!-- Messages assistant : rendu enrichi -->
        <template v-else>
          <!-- Indicateur de progression document -->
          <div
            v-if="documentProgress && isStreaming"
            class="flex items-center gap-2 mb-2 text-xs"
          >
            <!-- Spinner -->
            <div
              v-if="docStatusIcon === 'loading'"
              class="w-3.5 h-3.5 border-2 border-brand-green border-t-transparent rounded-full animate-spin shrink-0"
            />
            <!-- Check -->
            <svg
              v-else-if="docStatusIcon === 'check'"
              xmlns="http://www.w3.org/2000/svg"
              class="w-3.5 h-3.5 text-brand-green shrink-0"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
            <!-- Erreur -->
            <svg
              v-else-if="docStatusIcon === 'error'"
              xmlns="http://www.w3.org/2000/svg"
              class="w-3.5 h-3.5 text-red-500 shrink-0"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
            </svg>
            <span class="text-gray-500 dark:text-gray-400">
              {{ docStatusLabels[documentProgress.status] }}
              <span class="font-medium text-surface-text dark:text-surface-dark-text">{{ documentProgress.filename }}</span>
            </span>
          </div>
          <MessageParser
            :content="message.content"
            :is-streaming="isStreaming"
            :visualization-blocks="visualizationBlocks"
            @navigate="onNavigate"
            @open-source="onOpenSource"
          />
          <!-- Widget interactif (feature 018) : uniquement pour les etats finaux
               (historique) — les questions pending sont affichees dans la bottom sheet
               en bas de la page pour une meilleure UX. -->
          <InteractiveQuestionHost
            v-if="interactiveQuestion && interactiveQuestion.state !== 'pending'"
            :question="interactiveQuestion"
            @answer="onAnswer"
            @abandoned="onAbandoned"
          />
          <span
            v-if="isStreaming"
            class="inline-block w-1.5 h-4 bg-brand-green ml-0.5 animate-pulse"
          />
          <!-- Bouton copier -->
          <div v-if="!isStreaming && message.content" class="flex justify-end mt-2 pt-1 border-t border-gray-200/50 dark:border-dark-border/50">
            <button
              class="text-xs text-gray-400 hover:text-brand-green flex items-center gap-1 transition-colors"
              @click="copyContent"
            >
              <svg v-if="!copied" xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                <path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z" />
                <path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 3 3 0 01-3 3H9a3 3 0 01-3-3z" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 text-brand-green" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
              {{ copied ? 'Copié !' : 'Copier' }}
            </button>
          </div>
        </template>
      </div>

      <!-- Avatar utilisateur -->
      <div
        v-if="isUser"
        class="shrink-0 w-8 h-8 rounded-full bg-brand-blue flex items-center justify-center text-white text-sm font-bold mt-1"
      >
        U
      </div>
    </div>

    <!-- Notification de mise à jour du profil -->
    <div v-if="!isUser && !isStreaming && profileUpdates.length > 0" class="px-4 pb-1">
      <ProfileNotification :updates="profileUpdates" />
    </div>
  </div>
</template>

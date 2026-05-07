import { ref, computed } from 'vue'
import type { Conversation, Message, PaginatedResponse } from '~/types'
import type { ProfileUpdateEvent, CompletionResponse } from '~/types/company'
import type {
  InteractiveQuestion,
  InteractiveQuestionAnswer,
  InteractiveOption,
  InteractiveQuestionType,
  InteractiveQuestionState,
} from '~/types/interactive-question'
import { useAuthStore } from '~/stores/auth'
import { useCompanyStore } from '~/stores/company'
import { useUiStore } from '~/stores/ui'
// Review 6.4 P12 — import statique (evite await import(...) en hot-path)
import { useGuidedTour } from '~/composables/useGuidedTour'

// Sécurité : ce module-level state ne doit jamais s'exécuter côté serveur
if (import.meta.server) throw new Error('useChat is client-only')

// Review 6.4 P5 — flag : true apres une reponse 'yes' a un consent widget,
// consume par le prochain evenement SSE `guided_tour` pour distinguer une
// acceptance-via-consent d'un declenchement direct (verbe d'action visuel).
let _consentAcceptancePending = false

// ── Module-level state (singleton partagé entre tous les consommateurs) ──
const conversations = ref<Conversation[]>([])
const currentConversation = ref<Conversation | null>(null)
const messages = ref<Message[]>([])
const isStreaming = ref(false)
const streamingContent = ref('')
const error = ref('')
const documentProgress = ref<{
  documentId: string
  filename: string
  status: 'uploaded' | 'extracting' | 'analyzing' | 'done' | 'error'
} | null>(null)
const reportSuggestion = ref<{
  assessmentId: string
  message: string
} | null>(null)
const activeToolCall = ref<{
  name: string
  args: Record<string, unknown>
  callId: string
} | null>(null)
// Feature 018 — interactive widgets
const currentInteractiveQuestion = ref<InteractiveQuestion | null>(null)
const interactiveQuestionsByMessage = ref<Record<string, InteractiveQuestion>>({})

// F11 — Visualization blocks typés (KPICard, MatchCard, Map, ComparisonTable)
// Indexés par messageId, ordre d'arrivée préservé (concaténation).
export interface VisualizationBlock {
  blockType: 'show_kpi_card' | 'show_match_card' | 'show_map' | 'show_comparison_table'
  payload: Record<string, unknown>
}
const visualizationBlocksByMessage = ref<Record<string, VisualizationBlock[]>>({})
const searchQuery = ref('')
// SSE cross-routes : AbortController et reader module-level
const abortController = ref<AbortController | null>(null)
const sseReader = ref<ReadableStreamDefaultReader | null>(null)

// FR33/NFR17 — etat de connexion SSE/reseau deduit du dernier fetch + navigator.onLine.
// true par defaut (optimiste) ; bascule false sur TypeError/Failed to fetch ou event offline.
const isConnected = ref<boolean>(true)

// Message FR unique de perte de connexion : extrait en constante pour eviter la derive
// entre les 2 catches (sendMessage / submitInteractiveAnswer) et le clear dans le handler online.
const CONNECTION_LOST_MESSAGE = 'Connexion perdue. Verifiez votre reseau.'

// FR33 — classification des erreurs de fetch pour distinguer une coupure reseau
// d'une annulation volontaire (AbortError) ou d'une erreur HTTP serveur (response.ok=false).
type FetchErrorKind = 'abort' | 'network' | 'http' | 'other'
function classifyFetchError(e: unknown): FetchErrorKind {
  // Priorite 1 : annulation volontaire (AbortController)
  if (e instanceof DOMException && e.name === 'AbortError') return 'abort'
  // Priorite 2 : TypeError brut = network error (convention fetch API MDN)
  if (e instanceof TypeError) return 'network'
  // Priorite 3 : messages browser-specific (Firefox, Safari)
  if (e instanceof Error && /failed to fetch|network|load failed/i.test(e.message)) return 'network'
  // Priorite 4 : nos throw explicites apres !response.ok
  if (e instanceof Error && e.message.toLowerCase().includes('erreur lors de')) return 'http'
  return 'other'
}

// Installation des ecouteurs online/offline — robustesse cross-module (HMR, vi.resetModules).
// Les handlers precedents (d'un ancien import du module) sont stockes sur globalThis et
// retires avant reinstallation, evitant l'accumulation de listeners orphelins sur window.
type ConnectionListeners = { online: () => void, offline: () => void }
const _CONNECTION_LISTENERS_KEY = Symbol.for('esg-mefali:chat-connection-listeners')

if (import.meta.client) {
  const globalSlot = globalThis as typeof globalThis & {
    [key: symbol]: ConnectionListeners | undefined
  }
  const previous = globalSlot[_CONNECTION_LISTENERS_KEY]
  if (previous) {
    window.removeEventListener('online', previous.online)
    window.removeEventListener('offline', previous.offline)
  }
  const onlineHandler = () => {
    isConnected.value = true
    if (error.value === CONNECTION_LOST_MESSAGE) error.value = ''
  }
  const offlineHandler = () => {
    isConnected.value = false
  }
  isConnected.value = typeof navigator !== 'undefined' ? navigator.onLine : true
  window.addEventListener('online', onlineHandler)
  window.addEventListener('offline', offlineHandler)
  globalSlot[_CONNECTION_LISTENERS_KEY] = { online: onlineHandler, offline: offlineHandler }
}

/**
 * Normalise un label pour comparaison tolerante (minuscule + trim + compact).
 */
function _normalizeLabel(s: string): string {
  return s.toLowerCase().replace(/\s+/g, ' ').trim()
}

/**
 * Heuristique de detection d'une question de consentement guidage (story 6.4 / FR17).
 *
 * Review 6.4 P6 — hybride : module=='chat' + structure (qcu, 2 options positionnelles
 * id='yes'/'no') + labels canoniques normalises (tolere casse/espaces). Evite de
 * confondre avec une question ESG/carbone yes/no tout en tolerant la derive minime
 * du LLM (capitalisation, espaces). Une variation majeure (emoji, traduction) casse
 * intentionnellement la detection — c'est verrouille backend cote test T-AC1a (6.3).
 */
function isGuidanceConsentQuestion(q: InteractiveQuestion | null): boolean {
  if (!q || q.question_type !== 'qcu') return false
  if (q.module !== 'chat') return false
  if (!Array.isArray(q.options) || q.options.length !== 2) return false
  // Matching positionnel strict : options[0] = yes, options[1] = no.
  if (q.options[0]?.id !== 'yes' || q.options[1]?.id !== 'no') return false
  const yesNorm = _normalizeLabel(q.options[0]?.label || '')
  const noNorm = _normalizeLabel(q.options[1]?.label || '')
  return yesNorm === 'oui, montre-moi' && noNorm === 'non merci'
}

const filteredConversations = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return conversations.value
  return conversations.value.filter(c =>
    c.title.toLowerCase().includes(query),
  )
})

export function useChat() {
  // Les composables Nuxt doivent rester dans le contexte setup
  const config = useRuntimeConfig()
  const authStore = useAuthStore()
  const companyStore = useCompanyStore()
  const apiBase = config.public.apiBase

  function getHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      ...(authStore.accessToken
        ? { Authorization: `Bearer ${authStore.accessToken}` }
        : {}),
    }
  }

  async function fetchConversations(): Promise<void> {
    const response = await fetch(`${apiBase}/chat/conversations`, {
      headers: getHeaders(),
    })
    if (!response.ok) throw new Error('Erreur lors du chargement des conversations')
    const data: PaginatedResponse<Conversation> = await response.json()
    conversations.value = data.items
  }

  async function createConversation(title?: string): Promise<Conversation> {
    const response = await fetch(`${apiBase}/chat/conversations`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(title ? { title } : {}),
    })
    if (!response.ok) throw new Error('Erreur lors de la création de la conversation')
    const conversation: Conversation = await response.json()
    conversations.value = [conversation, ...conversations.value]
    return conversation
  }

  async function selectConversation(conversation: Conversation): Promise<void> {
    currentConversation.value = conversation
    await fetchMessages(conversation.id)
  }

  async function fetchMessages(conversationId: string): Promise<void> {
    const response = await fetch(
      `${apiBase}/chat/conversations/${conversationId}/messages`,
      { headers: getHeaders() },
    )
    if (!response.ok) throw new Error('Erreur lors du chargement des messages')
    const data: PaginatedResponse<Message> = await response.json()
    messages.value = data.items

    // Hydrater les questions interactives associees (feature 018)
    try {
      const iqResp = await fetch(
        `${apiBase}/chat/conversations/${conversationId}/interactive-questions?state=all&limit=200`,
        { headers: getHeaders() },
      )
      if (iqResp.ok) {
        const iqBody = await iqResp.json()
        const items: Array<InteractiveQuestion & { assistant_message_id: string | null }> = iqBody.data || []
        const byMessage: Record<string, InteractiveQuestion> = {}
        let pending: InteractiveQuestion | null = null
        for (const q of items) {
          if (q.assistant_message_id) {
            byMessage[q.assistant_message_id] = q
          }
          if (q.state === 'pending') {
            pending = q
          }
        }
        interactiveQuestionsByMessage.value = byMessage
        currentInteractiveQuestion.value = pending
      }
    } catch {
      // Best effort : ne pas bloquer le chargement des messages
    }
  }

  async function sendMessage(content: string, file?: File): Promise<void> {
    if (!currentConversation.value || isStreaming.value) return

    error.value = ''
    isStreaming.value = true
    streamingContent.value = ''
    documentProgress.value = null

    // Ajouter le message utilisateur localement
    const displayContent = file
      ? `${content || 'Analyse ce document'}\n📎 ${file.name}`
      : content
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: displayContent,
      created_at: new Date().toISOString(),
    }
    messages.value = [...messages.value, userMessage]

    // Annuler le stream précédent s'il existe
    if (abortController.value) {
      abortController.value.abort()
    }
    abortController.value = new AbortController()
    const localController = abortController.value

    try {
      // Construire la requete : multipart si fichier, sinon Form data
      const uiStore = useUiStore()
      const formData = new FormData()
      formData.append('content', content || (file ? `Analyse ce document : ${file.name}` : ''))
      if (file) {
        formData.append('file', file)
      }
      formData.append('current_page', uiStore.currentPage)

      // FR17 — transmettre les compteurs de modulation au LLM (story 6.4)
      const _gt = useGuidedTour()
      formData.append('guidance_stats', JSON.stringify({
        refusal_count: _gt.guidanceRefusalCount.value,
        acceptance_count: _gt.guidanceAcceptanceCount.value,
      }))

      const headers: Record<string, string> = {}
      if (authStore.accessToken) {
        headers.Authorization = `Bearer ${authStore.accessToken}`
      }

      const response = await fetch(
        `${apiBase}/chat/conversations/${currentConversation.value.id}/messages`,
        {
          method: 'POST',
          headers,
          body: formData,
          signal: localController.signal,
        },
      )

      if (!response.ok) {
        throw new Error('Erreur lors de l\'envoi du message')
      }

      if (!response.body) {
        throw new Error('Réponse sans body — streaming impossible')
      }

      // Annuler le reader précédent s'il existe (cancel() est safe même si le read est en cours)
      if (sseReader.value) {
        await sseReader.value.cancel()
      }
      // Lire le flux SSE via le reader module-level
      sseReader.value = response.body.getReader()
      const reader = sseReader.value
      const decoder = new TextDecoder()

      // Ajouter un message assistant vide pour le streaming
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      }
      messages.value = [...messages.value, assistantMessage]

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        // FR33/AC5 — premier chunk recu sans erreur = reprise de connexion immediate.
        if (!isConnected.value) isConnected.value = true

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6)

          try {
            const event = JSON.parse(jsonStr) as {
              type: string
              content?: string
              message_id?: string | null
              skipped_empty?: boolean
              field?: string
              value?: string | number | boolean
              label?: string
              identity_completion?: number
              esg_completion?: number
              overall_completion?: number
              document_id?: string
              filename?: string
              status?: string
              summary?: string
              document_type?: string
              assessment_id?: string
              tool_name?: string
              tool_args?: Record<string, unknown>
              tool_call_id?: string
              success?: boolean
              result_summary?: string
              error_message?: string
              message?: string
              // Feature 018 — interactive widgets
              id?: string
              conversation_id?: string
              question_type?: InteractiveQuestionType
              prompt?: string
              options?: InteractiveOption[]
              min_selections?: number
              max_selections?: number
              requires_justification?: boolean
              justification_prompt?: string | null
              module?: string
              created_at?: string
              response_values?: string[] | null
              response_justification?: string | null
              answered_at?: string
            }

            if (event.type === 'token' && event.content) {
              streamingContent.value += event.content
              // Mettre a jour le dernier message assistant
              const lastIdx = messages.value.length - 1
              messages.value = messages.value.map((msg, idx) =>
                idx === lastIdx
                  ? { ...msg, content: streamingContent.value }
                  : msg,
              )
            } else if (event.type === 'done' && event.skipped_empty) {
              // BUG-3 : le backend a saute la persistance car la reponse
              // assistant est vide (guided_tour emis). Retirer le placeholder
              // vide cree ligne 295-301 pour eviter une bulle muette dans l'UI.
              const lastIdx = messages.value.length - 1
              if (
                lastIdx >= 0 &&
                messages.value[lastIdx]?.role === 'assistant' &&
                !messages.value[lastIdx]?.content
              ) {
                messages.value = messages.value.slice(0, lastIdx)
              }
              documentProgress.value = null
            } else if (event.type === 'done' && event.message_id) {
              // Mettre a jour l'ID du message avec l'ID persiste
              const lastIdx = messages.value.length - 1
              const oldId = messages.value[lastIdx]?.id
              messages.value = messages.value.map((msg, idx) =>
                idx === lastIdx
                  ? { ...msg, id: event.message_id! }
                  : msg,
              )
              // Transferer la question interactive du tempId au vrai message_id
              if (oldId && interactiveQuestionsByMessage.value[oldId]) {
                const q = interactiveQuestionsByMessage.value[oldId]!
                const updated = { ...interactiveQuestionsByMessage.value }
                delete updated[oldId]
                updated[event.message_id!] = q
                interactiveQuestionsByMessage.value = updated
              }
              // F11 — Transférer les visualization_blocks du tempId au vrai message_id
              if (oldId && visualizationBlocksByMessage.value[oldId]) {
                const blocks = visualizationBlocksByMessage.value[oldId]!
                const updated = { ...visualizationBlocksByMessage.value }
                delete updated[oldId]
                updated[event.message_id!] = blocks
                visualizationBlocksByMessage.value = updated
              }
              documentProgress.value = null
            } else if (event.type === 'document_upload') {
              // Document recu
              documentProgress.value = {
                documentId: event.document_id!,
                filename: event.filename!,
                status: 'uploaded',
              }
            } else if (event.type === 'document_status') {
              // Progression document
              if (documentProgress.value) {
                documentProgress.value = {
                  ...documentProgress.value,
                  status: event.status as 'extracting' | 'analyzing' | 'error',
                }
              }
            } else if (event.type === 'document_analysis') {
              // Analyse terminee
              if (documentProgress.value) {
                documentProgress.value = {
                  ...documentProgress.value,
                  status: 'done',
                }
              }
            } else if (event.type === 'profile_update' && event.field) {
              // Mise a jour du profil extraite du chat
              const update: ProfileUpdateEvent = {
                field: event.field,
                value: event.value!,
                label: event.label || event.field,
              }
              companyStore.addProfileUpdate(update)
              companyStore.updateProfileField(event.field, event.value)
            } else if (event.type === 'profile_completion') {
              // Mise a jour de la completion
              companyStore.setCompletion({
                identity_completion: event.identity_completion!,
                esg_completion: event.esg_completion!,
                overall_completion: event.overall_completion!,
                identity_fields: { filled: [], missing: [] },
                esg_fields: { filled: [], missing: [] },
              })
            } else if (event.type === 'tool_call_start' && event.tool_name) {
              // Début d'exécution d'un tool
              activeToolCall.value = {
                name: event.tool_name,
                args: event.tool_args || {},
                callId: event.tool_call_id || '',
              }
            } else if (event.type === 'tool_call_end') {
              // Fin d'exécution d'un tool
              activeToolCall.value = null
            } else if (event.type === 'tool_call_error') {
              // Erreur d'un tool
              activeToolCall.value = null
            } else if (event.type === 'visualization_block' && event.block_type) {
              // F11 — Bloc de visualisation typé (KPICard, MatchCard, Map, ComparisonTable)
              const lastIdx = messages.value.length - 1
              if (lastIdx >= 0 && messages.value[lastIdx]?.role === 'assistant') {
                const msgId = messages.value[lastIdx]!.id
                const existing = visualizationBlocksByMessage.value[msgId] || []
                visualizationBlocksByMessage.value = {
                  ...visualizationBlocksByMessage.value,
                  [msgId]: [
                    ...existing,
                    {
                      blockType: event.block_type as VisualizationBlock['blockType'],
                      payload: (event.payload || {}) as Record<string, unknown>,
                    },
                  ],
                }
              }
            } else if (event.type === 'interactive_question' && event.id) {
              // Feature 018 — affichage d'une question interactive cliquable
              const question: InteractiveQuestion = {
                id: event.id,
                conversation_id: event.conversation_id || '',
                question_type: event.question_type || 'qcu',
                prompt: event.prompt || '',
                options: event.options || [],
                min_selections: event.min_selections ?? 1,
                max_selections: event.max_selections ?? 1,
                requires_justification: event.requires_justification ?? false,
                justification_prompt: event.justification_prompt ?? null,
                module: event.module || 'chat',
                created_at: event.created_at || new Date().toISOString(),
                state: 'pending',
                response_values: null,
                response_justification: null,
                answered_at: null,
              }
              currentInteractiveQuestion.value = question
              // Lier la question au dernier message assistant
              const lastIdx = messages.value.length - 1
              if (lastIdx >= 0 && messages.value[lastIdx]?.role === 'assistant') {
                interactiveQuestionsByMessage.value = {
                  ...interactiveQuestionsByMessage.value,
                  [messages.value[lastIdx]!.id]: question,
                }
              }
            } else if (event.type === 'interactive_question_resolved' && event.id) {
              // Mise a jour finale d'une question (answered/abandoned/expired)
              const newState = (event.state || 'answered') as InteractiveQuestionState
              if (currentInteractiveQuestion.value?.id === event.id) {
                currentInteractiveQuestion.value = {
                  ...currentInteractiveQuestion.value,
                  state: newState,
                  response_values: event.response_values ?? null,
                  response_justification: event.response_justification ?? null,
                  answered_at: event.answered_at ?? null,
                }
              }
              // Mettre a jour la question liee a un message si presente
              const updated: Record<string, InteractiveQuestion> = {}
              for (const [msgId, q] of Object.entries(interactiveQuestionsByMessage.value)) {
                if (q.id === event.id) {
                  updated[msgId] = {
                    ...q,
                    state: newState,
                    response_values: event.response_values ?? null,
                    response_justification: event.response_justification ?? null,
                    answered_at: event.answered_at ?? null,
                  }
                } else {
                  updated[msgId] = q
                }
              }
              interactiveQuestionsByMessage.value = updated
              if (newState !== 'pending') {
                // Liberer le state courant pour debloquer l'input texte
                if (currentInteractiveQuestion.value?.id === event.id) {
                  currentInteractiveQuestion.value = null
                }
              }
            } else if (event.type === 'report_suggestion' && event.assessment_id) {
              reportSuggestion.value = {
                assessmentId: event.assessment_id,
                message: event.message || 'Votre evaluation ESG est terminee ! Generez un rapport PDF.',
              }
            } else if (event.type === 'guided_tour') {
              // Feature 019 — Declenchement parcours guide via SSE
              await handleGuidedTourEvent(event as Record<string, unknown>)
            } else if (event.type === 'error') {
              error.value = event.content || 'Erreur du service IA'
            }
          } catch {
            // Ignorer les lignes qui ne sont pas du JSON valide
          }
        }
      }
    } catch (e) {
      // FR33/AC3 — classifier l'erreur avant de toucher isConnected / error.value.
      const kind = classifyFetchError(e)
      if (kind === 'abort') return
      if (kind === 'network') {
        isConnected.value = false
        const uiStore = useUiStore()
        if (!uiStore.guidedTourActive) {
          error.value = CONNECTION_LOST_MESSAGE
        }
        return
      }
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
    } finally {
      // Reset si c'est le même appel actif OU si aucun nouvel appel n'a pris le relais
      if (abortController.value === localController || abortController.value === null) {
        isStreaming.value = false
        streamingContent.value = ''
      }
    }
  }

  async function deleteConversation(conversationId: string): Promise<void> {
    const response = await fetch(
      `${apiBase}/chat/conversations/${conversationId}`,
      { method: 'DELETE', headers: getHeaders() },
    )
    if (!response.ok) throw new Error('Erreur lors de la suppression')
    conversations.value = conversations.value.filter(c => c.id !== conversationId)
    if (currentConversation.value?.id === conversationId) {
      currentConversation.value = null
      messages.value = []
    }
  }

  async function renameConversation(conversationId: string, title: string): Promise<void> {
    const response = await fetch(
      `${apiBase}/chat/conversations/${conversationId}`,
      {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify({ title }),
      },
    )
    if (response.status === 429) {
      error.value = 'Trop de requêtes. Veuillez patienter quelques instants.'
      return
    }
    if (!response.ok) throw new Error('Erreur lors du renommage')
    const updated: Conversation = await response.json()
    conversations.value = conversations.value.map(c =>
      c.id === conversationId ? updated : c,
    )
    if (currentConversation.value?.id === conversationId) {
      currentConversation.value = updated
    }
  }

  async function submitInteractiveAnswer(
    questionId: string,
    answer: InteractiveQuestionAnswer,
  ): Promise<void> {
    if (!currentConversation.value || isStreaming.value) return

    error.value = ''
    isStreaming.value = true
    streamingContent.value = ''

    // Construire la representation textuelle du choix utilisateur
    const question = currentInteractiveQuestion.value

    // Review 6.4 P3+P5 — capture l'intent (refus / acceptance consent) MAIS
    // ne commit pas encore les compteurs : seul un aller-retour reussi ou
    // un tour effectivement lance peuvent crediter le bon compteur.
    const isConsentQ = isGuidanceConsentQuestion(question)
    const pendingRefusal = isConsentQ && answer.values.includes('no')
    const pendingAcceptance = isConsentQ && answer.values.includes('yes')

    const labels = question
      ? question.options
          .filter(opt => answer.values.includes(opt.id))
          .map(opt => opt.label)
      : answer.values
    const displayContent = labels.join(', ') + (
      answer.justification ? `\n_${answer.justification}_` : ''
    )

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: displayContent,
      created_at: new Date().toISOString(),
    }
    messages.value = [...messages.value, userMessage]

    // Marquer la question courante comme answered localement
    if (currentInteractiveQuestion.value?.id === questionId) {
      const resolved: InteractiveQuestion = {
        ...currentInteractiveQuestion.value,
        state: 'answered',
        response_values: answer.values,
        response_justification: answer.justification ?? null,
        answered_at: new Date().toISOString(),
      }
      currentInteractiveQuestion.value = null
      const updated: Record<string, InteractiveQuestion> = {}
      for (const [msgId, q] of Object.entries(interactiveQuestionsByMessage.value)) {
        updated[msgId] = q.id === questionId ? resolved : q
      }
      interactiveQuestionsByMessage.value = updated
    }

    // Annuler le stream précédent s'il existe
    if (abortController.value) {
      abortController.value.abort()
    }
    abortController.value = new AbortController()
    const localController = abortController.value

    try {
      const uiStore = useUiStore()
      const formData = new FormData()
      formData.append('content', '')
      formData.append('current_page', uiStore.currentPage)

      // Review 6.4 P10 — `guidance_stats` ordonne APRES `current_page` et AVANT
      // le bloc `interactive_question_*` (cf spec AC2).
      // FR17 — transmettre les compteurs de modulation au LLM (story 6.4)
      const _gt = useGuidedTour()
      formData.append('guidance_stats', JSON.stringify({
        refusal_count: _gt.guidanceRefusalCount.value,
        acceptance_count: _gt.guidanceAcceptanceCount.value,
      }))

      formData.append('interactive_question_id', questionId)
      formData.append('interactive_question_values', JSON.stringify(answer.values))
      if (answer.justification) {
        formData.append('interactive_question_justification', answer.justification)
      }

      // Review 6.4 P5 — armer le flag AVANT l'appel. handleGuidedTourEvent
      // le consommera lors du SSE `guided_tour` qui va suivre (si LLM declenche).
      if (pendingAcceptance) {
        _consentAcceptancePending = true
      }

      const headers: Record<string, string> = {}
      if (authStore.accessToken) {
        headers.Authorization = `Bearer ${authStore.accessToken}`
      }

      const response = await fetch(
        `${apiBase}/chat/conversations/${currentConversation.value.id}/messages`,
        { method: 'POST', headers, body: formData, signal: localController.signal },
      )

      if (!response.ok) {
        throw new Error("Erreur lors de l'envoi de la reponse")
      }

      if (!response.body) {
        throw new Error('Réponse sans body — streaming impossible')
      }

      // Annuler le reader précédent s'il existe (cancel() est safe même si le read est en cours)
      if (sseReader.value) {
        await sseReader.value.cancel()
      }
      // Lecture du flux SSE via le reader module-level
      sseReader.value = response.body.getReader()
      const reader = sseReader.value
      const decoder = new TextDecoder()

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      }
      messages.value = [...messages.value, assistantMessage]

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        // FR33/AC5 — premier chunk recu sans erreur = reprise de connexion immediate.
        if (!isConnected.value) isConnected.value = true
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6)
          try {
            const evt = JSON.parse(jsonStr) as {
              type: string
              content?: string
              message_id?: string | null
              skipped_empty?: boolean
              id?: string
              conversation_id?: string
              question_type?: InteractiveQuestionType
              prompt?: string
              options?: InteractiveOption[]
              min_selections?: number
              max_selections?: number
              requires_justification?: boolean
              justification_prompt?: string | null
              module?: string
              created_at?: string
            }
            if (evt.type === 'token' && evt.content) {
              streamingContent.value += evt.content
              const lastIdx = messages.value.length - 1
              messages.value = messages.value.map((msg, idx) =>
                idx === lastIdx ? { ...msg, content: streamingContent.value } : msg,
              )
            } else if (evt.type === 'done' && evt.skipped_empty) {
              // BUG-3 : retirer le placeholder vide (voir sendMessage pour le rationale).
              const lastIdx = messages.value.length - 1
              if (
                lastIdx >= 0 &&
                messages.value[lastIdx]?.role === 'assistant' &&
                !messages.value[lastIdx]?.content
              ) {
                messages.value = messages.value.slice(0, lastIdx)
              }
            } else if (evt.type === 'done' && evt.message_id) {
              const lastIdx = messages.value.length - 1
              const oldId = messages.value[lastIdx]?.id
              messages.value = messages.value.map((msg, idx) =>
                idx === lastIdx ? { ...msg, id: evt.message_id! } : msg,
              )
              // Transferer la question interactive du tempId au vrai message_id
              if (oldId && interactiveQuestionsByMessage.value[oldId]) {
                const q = interactiveQuestionsByMessage.value[oldId]!
                const updated = { ...interactiveQuestionsByMessage.value }
                delete updated[oldId]
                updated[evt.message_id!] = q
                interactiveQuestionsByMessage.value = updated
              }
              // F11 — Transférer les visualization_blocks
              if (oldId && visualizationBlocksByMessage.value[oldId]) {
                const blocks = visualizationBlocksByMessage.value[oldId]!
                const updated = { ...visualizationBlocksByMessage.value }
                delete updated[oldId]
                updated[evt.message_id!] = blocks
                visualizationBlocksByMessage.value = updated
              }
            } else if (evt.type === 'interactive_question' && evt.id) {
              // Feature 018 — nouvelle question interactive dans un nouveau tour (apres submit d'une reponse)
              const newQ: InteractiveQuestion = {
                id: evt.id,
                conversation_id: evt.conversation_id || '',
                question_type: evt.question_type || 'qcu',
                prompt: evt.prompt || '',
                options: evt.options || [],
                min_selections: evt.min_selections ?? 1,
                max_selections: evt.max_selections ?? 1,
                requires_justification: evt.requires_justification ?? false,
                justification_prompt: evt.justification_prompt ?? null,
                module: evt.module || 'chat',
                created_at: evt.created_at || new Date().toISOString(),
                state: 'pending',
                response_values: null,
                response_justification: null,
                answered_at: null,
              }
              currentInteractiveQuestion.value = newQ
              const lastIdx = messages.value.length - 1
              if (lastIdx >= 0 && messages.value[lastIdx]?.role === 'assistant') {
                interactiveQuestionsByMessage.value = {
                  ...interactiveQuestionsByMessage.value,
                  [messages.value[lastIdx]!.id]: newQ,
                }
              }
            } else if (evt.type === 'guided_tour') {
              // Feature 019 — Declenchement parcours guide via SSE (apres submit reponse interactive)
              await handleGuidedTourEvent(evt as Record<string, unknown>)
            } else if (evt.type === 'visualization_block' && evt.block_type) {
              // F11 — Bloc de visualisation typé sur ce nouveau tour
              const lastIdx = messages.value.length - 1
              if (lastIdx >= 0 && messages.value[lastIdx]?.role === 'assistant') {
                const msgId = messages.value[lastIdx]!.id
                const existing = visualizationBlocksByMessage.value[msgId] || []
                visualizationBlocksByMessage.value = {
                  ...visualizationBlocksByMessage.value,
                  [msgId]: [
                    ...existing,
                    {
                      blockType: evt.block_type as VisualizationBlock['blockType'],
                      payload: (evt.payload || {}) as Record<string, unknown>,
                    },
                  ],
                }
              }
            }
          } catch {
            // Ignorer les lignes invalides
          }
        }
      }

      // Review 6.4 P3 — le flux SSE a termine normalement : on peut
      // commit le refus (network round-trip reussi). Si un throw est survenu
      // avant, on ne l'atteint pas et refus n'est pas credite (comportement
      // voulu par AC5).
      if (pendingRefusal) {
        useGuidedTour().incrementGuidanceRefusal()
      }
    } catch (e) {
      // FR33/AC3 — classifier l'erreur avant de toucher isConnected / error.value.
      const kind = classifyFetchError(e)
      if (kind === 'abort') return
      if (kind === 'network') {
        isConnected.value = false
        const uiStore = useUiStore()
        if (!uiStore.guidedTourActive) {
          error.value = CONNECTION_LOST_MESSAGE
        }
        return
      }
      error.value = e instanceof Error ? e.message : 'Erreur inconnue'
    } finally {
      // Reset si c'est le même appel actif OU si aucun nouvel appel n'a pris le relais
      if (abortController.value === localController || abortController.value === null) {
        isStreaming.value = false
        streamingContent.value = ''
      }
      // Review 6.4 P5 — si un flag consent etait arme mais qu'aucun guided_tour
      // n'a suivi (LLM n'a pas declenche), on le desarme pour ne pas polluer
      // un futur tour explicite.
      _consentAcceptancePending = false
    }
  }

  function addSystemMessage(content: string): void {
    const msg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content,
      created_at: new Date().toISOString(),
    }
    messages.value = [...messages.value, msg]
  }

  /**
   * Feature 019 — Gestionnaire centralise d'un event SSE `guided_tour`.
   *
   * Garde-fous (story 6.1 review) :
   *   - Ignore silencieusement si `tour_id` absent / vide / non string (log warn pour debug).
   *   - Bloque le declenchement quand une question interactive est `pending` :
   *     l'overlay Driver.js masquerait le widget, l'utilisateur ne pourrait plus repondre.
   *   - Rattrape les rejets asynchrones (`await import` / `startTour`) pour eviter
   *     les unhandled promise rejections remontees hors du try/catch du flux SSE.
   */
  async function handleGuidedTourEvent(event: Record<string, unknown>): Promise<void> {
    const tourId = event.tour_id
    if (typeof tourId !== 'string' || !tourId.trim()) {
      // eslint-disable-next-line no-console
      console.warn('[useChat] guided_tour event sans tour_id valide', event)
      return
    }
    if (currentInteractiveQuestion.value?.state === 'pending') {
      addSystemMessage("Repondez d'abord a la question en attente.")
      return
    }
    // Review 6.4 P5 — consomme le flag : un declenchement direct
    // (sans consent widget precedent) n'incrementera PAS acceptance.
    const fromConsent = _consentAcceptancePending
    _consentAcceptancePending = false
    try {
      const guided = useGuidedTour()
      // Review 6.4 P4 — commit acceptance UNIQUEMENT apres que startTour ait
      // mene le parcours a completion (pas d'acceptance fantome si tour_id
      // hors registre, DOM introuvable, ou utilisateur annule).
      const completed = await guided.startTour(tourId, (event.context as Record<string, unknown>) || {})
      if (completed && fromConsent) {
        guided.incrementGuidanceAcceptance()
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn('[useChat] Echec declenchement guided tour', err)
    }
  }

  function onInteractiveQuestionAbandoned(questionId: string): void {
    if (currentInteractiveQuestion.value?.id === questionId) {
      currentInteractiveQuestion.value = null
    }
    const updated: Record<string, InteractiveQuestion> = {}
    for (const [msgId, q] of Object.entries(interactiveQuestionsByMessage.value)) {
      updated[msgId] = q.id === questionId
        ? { ...q, state: 'abandoned', answered_at: new Date().toISOString() }
        : q
    }
    interactiveQuestionsByMessage.value = updated
  }

  return {
    conversations,
    currentConversation,
    messages,
    isStreaming,
    streamingContent,
    error,
    isConnected,
    searchQuery,
    filteredConversations,
    documentProgress,
    reportSuggestion,
    activeToolCall,
    currentInteractiveQuestion,
    interactiveQuestionsByMessage,
    // F11 — visualization blocks typés
    visualizationBlocksByMessage,
    fetchConversations,
    createConversation,
    selectConversation,
    fetchMessages,
    sendMessage,
    addSystemMessage,
    submitInteractiveAnswer,
    onInteractiveQuestionAbandoned,
    deleteConversation,
    renameConversation,
  }
}

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref, computed, nextTick, defineComponent } from 'vue'
import { useUiStore } from '~/stores/ui'
import type { InteractiveQuestion } from '~/types/interactive-question'

// Mock useRuntimeConfig (auto-import Nuxt)
vi.stubGlobal('useRuntimeConfig', () => ({
  public: { apiBase: 'http://localhost:8000/api' },
}))

// Mock useAuthStore
vi.mock('~/stores/auth', () => ({
  useAuthStore: () => ({ accessToken: 'test-token' }),
}))

// Mock GSAP
const mockFromTo = vi.fn()
const mockTo = vi.fn((_el: unknown, opts: Record<string, unknown>) => {
  if (typeof opts.onComplete === 'function') {
    ;(opts.onComplete as () => void)()
  }
})
const mockKillTweensOf = vi.fn()

vi.mock('gsap', () => ({
  gsap: {
    fromTo: (...args: unknown[]) => mockFromTo(...args),
    to: (...args: unknown[]) => mockTo(...args),
    killTweensOf: (...args: unknown[]) => mockKillTweensOf(...args),
  },
}))

// Mock useChat composable
const mockFetchConversations = vi.fn()
const mockSelectConversation = vi.fn()
const mockCreateConversation = vi.fn().mockResolvedValue({ id: 'new-conv', title: 'Nouvelle conversation', updated_at: new Date().toISOString() })
const mockDeleteConversation = vi.fn()
const mockRenameConversation = vi.fn()
const mockSendMessage = vi.fn()
const mockSubmitInteractiveAnswer = vi.fn()
const mockOnInteractiveQuestionAbandoned = vi.fn()
const mockFetchMessages = vi.fn()
const mockConversations = ref<Array<{ id: string; title: string; updated_at: string }>>([])
const mockCurrentConversation = ref<{ id: string; title: string; updated_at: string } | null>(null)
const mockSearchQuery = ref('')
const mockFilteredConversations = computed(() => mockConversations.value)
const mockMessages = ref<Array<{ id: string; role: string; content: string }>>([])
const mockIsStreaming = ref(false)
const mockStreamingContent = ref('')
const mockError = ref<string | null>(null)
const mockDocumentProgress = ref<{ documentId: string; filename: string; status: string } | null>(null)
const mockReportSuggestion = ref(null)
const mockActiveToolCall = ref<{ name: string; args: Record<string, unknown>; callId: string } | null>(null)
const mockCurrentInteractiveQuestion = ref<InteractiveQuestion | null>(null)
const mockInteractiveQuestionsByMessage = ref<Record<string, InteractiveQuestion>>({})
// F11 — visualization blocks par message
const mockVisualizationBlocksByMessage = ref<Record<string, unknown[]>>({})
// Story 7.3 — indicateur de connexion SSE exposee par useChat
const mockIsConnected = ref(true)

vi.mock('~/composables/useChat', () => ({
  useChat: () => ({
    conversations: mockConversations,
    currentConversation: mockCurrentConversation,
    searchQuery: mockSearchQuery,
    filteredConversations: mockFilteredConversations,
    fetchConversations: mockFetchConversations,
    selectConversation: mockSelectConversation,
    createConversation: mockCreateConversation,
    deleteConversation: mockDeleteConversation,
    renameConversation: mockRenameConversation,
    messages: mockMessages,
    isStreaming: mockIsStreaming,
    streamingContent: mockStreamingContent,
    error: mockError,
    isConnected: mockIsConnected,
    documentProgress: mockDocumentProgress,
    reportSuggestion: mockReportSuggestion,
    activeToolCall: mockActiveToolCall,
    currentInteractiveQuestion: mockCurrentInteractiveQuestion,
    interactiveQuestionsByMessage: mockInteractiveQuestionsByMessage,
    visualizationBlocksByMessage: mockVisualizationBlocksByMessage,
    sendMessage: mockSendMessage,
    submitInteractiveAnswer: mockSubmitInteractiveAnswer,
    onInteractiveQuestionAbandoned: mockOnInteractiveQuestionAbandoned,
    fetchMessages: mockFetchMessages,
  }),
}))

// Stub composants auto-importes Nuxt
const ChatWidgetHeaderStub = defineComponent({
  name: 'ChatWidgetHeader',
  props: {
    title: { type: String, required: true },
    showBackButton: { type: Boolean, required: true },
  },
  emits: ['close', 'toggleHistory', 'back'],
  template: `
    <header class="chat-widget-header-stub">
      <button v-if="showBackButton" aria-label="Retour à la conversation" @click="$emit('back')">back</button>
      <span class="header-title">{{ title }}</span>
      <button v-if="!showBackButton" aria-label="Historique des conversations" @click="$emit('toggleHistory')">history</button>
      <button aria-label="Fermer l'assistant IA" @click="$emit('close')">close</button>
    </header>
  `,
})

const ConversationListStub = defineComponent({
  name: 'ConversationList',
  props: {
    conversations: { type: Array, default: () => [] },
    currentId: { type: String, default: undefined },
    searchQuery: { type: String, default: '' },
    isDrawer: { type: Boolean, default: false },
  },
  emits: ['select', 'create', 'delete', 'rename', 'update:searchQuery'],
  template: '<div class="conversation-list-stub" />',
})

const WelcomeMessageStub = defineComponent({
  name: 'WelcomeMessage',
  template: '<div class="welcome-message-stub">Bienvenue</div>',
})

const ChatMessageStub = defineComponent({
  name: 'ChatMessage',
  props: {
    message: { type: Object, required: true },
    isStreaming: { type: Boolean, default: false },
    documentProgress: { type: Object, default: null },
    interactiveQuestion: { type: Object, default: null },
  },
  template: '<div class="chat-message-stub">{{ message.content }}</div>',
})

const ChatInputStub = defineComponent({
  name: 'ChatInput',
  props: {
    disabled: { type: Boolean, default: false },
  },
  emits: ['send', 'sendWithFile'],
  template: '<div class="chat-input-stub"><button class="send-btn" @click="$emit(\'send\', \'test message\')">Envoyer</button></div>',
})

const ToolCallIndicatorStub = defineComponent({
  name: 'ToolCallIndicator',
  props: {
    toolName: { type: String, required: true },
    args: { type: Object, default: () => ({}) },
  },
  template: '<div class="tool-call-indicator-stub">{{ toolName }}</div>',
})

const InteractiveQuestionInputBarStub = defineComponent({
  name: 'InteractiveQuestionInputBar',
  props: {
    question: { type: Object, required: true },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
  },
  emits: ['submit', 'abandonAndSend'],
  template: '<div class="interactive-input-bar-stub">Question interactive</div>',
})

// Story 7.3 — stub du badge de connexion (presentationnel, isole dans ses propres tests)
const ConnectionStatusBadgeStub = defineComponent({
  name: 'ConnectionStatusBadge',
  props: {
    isConnected: { type: Boolean, required: true },
  },
  template: '<div v-if="!isConnected" class="connection-status-badge-stub">Reconnexion...</div>',
})

describe('FloatingChatWidget', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    mockFromTo.mockClear()
    mockTo.mockClear()
    mockKillTweensOf.mockClear()
    mockFetchConversations.mockClear()
    mockSelectConversation.mockClear()
    mockCreateConversation.mockClear().mockResolvedValue({ id: 'new-conv', title: 'Nouvelle conversation', updated_at: new Date().toISOString() })
    mockDeleteConversation.mockClear()
    mockRenameConversation.mockClear()
    mockSendMessage.mockClear()
    mockSubmitInteractiveAnswer.mockClear()
    mockOnInteractiveQuestionAbandoned.mockClear()
    mockFetchMessages.mockClear()
    mockConversations.value = []
    mockCurrentConversation.value = null
    mockSearchQuery.value = ''
    mockMessages.value = []
    mockIsStreaming.value = false
    mockStreamingContent.value = ''
    mockError.value = null
    mockDocumentProgress.value = null
    mockReportSuggestion.value = null
    mockActiveToolCall.value = null
    mockCurrentInteractiveQuestion.value = null
    mockInteractiveQuestionsByMessage.value = {}
    mockIsConnected.value = true
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  async function mountWidget() {
    const { default: Component } = await import('~/components/copilot/FloatingChatWidget.vue')
    return mount(Component, {
      global: {
        plugins: [pinia],
        stubs: {
          ChatWidgetHeader: ChatWidgetHeaderStub,
          ConversationList: ConversationListStub,
          WelcomeMessage: WelcomeMessageStub,
          ChatMessage: ChatMessageStub,
          ChatInput: ChatInputStub,
          ToolCallIndicator: ToolCallIndicatorStub,
          InteractiveQuestionInputBar: InteractiveQuestionInputBarStub,
          ConnectionStatusBadge: ConnectionStatusBadgeStub,
        },
      },
    })
  }

  describe('Visibilite (AC #2, #4)', () => {
    it('le widget est cache par defaut (chatWidgetOpen = false)', async () => {
      const wrapper = await mountWidget()
      const widget = wrapper.find('.widget-glass')
      expect(widget.attributes('style')).toContain('display: none')
    })

    it('le widget devient visible quand chatWidgetOpen passe a true', async () => {
      const wrapper = await mountWidget()
      const uiStore = useUiStore()

      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      const widget = wrapper.find('.widget-glass')
      expect(widget.exists()).toBe(true)
      expect(widget.attributes('style') || '').not.toContain('display: none')
    })
  })

  describe('Structure du widget (AC #2, #3)', () => {
    it('a les dimensions par defaut 400x600 via style inline', async () => {
      const wrapper = await mountWidget()
      const widget = wrapper.find('.widget-glass')

      expect(widget.element.style.width).toBe('400px')
      expect(widget.element.style.height).toBe('600px')
    })

    it('a le positionnement fixed et z-50', async () => {
      const wrapper = await mountWidget()
      const widget = wrapper.find('.widget-glass')

      expect(widget.classes()).toContain('fixed')
      expect(widget.classes()).toContain('z-50')
      expect(widget.classes()).toContain('bottom-24')
      expect(widget.classes()).toContain('right-6')
    })

    it('a overflow-hidden et rounded-2xl', async () => {
      const wrapper = await mountWidget()
      const widget = wrapper.find('.widget-glass')

      expect(widget.classes()).toContain('overflow-hidden')
      expect(widget.classes()).toContain('rounded-2xl')
    })

    it('affiche le titre "Assistant IA" quand aucune conversation active', async () => {
      const wrapper = await mountWidget()
      const header = wrapper.findComponent(ChatWidgetHeaderStub)
      expect(header.exists()).toBe(true)
      expect(header.props('title')).toBe('Assistant IA')
    })

    it('affiche le titre de la conversation courante', async () => {
      mockCurrentConversation.value = { id: '1', title: 'Mon analyse ESG', updated_at: new Date().toISOString() }
      const wrapper = await mountWidget()
      await nextTick()

      const header = wrapper.findComponent(ChatWidgetHeaderStub)
      expect(header.props('title')).toBe('Mon analyse ESG')
    })
  })

  describe('WelcomeMessage (AC7)', () => {
    it('affiche WelcomeMessage quand aucun message', async () => {
      mockMessages.value = []
      const wrapper = await mountWidget()

      expect(wrapper.find('.welcome-message-stub').exists()).toBe(true)
      expect(wrapper.find('.chat-message-stub').exists()).toBe(false)
    })

    it('n\'affiche pas WelcomeMessage quand des messages existent', async () => {
      mockMessages.value = [{ id: '1', role: 'user', content: 'Bonjour' }]
      const wrapper = await mountWidget()

      expect(wrapper.find('.welcome-message-stub').exists()).toBe(false)
      expect(wrapper.find('.chat-message-stub').exists()).toBe(true)
    })
  })

  describe('ChatMessage (AC1, AC2, AC4)', () => {
    it('affiche ChatMessage pour chaque message', async () => {
      mockMessages.value = [
        { id: '1', role: 'user', content: 'Bonjour' },
        { id: '2', role: 'assistant', content: 'Bienvenue !' },
      ]
      const wrapper = await mountWidget()

      const chatMessages = wrapper.findAll('.chat-message-stub')
      expect(chatMessages).toHaveLength(2)
      expect(chatMessages[0].text()).toContain('Bonjour')
      expect(chatMessages[1].text()).toContain('Bienvenue !')
    })
  })

  describe('ChatInput (AC1, AC3)', () => {
    it('affiche ChatInput quand pas de question interactive pending', async () => {
      mockCurrentInteractiveQuestion.value = null
      const wrapper = await mountWidget()

      expect(wrapper.find('.chat-input-stub').exists()).toBe(true)
      expect(wrapper.find('.interactive-input-bar-stub').exists()).toBe(false)
    })

    it('affiche InteractiveQuestionInputBar quand question pending (AC3)', async () => {
      mockCurrentInteractiveQuestion.value = {
        id: 'q1',
        conversation_id: 'conv1',
        question_type: 'qcu',
        prompt: 'Quel secteur ?',
        options: [{ value: 'agriculture', label: 'Agriculture' }],
        min_selections: 1,
        max_selections: 1,
        requires_justification: false,
        justification_prompt: null,
        module: 'chat',
        created_at: new Date().toISOString(),
        state: 'pending',
        response_values: null,
        response_justification: null,
        answered_at: null,
      } as InteractiveQuestion
      const wrapper = await mountWidget()

      expect(wrapper.find('.interactive-input-bar-stub').exists()).toBe(true)
      expect(wrapper.find('.chat-input-stub').exists()).toBe(false)
    })
  })

  describe('ToolCallIndicator (AC5)', () => {
    it('affiche ToolCallIndicator quand activeToolCall est non null', async () => {
      mockActiveToolCall.value = { name: 'create_esg_assessment', args: {}, callId: 'tc1' }
      const wrapper = await mountWidget()

      expect(wrapper.find('.tool-call-indicator-stub').exists()).toBe(true)
      expect(wrapper.find('.tool-call-indicator-stub').text()).toContain('create_esg_assessment')
    })

    it('n\'affiche pas ToolCallIndicator quand activeToolCall est null', async () => {
      mockActiveToolCall.value = null
      const wrapper = await mountWidget()

      expect(wrapper.find('.tool-call-indicator-stub').exists()).toBe(false)
    })
  })

  describe('Erreur (AC1)', () => {
    it('affiche la banniere d\'erreur quand error est non null', async () => {
      mockError.value = 'Erreur de connexion'
      const wrapper = await mountWidget()

      const errorBanner = wrapper.find('.bg-red-50')
      expect(errorBanner.exists()).toBe(true)
      expect(errorBanner.text()).toBe('Erreur de connexion')
    })

    it('n\'affiche pas la banniere d\'erreur quand error est null', async () => {
      mockError.value = null
      const wrapper = await mountWidget()

      expect(wrapper.find('.bg-red-50').exists()).toBe(false)
    })
  })

  describe('Handlers (AC1, AC2, AC3)', () => {
    it('handleSend appelle sendMessage', async () => {
      mockCurrentConversation.value = { id: '1', title: 'Test', updated_at: new Date().toISOString() }
      const wrapper = await mountWidget()

      const chatInput = wrapper.findComponent(ChatInputStub)
      chatInput.vm.$emit('send', 'Mon message')
      await nextTick()
      await nextTick()

      expect(mockSendMessage).toHaveBeenCalledWith('Mon message')
    })

    it('handleSend cree une conversation si aucune n\'existe', async () => {
      mockCurrentConversation.value = null
      const wrapper = await mountWidget()

      const chatInput = wrapper.findComponent(ChatInputStub)
      chatInput.vm.$emit('send', 'Premier message')
      await nextTick()
      await nextTick()

      expect(mockCreateConversation).toHaveBeenCalled()
      expect(mockSelectConversation).toHaveBeenCalled()
    })

    it('handleSendWithFile appelle sendMessage avec fichier', async () => {
      mockCurrentConversation.value = { id: '1', title: 'Test', updated_at: new Date().toISOString() }
      const wrapper = await mountWidget()
      const file = new File(['content'], 'test.pdf', { type: 'application/pdf' })

      const chatInput = wrapper.findComponent(ChatInputStub)
      chatInput.vm.$emit('sendWithFile', 'Analyse ce doc', file)
      await nextTick()
      await nextTick()

      expect(mockSendMessage).toHaveBeenCalledWith('Analyse ce doc', file)
    })
  })

  describe('Auto-scroll (AC8)', () => {
    it('scrollToBottom est appele quand de nouveaux messages arrivent', async () => {
      const wrapper = await mountWidget()
      const uiStore = useUiStore()
      const scrollToMock = vi.fn()

      // Ouvrir le widget pour que isVisible = true (P7 guard)
      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      // Simuler le conteneur messages avec scrollTo
      const container = wrapper.find('[class*="overflow-y-auto"]')
      if (container.element) {
        container.element.scrollTo = scrollToMock
        Object.defineProperty(container.element, 'scrollHeight', { value: 1000, configurable: true })
      }

      // Ajouter un message
      mockMessages.value = [{ id: '1', role: 'user', content: 'Test' }]
      await nextTick()
      await nextTick()

      // Le watcher devrait avoir declenche scrollToBottom
      expect(scrollToMock).toHaveBeenCalled()
    })
  })

  describe('Dark mode (AC6)', () => {
    it('la zone messages a les variantes dark: appropriees', async () => {
      const wrapper = await mountWidget()
      const html = wrapper.html()

      expect(html).toContain('dark:bg-surface-dark-bg')
    })

    it('la banniere d\'erreur a les variantes dark: appropriees', async () => {
      mockError.value = 'Erreur test'
      const wrapper = await mountWidget()
      const html = wrapper.html()

      expect(html).toContain('dark:text-red-400')
      expect(html).toContain('dark:bg-red-900/20')
    })
  })

  describe('Fermeture via header (AC #4)', () => {
    it('appelle closeChatWidget quand le header emet close', async () => {
      const wrapper = await mountWidget()
      const uiStore = useUiStore()
      uiStore.chatWidgetOpen = true
      await nextTick()

      const closeButton = wrapper.find('button[aria-label="Fermer l\'assistant IA"]')
      expect(closeButton.exists()).toBe(true)

      await closeButton.trigger('click')
      expect(uiStore.chatWidgetOpen).toBe(false)
    })
  })

  describe('Navigation entre vues (AC #2, #3, #4)', () => {
    it('vue par defaut = chat (WelcomeMessage visible, ConversationList absente)', async () => {
      const wrapper = await mountWidget()

      expect(wrapper.find('.welcome-message-stub').exists()).toBe(true)
      expect(wrapper.find('.conversation-list-stub').exists()).toBe(false)
    })

    it('clic bouton historique → ConversationList s\'affiche', async () => {
      const wrapper = await mountWidget()

      const historyBtn = wrapper.find('button[aria-label="Historique des conversations"]')
      await historyBtn.trigger('click')
      await nextTick()

      expect(wrapper.find('.conversation-list-stub').exists()).toBe(true)
      expect(wrapper.find('.welcome-message-stub').exists()).toBe(false)
    })

    it('le header affiche "Conversations" en vue historique', async () => {
      const wrapper = await mountWidget()

      const historyBtn = wrapper.find('button[aria-label="Historique des conversations"]')
      await historyBtn.trigger('click')
      await nextTick()

      const header = wrapper.findComponent(ChatWidgetHeaderStub)
      expect(header.props('title')).toBe('Conversations')
      expect(header.props('showBackButton')).toBe(true)
    })

    it('fetchConversations est appele si la liste est vide au premier affichage historique', async () => {
      mockConversations.value = []
      const wrapper = await mountWidget()

      const historyBtn = wrapper.find('button[aria-label="Historique des conversations"]')
      await historyBtn.trigger('click')
      await nextTick()

      expect(mockFetchConversations).toHaveBeenCalledOnce()
    })

    it('fetchConversations n\'est pas appele si la liste contient deja des conversations', async () => {
      mockConversations.value = [{ id: '1', title: 'Conv 1', updated_at: new Date().toISOString() }]
      const wrapper = await mountWidget()

      const historyBtn = wrapper.find('button[aria-label="Historique des conversations"]')
      await historyBtn.trigger('click')
      await nextTick()

      expect(mockFetchConversations).not.toHaveBeenCalled()
    })

    it('selection conversation → retour a la vue chat', async () => {
      const conv = { id: '1', title: 'Test', updated_at: new Date().toISOString() }
      mockConversations.value = [conv]
      const wrapper = await mountWidget()

      // Aller dans l'historique
      const historyBtn = wrapper.find('button[aria-label="Historique des conversations"]')
      await historyBtn.trigger('click')
      await nextTick()

      // Simuler selection
      const list = wrapper.findComponent(ConversationListStub)
      list.vm.$emit('select', conv)
      await nextTick()
      await nextTick()

      expect(mockSelectConversation).toHaveBeenCalledWith(conv)
      expect(wrapper.find('.conversation-list-stub').exists()).toBe(false)
    })

    it('creation conversation → retour a la vue chat', async () => {
      const wrapper = await mountWidget()

      // Aller dans l'historique
      const historyBtn = wrapper.find('button[aria-label="Historique des conversations"]')
      await historyBtn.trigger('click')
      await nextTick()

      // Simuler creation
      const list = wrapper.findComponent(ConversationListStub)
      list.vm.$emit('create')
      await nextTick()
      await nextTick()
      await nextTick() // P4: attendre selectConversation async

      expect(mockCreateConversation).toHaveBeenCalled()
      expect(mockSelectConversation).toHaveBeenCalled() // P4: selectConversation appelee
      expect(wrapper.find('.conversation-list-stub').exists()).toBe(false)
    })

    it('bouton retour → revenir a la vue chat', async () => {
      const wrapper = await mountWidget()

      // Aller dans l'historique
      const historyBtn = wrapper.find('button[aria-label="Historique des conversations"]')
      await historyBtn.trigger('click')
      await nextTick()

      // Cliquer sur retour
      const backBtn = wrapper.find('button[aria-label="Retour à la conversation"]')
      await backBtn.trigger('click')
      await nextTick()

      expect(wrapper.find('.conversation-list-stub').exists()).toBe(false)
      expect(wrapper.find('.welcome-message-stub').exists()).toBe(true)
    })
  })

  describe('Glassmorphism et fallback (AC #3)', () => {
    it('le widget a la classe widget-glass pour le glassmorphism', async () => {
      const wrapper = await mountWidget()
      const widget = wrapper.find('.widget-glass')

      expect(widget.exists()).toBe(true)
    })
  })

  describe('prefers-reduced-motion (AC #6)', () => {
    it('utilise duration: 0 quand prefers-reduced-motion est actif', async () => {
      const originalMatchMedia = window.matchMedia
      window.matchMedia = vi.fn((query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        onchange: null,
        dispatchEvent: vi.fn(),
      })) as unknown as typeof window.matchMedia

      vi.resetModules()
      const { default: Component } = await import('~/components/copilot/FloatingChatWidget.vue')
      const wrapper = mount(Component, {
        global: {
          plugins: [pinia],
          stubs: {
            ChatWidgetHeader: ChatWidgetHeaderStub,
            ConversationList: ConversationListStub,
            WelcomeMessage: WelcomeMessageStub,
            ChatMessage: ChatMessageStub,
            ChatInput: ChatInputStub,
            ToolCallIndicator: ToolCallIndicatorStub,
            InteractiveQuestionInputBar: InteractiveQuestionInputBarStub,
          },
        },
      })
      const uiStore = useUiStore()

      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      expect(mockFromTo).toHaveBeenCalledWith(
        expect.any(Object),
        { scale: 0.8, opacity: 0, y: 20 },
        expect.objectContaining({ duration: 0 }),
      )

      window.matchMedia = originalMatchMedia
    })
  })

  describe('Resize du widget (Story 1.6)', () => {
    it('5.3 — les dimensions du widget refletent le store', async () => {
      // Definir un viewport assez grand pour eviter le clamp
      Object.defineProperty(window, 'innerWidth', { value: 1200, configurable: true })
      Object.defineProperty(window, 'innerHeight', { value: 900, configurable: true })

      const uiStore = useUiStore()
      uiStore.chatWidgetWidth = 500
      uiStore.chatWidgetHeight = 700
      const wrapper = await mountWidget()
      const widget = wrapper.find('.widget-glass')

      expect(widget.element.style.width).toBe('500px')
      expect(widget.element.style.height).toBe('700px')
    })

    it('5.4 — les poignees de resize sont presentes dans le DOM', async () => {
      const wrapper = await mountWidget()

      // 4 poignees : bord gauche, bord superieur, coin sup-gauche, coin sup-droit
      expect(wrapper.find('.cursor-ew-resize').exists()).toBe(true)
      expect(wrapper.find('.cursor-ns-resize').exists()).toBe(true)
      expect(wrapper.find('.cursor-nwse-resize').exists()).toBe(true)
      expect(wrapper.find('.cursor-nesw-resize').exists()).toBe(true)
    })

    it('5.5 — pointerdown + pointermove + pointerup modifie les dimensions', async () => {
      const uiStore = useUiStore()
      uiStore.chatWidgetWidth = 400
      uiStore.chatWidgetHeight = 600
      const wrapper = await mountWidget()

      // Ouvrir le widget pour que isVisible=true (F4 guard)
      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      const leftHandle = wrapper.find('.cursor-ew-resize')
      // Simuler pointerdown
      await leftHandle.trigger('pointerdown', {
        clientX: 100,
        clientY: 300,
        pointerId: 1,
        preventDefault: vi.fn(),
      })

      // Simuler pointermove via document
      const moveEvent = new PointerEvent('pointermove', {
        clientX: 50, // 50px vers la gauche = augmente la largeur de 50
        clientY: 300,
        pointerId: 1,
      })
      document.dispatchEvent(moveEvent)
      await nextTick()

      expect(uiStore.chatWidgetWidth).toBe(450) // 400 + (100 - 50) = 450

      // Simuler pointerup
      const upEvent = new PointerEvent('pointerup', {
        clientX: 50,
        clientY: 300,
        pointerId: 1,
      })
      document.dispatchEvent(upEvent)
      await nextTick()
    })

    it('5.6 — les dimensions sont clampees aux min/max', async () => {
      const uiStore = useUiStore()
      uiStore.chatWidgetWidth = 400
      uiStore.chatWidgetHeight = 600
      const wrapper = await mountWidget()

      // Ouvrir le widget pour que isVisible=true (F4 guard)
      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      const leftHandle = wrapper.find('.cursor-ew-resize')
      // Simuler un drag qui produirait une largeur inferieure au min (300)
      await leftHandle.trigger('pointerdown', {
        clientX: 100,
        clientY: 300,
        pointerId: 2,
        preventDefault: vi.fn(),
      })

      // Tirer vers la droite = reduire la largeur (deltaX negatif)
      const moveEvent = new PointerEvent('pointermove', {
        clientX: 300, // deltaX = 100 - 300 = -200, newWidth = 400 + (-200) = 200 < min 300
        clientY: 300,
        pointerId: 2,
      })
      document.dispatchEvent(moveEvent)
      await nextTick()

      expect(uiStore.chatWidgetWidth).toBe(300) // Clampe au min

      // Cleanup
      document.dispatchEvent(new PointerEvent('pointerup', { pointerId: 2 }))
    })

    it('5.7 — double-clic reset aux defauts', async () => {
      const uiStore = useUiStore()
      uiStore.chatWidgetWidth = 500
      uiStore.chatWidgetHeight = 700
      const wrapper = await mountWidget()

      const leftHandle = wrapper.find('.cursor-ew-resize')
      await leftHandle.trigger('dblclick')
      await nextTick()

      expect(uiStore.chatWidgetWidth).toBe(400)
      expect(uiStore.chatWidgetHeight).toBe(600)
    })

    it('5.9 — AC4 : pas de CSS transition sur width/height (pas de lag au resize)', async () => {
      const wrapper = await mountWidget()
      const widget = wrapper.find('.widget-glass')
      const style = widget.element.style

      // Verifier qu'aucune transition n'est definie sur les dimensions
      const transition = style.transition || style.getPropertyValue('transition') || ''
      expect(transition).not.toMatch(/width/)
      expect(transition).not.toMatch(/height/)
    })

    it('ajoute select-none pendant le resize', async () => {
      const uiStore = useUiStore()
      const wrapper = await mountWidget()

      // Ouvrir le widget pour que isVisible=true (F4 guard)
      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      const widget = wrapper.find('.widget-glass')

      // Avant resize : pas de select-none
      expect(widget.classes()).not.toContain('select-none')

      const leftHandle = wrapper.find('.cursor-ew-resize')
      await leftHandle.trigger('pointerdown', {
        clientX: 100,
        clientY: 300,
        pointerId: 3,
        preventDefault: vi.fn(),
      })
      await nextTick()

      // Pendant resize : select-none present
      expect(widget.classes()).toContain('select-none')

      // Cleanup
      document.dispatchEvent(new PointerEvent('pointerup', { pointerId: 3 }))
      await nextTick()

      // Apres resize : select-none retire
      expect(widget.classes()).not.toContain('select-none')
    })
  })

  describe('Accessibilite ARIA (Story 1.7)', () => {
    it('le widget porte role="dialog" et aria-label="Assistant IA ESG" (AC7)', async () => {
      const wrapper = await mountWidget()
      const widget = wrapper.find('[role="dialog"]')

      expect(widget.exists()).toBe(true)
      expect(widget.attributes('aria-label')).toBe('Assistant IA ESG')
      expect(widget.attributes('aria-modal')).toBe('true')
    })

    it('la zone messages porte aria-live="polite" (AC4)', async () => {
      mockMessages.value = [{ id: '1', role: 'assistant', content: 'Bonjour' }]
      const wrapper = await mountWidget()

      const liveRegion = wrapper.find('[aria-live="polite"]')
      expect(liveRegion.exists()).toBe(true)
      expect(liveRegion.attributes('aria-atomic')).toBe('false')
    })

    it('la region aria-live existe meme sans messages (F3 — premier message annonce)', async () => {
      mockMessages.value = []
      const wrapper = await mountWidget()

      const liveRegion = wrapper.find('[aria-live="polite"]')
      expect(liveRegion.exists()).toBe(true)
    })

    it('Escape ferme le widget (AC3)', async () => {
      const wrapper = await mountWidget()
      const uiStore = useUiStore()

      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      expect(uiStore.chatWidgetOpen).toBe(true)

      const widget = wrapper.find('[role="dialog"]')
      await widget.trigger('keydown', { key: 'Escape' })

      expect(uiStore.chatWidgetOpen).toBe(false)
    })

    it('le focus retourne au bouton flottant apres fermeture (AC3, D2)', async () => {
      // Creer un bouton flottant dans le DOM pour le test
      const floatingBtn = document.createElement('button')
      floatingBtn.setAttribute('data-testid', 'floating-chat-button')
      document.body.appendChild(floatingBtn)
      const focusSpy = vi.spyOn(floatingBtn, 'focus')

      const wrapper = await mountWidget()
      const uiStore = useUiStore()

      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      uiStore.chatWidgetOpen = false
      await nextTick()
      await nextTick()

      expect(focusSpy).toHaveBeenCalled()

      document.body.removeChild(floatingBtn)
    })

    it('AC2 : le premier focusable est dans le header, le dernier est dans le chat input (F5)', async () => {
      const wrapper = await mountWidget()
      const uiStore = useUiStore()

      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      const widget = wrapper.find('[role="dialog"]')
      const focusable = widget.element.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
      )

      expect(focusable.length).toBeGreaterThanOrEqual(2)

      // Premier focusable : dans le header (bouton historique ou fermer)
      const firstParent = focusable[0].closest('.chat-widget-header-stub')
      expect(firstParent).not.toBeNull()

      // Dernier focusable : dans le chat input
      const lastParent = focusable[focusable.length - 1].closest('.chat-input-stub')
      expect(lastParent).not.toBeNull()
    })
  })

  describe('GSAP animations (AC #2, #4, #6)', () => {
    it('appelle gsap.fromTo a l\'ouverture du widget', async () => {
      const wrapper = await mountWidget()
      const uiStore = useUiStore()

      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()

      expect(mockFromTo).toHaveBeenCalledWith(
        expect.any(Object),
        { scale: 0.8, opacity: 0, y: 20 },
        expect.objectContaining({
          scale: 1,
          opacity: 1,
          y: 0,
          duration: 0.25,
          ease: 'power2.out',
        }),
      )
    })

    it('appelle gsap.to a la fermeture du widget', async () => {
      const wrapper = await mountWidget()
      const uiStore = useUiStore()

      uiStore.chatWidgetOpen = true
      await nextTick()
      await nextTick()
      mockFromTo.mockClear()

      uiStore.chatWidgetOpen = false
      await nextTick()
      await nextTick()

      expect(mockTo).toHaveBeenCalledWith(
        expect.any(Object),
        expect.objectContaining({
          scale: 0.8,
          opacity: 0,
          y: 20,
          duration: 0.2,
          ease: 'power2.in',
        }),
      )
    })
  })
})

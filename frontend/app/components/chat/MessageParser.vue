<script setup lang="ts">
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { computed, defineAsyncComponent } from 'vue'
import { useMessageParser } from '~/composables/useMessageParser'
import type { ParsedSegment } from '~/types/richblocks'
import type { VisualizationBlock } from '~/composables/useChat'
import KPICardBlock from '~/components/richblocks/KPICardBlock.vue'
import MatchCardBlock from '~/components/richblocks/MatchCardBlock.vue'
import ComparisonTableBlock from '~/components/richblocks/ComparisonTableBlock.vue'

// F11 — MapBlock chargé en lazy-load (Leaflet ~150 KB ; sortir du bundle initial).
const MapBlock = defineAsyncComponent(
  () => import('~/components/richblocks/MapBlock.vue'),
)

const props = defineProps<{
  content: string
  isStreaming?: boolean
  visualizationBlocks?: VisualizationBlock[]
}>()

const emit = defineEmits<{
  navigate: [url: string]
  'open-source': [sourceId: string]
}>()

const { parse } = useMessageParser()

const segments = computed<ParsedSegment[]>(() => parse(props.content))

function renderMarkdown(text: string): string {
  const raw = marked.parse(text, { async: false }) as string
  return DOMPurify.sanitize(raw)
}

// Convertir un payload snake_case (Pydantic JSON) en camelCase (TS props).
// Money/objets Money sont préservés tels quels (champs `amount` + `currency`).
function toCamelCase(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(obj)) {
    const camelKey = k.replace(/_([a-z])/g, (_, c) => c.toUpperCase())
    if (Array.isArray(v)) {
      result[camelKey] = v.map((item) =>
        typeof item === 'object' && item !== null && !Array.isArray(item)
          ? toCamelCase(item as Record<string, unknown>)
          : item,
      )
    } else if (v && typeof v === 'object' && !Array.isArray(v)) {
      const inner = v as Record<string, unknown>
      const isMoney = 'amount' in inner && 'currency' in inner
      result[camelKey] = isMoney ? inner : toCamelCase(inner)
    } else {
      result[camelKey] = v
    }
  }
  return result
}

const camelBlocks = computed(() => {
  if (!props.visualizationBlocks) return []
  return props.visualizationBlocks.map((b) => ({
    blockType: b.blockType,
    componentProps: toCamelCase(b.payload),
  }))
})

function handleBlockNavigate(url: string) {
  emit('navigate', url)
}

function handleBlockOpenSource(sid: string) {
  emit('open-source', sid)
}
</script>

<template>
  <div class="message-parser">
    <template v-for="(segment, index) in segments" :key="index">
      <!-- Texte markdown -->
      <div
        v-if="segment.type === 'text'"
        class="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-2 prose-a:text-brand-blue prose-code:text-brand-green prose-code:bg-gray-100 dark:prose-code:bg-dark-card prose-code:px-1 prose-code:rounded"
        v-html="renderMarkdown(segment.content)"
      />

      <!-- Bloc incomplet pendant le streaming -->
      <BlockPlaceholder
        v-else-if="!segment.isComplete && isStreaming"
      />

      <!-- Blocs visuels complets ou incomplets post-streaming (fallback markdown) -->
      <ChartBlock
        v-else-if="segment.type === 'chart'"
        :raw-content="segment.content"
      />
      <MermaidBlock
        v-else-if="segment.type === 'mermaid'"
        :raw-content="segment.content"
      />
      <TableBlock
        v-else-if="segment.type === 'table'"
        :raw-content="segment.content"
      />
      <GaugeBlock
        v-else-if="segment.type === 'gauge'"
        :raw-content="segment.content"
      />
      <ProgressBlock
        v-else-if="segment.type === 'progress'"
        :raw-content="segment.content"
      />
      <TimelineBlock
        v-else-if="segment.type === 'timeline'"
        :raw-content="segment.content"
      />
    </template>

    <!-- F11 — Blocs de visualisation typés (KPICard, MatchCard, Map, ComparisonTable) -->
    <template v-for="(block, idx) in camelBlocks" :key="`viz-${idx}`">
      <KPICardBlock
        v-if="block.blockType === 'show_kpi_card'"
        v-bind="block.componentProps"
        @navigate="handleBlockNavigate"
        @open-source="handleBlockOpenSource"
      />
      <MatchCardBlock
        v-else-if="block.blockType === 'show_match_card'"
        v-bind="block.componentProps"
        @navigate="handleBlockNavigate"
      />
      <ComparisonTableBlock
        v-else-if="block.blockType === 'show_comparison_table'"
        v-bind="block.componentProps"
        @navigate="handleBlockNavigate"
        @open-source="handleBlockOpenSource"
      />
      <MapBlock
        v-else-if="block.blockType === 'show_map'"
        v-bind="block.componentProps"
        @navigate="handleBlockNavigate"
      />
    </template>
  </div>
</template>

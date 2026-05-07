<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import AttestationStatusBadge from '~/components/attestations/AttestationStatusBadge.vue'
import HashCompareInput from '~/components/attestations/HashCompareInput.vue'
import { useAttestations } from '~/composables/useAttestations'
import { detectLocale, VERIFY_MESSAGES } from '~/i18n/verify'
import type {
  AttestationStatus,
  VerificationResult,
} from '~/types/attestation'

definePageMeta({
  layout: 'public',
  // Pas d'authentification requise (le middleware auth.global.ts excepte /verify/*).
})

const route = useRoute()
const id = (route.params.id as string) || ''
const queryLang = (route.query.lang as string) || ''
const locale = detectLocale(null, queryLang)
const t = VERIFY_MESSAGES[locale]

const result = ref<VerificationResult | null>(null)
const loadingPage = ref(true)
const errorMsg = ref('')

const { verifyPublic } = useAttestations()

const status = computed<AttestationStatus | null>(() =>
  result.value ? result.value.status : null,
)

const showAuthenticDetails = computed(
  () =>
    !!result.value &&
    (result.value.status === 'authentic' ||
      result.value.status === 'revoked' ||
      result.value.status === 'expired'),
)

function fmtDate(s: string | undefined | null): string {
  if (!s) return ''
  return new Date(s).toLocaleString(locale === 'en' ? 'en-US' : 'fr-FR', {
    dateStyle: 'long',
    timeStyle: 'short',
  })
}

const typeLabels: Record<string, string> = {
  credit_score: locale === 'en' ? 'Credit score' : 'Score de crédit',
  esg_assessment: locale === 'en' ? 'ESG assessment' : 'Évaluation ESG',
  combined: locale === 'en' ? 'Combined' : 'Combinée (crédit + ESG)',
}

async function load() {
  loadingPage.value = true
  errorMsg.value = ''
  try {
    const r = await verifyPublic(id)
    if (r === null) {
      errorMsg.value = locale === 'en' ? 'Network error' : 'Erreur réseau'
    } else {
      result.value = r
    }
  } catch (e) {
    errorMsg.value = (e as Error).message || 'Erreur'
  } finally {
    loadingPage.value = false
  }
}

onMounted(load)

// Cast helper pour discriminated union (TypeScript)
const authentic = computed(() =>
  result.value && result.value.status === 'authentic' ? result.value : null,
)
const revoked = computed(() =>
  result.value && result.value.status === 'revoked' ? result.value : null,
)
const expired = computed(() =>
  result.value && result.value.status === 'expired' ? result.value : null,
)
</script>

<template>
  <div class="max-w-3xl mx-auto px-4 py-6 sm:py-10">
    <h1 class="sr-only">{{ t.page_title }}</h1>

    <div v-if="loadingPage" class="text-center py-12">
      <p class="text-gray-600">{{ t.loading }}</p>
    </div>

    <div v-else-if="errorMsg" class="bg-rose-50 border border-rose-200 rounded-md p-4">
      <p class="text-rose-700">{{ errorMsg }}</p>
    </div>

    <div v-else-if="result" class="space-y-6">
      <!-- Badge statut -->
      <div class="text-center">
        <AttestationStatusBadge v-if="status" :status="status" size="lg" />
        <p class="mt-3 text-base text-gray-700">
          <template v-if="status === 'authentic'">
            {{ t.status_authentic_description }}
          </template>
          <template v-else-if="status === 'revoked'">
            {{ t.status_revoked_description }}
          </template>
          <template v-else-if="status === 'expired'">
            {{ t.status_expired_description }}
          </template>
          <template v-else>
            {{ t.status_invalid_description }}
          </template>
        </p>
      </div>

      <!-- Détails si statut autre que invalid -->
      <div
        v-if="showAuthenticDetails && (authentic || revoked || expired)"
        class="bg-white border border-gray-200 rounded-lg p-4 sm:p-6 space-y-4"
      >
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <div>
            <dt class="text-gray-500 text-xs uppercase tracking-wider">
              {{ t.attestation_id_label }}
            </dt>
            <dd class="font-mono text-gray-900 break-all">
              {{ (authentic || revoked || expired)?.display_id }}
            </dd>
          </div>
          <div>
            <dt class="text-gray-500 text-xs uppercase tracking-wider">
              {{ t.type_label }}
            </dt>
            <dd class="text-gray-900">
              {{
                typeLabels[(authentic || revoked || expired)?.attestation_type || '']
              }}
            </dd>
          </div>
        </div>

        <!-- Scores -->
        <div
          v-if="
            (authentic || revoked || expired)?.scores &&
              Object.keys((authentic || revoked || expired)!.scores).length
          "
        >
          <h3 class="text-sm font-semibold text-gray-700 mb-2">
            {{ t.scores_label }}
          </h3>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div
              v-for="(value, key) in (authentic || revoked || expired)!.scores"
              :key="key"
              class="bg-emerald-50 border border-emerald-200 rounded p-2 text-center"
            >
              <div class="text-2xl font-bold text-emerald-700">{{ value }}</div>
              <div class="text-[10px] text-gray-600 uppercase tracking-wider">
                {{ key }}
              </div>
            </div>
          </div>
        </div>

        <!-- Référentiels -->
        <div
          v-if="(authentic || revoked || expired)?.referentials?.length"
        >
          <h3 class="text-sm font-semibold text-gray-700 mb-2">
            {{ t.referentials_label }}
          </h3>
          <ul class="text-sm text-gray-700 list-disc pl-5 space-y-1">
            <li
              v-for="(ref, idx) in (authentic || revoked || expired)!.referentials"
              :key="idx"
            >
              <span class="font-medium">{{ ref.name }}</span>
              <span v-if="ref.version"> v{{ ref.version }}</span>
              <span v-if="ref.published_at" class="text-gray-500">
                ({{ ref.published_at }})</span>
            </li>
          </ul>
        </div>

        <!-- Validité -->
        <div class="text-sm border-t border-gray-100 pt-3">
          <dt class="text-gray-500 text-xs uppercase tracking-wider">
            {{ t.validity_label }}
          </dt>
          <dd class="text-gray-900">
            {{ fmtDate((authentic || revoked || expired)?.valid_from) }}
            →
            {{ fmtDate((authentic || revoked || expired)?.valid_until) }}
          </dd>
        </div>

        <!-- Détails révocation -->
        <div
          v-if="revoked"
          class="bg-rose-50 border border-rose-200 rounded p-3 space-y-1 text-sm"
        >
          <p>
            <strong>{{ t.revoked_at_label }} :</strong>
            {{ fmtDate(revoked.revoked_at) }}
          </p>
          <p>
            <strong>{{ t.revoked_reason_label }} :</strong>
            {{ revoked.revoked_reason }}
          </p>
          <p>
            <strong>{{ t.revoked_by_label }} :</strong>
            {{
              revoked.revoked_by_role === 'admin'
                ? t.revoked_by_admin
                : t.revoked_by_pme
            }}
          </p>
        </div>

        <!-- Détails expiration -->
        <div
          v-if="expired"
          class="bg-amber-50 border border-amber-200 rounded p-3 text-sm"
        >
          <p>
            <strong>{{ t.expired_since_label }} :</strong>
            {{ fmtDate(expired.expired_since) }}
          </p>
        </div>

        <!-- Hash + comparaison -->
        <div class="border-t border-gray-100 pt-3 space-y-2">
          <dt class="text-gray-500 text-xs uppercase tracking-wider">
            {{ t.hash_label }}
          </dt>
          <dd class="font-mono text-xs sm:text-sm text-gray-700 break-all">
            {{ (authentic || revoked || expired)?.pdf_hash_sha256 }}
          </dd>
          <p class="text-[10px] text-gray-500 italic">
            {{ t.public_key_label }}:
            <code>{{ (authentic || revoked || expired)?.public_key_id }}</code>
          </p>

          <HashCompareInput
            class="mt-3"
            :expected="(authentic || revoked || expired)!.pdf_hash_sha256"
            :match-message="t.hash_match_message"
            :mismatch-message="t.hash_mismatch_message"
            :button-label="t.hash_compare_button"
            :placeholder="t.hash_compare_placeholder"
          >
            <template #title>{{ t.hash_compare_title }}</template>
          </HashCompareInput>
        </div>
      </div>
    </div>
  </div>
</template>

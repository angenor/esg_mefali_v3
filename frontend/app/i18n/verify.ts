/**
 * I18n FR/EN pour la page publique /verify/[id] (F08).
 *
 * Détection : Accept-Language ou ?lang=en (priorité query string).
 */

export type Locale = 'fr' | 'en'

export interface VerifyMessages {
  page_title: string
  loading: string
  status_authentic_label: string
  status_revoked_label: string
  status_expired_label: string
  status_invalid_label: string
  status_authentic_description: string
  status_revoked_description: string
  status_expired_description: string
  status_invalid_description: string
  attestation_id_label: string
  type_label: string
  scores_label: string
  referentials_label: string
  validity_label: string
  hash_label: string
  public_key_label: string
  hash_compare_title: string
  hash_compare_placeholder: string
  hash_compare_button: string
  hash_match_message: string
  hash_mismatch_message: string
  copy_id_label: string
  copy_url_label: string
  expires_in_label: string
  revoked_at_label: string
  revoked_reason_label: string
  revoked_by_label: string
  revoked_by_pme: string
  revoked_by_admin: string
  expired_since_label: string
  footer_brand: string
  footer_legal: string
}

const FR: VerifyMessages = {
  page_title: 'Vérification d\'attestation',
  loading: 'Chargement de l\'attestation…',
  status_authentic_label: 'AUTHENTIQUE',
  status_revoked_label: 'RÉVOQUÉE',
  status_expired_label: 'EXPIRÉE',
  status_invalid_label: 'INVALIDE',
  status_authentic_description:
    'Cette attestation est authentique et signée numériquement par ESG Mefali.',
  status_revoked_description:
    'Cette attestation a été révoquée et n\'est plus valide.',
  status_expired_description:
    'Cette attestation a expiré. Demandez à l\'entreprise une nouvelle attestation.',
  status_invalid_description:
    'Cet identifiant d\'attestation n\'existe pas ou la signature est invalide.',
  attestation_id_label: 'Identifiant',
  type_label: 'Type',
  scores_label: 'Scores certifiés',
  referentials_label: 'Référentiels appliqués',
  validity_label: 'Validité',
  hash_label: 'Hash SHA-256 du PDF',
  public_key_label: 'Clé publique',
  hash_compare_title: 'Comparer avec votre PDF',
  hash_compare_placeholder: 'Collez ici le hash imprimé en pied de page de votre PDF',
  hash_compare_button: 'Comparer',
  hash_match_message: 'Hash conforme — le PDF n\'a pas été altéré.',
  hash_mismatch_message: 'Hash non conforme — le PDF reçu diffère de l\'original.',
  copy_id_label: 'Copier l\'identifiant',
  copy_url_label: 'Copier l\'URL de vérification',
  expires_in_label: 'Expire le',
  revoked_at_label: 'Révoquée le',
  revoked_reason_label: 'Raison',
  revoked_by_label: 'Révoquée par',
  revoked_by_pme: 'l\'entreprise',
  revoked_by_admin: 'un administrateur ESG Mefali',
  expired_since_label: 'Expirée depuis le',
  footer_brand: 'ESG Mefali — Plateforme de finance durable',
  footer_legal: 'Mentions légales',
}

const EN: VerifyMessages = {
  page_title: 'Attestation Verification',
  loading: 'Loading attestation…',
  status_authentic_label: 'AUTHENTIC',
  status_revoked_label: 'REVOKED',
  status_expired_label: 'EXPIRED',
  status_invalid_label: 'INVALID',
  status_authentic_description:
    'This attestation is authentic and digitally signed by ESG Mefali.',
  status_revoked_description:
    'This attestation has been revoked and is no longer valid.',
  status_expired_description:
    'This attestation has expired. Ask the company for a new attestation.',
  status_invalid_description:
    'This attestation identifier does not exist or its signature is invalid.',
  attestation_id_label: 'Identifier',
  type_label: 'Type',
  scores_label: 'Certified scores',
  referentials_label: 'Applied referentials',
  validity_label: 'Validity',
  hash_label: 'PDF SHA-256 hash',
  public_key_label: 'Public key',
  hash_compare_title: 'Compare with your PDF',
  hash_compare_placeholder: 'Paste here the hash printed on your PDF',
  hash_compare_button: 'Compare',
  hash_match_message: 'Hashes match — the PDF was not altered.',
  hash_mismatch_message: 'Hash mismatch — the received PDF differs from the original.',
  copy_id_label: 'Copy identifier',
  copy_url_label: 'Copy verification URL',
  expires_in_label: 'Expires on',
  revoked_at_label: 'Revoked on',
  revoked_reason_label: 'Reason',
  revoked_by_label: 'Revoked by',
  revoked_by_pme: 'the company',
  revoked_by_admin: 'an ESG Mefali administrator',
  expired_since_label: 'Expired since',
  footer_brand: 'ESG Mefali — Sustainable finance platform',
  footer_legal: 'Legal',
}

export const VERIFY_MESSAGES: Record<Locale, VerifyMessages> = {
  fr: FR,
  en: EN,
}

export function detectLocale(
  acceptLanguage: string | null = null,
  queryLang: string | null = null,
): Locale {
  if (queryLang === 'en' || queryLang === 'fr') {
    return queryLang
  }
  const lang = (acceptLanguage || '').toLowerCase()
  if (lang.startsWith('en')) return 'en'
  return 'fr'
}

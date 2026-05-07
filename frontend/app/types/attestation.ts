/**
 * Types TypeScript pour les attestations vérifiables (F08).
 */

export type AttestationType = 'credit_score' | 'esg_assessment' | 'combined'
export type AttestationStatus = 'authentic' | 'revoked' | 'expired' | 'invalid'
export type RevokerRole = 'pme' | 'admin'

/** Résumé d'attestation (liste). */
export interface AttestationSummary {
  id: string
  display_id: string
  attestation_type: AttestationType
  valid_from: string
  valid_until: string
  revoked_at: string | null
  revoked_reason: string | null
  verification_url: string
  pdf_hash_sha256: string
  public_key_id: string
  created_at: string
  account_id?: string
  user_id?: string
}

/** Détail d'attestation (avec payload + référentiels). */
export interface AttestationRead extends AttestationSummary {
  payload: Record<string, unknown>
  referential_snapshot: Array<Record<string, unknown>>
}

// ----------------------------------------------------------------------
// Verification Result — Discriminated union par status
// ----------------------------------------------------------------------

interface VerificationBase {
  verified_at: string
  message: string
}

export interface AuthenticVerification extends VerificationBase {
  status: 'authentic'
  attestation_id: string
  display_id: string
  attestation_type: AttestationType
  valid_from: string
  valid_until: string
  issued_at: string
  scores: Record<string, number>
  referentials: Array<Record<string, unknown>>
  pdf_hash_sha256: string
  public_key_id: string
}

export interface RevokedVerification extends VerificationBase {
  status: 'revoked'
  attestation_id: string
  display_id: string
  attestation_type: AttestationType
  valid_from: string
  valid_until: string
  issued_at: string
  scores: Record<string, number>
  referentials: Array<Record<string, unknown>>
  pdf_hash_sha256: string
  public_key_id: string
  revoked_at: string
  revoked_reason: string
  revoked_by_role: RevokerRole
}

export interface ExpiredVerification extends VerificationBase {
  status: 'expired'
  attestation_id: string
  display_id: string
  attestation_type: AttestationType
  valid_from: string
  valid_until: string
  issued_at: string
  scores: Record<string, number>
  referentials: Array<Record<string, unknown>>
  pdf_hash_sha256: string
  public_key_id: string
  expired_since: string
}

export interface InvalidVerification extends VerificationBase {
  status: 'invalid'
}

export type VerificationResult =
  | AuthenticVerification
  | RevokedVerification
  | ExpiredVerification
  | InvalidVerification

/** Réponse de l'endpoint clé publique. */
export interface PublicKeyResponse {
  public_key_id: string
  algorithm: 'ed25519'
  public_key_pem: string
  canonical_format_doc_url: string
  issued_at: string
}

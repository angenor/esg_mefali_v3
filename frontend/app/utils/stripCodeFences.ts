/**
 * Retire les fences markdown (```html … ```) d'un contenu généré par LLM.
 *
 * Le LLM enveloppe parfois le HTML d'une section de dossier dans un bloc de
 * code ` ```html … ``` `, qui s'afficherait alors littéralement (les marqueurs
 * ```html / ``` visibles) via `v-html` ou dans l'éditeur. Ce helper retire un
 * bloc englobant complet, ou des fences orphelines en début/fin. Idempotent.
 *
 * Le correctif principal est côté backend (génération + export) ; cette
 * fonction protège l'affichage du contenu déjà stocké avec des fences.
 */
const WRAP_RE = /^```[a-zA-Z0-9_-]*[ \t]*\r?\n?([\s\S]*?)\r?\n?```$/

export function stripCodeFences(content: string | null | undefined): string {
  if (!content) return ''
  const trimmed = content.trim()
  const wrapped = trimmed.match(WRAP_RE)
  if (wrapped) return wrapped[1].trim()
  // Fences orphelines (ouverture ou fermeture seule).
  return trimmed
    .replace(/^```[a-zA-Z0-9_-]*[ \t]*\r?\n?/, '')
    .replace(/\r?\n?```[ \t]*$/, '')
    .trim()
}

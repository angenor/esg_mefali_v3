# Contract — POST /api/extension/v1/detect

**Auth** : Bearer token extension requis

## Request

```http
POST /api/extension/v1/detect HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: application/json
Origin: chrome-extension://<extension-id>

{
  "url": "https://sunref.boad.org/programme/page-x"
}
```

## Response 200 (match)

```json
{
  "offer_id": "uuid-offer",
  "offer_name": "SUNREF Ecobank — Programme efficacité énergétique",
  "source_id": "uuid-source",
  "confidence": 1.0
}
```

- `offer_id` : identifiant de l'offre F07 correspondante (couple Fonds × Intermédiaire)
- `offer_name` : nom complet pour affichage bandeau
- `source_id` : identifiant de la source F01 (peut être null si offre sans source rattachée)
- `confidence` : score de matching, ∈ [0.0, 1.0]. MVP : 1.0 si un seul pattern matche, 1.0 si plusieurs patterns matchent (déterministe). Seuil minimal côté serveur = 0.8 (FR-009).

## Response 204 (no match)

Aucun body. Aucun pattern publié ne matche l'URL fournie.

## Errors

- **401 Unauthorized** : token invalide
- **422 Unprocessable Entity** : URL malformée (regex `^https?://`)

## Logique serveur

1. Récupérer toutes les `offers.publication_status='published'`
2. Pour chaque offre, charger `fund.url_patterns` ∪ `intermediary.url_patterns`
3. Tester chaque pattern compilé contre `request.url`
4. Si match : ajouter offre à liste candidate
5. Si plusieurs candidates : prioriser celles dont `intermediary.code='DIRECT'` ; sinon, première par `offer.created_at` croissant (déterministe)
6. Si confidence ≥ 0.8 : renvoyer 200, sinon 204
7. Cache mémoire en process (LRU 500 entrées TTL 5 min) sur la liste compilée des patterns pour éviter recompilation

## Side effects

- Audit log entry `source_of_change='extension'`, `action='view'`, `entity_type='offer'` si match

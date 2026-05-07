# Contract — Événements SSE étendus

**Date** : 2026-05-07
**Phase** : 1

## Marker SSE backend (string retournée par le tool)

Pattern conservé F18 :
```
"Question posée à l'utilisateur.\n\n<!--SSE:{...JSON serialisé...}-->"
```

## Forme JSON du marker SSE

### Existant F18 (inchangé)

```json
{
  "__sse_interactive_question__": true,
  "type": "interactive_question",
  "id": "uuid",
  "conversation_id": "uuid",
  "question_type": "qcu" | "qcm" | "qcu_justification" | "qcm_justification",
  "prompt": "...",
  "options": [...],
  "min_selections": 1,
  "max_selections": 1,
  "requires_justification": false,
  "justification_prompt": null,
  "module": "esg_scoring",
  "created_at": "2026-05-07T..."
}
```

### Étendu F10 (nouveau)

Pour les 9 nouveaux types, le marker SSE inclut les champs spécifiques via la clé `payload` :

```json
{
  "__sse_interactive_question__": true,
  "type": "interactive_question",
  "id": "uuid",
  "conversation_id": "uuid",
  "question_type": "yes_no" | "select" | "number" | "date" | "date_range" | "rating" | "file_upload" | "form" | "summary_card",
  "prompt": "...",
  "module": "chat",
  "created_at": "2026-05-07T...",
  "payload": {
    // Forme variante-specific (cf. widget_payloads.md)
    "question_type": "yes_no",
    "confirm_label": "Oui, supprimer",
    "deny_label": "Non, annuler",
    "destructive": true
  }
}
```

Notes :
- Pour les types F18 (`qcu`, ...), `payload` n'est PAS présent (rétro-compat). Le frontend reconnaît les 4 types historiques et utilise les champs racine (`options`, `min_selections`, etc.).
- Pour les 9 nouveaux types, `payload` est obligatoire et contient toutes les paramètres spécifiques.
- `module` indique le nœud LangGraph d'origine (chat, esg_scoring, carbon, financing, application, credit, action_plan, document, profiling).

## Événement frontend (étendu)

Le composable `useChat.ts` intercepte le marker SSE via `stream_graph_events` et émet un événement `interactive_question` :

```typescript
type InteractiveQuestionEvent = {
  type: "interactive_question"
  id: string
  conversation_id: string
  question_type: InteractiveQuestionType  // 13 valeurs (4 F18 + 9 F10)
  prompt: string
  module: string
  created_at: string
  // Champs F18 conservés pour rétro-compat
  options?: SelectOption[]
  min_selections?: number
  max_selections?: number
  requires_justification?: boolean
  justification_prompt?: string | null
  // Nouveau F10
  payload?: InteractiveQuestionPayload  // Union TypeScript discriminée
}
```

## Événement de résolution (existant F18, étendu)

`interactive_question_resolved` est émis quand une question passe en `answered`/`abandoned`/`expired`. F10 ajoute `response_payload` au payload :

```json
{
  "type": "interactive_question_resolved",
  "id": "uuid",
  "state": "answered" | "abandoned" | "expired",
  "answered_at": "2026-05-07T...",
  "response_payload": {
    // Forme variante-specific (cf. widget_responses.md)
  }
}
```

## API REST étendue

### Existant F18 (étendu)

`POST /api/chat/messages` accepte 3 nouveaux champs F18 :
- `interactive_question_id: UUID | null`
- `interactive_question_values: list[str] | null`
- `interactive_question_justification: str | null` (max 400)

F10 étend avec :
- `interactive_question_response_payload: dict | null` — payload structuré conforme au schéma `InteractiveQuestionResponse` discriminé.

Exemple POST avec `ask_yes_no` destructif :
```json
{
  "conversation_id": "uuid",
  "content": "✓ Oui, supprimer",
  "interactive_question_id": "uuid",
  "interactive_question_response_payload": {
    "question_type": "yes_no",
    "value": true,
    "label": "Oui, supprimer"
  }
}
```

Exemple POST avec `show_form` :
```json
{
  "conversation_id": "uuid",
  "content": "✓ Projet créé : Panneaux solaires PME, 5 000 000 FCFA, énergie",
  "interactive_question_id": "uuid",
  "interactive_question_response_payload": {
    "question_type": "form",
    "values": {
      "project_name": "Panneaux solaires PME",
      "target_amount": 5000000,
      ...
    },
    "summary_label": "Projet créé : Panneaux solaires PME, 5 000 000 FCFA, énergie"
  }
}
```

### Existant F18 (inchangé)

- `POST /api/chat/interactive-questions/{id}/abandon` — marque `abandoned`.
- `GET /api/chat/conversations/{id}/interactive-questions` — liste les questions.

## Compatibilité ascendante

Les clients F18 (frontend non-mis-à-jour) :
- Reçoivent les événements SSE des nouveaux types mais ne savent pas les parser → fallback `UnsupportedWidget.vue` les rend en textarea (FR-026).
- Ne peuvent pas envoyer `interactive_question_response_payload` → l'API accepte un POST sans ce champ (rétro-compat).

Les clients F10 :
- Parsent les types F18 via la logique existante.
- Parsent les types F10 via le dispatcher.
- Peuvent toujours utiliser le bouton « Répondre librement » qui passe par la voie texte standard.

# Endpoint REST — `GET /api/admin/metrics/validation-failures`

## Description

Retourne l'agrégation des échecs de validation des tools LLM sur la période demandée.

## Authentification

Header `Authorization: Bearer <jwt>`. La dépendance FastAPI `require_admin_role` (F02) vérifie que l'utilisateur a le rôle `admin`.

## Request

`GET /api/admin/metrics/validation-failures?period=7d&limit=10`

| Param | Type | Default | Valeurs | Description |
|-------|------|---------|---------|-------------|
| `period` | `string` | `"7d"` | `"24h" \| "7d" \| "30d"` | Période d'agrégation |
| `limit` | `integer` | `10` | `1-50` | Top N tools concernés |

## Response 200

```json
{
  "period": "7d",
  "from_iso": "2026-04-30T00:00:00Z",
  "to_iso": "2026-05-07T00:00:00Z",
  "total_calls": 12345,
  "failure_count": 234,
  "failure_rate": 0.019,
  "top_tools": [
    {
      "tool_name": "batch_save_esg_criteria",
      "count": 89,
      "rate": 0.038
    },
    {
      "tool_name": "create_fund_application",
      "count": 45,
      "rate": 0.022
    }
  ],
  "alert": false,
  "alert_threshold": 0.05
}
```

### Champs

| Champ | Type | Description |
|-------|------|-------------|
| `period` | `string` | Période demandée (echo) |
| `from_iso` | `datetime` | Début de la fenêtre (ISO8601) |
| `to_iso` | `datetime` | Fin de la fenêtre (ISO8601, = now) |
| `total_calls` | `integer` | Nombre total d'appels tools sur la période |
| `failure_count` | `integer` | Nombre d'appels avec `validation_error IS NOT NULL` |
| `failure_rate` | `number` | `failure_count / total_calls` |
| `top_tools` | `array` | Top N tools par nombre d'échecs (desc) |
| `top_tools[].tool_name` | `string` | Nom du tool |
| `top_tools[].count` | `integer` | Nombre d'échecs pour ce tool |
| `top_tools[].rate` | `number` | `count / total_calls_of_this_tool` |
| `alert` | `boolean` | `true` si `failure_rate > alert_threshold` |
| `alert_threshold` | `number` | Seuil par défaut `0.05` |

## Response 403 (non-admin)

```json
{
  "detail": "Admin role required"
}
```

## Response 422 (params invalides)

```json
{
  "detail": [
    {
      "loc": ["query", "period"],
      "msg": "value is not a valid enumeration member; permitted: '24h', '7d', '30d'",
      "type": "type_error.enum"
    }
  ]
}
```

## Performance

- Temps de réponse < 500ms P95 sur `tool_call_logs` jusqu'à 100k rows.
- Index utilisé : `idx_tool_call_logs_created_at_status` (déjà existant) + filtre `WHERE validation_error IS NOT NULL`.

## SQL implémenté (extrait)

```sql
SELECT
  COUNT(*) FILTER (WHERE validation_error IS NOT NULL) AS failure_count,
  COUNT(*) AS total_calls,
  (COUNT(*) FILTER (WHERE validation_error IS NOT NULL)::float / NULLIF(COUNT(*), 0)) AS failure_rate
FROM tool_call_logs
WHERE created_at >= :from_iso AND created_at < :to_iso;

-- Top tools
SELECT
  tool_name,
  COUNT(*) FILTER (WHERE validation_error IS NOT NULL) AS count,
  (COUNT(*) FILTER (WHERE validation_error IS NOT NULL)::float / NULLIF(COUNT(*), 0)) AS rate
FROM tool_call_logs
WHERE created_at >= :from_iso AND created_at < :to_iso
GROUP BY tool_name
HAVING COUNT(*) FILTER (WHERE validation_error IS NOT NULL) > 0
ORDER BY count DESC
LIMIT :limit;
```

## Garde-fous

- L'endpoint NE retourne PAS le contenu brut de `validation_error` (peut contenir des données sensibles via `input` Pydantic). Seuls les agrégats sont exposés.
- Pas de pagination — toujours un seul appel.
- Si `total_calls == 0` → `failure_rate = 0.0`, `top_tools = []`, `alert = false`.

# Tools LangChain — F07

**Fichier d'extension** : `backend/app/graph/tools/financing_tools.py`
**Tools nouveaux** : 3 (`list_offers`, `get_offer`, `compare_offers_for_fund`)
**Tool étendu** : 1 (`create_fund_application` accepte désormais `offer_id`)

Tous les tools sont **read-only** sur le catalogue (offers, funds, intermediaries) — aucun ne peut muter (invariant n°7).
Le tool `create_fund_application` mute la table `fund_applications` (table métier multi-tenant), pas le catalogue.

## 1. `list_offers`

### Schéma Pydantic Args

```python
from typing import Literal
from pydantic import BaseModel, Field


class ListOffersInput(BaseModel):
    """Filtres pour lister les offres de financement vert."""
    fund_id: str | None = Field(None, description="UUID du fonds (filtre exact)")
    intermediary_id: str | None = Field(None, description="UUID de l'intermédiaire")
    theme: Literal["mitigation", "adaptation", "biodiversity", "circular_economy", "mixed"] | None = Field(
        None, description="Thème climat (au moins une correspondance)"
    )
    instrument: Literal["subvention", "pret_concessionnel", "garantie", "equity", "blending"] | None = Field(
        None, description="Type d'instrument financier"
    )
    country: str | None = Field(None, description="Pays de l'intermédiaire (ex : 'CI', 'SN')")
    language: Literal["FR", "EN"] | None = Field(None, description="Langue acceptée du dossier")
    sort: Literal["success_rate", "processing_time"] = Field("success_rate", description="Tri")
    limit: int = Field(20, ge=1, le=50, description="Nombre max résultats")
```

### Description LangChain (français)

> Liste les offres de financement vert disponibles pour les PME africaines. Une offre = couple (Fonds, Intermédiaire) avec critères, documents et frais cumulés. Filtre optionnellement par fonds, intermédiaire, thème climat (mitigation/adaptation/biodiversité/économie circulaire), instrument financier, pays de l'intermédiaire, ou langue acceptée. Retourne au maximum 20 offres par défaut, triées par taux de succès historique. Utilisez ce tool pour aider une PME à explorer les financements.

### Sortie

```python
class OfferSummary(BaseModel):
    id: str
    name: str
    fund_name: str
    fund_organization: str
    intermediary_name: str
    intermediary_country: str
    accepted_languages: list[str]
    effective_fees_summary: str  # ex : "Frais cumulés ~2 550 000 XOF (0.5%-2.5%)"
    effective_processing_time_summary: str  # ex : "630 à 720 jours (~21-24 mois)"
    success_rate: float | None
```

## 2. `get_offer`

### Schéma Args

```python
class GetOfferInput(BaseModel):
    offer_id: str = Field(..., description="UUID de l'offre")
```

### Description LangChain

> Récupère le détail complet d'une offre de financement vert : fonds source, intermédiaire, critères effectifs (intersection fonds+intermédiaire), documents requis (union dédupliquée), frais effectifs (Money typed), délais effectifs, langues acceptées, taux de succès. Utilisez ce tool quand une PME veut consulter une offre spécifique.

### Sortie

```python
class OfferDetail(BaseModel):
    id: str
    name: str
    fund: dict  # FundSummary
    intermediary: dict  # IntermediarySummary
    accepted_languages: list[str]
    target_sector: list[str] | None
    effective_criteria: dict
    effective_required_documents: list[dict]  # [{title, source_id, mandatory, format_spec, from}]
    effective_fees: dict  # {total_min, total_max, breakdown}
    effective_processing_time_days_min: int | None
    effective_processing_time_days_max: int | None
    effective_disbursement_time_days_min: int | None
    effective_disbursement_time_days_max: int | None
    notes: str | None
    publication_status: str
    is_active: bool
    source_id: str
```

## 3. `compare_offers_for_fund`

### Schéma Args

```python
class CompareOffersInput(BaseModel):
    fund_id: str = Field(..., description="UUID du fonds à comparer")
```

### Description LangChain

> Compare côte-à-côte toutes les offres publiées pour un même fonds (ex : GCF via BOAD, GCF via UNDP, GCF via AFD). Retourne un tableau avec frais effectifs cumulés, délais de traitement et de décaissement, taux de succès, langue acceptée et nombre de documents requis. Utilisez ce tool quand une PME veut choisir entre plusieurs intermédiaires pour un même fonds.

### Sortie

```python
class OfferComparison(BaseModel):
    offer_id: str
    name: str
    intermediary_name: str
    intermediary_country: str
    accepted_languages: list[str]
    effective_fees_total_min: dict | None  # {amount, currency}
    effective_fees_total_max: dict | None
    effective_processing_time_days_min: int | None
    effective_processing_time_days_max: int | None
    effective_disbursement_time_days_min: int | None
    effective_disbursement_time_days_max: int | None
    success_rate: float | None
    documents_count: int


class CompareOffersOutput(BaseModel):
    fund_name: str
    fund_organization: str
    comparisons: list[OfferComparison]
```

## 4. `create_fund_application` (extension)

### Schéma Args (NOUVEAU avec offer_id)

```python
class CreateFundApplicationInput(BaseModel):
    """Crée un dossier de candidature lié à une offre F07 et un projet F06.
    
    Migration en cours (2 sprints) :
    - Mode F07 nouveau (PRÉFÉRÉ) : passer offer_id + project_id
    - Mode legacy (DEPRECATED) : passer fund_id + intermediary_id (sera supprimé après 2 sprints)
    """
    offer_id: str | None = Field(None, description="UUID de l'offre (mode F07)")
    project_id: str | None = Field(None, description="UUID du projet F06 (recommandé)")
    fund_id: str | None = Field(None, description="UUID du fonds (legacy, deprecated)")
    intermediary_id: str | None = Field(None, description="UUID de l'intermédiaire (legacy, deprecated)")
    target_type: str = Field(..., description="Type de destinataire (cf. enum TargetType)")
    notes: str | None = None
```

### Règles applicatives

- Si `offer_id` est renseigné, prendre le dossier en mode F07 (`fund_id` et `intermediary_id` sont dérivés de l'offre).
- Si `offer_id` est `None`, fallback legacy avec `fund_id` + `intermediary_id` (warning log + audit_log `metadata.legacy_mode=true`).
- Si ni `offer_id` ni `fund_id` : retourner une `ToolException` avec message « Veuillez fournir offer_id ou fund_id+intermediary_id ».
- Si `project_id` n'est pas renseigné : tenter de lier au projet « principal » de l'utilisateur (mode F06 backward-compat) ; si aucun projet, retourner exception.

### Description LangChain (mise à jour)

> Crée un dossier de candidature pour qu'une PME puisse candidater à une offre de financement vert. Préférer le mode offre (offer_id) pour bénéficier des critères et documents effectifs cumulés. Le project_id (F06) est requis pour lier la candidature au projet vert de la PME. Utilisez ce tool seulement après avoir confirmé l'intention de la PME de candidater à une offre précise (jamais de manière proactive).

### Sortie

Inchangée (return `FundApplication` schema).

## Contrats d'erreur

Tous les tools utilisent la convention LangChain `ToolException` avec messages en français, par exemple :
- `list_offers` : « Aucune offre trouvée pour les critères donnés. Élargissez les filtres. »
- `get_offer` : « Offre introuvable ou non publiée. Vérifiez l'identifiant. »
- `compare_offers_for_fund` : « Aucune offre publiée pour ce fonds actuellement. Le catalogue est en cours d'enrichissement. »
- `create_fund_application` : « Veuillez fournir offer_id (recommandé) ou fund_id+intermediary_id (legacy). »

## Tests d'intégration

Tests dans `backend/tests/integration/test_financing_tools_offers.py` :
- `test_list_offers_returns_published_only`
- `test_list_offers_filters_by_theme`
- `test_get_offer_returns_404_for_draft`
- `test_compare_offers_for_fund_returns_all_published`
- `test_create_fund_application_with_offer_id`
- `test_create_fund_application_legacy_mode_deprecated_warning`
- `test_tools_are_read_only_on_catalog` (vérifie qu'aucun tool ne mute funds/intermediaries/offers)

## Enregistrement dans le graphe

Les 3 nouveaux tools (`list_offers`, `get_offer`, `compare_offers_for_fund`) sont ajoutés à la liste de tools du nœud `financing_node` dans `backend/app/graph/graph.py` (ligne `financing_tools = [...]`). Ils sont également exposés au nœud `chat_node` pour permettre l'exploration générale via le chat principal.

Le tool étendu `create_fund_application` reste dans `application_node` (cohérent avec l'usage actuel).

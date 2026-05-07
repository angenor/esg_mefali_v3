# Contract — F08 Tools LangChain Attestations

**Spec** : [../spec.md](../spec.md)
**Plan** : [../plan.md](../plan.md)
**Date** : 2026-05-07

## Résumé

F08 refactore **1 tool LangChain existant** (placeholder → réel) :

- `generate_credit_certificate` : refactoré pour appeler réellement le service `attestations.service.generate_attestation`. Conserve le nom historique pour rétrocompatibilité. Dans `backend/app/graph/tools/credit_tools.py`.

Aucun NOUVEAU tool n'est ajouté pour le MVP F08. La révocation reste UI-only (pas de tool LLM `revoke_attestation`) pour éviter qu'un LLM ne révoque accidentellement une attestation par erreur d'interprétation.

## Tool refactoré : `generate_credit_certificate`

### Schema d'entrée (Pydantic v2)

```python
from pydantic import BaseModel, Field
from typing import Literal

class GenerateCertificateArgs(BaseModel):
    """Arguments pour générer une attestation vérifiable signée Ed25519."""

    attestation_type: Literal["credit_score", "esg_assessment", "combined"] = Field(
        default="combined",
        description=(
            "Type d'attestation : 'credit_score' pour le score crédit seul, "
            "'esg_assessment' pour l'évaluation ESG seule, "
            "'combined' (par défaut) pour la combinaison des deux."
        ),
    )
```

### Docstring du tool

```python
@tool(args_schema=GenerateCertificateArgs)
async def generate_credit_certificate(
    attestation_type: Literal["credit_score", "esg_assessment", "combined"] = "combined",
    *,
    config: RunnableConfig,
) -> dict:
    """
    Génère une attestation vérifiable signée Ed25519 pour la PME courante.

    L'attestation est un PDF officiel avec QR code intégré pointant vers une page
    publique `/verify/{id}` où un partenaire (banquier, fund officer) peut vérifier
    l'authenticité sans authentification.

    PRÉ-CONDITIONS (vérifiées par le service) :
      - attestation_type='credit_score' : un CreditScore doit exister.
      - attestation_type='esg_assessment' : au moins une EsgAssessment finalisée.
      - attestation_type='combined' : les deux ci-dessus.

    EFFETS :
      - Crée une ligne 'attestations' en base avec audit_log F03 source_of_change='llm'.
      - Génère un PDF + QR + signature Ed25519.
      - Retourne l'URL de vérification publique à transmettre à l'utilisateur.

    NE PAS :
      - Citer de chiffres dans la réponse texte sans utiliser cite_source (validator F01 actif).
      - Appeler ce tool sans confirmation explicite de l'utilisateur (le PDF est officiel).

    Args:
        attestation_type: 'credit_score', 'esg_assessment' ou 'combined' (défaut).

    Returns:
        Dict avec les clés :
          - ok (bool) : succès ou échec
          - attestation_id (str, UUID) : identifiant unique de l'attestation
          - display_id (str) : identifiant lisible "ATT-YYYY-NNNNN"
          - verification_url (str) : URL publique pour vérification
          - pdf_path (str) : chemin du PDF généré
          - error (str, optionnel) : message d'erreur si ok=false

    Exemples de réponses :
      Succès :
        {
          "ok": true,
          "attestation_id": "abc-1234-def-5678",
          "display_id": "ATT-2026-00042",
          "verification_url": "https://esg-mefali.com/verify/abc-1234-def-5678",
          "pdf_path": "/uploads/attestations/pdfs/abc-1234-def-5678.pdf"
        }

      Pré-condition manquante :
        {
          "ok": false,
          "error": "credit_score_missing",
          "message": "Aucun score crédit calculé. Veuillez d'abord finaliser le scoring crédit via /credit-score."
        }

      Erreur génération :
        {
          "ok": false,
          "error": "pdf_generation_failed",
          "message": "Erreur lors de la génération du PDF. Veuillez réessayer ou contacter le support."
        }
    """
```

### Implémentation cible

```python
from app.modules.attestations.service import AttestationService
from app.core.exceptions import (
    CreditScoreMissingError,
    EsgAssessmentMissingError,
    PdfGenerationError,
)


@tool(args_schema=GenerateCertificateArgs)
async def generate_credit_certificate(
    attestation_type: Literal["credit_score", "esg_assessment", "combined"] = "combined",
    *,
    config: RunnableConfig,
) -> dict:
    """[docstring ci-dessus]"""
    user_id = config["configurable"]["user_id"]
    account_id = config["configurable"]["account_id"]

    async with get_db_session() as session:
        service = AttestationService(session)
        try:
            attestation = await service.generate_attestation(
                account_id=account_id,
                user_id=user_id,
                attestation_type=attestation_type,
                source_of_change="llm",  # source_of_change F03
            )
            return {
                "ok": True,
                "attestation_id": str(attestation.id),
                "display_id": attestation.display_id,
                "verification_url": attestation.verification_url,
                "pdf_path": attestation.pdf_path,
            }
        except CreditScoreMissingError:
            return {
                "ok": False,
                "error": "credit_score_missing",
                "message": "Aucun score crédit calculé. Veuillez d'abord finaliser le scoring crédit via /credit-score.",
            }
        except EsgAssessmentMissingError:
            return {
                "ok": False,
                "error": "esg_assessment_missing",
                "message": "Aucune évaluation ESG finalisée. Veuillez d'abord finaliser une évaluation ESG via /esg.",
            }
        except PdfGenerationError as e:
            logger.exception("PDF generation failed", attestation_type=attestation_type, account_id=account_id)
            return {
                "ok": False,
                "error": "pdf_generation_failed",
                "message": "Erreur lors de la génération du PDF. Veuillez réessayer ou contacter le support.",
            }
```

### Test de non-régression

Avant F08 (placeholder) :
```python
# credit_tools.py:101-119 (avant)
def generate_credit_certificate(...):
    return {
        "ok": True,
        "verification_url": "https://esg-mefali.com/verify/fake-uuid-1234",  # FICTIVE
        "pdf_path": "/uploads/certificates/fake.pdf",  # FICTIVE
    }
```

Après F08 (réel) :
```python
# Test : la verification_url DOIT pointer vers une vraie attestation
result = await generate_credit_certificate(attestation_type="combined", config=test_config)
assert result["ok"]
assert UUID(result["attestation_id"])  # UUID valide

# Vérifier que la ligne 'attestations' existe vraiment en base
attestation = await session.get(Attestation, UUID(result["attestation_id"]))
assert attestation is not None
assert attestation.signature_ed25519  # Signature non vide
assert len(attestation.pdf_hash_sha256) == 64  # Hash SHA-256 valide

# Vérifier que la verification_url pointe vers l'attestation créée
expected_url = f"https://esg-mefali.com/verify/{result['attestation_id']}"
assert result["verification_url"] == expected_url

# Vérifier que le fichier PDF existe sur disque
assert Path(result["pdf_path"]).exists()
```

## Tools NON ajoutés (par décision)

### Pas de tool `revoke_attestation`

**Décision** : la révocation passe uniquement par UI explicite (`/attestations` → bouton + modal de confirmation).

**Rationale** :
- Le risque qu'un LLM révoque une attestation par erreur d'interprétation utilisateur est trop élevé pour le MVP.
- La révocation est un acte critique (irréversible) qui mérite une confirmation explicite UI avec saisie d'une raison.
- Post-MVP : pourrait être ajouté avec un flow `ask_yes_no` (F10) de confirmation forcée, mais hors-scope F08.

### Pas de tool `verify_attestation`

**Décision** : la vérification passe par l'endpoint public `/api/public/verify/{id}` (no-auth).

**Rationale** :
- Si un LLM (côté plateforme) doit vérifier une attestation, il peut appeler l'endpoint REST public via un client HTTP standard.
- Pas besoin d'exposer un tool dédié — le LLM sait déjà manipuler les URLs (verification_url retournée par `generate_credit_certificate`).

## Intégration tool selector

`backend/app/graph/tool_selector_config.py` :

Aucune modification : `generate_credit_certificate` est déjà mappé à la page `/credit-score` et au module `credit`. Le refactor est transparent côté tool selector (le tool conserve son nom et son schema).

## Tests d'intégration

`backend/tests/integration/test_attestation_tool_integration.py` :

```python
@pytest.mark.asyncio
async def test_generate_credit_certificate_real_call(test_db_session, test_user_with_scores):
    """Test que le tool refactor crée vraiment une attestation en base."""
    config = {"configurable": {"user_id": str(test_user_with_scores.id), "account_id": ...}}

    result = await generate_credit_certificate(attestation_type="combined", config=config)

    assert result["ok"]
    assert result["verification_url"].startswith("https://esg-mefali.com/verify/")

    # Vérifier persistence
    attestation = await test_db_session.get(Attestation, UUID(result["attestation_id"]))
    assert attestation.signature_ed25519
    assert attestation.attestation_type == "combined"


@pytest.mark.asyncio
async def test_generate_credit_certificate_missing_score(test_db_session, test_user_no_score):
    """Test que le tool retourne ok=false si pas de CreditScore."""
    config = {"configurable": {"user_id": str(test_user_no_score.id), "account_id": ...}}

    result = await generate_credit_certificate(attestation_type="credit_score", config=config)

    assert not result["ok"]
    assert result["error"] == "credit_score_missing"


@pytest.mark.asyncio
async def test_generate_credit_certificate_audit_log_llm(test_db_session, test_user_with_scores):
    """Test que l'audit log F03 marque source_of_change='llm'."""
    config = {"configurable": {"user_id": str(test_user_with_scores.id), "account_id": ...}}

    result = await generate_credit_certificate(attestation_type="combined", config=config)

    audit_logs = await test_db_session.execute(
        select(AuditLog).where(AuditLog.entity_id == UUID(result["attestation_id"]))
    )
    audit = audit_logs.scalar_one()
    assert audit.source_of_change == "llm"
    assert audit.action == "create"
    assert audit.entity_type == "attestations"
```

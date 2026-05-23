"""F047 (US4) — Tools LangChain pour l'évaluation ESG-projet.

5 tools async décorés ``@tool`` orchestrent le pipeline US1 depuis le chat
LLM :

- ``create_project_esg_assessment``
- ``save_project_esg_criterion``
- ``finalize_project_esg_assessment``
- ``get_project_esg_assessment``
- ``list_project_esg_assessments``

Chaque mutation s'exécute dans ``source_of_change_scope('llm')`` pour
l'audit log F03. Les helpers `_get_account_id_from_config` réutilisent
le pattern F18 (fallback BDD si `account_id` absent du RunnableConfig).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.core.audit_context import source_of_change_scope
from app.graph.tools.common import get_db_and_user
from app.models.user import User
from app.modules.esg.project_schemas import ProjectEsgCriterionResponseSave
from app.modules.esg.project_report import generate_project_esg_report as svc_report
from app.modules.esg.project_service import (
    create_project_esg_assessment as svc_create,
    finalize_project_esg_assessment as svc_finalize,
    get_project_esg_assessment as svc_get,
    list_project_esg_assessments as svc_list,
    save_project_esg_criterion_response as svc_save,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


async def _resolve_account_id(
    config: RunnableConfig,
) -> tuple[Any, uuid.UUID, uuid.UUID]:
    """Retourne (db, user_id, account_id) en s'appuyant sur le RunnableConfig.

    Priorité : ``config['configurable']['account_id']`` → fallback BDD via
    ``User.account_id``. Reprise du pattern F18 livré (cf. CLAUDE.md).
    """
    db, user_id = get_db_and_user(config)
    configurable = (config or {}).get("configurable", {}) or {}
    account_id_raw = configurable.get("account_id")
    if account_id_raw is not None:
        account_id = (
            uuid.UUID(account_id_raw)
            if isinstance(account_id_raw, str)
            else account_id_raw
        )
    else:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or user.account_id is None:
            raise ValueError(
                "account_id du tenant introuvable — tool ESG-projet "
                "inutilisable hors d'un compte authentifié."
            )
        account_id = user.account_id
    return db, user_id, account_id


def _assessment_to_dict(a: Any) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "project_id": str(a.project_id),
        "referential_id": str(a.referential_id),
        "referential_version": a.referential_version,
        "state": a.state,
        "score": a.score,
        "pillar_scores": dict(a.pillar_scores or {}),
        "covered_criteria": [str(x) for x in (a.covered_criteria or [])],
        "missing_criteria": [str(x) for x in (a.missing_criteria or [])],
        "coverage_rate": float(a.coverage_rate) if a.coverage_rate is not None else None,
        "finalized_at": a.finalized_at.isoformat() if a.finalized_at else None,
    }


# ---------------------------------------------------------------------
# Args schemas
# ---------------------------------------------------------------------


class CreateAssessmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="ID du projet ciblé")]
    referential_id: Annotated[
        uuid.UUID, Field(description="ID du référentiel cible (IFC PS / GCF ESS / BOAD ESS)"),
    ]


class SaveCriterionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: uuid.UUID
    criterion_id: uuid.UUID
    response_type: Annotated[
        str,
        Field(
            description=(
                "Type de widget F18 ayant collecté la réponse : qcu, qcm, "
                "qcu_justification, qcm_justification, numeric, money, free_text"
            )
        ),
    ]
    response_value: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Payload typé selon response_type, en OBJET JSON (pas de "
                "chaîne sérialisée) : {\"choice\":\"yes\"} | {\"choices\":[\"a\",\"b\"]} "
                "| {\"choice\":\"yes\",\"justification\":\"...\"} | "
                "{\"value\":42} | {\"amount\":1000,\"currency\":\"XOF\"} | "
                "{\"text\":\"...\"}. Une string JSON sera tolérée et "
                "auto-parsée en objet."
            )
        ),
    ]
    source_id: uuid.UUID | None = None
    unsourced: bool = False

    @field_validator("response_value", mode="before")
    @classmethod
    def _accept_json_string(cls, v: Any) -> Any:
        """Tolérer une string JSON sérialisée passée par certains LLMs.

        Sans ce validator, le LLM se voit refuser le payload quand il
        envoie `response_value="{\"choice\":\"yes\"}"` (string) au lieu
        de l'objet JSON natif. On parse alors la string en dict.
        """
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"response_value est une chaîne non-JSON valide : {exc}"
                ) from exc
            if not isinstance(parsed, dict):
                raise ValueError(
                    "response_value doit être un objet JSON (dict), "
                    f"reçu : {type(parsed).__name__}"
                )
            return parsed
        return v


class FinalizeAssessmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: uuid.UUID


class GetAssessmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: uuid.UUID


class ListAssessmentsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    state: str | None = None


class GenerateReportArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: Annotated[
        uuid.UUID,
        Field(
            description=(
                "ID de l'évaluation ESG-projet `finalized`. Le rapport "
                "ESIA-light est refusé sur les drafts (FR-019)."
            )
        ),
    ]
    include_appendix_sources: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "Inclure l'annexe « Sources et références » (F01) "
                "listant les sources citées dans le rapport."
            ),
        ),
    ] = True


# ---------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------


@tool(args_schema=CreateAssessmentArgs)
async def create_project_esg_assessment(
    config: RunnableConfig,
    project_id: uuid.UUID,
    referential_id: uuid.UUID,
) -> str:
    """Démarre une évaluation ESG-projet en `draft` contre un référentiel F13.

    Use when:
    - L'utilisateur demande à évaluer son projet pour un bailleur vert (GCF, BOAD…).
    - Aucune évaluation `draft` n'existe déjà pour ce couple (projet, référentiel).
    Don't use when:
    - L'évaluation déjà en cours doit être reprise (utiliser
      `get_project_esg_assessment` puis `save_project_esg_criterion`).
    """
    try:
        db, user_id, account_id = await _resolve_account_id(config)
        with source_of_change_scope("llm"):
            a = await svc_create(
                db,
                account_id=account_id,
                user_id=user_id,
                project_id=project_id,
                referential_id=referential_id,
            )
        return json.dumps({"ok": True, "assessment": _assessment_to_dict(a)},
                          ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("create_project_esg_assessment échec")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=SaveCriterionArgs)
async def save_project_esg_criterion(
    config: RunnableConfig,
    assessment_id: uuid.UUID,
    criterion_id: uuid.UUID,
    response_type: str,
    response_value: dict[str, Any],
    source_id: uuid.UUID | None = None,
    unsourced: bool = False,
) -> str:
    """Sauvegarde la réponse à un critère ESG-projet.

    AVANT ce tool, tu DOIS soit fournir ``source_id`` (issu de
    ``search_source`` ou ``cite_source``), soit appeler
    ``flag_unsourced(reason='user_input')`` pour expliciter l'absence de
    source (validator F01 retry 1× sinon fallback texte).

    Use when:
    - Une question F18 a reçu une réponse de l'utilisateur et tu disposes
      du couple (criterion_id, response_value).
    Don't use when:
    - L'évaluation est `finalized` (réponse 409 garantie).
    """
    try:
        db, _user_id, account_id = await _resolve_account_id(config)
        payload = ProjectEsgCriterionResponseSave(
            criterion_id=criterion_id,
            response_type=response_type,  # type: ignore[arg-type]
            response_value=response_value,
            source_id=source_id,
            unsourced=unsourced,
        )
        with source_of_change_scope("llm"):
            row = await svc_save(
                db,
                account_id=account_id,
                assessment_id=assessment_id,
                payload=payload,
            )
        return json.dumps(
            {
                "ok": True,
                "response": {
                    "id": str(row.id),
                    "criterion_id": str(row.criterion_id),
                    "normalized_score": float(row.normalized_score),
                    "unsourced": row.unsourced,
                },
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("save_project_esg_criterion échec")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=FinalizeAssessmentArgs)
async def finalize_project_esg_assessment(
    config: RunnableConfig,
    assessment_id: uuid.UUID,
) -> str:
    """Finalise une évaluation (calcul du score 0..100, transition draft→finalized).

    Use when:
    - Tous les critères obligatoires ont reçu une réponse sourcée.
    - L'utilisateur valide le récapitulatif de la wizard / chat.
    Don't use when:
    - Critères obligatoires restants → finalisation refusée (422 + liste).
    """
    try:
        db, _user_id, account_id = await _resolve_account_id(config)
        with source_of_change_scope("llm"):
            result = await svc_finalize(
                db,
                account_id=account_id,
                assessment_id=assessment_id,
            )
        return json.dumps(
            {
                "ok": True,
                "assessment": _assessment_to_dict(result["assessment"]),
                "score": result["score"],
                "pillar_scores": result["pillar_scores"],
                "coverage_rate": float(result["coverage_rate"]),
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("finalize_project_esg_assessment échec")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=GetAssessmentArgs)
async def get_project_esg_assessment(
    config: RunnableConfig,
    assessment_id: uuid.UUID,
) -> str:
    """Récupère le détail d'une évaluation ESG-projet (assessment + réponses)."""
    try:
        db, _user_id, account_id = await _resolve_account_id(config)
        a, responses = await svc_get(
            db, account_id=account_id, assessment_id=assessment_id,
        )
        return json.dumps(
            {
                "ok": True,
                "assessment": _assessment_to_dict(a),
                "responses_count": len(responses),
                "responses": [
                    {
                        "criterion_id": str(r.criterion_id),
                        "response_type": r.response_type,
                        "response_value": r.response_value,
                        "normalized_score": float(r.normalized_score),
                        "unsourced": r.unsourced,
                    }
                    for r in responses
                ],
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("get_project_esg_assessment échec")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=ListAssessmentsArgs)
async def list_project_esg_assessments(
    config: RunnableConfig,
    project_id: uuid.UUID,
    state: str | None = None,
) -> str:
    """Liste les évaluations ESG-projet d'un projet (filtrable par state)."""
    try:
        db, _user_id, account_id = await _resolve_account_id(config)
        items = await svc_list(
            db,
            account_id=account_id,
            project_id=project_id,
            state=state,
        )
        return json.dumps(
            {
                "ok": True,
                "count": len(items),
                "items": [_assessment_to_dict(a) for a in items],
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("list_project_esg_assessments échec")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=GenerateReportArgs)
async def generate_project_esg_report(
    config: RunnableConfig,
    assessment_id: uuid.UUID,
    include_appendix_sources: bool = True,
) -> str:
    """Génère le rapport ESIA-light PDF d'une évaluation ESG-projet F047.

    DIFFERENT de `generate_esg_report` (ESG entreprise F05). À utiliser
    quand l'utilisateur demande un rapport ESIA-light, un rapport ESG-projet,
    ou un dossier bailleur (GCF / BOAD / IFC PS / etc.) pour un projet
    vert spécifique.

    Use when:
    - L'utilisateur demande à générer / produire / créer le rapport
      ESIA-light, le rapport ESG-projet, ou un dossier bailleur.
    - Une évaluation ESG-projet `finalized` existe pour ce projet.

    Don't use when:
    - L'évaluation est encore `draft` (réponse 422 garantie). Finaliser
      d'abord via `finalize_project_esg_assessment`.
    - L'utilisateur veut un rapport ESG entreprise (F05 / page /esg)
      → utiliser `generate_esg_report` à la place.
    """
    try:
        db, _user_id, account_id = await _resolve_account_id(config)
        out = await svc_report(
            db,
            account_id=account_id,
            assessment_id=assessment_id,
            include_appendix_sources=include_appendix_sources,
        )
        return json.dumps(
            {
                "ok": True,
                "file_path": out["file_path"],
                "generated_at": out["generated_at"].isoformat(),
                "template_version": out["template_version"],
                "section_count": out["section_count"],
                "chart_count": out["chart_count"],
                "sources_cited": out["sources_cited"],
                "message": (
                    "Rapport ESIA-light généré avec succès. "
                    "Le fichier est disponible dans /uploads et "
                    "téléchargeable depuis l'UI projet."
                ),
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("generate_project_esg_report échec")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


PROJECT_ESG_TOOLS = [
    create_project_esg_assessment,
    save_project_esg_criterion,
    finalize_project_esg_assessment,
    get_project_esg_assessment,
    list_project_esg_assessments,
    generate_project_esg_report,
]

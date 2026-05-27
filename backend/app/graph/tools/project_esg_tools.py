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
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from app.core.audit_context import source_of_change_scope
from app.graph.tools.common import get_db_and_user
from app.models.indicator import Criterion
from app.models.referential import Referential
from app.models.source import PublicationStatus
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


async def _load_available_referentials(db: Any) -> list[dict[str, Any]]:
    """F047 bugfix US3 (2026-05-23) — Liste les référentiels F047 publiés
    disponibles avec leur ``id`` UUID pour que le LLM puisse appeler
    ``create_project_esg_assessment`` sans inventer un UUID.

    Sans cet helper, le LLM connaît les codes (``ifc_ps``, ``gcf_ess``,
    ``boad_ess``) mais pas les UUIDs (générés au seed F047, instable
    entre environnements). ``search_source`` retournait ``source.id`` —
    différent de ``referential.id`` — d'où le blocage observé live.
    """
    rows = (
        await db.execute(
            select(Referential).where(
                Referential.publication_status == PublicationStatus.PUBLISHED.value,
            ).order_by(Referential.code)
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "code": r.code,
            "label": r.label,
        }
        for r in rows
    ]


async def _load_applicable_criteria(
    db: Any, referential_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Charge les critères ``applies_to_project=True`` du référentiel cible.

    Retourne la liste exposée au LLM (id, code, label, pillar, is_required,
    weight) pour qu'il puisse appeler ``save_project_esg_criterion`` avec
    des ``criterion_id`` valides sans inventer d'UUID.

    Le ``pillar`` est dérivé du préfixe du code (ex. ``IFCPS1-A`` → ``PS1``,
    cohérent avec :func:`app.modules.esg.project_scoring.compute_score`).
    """
    rows = (
        await db.execute(
            select(Criterion).where(
                Criterion.referential_id == referential_id,
                Criterion.applies_to_project.is_(True),
            ).order_by(Criterion.code)
        )
    ).scalars().all()
    return [
        {
            "id": str(c.id),
            "code": c.code,
            "label": c.label,
            "pillar": (c.code.split("-")[0] if c.code else None),
            "is_required": bool(c.is_required),
            "weight": float(c.weight) if c.weight is not None else None,
        }
        for c in rows
    ]


# ---------------------------------------------------------------------
# Args schemas
# ---------------------------------------------------------------------


class CreateAssessmentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="ID du projet ciblé")]
    referential_id: Annotated[
        uuid.UUID, Field(description="ID du référentiel cible (IFC PS / GCF ESS / BOAD ESS)"),
    ]


_ALLOWED_RESPONSE_TYPES = frozenset({
    "qcu",
    "qcm",
    "qcu_justification",
    "qcm_justification",
    "numeric",
    "money",
    "free_text",
})


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
                "chaîne sérialisée). Les clefs autorisées dépendent de "
                "response_type — utiliser une autre clef (ex {\"value\":\"B\"} "
                "pour qcu) déclenche une erreur de validation et le LLM doit "
                "retry. Formats attendus :\n"
                "  qcu / qcm                : {\"choice\":\"yes|no\"} ou {\"choices\":[\"a\",\"b\"]}\n"
                "  qcu_justification        : {\"choice\":\"yes\",\"justification\":\"...\"}\n"
                "  qcm_justification        : {\"choices\":[\"a\"],\"justification\":\"...\"}\n"
                "  numeric                  : {\"value\":42}  (nombre 0..1 ou clampé)\n"
                "  money                    : {\"amount\":1000,\"currency\":\"XOF\"}\n"
                "  free_text                : {\"text\":\"...\"}"
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

    @field_validator("response_type")
    @classmethod
    def _check_response_type(cls, v: str) -> str:
        if v not in _ALLOWED_RESPONSE_TYPES:
            raise ValueError(
                f"response_type={v!r} invalide. Valeurs autorisées : "
                f"{sorted(_ALLOWED_RESPONSE_TYPES)}."
            )
        return v

    @model_validator(mode="after")
    def _check_payload_matches_type(self) -> "SaveCriterionArgs":
        """F047 bugfix US3 (2026-05-23) — Valider que `response_value`
        respecte la structure attendue selon `response_type`.

        Avant ce validator, le LLM pouvait passer `{"value":"B"}` pour
        un `qcu` et le tool acceptait silencieusement (mais
        `normalize_response` retournait 0.0 car ni `choice` ni `choices`
        n'étaient présents). Conséquence observée live : 4 critères BOAD
        ESS persistés avec `normalized_score=0` chacun → score global = 0.

        Désormais on lève une erreur explicite que le LLM lit et corrige
        au retry suivant (le validator F01 ``source_required.py``
        autorise 1 retry avant fallback texte).
        """
        rt = self.response_type
        val = self.response_value
        if rt in ("qcu", "qcm", "qcu_justification", "qcm_justification"):
            has_choice = isinstance(val.get("choice"), str) and val["choice"].strip()
            has_choices = (
                isinstance(val.get("choices"), list)
                and all(isinstance(c, str) for c in val["choices"])
                and len(val["choices"]) > 0
            )
            if not (has_choice or has_choices):
                raise ValueError(
                    f"Pour response_type='{rt}', response_value doit contenir "
                    f"`choice` (str non vide) OU `choices` (list[str] non vide). "
                    f"Reçu clefs : {sorted(val.keys())}. "
                    f"Exemple attendu : {{\"choice\":\"yes\"}} ou "
                    f"{{\"choices\":[\"a\",\"b\"]}}."
                )
            if rt.endswith("_justification"):
                just = val.get("justification")
                if not isinstance(just, str):
                    raise ValueError(
                        f"Pour response_type='{rt}', response_value doit aussi "
                        f"contenir `justification` (str). "
                        f"Exemple : {{\"choice\":\"yes\",\"justification\":\"...\"}}."
                    )
        elif rt == "numeric":
            v = val.get("value")
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError(
                    "Pour response_type='numeric', response_value doit contenir "
                    "`value` (nombre). Exemple : {\"value\":0.7}."
                )
        elif rt == "money":
            amount = val.get("amount")
            if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                raise ValueError(
                    "Pour response_type='money', response_value doit contenir "
                    "`amount` (nombre). Exemple : "
                    "{\"amount\":1000,\"currency\":\"XOF\"}."
                )
            currency = val.get("currency")
            if currency is not None and not isinstance(currency, str):
                raise ValueError(
                    "Pour response_type='money', `currency` doit être une str "
                    "(XOF, EUR, USD, etc.) ou être omis."
                )
        elif rt == "free_text":
            text = val.get("text")
            if not isinstance(text, str):
                raise ValueError(
                    "Pour response_type='free_text', response_value doit contenir "
                    "`text` (str). Exemple : {\"text\":\"...\"}."
                )
        return self


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

    Returns (JSON):
    - ``assessment`` : détail créé (incl. `id` requis pour les tools suivants).
    - ``applicable_criteria`` : liste des critères du référentiel
      (id, code, label, pillar, is_required, weight). C'est cette liste qui
      fournit les ``criterion_id`` valides à passer à
      ``save_project_esg_criterion`` — **N'INVENTE JAMAIS un UUID**.

    Workflow attendu après ce tool :
    1. Pour CHAQUE critère de ``applicable_criteria`` (tous, pas seulement les
       ``is_required=True``), poser une question via
       ``ask_interactive_question`` puis appeler
       ``save_project_esg_criterion(assessment_id=<id retourné>,
       criterion_id=<id du critère>, …)``. Traite d'abord les obligatoires,
       puis enchaîne sur les recommandés : un rapport ESIA-light complet
       suppose une couverture maximale du référentiel, pas seulement les
       4 critères obligatoires.
    2. ``finalize_project_esg_assessment(assessment_id=<id>)``.
    3. ``generate_project_esg_report(assessment_id=<id>)`` si l'utilisateur
       demande le rapport ESIA-light.
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
        applicable = await _load_applicable_criteria(db, referential_id)
        return json.dumps(
            {
                "ok": True,
                "assessment": _assessment_to_dict(a),
                "applicable_criteria": applicable,
                "applicable_criteria_count": len(applicable),
                "next_step": (
                    "Pour TOUS les critères applicables ci-dessus (obligatoires "
                    "ET recommandés, pas seulement is_required=True), appelle "
                    "ask_interactive_question puis save_project_esg_criterion "
                    "avec son criterion_id. Commence par les obligatoires, puis "
                    "couvre les recommandés pour un rapport ESIA-light complet."
                ),
            },
            ensure_ascii=False,
        )
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

    Where to get ``criterion_id``:
    - Le tool ``create_project_esg_assessment`` retourne
      ``applicable_criteria`` qui contient les ``id`` valides.
    - ``get_project_esg_assessment`` et ``list_project_esg_assessments``
      les retournent aussi quand un draft existe déjà.
    - N'INVENTE JAMAIS un UUID — si tu n'as pas la liste, rappelle
      ``get_project_esg_assessment(assessment_id=<id>)`` d'abord.

    Exemple : save_project_esg_criterion(
      assessment_id="…", criterion_id="…", response_type="qcu",
      response_value={"choice":"yes"}, source_id="…"
    )
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
    - Tous les critères obligatoires ont reçu une réponse sourcée
      (via ``save_project_esg_criterion``).
    - L'utilisateur valide le récapitulatif de la wizard / chat.
    Don't use when:
    - Critères obligatoires restants → finalisation refusée (422 + liste).
      → reprends ``save_project_esg_criterion`` pour combler la liste retournée.

    Après finalisation OK, si l'utilisateur demande un rapport ESIA-light,
    appelle IMPÉRATIVEMENT ``generate_project_esg_report(assessment_id=<id>)``.
    N'AFFIRME JAMAIS que le rapport est généré sans avoir appelé ce tool.
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
    """Récupère le détail d'une évaluation ESG-projet (assessment + réponses
    + critères applicables au référentiel).

    Use when:
    - Tu reprends une évaluation existante et il te faut les
      ``criterion_id`` valides pour ``save_project_esg_criterion``.
    - Tu veux vérifier le state d'un assessment avant
      ``generate_project_esg_report`` (doit être ``finalized``).

    Returns (JSON) : ``assessment``, ``responses`` déjà persistées,
    ``applicable_criteria`` (id, code, label, pillar, is_required, weight)
    du référentiel cible.
    """
    try:
        db, _user_id, account_id = await _resolve_account_id(config)
        a, responses = await svc_get(
            db, account_id=account_id, assessment_id=assessment_id,
        )
        applicable = await _load_applicable_criteria(db, a.referential_id)
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
                "applicable_criteria": applicable,
                "applicable_criteria_count": len(applicable),
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
    """Liste les évaluations ESG-projet d'un projet (filtrable par state).

    Use when:
    - Tu démarres une évaluation : appelle d'abord pour vérifier si un
      ``draft`` existe déjà sur le référentiel ciblé.
    - L'utilisateur demande « génère le rapport ESIA-light » : appelle pour
      retrouver l'``assessment_id`` du draft / finalized à utiliser dans
      ``generate_project_esg_report``.

    Returns (JSON) : ``items[]`` (assessments existants) + ``available_referentials[]``
    (les référentiels F047 publiés disponibles avec leur ``id`` UUID +
    ``code`` : ``ifc_ps`` / ``gcf_ess`` / ``boad_ess``). Utilise le ``id``
    de ce dernier comme ``referential_id`` pour
    ``create_project_esg_assessment``. Pas d'``applicable_criteria`` ici —
    utilise ``create_project_esg_assessment`` ou ``get_project_esg_assessment``.
    """
    try:
        db, _user_id, account_id = await _resolve_account_id(config)
        items = await svc_list(
            db,
            account_id=account_id,
            project_id=project_id,
            state=state,
        )
        available_referentials = await _load_available_referentials(db)
        return json.dumps(
            {
                "ok": True,
                "count": len(items),
                "items": [_assessment_to_dict(a) for a in items],
                "available_referentials": available_referentials,
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

    Où trouver ``assessment_id`` :
    - Retourné par ``create_project_esg_assessment`` (champ ``assessment.id``).
    - Retourné par ``finalize_project_esg_assessment`` (idem).
    - Sinon : ``list_project_esg_assessments(project_id=…, state="finalized")``
      puis prendre le premier ``items[0].id``.

    REGLE ABSOLUE — ANTI-HALLUCINATION :
    Tu DOIS APPELER ce tool pour que le rapport soit réellement généré.
    N'AFFIRME JAMAIS « le rapport ESIA-light a été généré » dans une
    réponse texte tant que ce tool n'a pas retourné ``ok=true``. Le
    fichier PDF n'existe sur disque que si ce tool a été invoqué et a
    renvoyé un ``file_path`` non vide.

    Exemple : generate_project_esg_report(
      assessment_id="<UUID retourné par finalize_project_esg_assessment>",
      include_appendix_sources=True
    )

    Returns (JSON) : ``file_path`` (PDF local), ``generated_at``,
    ``template_version``, ``section_count``, ``chart_count``,
    ``sources_cited``. Le format est volontairement PDF (pas .docx) car
    les bailleurs préfèrent ce format.
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

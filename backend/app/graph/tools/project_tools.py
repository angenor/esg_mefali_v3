"""Tools LangChain pour le module Projets (F06).

7 tools async décorés ``@tool`` qui mutent ou lisent l'entité ``Project``
via le service ``app.modules.projects.service``. Toutes les mutations
s'exécutent dans le scope ``source_of_change_scope('llm')`` (F03).

Tools exposés :

- ``list_projects`` : lister les projets de l'utilisateur (filtrables).
- ``get_project`` : détail d'un projet.
- ``create_project`` : créer un nouveau projet (sourçage F01 obligatoire si
  ``target_amount`` ou ``expected_impact_tco2e`` non null).
- ``update_project`` : mise à jour partielle.
- ``delete_project`` : suppression soft avec garde-fou (force=true requis si
  applications actives).
- ``duplicate_project`` : duplication (force status=draft).
- ``link_document_to_project`` : associer un document existant.
"""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.audit_context import source_of_change_scope
from app.core.money import Money
from app.graph.tools.common import get_db_and_user, with_retry
from app.models.user import User
from app.modules.projects import service as project_service
from app.modules.projects.schemas import (
    DOC_TYPE_VALUES,
    FINANCING_STRUCTURE_VALUES,
    MATURITY_VALUES,
    OBJECTIVE_ENV_VALUES,
    STATUS_VALUES,
    ProjectCreate,
    ProjectFilters,
    ProjectUpdate,
)


logger = logging.getLogger(__name__)


# =====================================================================
# Helpers
# =====================================================================


async def _get_account_id_from_config(
    config: RunnableConfig,
) -> tuple[Any, uuid.UUID, uuid.UUID]:
    """Extraire (db, user_id, account_id) depuis le RunnableConfig.

    L'``account_id`` est lu depuis ``configurable['account_id']`` si fourni,
    sinon résolu via ``User.account_id`` en base.
    """
    db, user_id = get_db_and_user(config)
    configurable = (config or {}).get("configurable", {})
    account_id_raw = configurable.get("account_id")

    if account_id_raw is not None:
        if isinstance(account_id_raw, str):
            account_id = uuid.UUID(account_id_raw)
        else:
            account_id = account_id_raw
    else:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or user.account_id is None:
            raise ValueError(
                "account_id introuvable pour l'utilisateur courant — "
                "tool projet inutilisable hors d'un compte."
            )
        account_id = user.account_id

    return db, user_id, account_id


def _serialize_project_detail(detail: Any) -> str:
    """Sérialiser un ProjectDetail/ProjectSummary/etc en JSON."""
    if hasattr(detail, "model_dump"):
        payload = detail.model_dump(mode="json")
    elif isinstance(detail, list):
        payload = [
            d.model_dump(mode="json") if hasattr(d, "model_dump") else d
            for d in detail
        ]
    else:
        payload = detail
    return json.dumps(payload, ensure_ascii=False, default=str)


# =====================================================================
# Args schemas
# =====================================================================


class ListProjectsArgs(BaseModel):
    """Args pour list_projects."""

    model_config = ConfigDict(extra="forbid")

    status: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Filtrer par statut (draft/seeking_funding/funded/in_execution"
                "/closed/cancelled)"
            ),
        ),
    ] = None
    maturity: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Filtrer par maturité (ideation/pre_feasibility/pilot/scale/"
                "replication)"
            ),
        ),
    ] = None
    auto_generated: Annotated[
        bool | None,
        Field(
            default=None,
            description="Filtrer les projets auto-générés (migration backfill).",
        ),
    ] = None


class GetProjectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="UUID du projet à récupérer")]


class CreateProjectArgs(BaseModel):
    """Args pour create_project."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str, Field(min_length=1, max_length=200, description="Nom du projet")
    ]
    description: str | None = Field(default=None, description="Description détaillée")
    objective_env: list[str] = Field(
        default_factory=list,
        description=(
            "Objectifs environnementaux : mitigation, adaptation, biodiversity, "
            "circular_economy, water, renewable_energy, sustainable_agriculture, mixed"
        ),
    )
    maturity: str | None = Field(
        default=None,
        description="ideation/pre_feasibility/pilot/scale/replication",
    )
    status: str = Field(
        default="draft",
        description="draft/seeking_funding/funded/in_execution/closed/cancelled",
    )
    target_amount_amount: Annotated[
        Decimal | None, Field(default=None, ge=0)
    ] = None
    target_amount_currency: Annotated[
        str | None, Field(default=None, description="XOF/EUR/USD/GBP/JPY")
    ] = None
    duration_months: Annotated[int | None, Field(default=None, gt=0)] = None
    financing_structure: str | None = Field(
        default=None,
        description="subvention/pret_concessionnel/equity/blending/mixte",
    )
    expected_impact_tco2e: Annotated[
        Decimal | None, Field(default=None, ge=0)
    ] = None
    expected_jobs_created: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_beneficiaries: Annotated[int | None, Field(default=None, ge=0)] = None
    expected_hectares_restored: Annotated[
        Decimal | None, Field(default=None, ge=0)
    ] = None
    location_country: Annotated[
        str | None, Field(default=None, min_length=2, max_length=2)
    ] = None
    location_region: Annotated[
        str | None, Field(default=None, max_length=100)
    ] = None

    @field_validator("objective_env")
    @classmethod
    def _validate_objective_env(cls, v: list[str]) -> list[str]:
        for o in v:
            if o not in OBJECTIVE_ENV_VALUES:
                raise ValueError(
                    f"objective_env value '{o}' invalide"
                )
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in STATUS_VALUES:
            raise ValueError(f"status '{v}' invalide")
        return v

    @field_validator("maturity")
    @classmethod
    def _validate_maturity(cls, v: str | None) -> str | None:
        if v is not None and v not in MATURITY_VALUES:
            raise ValueError(f"maturity '{v}' invalide")
        return v

    @field_validator("financing_structure")
    @classmethod
    def _validate_financing(cls, v: str | None) -> str | None:
        if v is not None and v not in FINANCING_STRUCTURE_VALUES:
            raise ValueError(f"financing_structure '{v}' invalide")
        return v

    @model_validator(mode="after")
    def _validate_money_pair(self) -> "CreateProjectArgs":
        amt = self.target_amount_amount
        cur = self.target_amount_currency
        if (amt is None) != (cur is None):
            raise ValueError(
                "target_amount_amount et target_amount_currency doivent être "
                "tous deux fournis OU tous deux absents"
            )
        return self


class UpdateProjectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[
        uuid.UUID, Field(description="UUID du projet à mettre à jour"),
    ]
    fields: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Dictionnaire {champ: nouvelle_valeur}. "
                "Les champs non fournis ne sont pas modifiés."
            ),
        ),
    ]


class DeleteProjectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="UUID du projet à supprimer")]
    force: Annotated[
        bool,
        Field(
            default=False,
            description="True pour confirmer malgré les candidatures actives",
        ),
    ] = False
    # F10 — pattern destructif (Module 1.1.3) : confirm=True obligatoire après ask_yes_no.
    confirm: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "F10 — True pour confirmer la suppression après widget ask_yes_no. "
                "Si False, retourne {requires_confirmation: True} sans toucher la BDD."
            ),
        ),
    ] = False


class DuplicateProjectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[
        uuid.UUID, Field(description="UUID du projet source à dupliquer"),
    ]
    new_name: Annotated[
        str | None,
        Field(
            default=None,
            min_length=1,
            max_length=200,
            description="Nouveau nom (optionnel)",
        ),
    ] = None


class LinkDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Annotated[uuid.UUID, Field(description="UUID du projet")]
    document_id: Annotated[uuid.UUID, Field(description="UUID du document existant")]
    doc_type: Annotated[
        str,
        Field(
            description=(
                "feasibility_study/business_plan/impact_assessment/"
                "support_letter/other"
            ),
        ),
    ]

    @field_validator("doc_type")
    @classmethod
    def _validate_doc_type(cls, v: str) -> str:
        if v not in DOC_TYPE_VALUES:
            raise ValueError(f"doc_type '{v}' invalide")
        return v


# =====================================================================
# Tools
# =====================================================================


@tool(args_schema=ListProjectsArgs)
async def list_projects(
    config: RunnableConfig,
    status: str | None = None,
    maturity: str | None = None,
    auto_generated: bool | None = None,
) -> str:
    """Liste les projets verts de l'entreprise (nom, statut, maturite, montant cible, impact CO2e, nb candidatures).

    Use when:
    - "Quels sont mes projets ?", "Liste mes projets actifs".
    - Avant de creer une candidature de financement (identifier le projet).
    Don't use when:
    - Demande de detail precis (utiliser `get_project`).
    - Creation directe (utiliser `create_project`).
    Exemple: "Mes projets en quete de financement" -> list_projects(status='seeking_funding').
    Anti: "Detail de mon projet solaire" -> NE PAS appeler (utiliser `get_project`).
    """
    try:
        db, _user_id, account_id = await _get_account_id_from_config(config)
        filters = ProjectFilters(
            status=status,
            maturity=maturity,
            auto_generated=auto_generated,
            page=1,
            limit=50,
        )
        result = await project_service.list_projects(
            db, account_id=account_id, filters=filters,
        )
        return _serialize_project_detail(result)
    except Exception as e:
        logger.exception("Erreur dans list_projects")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=GetProjectArgs)
async def get_project(
    config: RunnableConfig,
    project_id: uuid.UUID,
) -> str:
    """Recupere le detail complet d'un projet par son UUID (documents lies + nb candidatures).

    Use when:
    - "Details du projet X", "Quel est le statut du projet Y".
    - Avant `update_project` ou `delete_project`, valider l'identifiant.
    Don't use when:
    - Liste generale (utiliser `list_projects`).
    - Mise a jour (utiliser `update_project`).
    Exemple: "Montre-moi le projet panneaux solaires" -> get_project(project_id=...).
    Anti: "Mes projets" -> NE PAS appeler (utiliser `list_projects`).
    """
    try:
        db, _user_id, account_id = await _get_account_id_from_config(config)
        detail = await project_service.get_project(
            db, account_id=account_id, project_id=project_id,
        )
        if detail is None:
            return json.dumps(
                {"ok": False, "error": "Project not found"}, ensure_ascii=False,
            )
        return _serialize_project_detail(detail)
    except Exception as e:
        logger.exception("Erreur dans get_project")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=CreateProjectArgs)
async def create_project(
    config: RunnableConfig,
    name: str,
    description: str | None = None,
    objective_env: list[str] | None = None,
    maturity: str | None = None,
    status: str = "draft",
    target_amount_amount: Decimal | None = None,
    target_amount_currency: str | None = None,
    duration_months: int | None = None,
    financing_structure: str | None = None,
    expected_impact_tco2e: Decimal | None = None,
    expected_jobs_created: int | None = None,
    expected_beneficiaries: int | None = None,
    expected_hectares_restored: Decimal | None = None,
    location_country: str | None = None,
    location_region: str | None = None,
) -> str:
    """Cree un nouveau projet vert pour l'entreprise (audit log = source_of_change='llm').

    Use when:
    - L'utilisateur decrit une initiative a financer ("installer panneaux solaires").
    - Apres collecte des elements minimum (nom + objectif env).
    Don't use when:
    - Projet existant a modifier (utiliser `update_project`).
    - Simple consultation (utiliser `list_projects`/`get_project`).
    Exemple: "Je veux ajouter mon projet d'installation solaire" -> create_project(name='Solaire Bamako', objective_env=['energy']).
    Anti: "Modifier mon projet X" -> NE PAS appeler (utiliser `update_project`).

    AVANT ce tool avec ``target_amount`` ou ``expected_impact_tco2e``, tu DOIS
    appeler ``cite_source(source_id)`` ou ``flag_unsourced(reason='user_input')``.
    """
    try:
        db, _user_id, account_id = await _get_account_id_from_config(config)
        target_amount: Money | None = None
        if target_amount_amount is not None and target_amount_currency is not None:
            target_amount = Money(
                amount=target_amount_amount,
                currency=target_amount_currency,  # type: ignore[arg-type]
            )

        payload = ProjectCreate(
            name=name,
            description=description,
            objective_env=objective_env or [],
            maturity=maturity,
            status=status,
            target_amount=target_amount,
            duration_months=duration_months,
            financing_structure=financing_structure,
            expected_impact_tco2e=expected_impact_tco2e,
            expected_jobs_created=expected_jobs_created,
            expected_beneficiaries=expected_beneficiaries,
            expected_hectares_restored=expected_hectares_restored,
            location_country=location_country,
            location_region=location_region,
        )

        with source_of_change_scope("llm"):
            detail = await project_service.create_project(
                db, account_id=account_id, payload=payload,
            )
        return _serialize_project_detail(detail)
    except Exception as e:
        logger.exception("Erreur dans create_project")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=UpdateProjectArgs)
@with_retry(
    max_retries=1,
    node_name="project_node",
    fallback_message=(
        "Je n'arrive pas à mettre à jour ce projet. "
        "Pouvez-vous reformuler les modifications souhaitées ?"
    ),
)
async def update_project(
    config: RunnableConfig,
    project_id: uuid.UUID,
    fields: dict[str, Any],
) -> str:
    """Met a jour les champs d'un projet existant (montant, statut, maturite, impact).

    Use when:
    - L'utilisateur precise un montant cible, un delai, un impact attendu.
    - Changement de statut/maturite signale.
    Don't use when:
    - Creation initiale (utiliser `create_project`).
    - Suppression demandee (utiliser `delete_project` avec confirm).
    Exemple: "Mon projet solaire passe a 50M FCFA" -> update_project(project_id=..., fields={'target_amount_amount': 50_000_000}).
    Anti: "Cree un nouveau projet" -> NE PAS appeler (utiliser `create_project`).

    Tu peux modifier n'importe quel champ sauf ``id``, ``account_id``,
    ``auto_generated``, ``created_at``. Pour ajouter ou retirer des objectifs
    environnementaux, fournis le tableau ``objective_env`` complet.
    """
    try:
        db, _user_id, account_id = await _get_account_id_from_config(config)
        # Convertir le dict de fields en payload Pydantic strict
        try:
            payload = ProjectUpdate(**fields)
        except Exception as ve:
            return json.dumps(
                {"ok": False, "error": f"Invalid fields: {ve}"},
                ensure_ascii=False,
            )

        with source_of_change_scope("llm"):
            detail = await project_service.update_project(
                db,
                account_id=account_id,
                project_id=project_id,
                payload=payload,
            )
        if detail is None:
            return json.dumps(
                {"ok": False, "error": "Project not found"}, ensure_ascii=False,
            )
        return _serialize_project_detail(detail)
    except Exception as e:
        logger.exception("Erreur dans update_project")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=DeleteProjectArgs)
@with_retry(
    max_retries=1,
    node_name="project_node",
    fallback_message=(
        "Je n'arrive pas à supprimer ce projet. "
        "Pouvez-vous me redonner l'identifiant du projet à supprimer ?"
    ),
)
async def delete_project(
    config: RunnableConfig,
    project_id: uuid.UUID,
    force: bool = False,
    confirm: bool = False,
) -> str:
    """Supprime (soft-delete : statut -> 'cancelled') un projet, avec confirmation destructive.

    Use when:
    - L'utilisateur demande explicitement la suppression d'un projet.
    - Apres confirmation utilisateur via `ask_yes_no(destructive=True)`.
    Don't use when:
    - Aucune confirmation (le tool retournera `requires_destructive_confirmation`).
    - Mise a jour souhaitee (utiliser `update_project`).
    Exemple: ask_yes_no(destructive=True) + reponse oui -> delete_project(project_id=..., confirm=True).
    Anti: appel direct sans `ask_yes_no` -> NE PAS le faire (le tool refusera).

    PATTERN DESTRUCTIF F10 (Module 1.1.3) :
    - Premier appel sans ``confirm`` : retourne ``{requires_confirmation: True}``
      sans toucher la BDD. Le LLM doit alors invoquer ``ask_yes_no(destructive=True)``.
    - Second appel avec ``confirm=True`` apres reponse utilisateur : execute la suppression.

    Si le projet a des candidatures actives (status NOT IN rejected/accepted/cancelled),
    le tool refuse par defaut et retourne la liste des candidatures bloquantes.
    Tu peux alors appeler ``ask_interactive_question`` pour demander confirmation
    a l'utilisateur, puis re-appeler ``delete_project(project_id, force=true, confirm=true)``
    si l'utilisateur confirme.
    """
    # F10 — Garde-fou destructif (Module 1.1.3)
    if not confirm:
        from app.graph.tools.common import requires_destructive_confirmation
        return requires_destructive_confirmation("delete_project")

    try:
        db, user_id, account_id = await _get_account_id_from_config(config)
        with source_of_change_scope("llm"):
            result = await project_service.soft_delete_project(
                db,
                account_id=account_id,
                user_id=user_id,
                project_id=project_id,
                force=force,
            )
        if result is None:
            return json.dumps(
                {"ok": False, "error": "Project not found"}, ensure_ascii=False,
            )
        return _serialize_project_detail(result)
    except Exception as e:
        logger.exception("Erreur dans delete_project")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=DuplicateProjectArgs)
async def duplicate_project(
    config: RunnableConfig,
    project_id: uuid.UUID,
    new_name: str | None = None,
) -> str:
    """Duplique un projet existant (statut force a 'draft', suffixe ' (copie)' si pas de new_name).

    Use when:
    - L'utilisateur veut preparer un projet similaire sur un autre site.
    - Variante d'un projet existant en draft (nouveau montant, nouveau pays).
    Don't use when:
    - Mise a jour du projet source (utiliser `update_project`).
    - Creation from scratch (utiliser `create_project`).
    Exemple: "Duplique mon projet solaire pour Bamako" -> duplicate_project(project_id=..., new_name='Solaire Bamako').
    Anti: "Modifier le projet" -> NE PAS appeler (utiliser `update_project`).

    Le nouveau projet herite de tous les champs metier sauf ``id``,
    ``created_at``, ``updated_at``, ``auto_generated`` et ``project_documents``.
    Le statut est force a 'draft'. Si ``new_name`` est absent, le nom source
    recoit le suffixe ' (copie)'.
    """
    try:
        db, _user_id, account_id = await _get_account_id_from_config(config)
        with source_of_change_scope("llm"):
            detail = await project_service.duplicate_project(
                db,
                account_id=account_id,
                project_id=project_id,
                new_name=new_name,
            )
        if detail is None:
            return json.dumps(
                {"ok": False, "error": "Project not found"}, ensure_ascii=False,
            )
        return _serialize_project_detail(detail)
    except Exception as e:
        logger.exception("Erreur dans duplicate_project")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


@tool(args_schema=LinkDocumentArgs)
async def link_document_to_project(
    config: RunnableConfig,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    doc_type: str,
) -> str:
    """Associe un document deja uploade a un projet vert (lien project_documents).

    Use when:
    - L'utilisateur veut lier un business plan, un titre foncier ou une etude a un projet.
    - Apres `analyze_uploaded_document` ou `list_user_documents`, lier au projet.
    Don't use when:
    - Document non uploade (utiliser `analyze_uploaded_document` apres upload).
    - Creation projet (utiliser `create_project`).
    Exemple: "Associe mon business plan au projet solaire" -> link_document_to_project(project_id=..., document_id=..., doc_type='business_plan').
    Anti: "Cree un projet avec ce document" -> NE PAS appeler (creer projet d'abord via `create_project`).

    Echoue si l'association existe deja (UNIQUE constraint).
    """
    try:
        db, _user_id, account_id = await _get_account_id_from_config(config)
        try:
            with source_of_change_scope("llm"):
                link = await project_service.link_document_to_project(
                    db,
                    account_id=account_id,
                    project_id=project_id,
                    document_id=document_id,
                    doc_type=doc_type,
                )
        except IntegrityError:
            return json.dumps(
                {"ok": False, "error": "Association already exists"},
                ensure_ascii=False,
            )
        if link is None:
            return json.dumps(
                {"ok": False, "error": "Project or document not found"},
                ensure_ascii=False,
            )
        return _serialize_project_detail(link)
    except Exception as e:
        logger.exception("Erreur dans link_document_to_project")
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


PROJECT_TOOLS = [
    list_projects,
    get_project,
    create_project,
    update_project,
    delete_project,
    duplicate_project,
    link_document_to_project,
]


__all__ = ["PROJECT_TOOLS"]

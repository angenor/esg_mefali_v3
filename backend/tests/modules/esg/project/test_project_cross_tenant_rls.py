"""T083 — Audit RLS cross-tenant pour les évaluations ESG-projet (R4).

Vérifie que (a) un compte PME tiers ne peut pas voir / charger / saisir
contre l'évaluation d'un autre tenant, (b) le service applicatif renvoie
404 dans tous les cas (pas 403 — la PME ne doit pas inférer l'existence
de l'évaluation). Cette défense applicative complète l'isolation BDD
(``ENABLE+FORCE`` RLS testé séparément dans
``test_project_models_rls.py`` sur PostgreSQL réel).

Référence : spec.md R4 ; data-model.md « RLS F02 » ; constitution V.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.indicator import Criterion
from app.models.project import Project
from app.models.referential import Referential
from app.modules.esg.project_models import ProjectEsgAssessment
from app.modules.esg.project_schemas import ProjectEsgCriterionResponseSave
from app.modules.esg.project_service import (
    create_project_esg_assessment,
    finalize_project_esg_assessment,
    get_project_esg_assessment,
    list_project_esg_assessments,
    save_project_esg_criterion_response,
)
from tests.conftest import make_account, make_pme_user


async def _ifc_id(db_session) -> uuid.UUID:
    ref = (
        await db_session.execute(
            select(Referential).where(Referential.code == "ifc_ps")
        )
    ).scalar_one()
    return ref.id


@pytest.fixture
async def other_pme(db_session, seed_047):
    """Compte PME tiers (différent du fixture ``pme_user``)."""
    acc = await make_account(db_session, name="OtherPME-RLS")
    return await make_pme_user(
        db_session,
        email=f"other-{uuid.uuid4().hex[:6]}@test",
        company_name="OtherPME-RLS",
        account=acc,
    )


@pytest.mark.asyncio
class TestRlsCrossTenantIsolation:
    """T083 — un tenant tiers ne doit jamais voir l'évaluation d'un autre."""

    async def test_create_for_other_tenant_project_returns_404(
        self, db_session, pme_user, project, other_pme,
    ):
        """Création par un tenant tiers contre un projet qui ne lui appartient
        pas → 404 (le service applicatif filtre par account_id avant tout
        autre check)."""
        ref_id = await _ifc_id(db_session)
        with pytest.raises(HTTPException) as exc:
            await create_project_esg_assessment(
                db_session,
                account_id=other_pme.account_id,
                user_id=other_pme.id,
                project_id=project.id,  # appartient à pme_user, pas other_pme
                referential_id=ref_id,
            )
        assert exc.value.status_code == 404, (
            "Le tenant tiers ne doit ni voir l'existence du projet ni pouvoir "
            "lancer une évaluation contre celui-ci."
        )

    async def test_get_other_tenants_assessment_returns_404(
        self, db_session, pme_user, project, other_pme,
    ):
        """Lecture d'une évaluation appartenant à un autre tenant → 404."""
        ref_id = await _ifc_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        with pytest.raises(HTTPException) as exc:
            await get_project_esg_assessment(
                db_session, account_id=other_pme.account_id, assessment_id=a.id,
            )
        assert exc.value.status_code == 404, (
            "Un tenant tiers ne doit jamais récupérer l'évaluation d'un "
            "autre tenant — RLS défense applicative + BDD."
        )

    async def test_save_criterion_on_other_tenants_assessment_returns_404(
        self, db_session, pme_user, project, other_pme,
    ):
        """Saisie d'un critère sur l'évaluation d'un autre tenant → 404."""
        ref_id = await _ifc_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        crit = (
            await db_session.execute(
                select(Criterion).where(
                    Criterion.referential_id == ref_id,
                    Criterion.is_required.is_(True),
                ).limit(1)
            )
        ).scalar_one()
        payload = ProjectEsgCriterionResponseSave(
            criterion_id=crit.id,
            response_type="qcu",
            response_value={"choice": "yes"},
            source_id=None,
            unsourced=True,
        )
        with pytest.raises(HTTPException) as exc:
            await save_project_esg_criterion_response(
                db_session,
                account_id=other_pme.account_id,
                assessment_id=a.id,
                payload=payload,
            )
        assert exc.value.status_code == 404

    async def test_finalize_other_tenants_assessment_returns_404(
        self, db_session, pme_user, project, other_pme,
    ):
        """Finalisation d'une évaluation tiers → 404 (jamais 403)."""
        ref_id = await _ifc_id(db_session)
        a = await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        with pytest.raises(HTTPException) as exc:
            await finalize_project_esg_assessment(
                db_session,
                account_id=other_pme.account_id,
                assessment_id=a.id,
            )
        assert exc.value.status_code == 404

    async def test_list_for_other_tenants_project_returns_empty_or_404(
        self, db_session, pme_user, project, other_pme,
    ):
        """Lister les évaluations d'un projet appartenant à un autre tenant
        ne doit jamais retourner les lignes du tenant légitime — soit
        retour 404 (projet introuvable), soit liste vide (filtrée par
        account_id). Pas de fuite cross-tenant."""
        ref_id = await _ifc_id(db_session)
        await create_project_esg_assessment(
            db_session,
            account_id=pme_user.account_id,
            user_id=pme_user.id,
            project_id=project.id,
            referential_id=ref_id,
        )
        try:
            items = await list_project_esg_assessments(
                db_session,
                account_id=other_pme.account_id,
                project_id=project.id,
            )
            # Si le service tolère la liste vide pour un projet inaccessible :
            assert items == [], (
                "Cross-tenant : list_project_esg_assessments ne doit jamais "
                "exposer les évaluations d'un autre tenant."
            )
        except HTTPException as exc:
            # Sinon le service rejette frontalement → 404 acceptable
            assert exc.status_code == 404

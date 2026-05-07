"""Tests unitaires du modèle SQLAlchemy Project (F06).

Couvre :
- Whitelists ``PROJECT_*_VALUES`` exposées au top du module.
- Création d'instance avec les colonnes attendues.
- Présence des index + CHECK constraints.
- Présence dans ``AUDITABLE_MODELS`` ; ``ProjectDocument`` dans ``EXEMPT_MODELS``.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.auditable import AUDITABLE_MODELS, EXEMPT_MODELS
from app.models.project import (
    PROJECT_CURRENCY_VALUES,
    PROJECT_FINANCING_STRUCTURE_VALUES,
    PROJECT_MATURITY_VALUES,
    PROJECT_OBJECTIVE_ENV_VALUES,
    PROJECT_STATUS_VALUES,
    Project,
)
from app.models.project_document import (
    PROJECT_DOC_TYPE_VALUES,
    ProjectDocument,
)
from tests.conftest import make_account


def test_whitelists_are_frozensets():
    assert isinstance(PROJECT_OBJECTIVE_ENV_VALUES, frozenset)
    assert isinstance(PROJECT_MATURITY_VALUES, frozenset)
    assert isinstance(PROJECT_STATUS_VALUES, frozenset)
    assert isinstance(PROJECT_FINANCING_STRUCTURE_VALUES, frozenset)
    assert isinstance(PROJECT_CURRENCY_VALUES, frozenset)
    assert isinstance(PROJECT_DOC_TYPE_VALUES, frozenset)


def test_objective_env_values():
    assert "renewable_energy" in PROJECT_OBJECTIVE_ENV_VALUES
    assert "mitigation" in PROJECT_OBJECTIVE_ENV_VALUES
    assert "circular_economy" in PROJECT_OBJECTIVE_ENV_VALUES
    assert "mixed" in PROJECT_OBJECTIVE_ENV_VALUES
    assert len(PROJECT_OBJECTIVE_ENV_VALUES) == 8


def test_maturity_values():
    assert PROJECT_MATURITY_VALUES == frozenset(
        {"ideation", "pre_feasibility", "pilot", "scale", "replication"}
    )


def test_status_values():
    assert PROJECT_STATUS_VALUES == frozenset(
        {
            "draft",
            "seeking_funding",
            "funded",
            "in_execution",
            "closed",
            "cancelled",
        }
    )


def test_financing_structure_values():
    assert PROJECT_FINANCING_STRUCTURE_VALUES == frozenset(
        {"subvention", "pret_concessionnel", "equity", "blending", "mixte"}
    )


def test_doc_type_values():
    assert PROJECT_DOC_TYPE_VALUES == frozenset(
        {
            "feasibility_study",
            "business_plan",
            "impact_assessment",
            "support_letter",
            "other",
        }
    )


def test_project_in_auditable_models():
    assert "Project" in AUDITABLE_MODELS


def test_project_document_in_exempt_models():
    assert "ProjectDocument" in EXEMPT_MODELS


def test_project_table_columns():
    """Vérifier que la table projects a bien les colonnes attendues."""
    columns = {c.name for c in Project.__table__.columns}
    expected = {
        "id",
        "account_id",
        "name",
        "description",
        "objective_env",
        "maturity",
        "status",
        "target_amount_amount",
        "target_amount_currency",
        "duration_months",
        "financing_structure",
        "expected_impact_tco2e",
        "expected_jobs_created",
        "expected_beneficiaries",
        "expected_hectares_restored",
        "expected_other_impacts",
        "location_country",
        "location_region",
        "auto_generated",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(columns)


def test_project_indexes():
    """Vérifier les indexes composites."""
    index_names = {idx.name for idx in Project.__table__.indexes}
    assert "idx_projects_account_status" in index_names
    assert "idx_projects_account_maturity" in index_names


def test_project_check_constraints():
    """Vérifier que les CHECK constraints sont définies."""
    check_names = {
        c.name
        for c in Project.__table__.constraints
        if hasattr(c, "name") and c.name
    }
    assert "projects_target_amount_pair_chk" in check_names
    assert "projects_status_chk" in check_names
    assert "projects_maturity_chk" in check_names
    assert "projects_financing_structure_chk" in check_names
    assert "projects_location_country_chk" in check_names


def test_project_document_unique_constraint():
    """Vérifier la contrainte UNIQUE (project_id, document_id)."""
    constraint_names = {
        c.name
        for c in ProjectDocument.__table__.constraints
        if hasattr(c, "name") and c.name
    }
    assert "project_documents_unique" in constraint_names


def test_project_document_indexes():
    index_names = {idx.name for idx in ProjectDocument.__table__.indexes}
    assert "idx_project_documents_project_id" in index_names
    assert "idx_project_documents_document_id" in index_names


@pytest.mark.asyncio
async def test_project_instantiation(db_session):
    """Créer une instance Project minimale en SQLite."""
    account = await make_account(db_session, name="TestAcc")

    project = Project(
        account_id=account.id,
        name="Panneaux solaires usine",
        description="Installation 50 kWc",
        objective_env=["renewable_energy", "mitigation"],
        maturity="pilot",
        status="draft",
    )
    db_session.add(project)
    await db_session.flush()
    assert project.id is not None
    assert project.account_id == account.id
    assert project.objective_env == ["renewable_energy", "mitigation"]
    assert project.status == "draft"
    assert project.auto_generated is False


@pytest.mark.asyncio
async def test_project_required_account_id(db_session):
    """account_id NOT NULL → IntegrityError sans account."""
    project = Project(
        name="Test",
        objective_env=[],
    )
    db_session.add(project)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_project_default_status_draft(db_session):
    account = await make_account(db_session, name="Acc")
    project = Project(account_id=account.id, name="P1", objective_env=[])
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    assert project.status == "draft"
    assert project.auto_generated is False

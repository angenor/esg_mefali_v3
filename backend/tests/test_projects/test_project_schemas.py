"""Tests unitaires des schémas Pydantic Projects (F06).

Couvre :
- Validators enum (objective_env, maturity, status, financing_structure, doc_type).
- Validators numériques (>=0, >0).
- Money pair (les 2 NULL ou les 2 non-NULL).
- ISO country code (alpha-2 majuscules).
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.money import Money
from app.modules.projects.schemas import (
    DOC_TYPE_VALUES,
    OBJECTIVE_ENV_VALUES,
    LinkDocumentRequest,
    ProjectCreate,
    ProjectFilters,
    ProjectUpdate,
)


def test_project_create_valid_minimal():
    payload = ProjectCreate(name="Mon projet")
    assert payload.name == "Mon projet"
    assert payload.status == "draft"
    assert payload.objective_env == []


def test_project_create_invalid_objective_env():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", objective_env=["invalid_value"])


def test_project_create_valid_objective_env():
    payload = ProjectCreate(
        name="P", objective_env=["renewable_energy", "mitigation"],
    )
    assert "renewable_energy" in payload.objective_env


def test_project_create_invalid_maturity():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", maturity="not_a_value")


def test_project_create_invalid_status():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", status="bogus")


def test_project_create_invalid_financing_structure():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", financing_structure="bogus")


def test_project_create_invalid_country_code_too_short():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", location_country="C")


def test_project_create_country_uppercased():
    payload = ProjectCreate(name="P", location_country="ci")
    assert payload.location_country == "CI"


def test_project_create_country_non_alpha():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", location_country="12")


def test_project_create_negative_jobs_rejected():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", expected_jobs_created=-1)


def test_project_create_zero_jobs_accepted():
    payload = ProjectCreate(name="P", expected_jobs_created=0)
    assert payload.expected_jobs_created == 0


def test_project_create_negative_duration_rejected():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", duration_months=-1)


def test_project_create_zero_duration_rejected():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", duration_months=0)


def test_project_create_money_valid():
    payload = ProjectCreate(
        name="P",
        target_amount=Money(amount=Decimal("50000000"), currency="XOF"),
    )
    assert payload.target_amount.amount == Decimal("50000000.00")
    assert payload.target_amount.currency == "XOF"


def test_project_create_with_all_fields():
    payload = ProjectCreate(
        name="Test complet",
        description="Description",
        objective_env=["water", "biodiversity"],
        maturity="scale",
        status="seeking_funding",
        target_amount=Money(amount=Decimal("100"), currency="EUR"),
        duration_months=12,
        financing_structure="blending",
        expected_impact_tco2e=Decimal("50.5"),
        expected_jobs_created=5,
        expected_beneficiaries=100,
        expected_hectares_restored=Decimal("2.5"),
        location_country="FR",
        location_region="Paris",
    )
    assert payload.duration_months == 12
    assert payload.financing_structure == "blending"


def test_project_create_extra_field_forbidden():
    with pytest.raises(ValidationError):
        ProjectCreate(name="P", unknown_field="x")


def test_project_create_name_required():
    with pytest.raises(ValidationError):
        ProjectCreate()


def test_project_create_name_max_length():
    with pytest.raises(ValidationError):
        ProjectCreate(name="x" * 201)


def test_project_create_name_min_length():
    with pytest.raises(ValidationError):
        ProjectCreate(name="")


def test_project_update_partial_no_required_fields():
    payload = ProjectUpdate()
    assert payload.name is None
    assert payload.objective_env is None


def test_project_update_invalid_objective_env():
    with pytest.raises(ValidationError):
        ProjectUpdate(objective_env=["bogus_value"])


def test_project_update_objective_env_none_ok():
    payload = ProjectUpdate(objective_env=None)
    assert payload.objective_env is None


def test_project_update_status_validated():
    with pytest.raises(ValidationError):
        ProjectUpdate(status="bogus")


def test_project_filters_defaults():
    f = ProjectFilters()
    assert f.page == 1
    assert f.limit == 25


def test_project_filters_limit_max():
    with pytest.raises(ValidationError):
        ProjectFilters(limit=101)


def test_project_filters_page_min():
    with pytest.raises(ValidationError):
        ProjectFilters(page=0)


def test_link_document_request_valid_doc_types():
    for v in DOC_TYPE_VALUES:
        payload = LinkDocumentRequest(
            document_id="00000000-0000-0000-0000-000000000001",
            doc_type=v,
        )
        assert payload.doc_type == v


def test_link_document_request_invalid_doc_type():
    with pytest.raises(ValidationError):
        LinkDocumentRequest(
            document_id="00000000-0000-0000-0000-000000000001",
            doc_type="invalid",
        )


def test_objective_env_values_consistent():
    assert "mixed" in OBJECTIVE_ENV_VALUES
    assert "biodiversity" in OBJECTIVE_ENV_VALUES
    assert len(OBJECTIVE_ENV_VALUES) == 8

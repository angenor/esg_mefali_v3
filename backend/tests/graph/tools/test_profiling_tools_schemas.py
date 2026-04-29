"""Tests unitaires des schemas Pydantic des tools profiling (story 10.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.graph.tools.profiling_tools import (
    GetCompanyProfileArgs,
    UpdateCompanyProfileArgs,
)


pytestmark = pytest.mark.unit


def test_valid_partial_payload():
    args = UpdateCompanyProfileArgs(company_name="Solar Niger", employee_count=25)
    assert args.company_name == "Solar Niger"
    assert args.employee_count == 25


def test_valid_with_sector_enum():
    args = UpdateCompanyProfileArgs(sector="agriculture")
    assert args.sector.value == "agriculture"


def test_empty_payload_accepted():
    args = UpdateCompanyProfileArgs()
    assert args.company_name is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("sector", "not_a_real_sector"),
        ("employee_count", -1),
        ("employee_count", 100_001),
        ("annual_revenue_xof", -1),
        ("annual_revenue_xof", 10_000_000_000_001),
        ("year_founded", 1899),
        ("year_founded", 2101),
        ("company_name", ""),
        ("company_name", "x" * 256),
        ("city", ""),
        ("governance_structure", "x" * 2001),
    ],
)
def test_update_invalid_value_rejected(field, value):
    with pytest.raises(ValidationError):
        UpdateCompanyProfileArgs(**{field: value})


def test_update_extra_field_forbidden():
    with pytest.raises(ValidationError) as exc:
        UpdateCompanyProfileArgs(unknown_field="boom")
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())


def test_get_empty_payload_accepted():
    args = GetCompanyProfileArgs()
    assert args is not None


def test_get_extra_field_forbidden():
    with pytest.raises(ValidationError) as exc:
        GetCompanyProfileArgs(some_arg="x")
    assert any(e["type"] == "extra_forbidden" for e in exc.value.errors())
